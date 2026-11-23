"""
Built-in question-to-SQL engine. No API key and no network: it reads the dataset's own column
names and types and recognises the common question shapes (totals, averages, top N by a group,
trends over time, unique counts). It is what answers when no AI model is configured, and the
fallback when the configured model fails. Anything it cannot read gets a clear message.
"""
import re
from dataclasses import dataclass
from typing import Callable

# Words that mean the same column, so "sales" finds a revenue column and "units" finds quantity
_SYN = [{"revenue", "sale", "income", "turnover"}, {"price", "cost"}, {"quantity", "qty", "unit", "volume"},
        {"amount", "value", "spend", "payment"}, {"customer", "client", "buyer", "user"},
        {"product", "item", "stock"}, {"country", "nation"}, {"date", "day", "time"}]


@dataclass
class Plan:
    sql: str
    explain: Callable[[list], str]


def _norm(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def _tokens(text: str) -> set:
    return {_norm(w) for w in re.findall(r"[a-z0-9]+", text.lower())}


def _expand(tokens: set) -> set:
    out = set(tokens)
    for group in _SYN:
        if tokens & group:
            out |= group
    return out


def _best(cols: list, qtok: set):
    """The column whose name shares the most words with the question, or None if none do."""
    scored = [(len(_expand(_tokens(c.name.replace("_", " "))) & qtok), -i, c) for i, c in enumerate(cols)]
    top = max(scored, default=None)
    return top[2] if top and top[0] > 0 else None


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _label(name: str) -> str:
    return name.replace("_", " ")


def _fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def plan(question: str, dataset) -> "Plan | None":
    from chain import _rank_categorical, _rank_numeric   # imported here: chain imports this module

    q = question.lower().strip().rstrip("?.! ")
    qtok = _tokens(q)
    t = _q(dataset.table)
    numeric = [c for c in dataset.columns if c.kind == "numeric"]
    categorical = [c for c in dataset.columns if c.kind == "categorical"]
    dates = [c for c in dataset.columns if c.kind == "date"]

    measure = _best(numeric, qtok)
    dim = _best(categorical, qtok)
    ranked = _rank_categorical([c.name for c in categorical])
    default_dim = next((c for c in categorical if ranked and c.name == ranked[0]), None)
    date = _best(dates, qtok) or (dates[0] if dates else None)

    agg = "AVG" if re.search(r"\b(average|avg|mean)\b", q) else \
          "MAX" if re.search(r"\b(highest single|largest|maximum|max|biggest single)\b", q) else \
          "MIN" if re.search(r"\b(lowest single|smallest|minimum|min)\b", q) else "SUM"
    word = {"AVG": "average", "MAX": "highest single", "MIN": "lowest single", "SUM": "total"}[agg]
    asc = bool(re.search(r"\b(lowest|least|fewest|smallest|bottom)\b", q))
    top_n = re.search(r"\b(?:top|bottom)\s+(\d+)\b", q)
    limit = int(top_n.group(1)) if top_n else 5

    # how many rows
    if re.search(r"\bhow many (rows|records|entries|lines)\b", q):
        return Plan(f"SELECT COUNT(*) AS row_count FROM {t}", lambda r: f"The dataset has {_fmt(r[0]['row_count'])} rows.")

    # how many unique / distinct X
    m = re.search(r"\b(unique|distinct|different)\b", q)
    if m and "how many" in q:
        col = _best(categorical + dates, qtok)
        if col:
            return Plan(f"SELECT COUNT(DISTINCT {_q(col.name)}) AS unique_{col.name} FROM {t}",
                        lambda r: f"There are {_fmt(list(r[0].values())[0])} unique {_label(col.name)} values.")

    # most common values of X
    if re.search(r"\b(most common|most frequent|common values)\b", q):
        col = dim or default_dim
        if col:
            return Plan(f"SELECT {_q(col.name)}, COUNT(*) AS rows FROM {t} GROUP BY 1 ORDER BY rows DESC LIMIT {limit}",
                        lambda r: f"The most common {_label(col.name)} is {r[0][col.name]} ({_fmt(r[0]['rows'])} rows)." if r else "No rows.")

    # Nothing in the question points at this data and it asks for no calculation: say so instead of guessing
    asks_for_numbers = re.search(r"\b(total|sum|average|avg|mean|highest|lowest|top|bottom|most|least|largest|smallest|"
                                 r"maximum|minimum|how many|count|trend|over time|per|by|each|change)\b", q)
    if measure is None and dim is None and not asks_for_numbers:
        return None
    if measure is None and numeric:
        measure = next(c for c in numeric if c.name == _rank_numeric([n.name for n in numeric])[0])
    if measure is None:
        return None
    mc = _q(measure.name)
    mlabel = _label(measure.name)

    # change over time
    if re.search(r"\b(over time|trend|change|monthly|per month|by month|each month|by year|yearly|per year|each year|annual)\b", q) and date:
        grain = "year" if re.search(r"\b(year|yearly|annual)\b", q) else "month"
        a = "AVG" if agg == "AVG" else "SUM"
        sql = (f"SELECT STRFTIME(DATE_TRUNC('{grain}', {_q(date.name)}), '{'%Y' if grain == 'year' else '%Y-%m'}') AS {grain}, "
               f"ROUND({a}({mc}), 2) AS {measure.name} FROM {t} GROUP BY 1 ORDER BY 1")

        def explain_time(r):
            if len(r) < 2:
                return "Not enough periods to show a trend."
            peak = max(r, key=lambda x: x[measure.name] or 0)
            return (f"{mlabel.capitalize()} went from {_fmt(r[0][measure.name])} in {r[0][grain]} to "
                    f"{_fmt(r[-1][measure.name])} in {r[-1][grain]}. The peak was {_fmt(peak[measure.name])} in {peak[grain]}.")
        return Plan(sql, explain_time)

    # "highest single X" / "lowest single X" is one number; "which Y has the highest X" is a ranking
    grouped = dim is not None or re.search(r"\b(which|top|bottom|by|per|each)\b", q) or \
        (agg in ("SUM", "AVG") and re.search(r"\b(highest|lowest|most|least)\b", q))
    if grouped:
        col = dim or default_dim
        if col:
            a = "AVG" if agg == "AVG" else "SUM"
            order = "ASC" if asc else "DESC"
            sql = (f"SELECT {_q(col.name)}, ROUND({a}({mc}), 2) AS {measure.name} FROM {t} "
                   f"WHERE {_q(col.name)} IS NOT NULL GROUP BY 1 ORDER BY {measure.name} {order} LIMIT {limit}")

            def explain_group(r):
                if not r:
                    return "No rows matched."
                rest = ", ".join(f"{x[col.name]} ({_fmt(x[measure.name])})" for x in r[1:3])
                head = f"{r[0][col.name]} is {'lowest' if asc else 'highest'} on {'average ' if a == 'AVG' else 'total '}{mlabel} at {_fmt(r[0][measure.name])}"
                return head + (f", followed by {rest}." if rest else ".")
            return Plan(sql, explain_group)

    # a single number
    fn = {"SUM": "SUM", "AVG": "AVG", "MAX": "MAX", "MIN": "MIN"}[agg]
    return Plan(f"SELECT ROUND({fn}({mc}), 2) AS {measure.name} FROM {t}",
                lambda r: f"The {word} {mlabel} is {_fmt(r[0][measure.name])}.")


def help_text(dataset) -> str:
    from chain import generate_example_questions
    return ("I couldn't match that to this dataset's columns. Try something like: "
            + " / ".join(generate_example_questions(dataset)[:3]))
