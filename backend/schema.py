"""
Dataset registry: loads the built-in retail.csv as the "default" dataset, and
lets users register their own CSV as an additional in-memory DuckDB table —
each with its own connection, schema description, and classified columns (so
suggested questions/follow-ups can be generated from the actual data instead
of hardcoded UK-retail wording).
"""
import io
import json
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data" / "retail.csv"
MAX_ROWS = 1_000_000
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200MB — covers real-world CSVs (e.g. the ~144MB Kaggle credit-card-fraud dataset)

# Uploaded datasets are also written here (parquet + a JSON manifest) so they
# survive a process restart — without this, a single Render free-tier
# sleep/wake cycle (or any dev-server reload) silently wipes every dataset a
# user has uploaded, since the DuckDB tables otherwise live only in memory.
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Column:
    name: str
    kind: str  # 'numeric' | 'date' | 'categorical' | 'text'


@dataclass
class Dataset:
    id: str
    name: str
    con: duckdb.DuckDBPyConnection | None
    table: str
    schema_text: str
    row_count: int
    columns: list[Column] = field(default_factory=list)


_datasets: dict[str, Dataset] = {}


def _load_default() -> Dataset:
    con = duckdb.connect()
    con.execute(f"""
        CREATE TABLE orders AS
        SELECT
            invoice       AS invoice_no,
            stockcode     AS stock_code,
            description,
            CAST(quantity AS INTEGER) AS quantity,
            invoicedate   AS invoice_date,
            CAST(price AS DOUBLE) AS price,
            customer_id,
            country,
            CAST(revenue AS DOUBLE) AS revenue
        FROM read_csv_auto(
            '{DATA.as_posix()}',
            header=True,
            timestampformat='%Y-%m-%d %H:%M:%S',
            types={{'invoice':'VARCHAR','stockcode':'VARCHAR','customer_id':'VARCHAR'}}
        )
    """)
    row_count = con.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    schema_text = """
Table: orders
Columns:
  invoice_no   VARCHAR  — unique invoice identifier (each invoice = one transaction)
  stock_code   VARCHAR  — product/item code
  description  VARCHAR  — product name/description
  quantity     INTEGER  — units sold (always > 0; cancellations excluded)
  invoice_date TIMESTAMP — transaction datetime (range: 2009-12-01 to 2011-12-09)
  price        DOUBLE   — unit price in GBP (£)
  customer_id  VARCHAR  — customer identifier (NULL for guest/unregistered orders)
  country      VARCHAR  — customer's country (predominantly United Kingdom)
  revenue      DOUBLE   — computed column: quantity × price (in £)

Data: ~400K valid order lines from a UK-based online retailer.
Useful DuckDB date functions: DATE_PART('year', invoice_date), DATE_TRUNC('month', invoice_date),
  STRFTIME(invoice_date, '%Y-%m'), date_diff('day', d1, d2).
For top-N queries use: ORDER BY ... DESC LIMIT N.
Always use double-quoted column names if they contain spaces (none here).
Return results rounded to 2 decimal places for monetary values.
"""
    columns = [
        Column("invoice_no", "categorical"),
        Column("stock_code", "categorical"),
        Column("description", "categorical"),
        Column("quantity", "numeric"),
        Column("invoice_date", "date"),
        Column("price", "numeric"),
        Column("customer_id", "categorical"),
        Column("country", "categorical"),
        Column("revenue", "numeric"),
    ]
    return Dataset(id="default", name="UK Online Retail (2009–2011)", con=con, table="orders",
                    schema_text=schema_text, row_count=row_count, columns=columns)


def _manifest_path(dataset_id: str) -> Path:
    return UPLOAD_DIR / f"{dataset_id}.json"


def _parquet_path(dataset_id: str) -> Path:
    return UPLOAD_DIR / f"{dataset_id}.parquet"


def _persist_to_disk(dataset_id: str, name: str, df: pd.DataFrame, columns: list[Column], schema_text: str) -> None:
    df.to_parquet(_parquet_path(dataset_id))
    manifest = {
        "id": dataset_id,
        "name": name,
        "row_count": len(df),
        "columns": [{"name": c.name, "kind": c.kind} for c in columns],
        "schema_text": schema_text,
    }
    _manifest_path(dataset_id).write_text(json.dumps(manifest))


