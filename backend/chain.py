"""
NL → SQL chain with self-correction.
Set LLM to one of:
  claude (default) — needs ANTHROPIC_API_KEY, paid credits required
  groq              — needs GROQ_API_KEY, free tier (console.groq.com)
  ollama            — needs a locally reachable Ollama daemon, OLLAMA_MODEL env var
Dataset-aware: works against the built-in "default" dataset or any user-uploaded
CSV registered via schema.register_csv_dataset, using that dataset's own schema
text, connection, and column classification.
"""
import os, re, textwrap
from datetime import date, datetime
from decimal import Decimal
from typing import Iterator
from schema import Dataset, get_dataset, run_sql

MAX_CORRECTION_ATTEMPTS = 2


def _sql_system(schema_text: str) -> str:
    return textwrap.dedent(f"""\
        You are a precise SQL analyst. Generate a single DuckDB SQL query that answers
        the user's question. Return ONLY the SQL — no markdown fences, no explanation.

        {schema_text}
    """)


EXPLAIN_SYSTEM = textwrap.dedent("""\
    You are a senior data analyst presenting a finding, not a database reading
    out rows. Given a question, the SQL that answered it, and the result:

    1. Answer the question directly in the first sentence, with the exact number(s).
    2. Add one sentence of higher-level framing that a raw table doesn't show —
       how concentrated/spread out the result is, how the top value compares to
       the rest, or what the pattern implies — but ONLY using numbers that are
       actually present in the result. Never invent a comparison, trend, or
       figure that isn't directly computable from the data you were given.

    2-4 sentences total. Be specific with numbers. No filler like "this
    suggests further analysis could be valuable." Do not mention SQL or
    technical terms.
""")


def _correction_system(schema_text: str) -> str:
    return textwrap.dedent(f"""\
        You are a SQL debugging assistant. The query below failed with the given error.
        Fix it and return ONLY corrected DuckDB SQL — no markdown, no explanation.

        {schema_text}
    """)


