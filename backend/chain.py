"""
NL → SQL chain with self-correction.
Supports Claude (ANTHROPIC_API_KEY) or Ollama (OLLAMA_MODEL env var, default llama3.1:8b).
"""
import os, re, textwrap
from schema import SCHEMA_TEXT, run_sql

MAX_CORRECTION_ATTEMPTS = 2

SQL_SYSTEM = textwrap.dedent(f"""\
    You are a precise SQL analyst. Generate a single DuckDB SQL query that answers
    the user's question. Return ONLY the SQL — no markdown fences, no explanation.

    {SCHEMA_TEXT}
""")

EXPLAIN_SYSTEM = textwrap.dedent("""\
    You are a data analyst assistant. Given a natural-language question, the SQL
    that was executed to answer it, and the resulting data, write a concise
    (2-4 sentence) plain-English answer. Be specific with numbers.
    Do not mention SQL or technical terms.
""")

CORRECTION_SYSTEM = textwrap.dedent(f"""\
    You are a SQL debugging assistant. The query below failed with the given error.
    Fix it and return ONLY corrected DuckDB SQL — no markdown, no explanation.

    {SCHEMA_TEXT}
""")


def _chat(system: str, user: str) -> str:
    model_env = os.environ.get("LLM", "claude").lower()

    if model_env == "ollama":
        from langchain_ollama import ChatOllama
        from langchain_core.messages import SystemMessage, HumanMessage
        llm = ChatOllama(model=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"), temperature=0)
        resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        return resp.content.strip()

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


def _strip_fences(text: str) -> str:
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text.strip())
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


def answer(question: str) -> dict:
    """
    Returns:
        {question, sql, rows, answer, error (optional)}
    """
    sql = _strip_fences(_chat(SQL_SYSTEM, question))

    rows = None
    last_error = None
    for attempt in range(MAX_CORRECTION_ATTEMPTS + 1):
        try:
            rows = run_sql(sql)
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
                sql = _strip_fences(_chat(CORRECTION_SYSTEM, correction_prompt))

    if last_error:
        return {"question": question, "sql": sql, "rows": [], "answer": None, "error": last_error}

    # Generate plain-English explanation
    rows_preview = rows[:20]  # cap for prompt size
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