def _list_persisted_manifests() -> list[dict]:
    manifests = []
    for path in UPLOAD_DIR.glob("*.json"):
        try:
            manifests.append(json.loads(path.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    return manifests


def _restore_from_disk(dataset_id: str) -> Dataset | None:
    manifest_path, parquet_path = _manifest_path(dataset_id), _parquet_path(dataset_id)
    if not manifest_path.exists() or not parquet_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text())
        df = pd.read_parquet(parquet_path)
    except (json.JSONDecodeError, OSError, ValueError):
        return None

    table = f"user_{dataset_id}"
    con = duckdb.connect()
    con.register("incoming", df)
    con.execute(f"CREATE TABLE {table} AS SELECT * FROM incoming")
    con.unregister("incoming")

    columns = [Column(c["name"], c["kind"]) for c in manifest["columns"]]
    return Dataset(id=dataset_id, name=manifest["name"], con=con, table=table,
                    schema_text=manifest["schema_text"], row_count=manifest["row_count"], columns=columns)


def get_dataset(dataset_id: str = "default") -> Dataset:
    if dataset_id in _datasets:
        return _datasets[dataset_id]
    if dataset_id == "default":
        _datasets["default"] = _load_default()
        return _datasets["default"]

    restored = _restore_from_disk(dataset_id)
    if restored is None:
        raise KeyError(f"Unknown dataset: {dataset_id}")
    _datasets[dataset_id] = restored
    return restored


def list_datasets() -> list[Dataset]:
    get_dataset("default")  # ensure it's loaded so it always shows up
    result = list(_datasets.values())
    seen_ids = {ds.id for ds in result}
    for manifest in _list_persisted_manifests():
        if manifest["id"] in seen_ids:
            continue
        columns = [Column(c["name"], c["kind"]) for c in manifest["columns"]]
        # Listed without a live connection until actually queried — get_dataset()
        # does the full restore-from-parquet lazily at that point.
        result.append(Dataset(id=manifest["id"], name=manifest["name"], con=None,
                               table=f"user_{manifest['id']}", schema_text=manifest["schema_text"],
                               row_count=manifest["row_count"], columns=columns))
        seen_ids.add(manifest["id"])
    return result


def _sanitize_columns(raw_columns: list[str]) -> list[str]:
    """User CSV headers can be anything ('Order Date', '2023 Sales!', ...).
    Normalizing to safe snake_case identifiers up front means the LLM never
    has to get quoting of odd column names right, which is a much more
    common NL2SQL failure mode than the query logic itself."""
    seen: dict[str, int] = {}
    out = []
    for raw in raw_columns:
        base = re.sub(r"[^0-9a-zA-Z_]+", "_", str(raw).strip().lower()).strip("_") or "col"
        if base[0].isdigit():
            base = f"c_{base}"
        name = base
        while name in out:
            seen[base] = seen.get(base, 0) + 1
            name = f"{base}_{seen[base]}"
        out.append(name)
    return out


def _classify_columns(df: pd.DataFrame) -> list[Column]:
    columns = []
    n = len(df)
    for col in df.columns:
        series = df[col]
        if pd.api.types.is_numeric_dtype(series):
            # A numeric column with only 2 distinct values (0/1, 1/2, ...) is a
            # flag/label, not a continuous measure — summing or averaging a
            # fraud-class flag produces a meaningless "total class" question.
            # Group-by/breakdown questions are what it's actually useful for.
            if series.nunique(dropna=True) <= 2:
                columns.append(Column(col, "categorical"))
            else:
                columns.append(Column(col, "numeric"))
            continue
        if pd.api.types.is_datetime64_any_dtype(series):
            columns.append(Column(col, "date"))
            continue
        # try parsing as date; if most non-null values parse, treat as a date column
        try:
            parsed = pd.to_datetime(series, errors="coerce")
            if parsed.notna().mean() > 0.8:
                columns.append(Column(col, "date"))
                continue
        except (ValueError, TypeError):
            pass
        nunique = series.nunique(dropna=True)
        # Absolute cap handles small datasets (ratio alone misclassifies a
        # 3-value column as "text" when there are only 5 rows); ratio handles
        # large ones where 50 unique values could still be high-cardinality text.
        if n > 0 and (nunique <= 50 or nunique / n < 0.5):
            columns.append(Column(col, "categorical"))
        else:
            columns.append(Column(col, "text"))
    return columns


def _build_schema_text(table: str, df: pd.DataFrame, columns: list[Column]) -> str:
    lines = [f"Table: {table}", "Columns:"]
    for col in columns:
        dtype = str(df[col.name].dtype)
        lines.append(f"  {col.name}   ({dtype}, {col.kind})")
    sample = df.head(3).to_dict(orient="records")
    lines.append(f"\nSample rows (first 3, for format/context only): {sample}")
    lines.append(f"\nTotal rows: {len(df)}")
    lines.append("Column names are already safe snake_case identifiers — no quoting needed.")
    lines.append("For top-N queries use: ORDER BY ... DESC LIMIT N.")
    return "\n".join(lines)


def register_csv_dataset(filename: str, file_bytes: bytes) -> Dataset:
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError(f"File too large — max {MAX_UPLOAD_BYTES // (1024 * 1024)}MB for this demo.")

    df = pd.read_csv(io.BytesIO(file_bytes))
    if len(df) == 0 or len(df.columns) == 0:
        raise ValueError("CSV appears to be empty.")
    if len(df) > MAX_ROWS:
        df = df.head(MAX_ROWS)  # keep it usable rather than rejecting outright

    df.columns = _sanitize_columns(list(df.columns))
    columns = _classify_columns(df)

    dataset_id = uuid.uuid4().hex[:10]
    table = f"user_{dataset_id}"
    con = duckdb.connect()
    con.register("incoming", df)
    con.execute(f"CREATE TABLE {table} AS SELECT * FROM incoming")
    con.unregister("incoming")

    schema_text = _build_schema_text(table, df, columns)
    display_name = Path(filename).stem[:60] or "Uploaded dataset"

    ds = Dataset(id=dataset_id, name=display_name, con=con, table=table,
                 schema_text=schema_text, row_count=len(df), columns=columns)
    _datasets[dataset_id] = ds
    _persist_to_disk(dataset_id, display_name, df, columns, schema_text)
    return ds


_WRITE_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|ATTACH|COPY|PRAGMA|EXPORT|IMPORT|CALL|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


class UnsafeSQLError(ValueError):
    """Raised when LLM-generated SQL would mutate state instead of just reading it."""


def validate_readonly_sql(sql: str) -> None:
    """Guard against a hallucinated or injected destructive statement being run
    against a shared, process-lifetime DuckDB connection. Every request against
    a given dataset hits the *same* in-memory table — a single `DROP TABLE` or
    `DELETE FROM` generated by the LLM (whether from a bad prompt, a genuine
    hallucination, or a crafted question designed to inject one) would corrupt
    data for every subsequent user of that dataset until restart.
    Belt: only the first statement's leading keyword must be SELECT/WITH.
    Suspenders: block write/DDL keywords anywhere, including inside a stacked
    `; DROP TABLE ...` second statement.
    """
    stripped = sql.strip().rstrip(";")
    if ";" in stripped:
        raise UnsafeSQLError("Multiple statements are not allowed.")
    first_word = re.match(r"\s*(\w+)", stripped)
    if not first_word or first_word.group(1).upper() not in ("SELECT", "WITH"):
        raise UnsafeSQLError("Only SELECT queries are allowed.")
    if _WRITE_KEYWORDS.search(stripped):
        raise UnsafeSQLError("Query contains a disallowed write/DDL keyword.")


def run_sql(sql: str, dataset_id: str = "default") -> list[dict]:
    validate_readonly_sql(sql)
    ds = get_dataset(dataset_id)
    result = ds.con.execute(sql).fetchdf()
    return result.to_dict(orient="records")