def _chat(system: str, user: str) -> str:
    model_env = os.environ.get("LLM", "claude").lower()

    if model_env == "ollama":
        from langchain_ollama import ChatOllama
        from langchain_core.messages import SystemMessage, HumanMessage
        llm = ChatOllama(model=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"), temperature=0)
        resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        return resp.content.strip()

    if model_env == "groq":
        import httpx
        resp = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
            json={
                "model": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    # Default: Anthropic Claude
    from anthropic import Anthropic
    client = Anthropic()
    resp = client.messages.create(
        model=os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001"),
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return resp.content[0].text.strip()


def _chat_stream(system: str, user: str) -> Iterator[str]:
    """Same as _chat but yields text chunks as they're generated, so the
    frontend can render the explanation word-by-word instead of waiting for
    the full response — the single biggest perceived-latency win available
    without changing models."""
    model_env = os.environ.get("LLM", "claude").lower()

    if model_env == "ollama":
        from langchain_ollama import ChatOllama
        from langchain_core.messages import SystemMessage, HumanMessage
        llm = ChatOllama(model=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"), temperature=0)
        for chunk in llm.stream([SystemMessage(content=system), HumanMessage(content=user)]):
            if chunk.content:
                yield chunk.content
        return

    if model_env == "groq":
        import httpx, json as _json
        with httpx.stream(
            "POST",
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
            json={
                "model": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
                "temperature": 0,
                "stream": True,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=30,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[len("data: "):]
                if payload.strip() == "[DONE]":
                    break
                delta = _json.loads(payload)["choices"][0]["delta"].get("content")
                if delta:
                    yield delta
        return

    from anthropic import Anthropic
    client = Anthropic()
    with client.messages.stream(
        model=os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001"),
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        yield from stream.text_stream


def _strip_fences(text: str) -> str:
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text.strip())
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


def json_default(obj):
    """Fallback encoder for SSE payloads — DuckDB/pandas results carry
    Timestamp/Decimal/numpy scalar types that plain json.dumps chokes on."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if hasattr(obj, "item"):  # numpy scalar (int64, float64, ...)
        return obj.item()
    return str(obj)


_DATE_LIKE = re.compile(r"date|month|year|week|quarter", re.IGNORECASE)


def suggest_chart(rows: list[dict]) -> dict | None:
    """Deterministic (no LLM call, no added latency) heuristic for how to
    visualize a result beyond a plain table/sentence:
      - a single-row result with numeric columns becomes KPI "stat" cards
        (a raw number sitting in one table cell reads as an afterthought;
        the same number as a large stat tile reads as an analytics product)
      - a 2-column, multi-row result with one label + one numeric column
        becomes a bar/line chart
    Anything wider/tabular is left as a plain table, where a chart wouldn't help."""
    if not rows:
        return None
    cols = list(rows[0].keys())

    def is_numeric(col: str) -> bool:
        return all(isinstance(r[col], (int, float, Decimal)) and not isinstance(r[col], bool) for r in rows)

    if len(rows) == 1:
        numeric_cols = [c for c in cols if is_numeric(c)]
        if not numeric_cols:
            return None
        return {"type": "stat", "fields": numeric_cols}

    if not (1 < len(rows) <= 50) or len(cols) != 2:
        return None

    numeric_cols = [c for c in cols if is_numeric(c)]
    label_cols = [c for c in cols if c not in numeric_cols]
    if len(numeric_cols) != 1 or len(label_cols) != 1:
        return None

    label_key, value_key = label_cols[0], numeric_cols[0]
    chart_type = "line" if _DATE_LIKE.search(label_key) else "bar"
    return {"type": chart_type, "labelKey": label_key, "valueKey": value_key}


# ---------------------------------------------------------------------------
# Default dataset: hand-curated follow-ups, tuned for this specific schema.
# ---------------------------------------------------------------------------
_DEFAULT_FOLLOWUP_RULES = [
    (re.compile(r"\bcountry\b", re.I), "Break this down by month instead of country"),
    (re.compile(r"\bmonth\b|\byear\b", re.I), "Which country drives most of this?"),
    (re.compile(r"\bproduct\b|\bstock_code\b|\bdescription\b", re.I), "Which customers bought this the most?"),
    (re.compile(r"\bcustomer\b", re.I), "What's the average order value for these customers?"),
    (re.compile(r"\btop\b|\border by .* desc\b", re.I), "Show the bottom 5 instead"),
]
_DEFAULT_GENERIC_FOLLOWUPS = [
    "Show this as a trend over time",
    "Break this down by country",
    "What's driving the top result?",
]


def _humanize(col: str) -> str:
    return col.replace("_", " ")


def _default_followups(question: str, sql: str) -> list[str]:
    haystack = f"{question} {sql}"
    matched = [suggestion for pattern, suggestion in _DEFAULT_FOLLOWUP_RULES if pattern.search(haystack)]
    for generic in _DEFAULT_GENERIC_FOLLOWUPS:
        if len(matched) >= 3:
            break
        if generic not in matched:
            matched.append(generic)
    return matched[:3]


_MEASURE_LIKE = re.compile(r"amount|price|revenue|total|cost|value|sales|salary|score|profit|qty|quantity|count", re.I)
_ID_LIKE = re.compile(r"^(id|index|time|timestamp|seq|row|key|no|num)_?\d*$", re.I)


def _rank_numeric(numeric_cols: list[str]) -> list[str]:
    """Prefer columns that read like an actual measure ('amount', 'price') over
    ones that read like an identifier or raw counter ('time', 'id', 'index')
    when picking which numeric column to feature first — otherwise a fraud
    dataset's first suggested question becomes 'total time' instead of
    'total amount', which is technically valid SQL but useless to a user."""
    def rank(name: str) -> tuple[int, int]:
        return (0 if _MEASURE_LIKE.search(name) else (2 if _ID_LIKE.match(name) else 1), numeric_cols.index(name))
    return sorted(numeric_cols, key=rank)


_ID_LIKE_NAME = re.compile(r"^(id|uuid|guid)$|_id$|^id_", re.I)


def _rank_categorical(cat_cols: list[str]) -> list[str]:
    """Same idea as _rank_numeric: a raw id/key column technically qualifies
    as 'categorical' by cardinality, but 'break this down by customer_id'
    is a far weaker suggestion than 'break this down by country' — push
    id-shaped names to the back instead of excluding them outright."""
    def rank(name: str) -> tuple[int, int]:
        return (1 if _ID_LIKE_NAME.search(name) else 0, cat_cols.index(name))
    return sorted(cat_cols, key=rank)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _generic_followups(dataset: Dataset, sql: str) -> list[str]:
    """For a user-uploaded dataset there's no hand-written domain knowledge to
    lean on, so follow-ups are generated from the dataset's own column
    classification instead — still specific to *this* data, just built from
    structure (numeric/categorical/date) rather than curated wording."""
    numeric = _rank_numeric([c.name for c in dataset.columns if c.kind == "numeric"])
    categorical = _rank_categorical([c.name for c in dataset.columns if c.kind == "categorical"])
    dates = [c.name for c in dataset.columns if c.kind == "date"]

    used_cols = {c.name for c in dataset.columns if re.search(rf"\b{re.escape(c.name)}\b", sql, re.I)}
    unused_categorical = [c for c in categorical if c not in used_cols] or categorical
    unused_dates = [c for c in dates if c not in used_cols] or dates
    unused_numeric = [c for c in numeric if c not in used_cols] or numeric

    suggestions = []
    if unused_categorical:
        suggestions.append(f"Break this down by {_humanize(unused_categorical[0])}")
    if unused_dates:
        suggestions.append(f"Show this as a trend over {_humanize(unused_dates[0])}")
    if unused_numeric and categorical:
        suggestions.append(f"Which {_humanize(categorical[0])} has the lowest {_humanize(unused_numeric[0])}?")
    if len(categorical) > 1:
        suggestions.append(f"Compare this across {_humanize(categorical[1])} instead")
    if not suggestions:
        suggestions.append("Show the bottom 5 instead")
    return _dedupe(suggestions)[:3]


def suggest_followups(question: str, sql: str, dataset: Dataset) -> list[str]:
    """Curated, deterministic next-question suggestions instead of a third
    LLM round-trip — keeps the 'what should I ask next' feature free and
    instant instead of adding latency for something secondary to the answer."""
    if dataset.id == "default":
        return _default_followups(question, sql)
    return _generic_followups(dataset, sql)


def generate_example_questions(dataset: Dataset) -> list[str]:
    """Schema-driven starter questions for a freshly uploaded dataset — a user
    staring at their own CSV with no idea what's askable is the single biggest
    drop-off risk of a 'bring your own data' feature, so this has to hand them
    something concrete and immediately runnable, built only from column names
    and types (no LLM call, no latency, works the instant upload finishes).

    Spreads across whichever numeric/categorical/date columns actually exist
    instead of reusing column [0] for every template — a dataset with two
    real measures (e.g. amount and a second numeric column) should surface
    both, not ask "total X" and "average X" back to back."""
    numeric = _rank_numeric([c.name for c in dataset.columns if c.kind == "numeric"])
    categorical = _rank_categorical([c.name for c in dataset.columns if c.kind == "categorical"])
    dates = [c.name for c in dataset.columns if c.kind == "date"]

    questions = ["How many rows are in this dataset?"]

    if numeric:
        m0 = _humanize(numeric[0])
        questions.append(f"What is the total {m0}?")
        questions.append(f"What is the highest single {m0}?")

    if categorical and numeric:
        c0, m0 = _humanize(categorical[0]), _humanize(numeric[0])
        questions.append(f"Which {c0} has the highest total {m0}?")
        questions.append(f"Show the top 5 {c0} by {m0}")
        if len(numeric) > 1:
            questions.append(f"Which {c0} has the highest average {_humanize(numeric[1])}?")
    elif categorical:
        questions.append(f"What are the most common values of {_humanize(categorical[0])}?")

    if len(categorical) > 1:
        questions.append(f"How many unique {_humanize(categorical[1])} are there?")

    if dates and numeric:
        questions.append(f"How does {_humanize(numeric[0])} change over {_humanize(dates[0])}?")

    return _dedupe(questions)[:6]


_CACHE: dict[str, dict] = {}


def _cache_key(question: str, dataset_id: str) -> str:
    return f"{dataset_id}:" + re.sub(r"\s+", " ", question.strip().lower())


def answer_stream(question: str, dataset_id: str = "default") -> Iterator[dict]:
    """Streaming counterpart to `answer()`: yields event dicts as soon as each
    stage completes instead of blocking on the full pipeline, so the frontend
    can render the SQL, then the table, then the chart, all before the
    explanation has even finished generating.

    Identical questions against the same dataset (case/whitespace-insensitive)
    skip straight to a cached SQL+rows+explanation instead of re-running two
    LLM round-trips — real speedup for the common case of a user re-asking or
    clicking a follow-up suggestion that overlaps a prior question, at zero
    risk of staleness since a given dataset's table never changes within a
    process lifetime."""
    dataset = get_dataset(dataset_id)
    cache_key = _cache_key(question, dataset_id)
    cached = _CACHE.get(cache_key)

    if cached:
        yield {"type": "sql", "sql": cached["sql"], "cached": True}
        yield {"type": "rows", "rows": cached["rows"], "row_count": len(cached["rows"])}
        chart = suggest_chart(cached["rows"])
        if chart:
            yield {"type": "chart", "chart": chart}
        for word in cached["explanation"].split(" "):
            yield {"type": "explanation_delta", "text": word + " "}
        yield {"type": "followups", "questions": suggest_followups(question, cached["sql"], dataset)}
        yield {"type": "done"}
        return

    sql = _strip_fences(_chat(_sql_system(dataset.schema_text), question))

    rows = None
    last_error = None
    for attempt in range(MAX_CORRECTION_ATTEMPTS + 1):
        try:
            rows = run_sql(sql, dataset_id)
            last_error = None
            break
        except Exception as exc:
            last_error = str(exc)
            if attempt < MAX_CORRECTION_ATTEMPTS:
                yield {"type": "correcting", "sql": sql, "error": last_error}
                correction_prompt = (
                    f"Question: {question}\n\n"
                    f"Failing SQL:\n{sql}\n\n"
                    f"Error: {last_error}\n\nReturn the corrected SQL."
                )
                sql = _strip_fences(_chat(_correction_system(dataset.schema_text), correction_prompt))

    yield {"type": "sql", "sql": sql}

    if last_error:
        yield {"type": "error", "error": last_error}
        return

    yield {"type": "rows", "rows": rows, "row_count": len(rows)}

    chart = suggest_chart(rows)
    if chart:
        yield {"type": "chart", "chart": chart}

    rows_preview = rows[:20]
    explain_prompt = (
        f"Question: {question}\n\n"
        f"SQL: {sql}\n\n"
        f"Result ({len(rows)} rows, showing first {len(rows_preview)}):\n{rows_preview}"
    )
    explanation_parts = []
    for chunk in _chat_stream(EXPLAIN_SYSTEM, explain_prompt):
        explanation_parts.append(chunk)
        yield {"type": "explanation_delta", "text": chunk}

    _CACHE[cache_key] = {"sql": sql, "rows": rows, "explanation": "".join(explanation_parts)}

    yield {"type": "followups", "questions": suggest_followups(question, sql, dataset)}
    yield {"type": "done"}


def answer(question: str, dataset_id: str = "default") -> dict:
    """
    Non-streaming counterpart used by the eval harness.
    Returns: {question, sql, rows, answer, error (optional)}
    """
    dataset = get_dataset(dataset_id)
    sql = _strip_fences(_chat(_sql_system(dataset.schema_text), question))

    rows = None
    last_error = None
    for attempt in range(MAX_CORRECTION_ATTEMPTS + 1):
        try:
            rows = run_sql(sql, dataset_id)
            last_error = None
            break
        except Exception as exc:
            last_error = str(exc)
            if attempt < MAX_CORRECTION_ATTEMPTS:
                correction_prompt = (
                    f"Question: {question}\n\n"
                    f"Failing SQL:\n{sql}\n\n"
                    f"Error: {last_error}\n\nReturn the corrected SQL."
                )
                sql = _strip_fences(_chat(_correction_system(dataset.schema_text), correction_prompt))

    if last_error:
        return {"question": question, "sql": sql, "rows": [], "answer": None, "error": last_error}

    rows_preview = rows[:20]
    explain_prompt = (
        f"Question: {question}\n\n"
        f"SQL: {sql}\n\n"
        f"Result ({len(rows)} rows, showing first {len(rows_preview)}):\n{rows_preview}"
    )
    plain_answer = _chat(EXPLAIN_SYSTEM, explain_prompt)

    return {
        "question": question,
        "sql": sql,
        "rows": rows,
        "answer": plain_answer,
        "error": None,
    }
