"""Tools the agent can call. Each returns a string the model reads as an observation."""

from pathlib import Path

from querypilot.config import settings
from querypilot.db import UnsafeQuery, run_query


def list_tables(db_path: Path) -> str:
    try:
        result = run_query(
            db_path,
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name",
            settings.sql_timeout_s,
            settings.max_rows,
        )
        return "\n".join(r[0] for r in result.rows) if result.rows else "(no tables found)"
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}: {exc}"


def get_schema(db_path: Path, table: str) -> str:
    table_name = table.strip().strip("'\"`;")
    if not table_name:
        return "ERROR: table name required"
    try:
        escaped_name = table_name.replace("'", "''")
        result = run_query(
            db_path,
            f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{escaped_name}'",
            settings.sql_timeout_s,
            settings.max_rows,
        )
        if not result.rows or not result.rows[0][0]:
            return f"no table named {table_name}"
        return result.rows[0][0]
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}: {exc}"


def sample_rows(db_path: Path, table: str, n: int = 5) -> str:
    parts = table.strip().replace(",", " ").split()
    limit = n
    if len(parts) >= 2 and parts[-1].isdigit():
        table_name = parts[0].strip("',\"`;")
        limit = int(parts[-1])
    elif parts:
        table_name = parts[0].strip("',\"`;")
    else:
        return "ERROR: table name required"

    try:
        escaped_table = table_name.replace('"', '""')
        result = run_query(
            db_path, f'SELECT * FROM "{escaped_table}" LIMIT {limit}', settings.sql_timeout_s, limit
        )
        return format_result(result.columns, result.rows)
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}: {exc}"


def explain_query(db_path: Path, sql: str) -> str:
    """Query plan, so the agent can see a full table scan before paying for it."""
    try:
        result = run_query(
            db_path, "EXPLAIN QUERY PLAN " + sql, settings.sql_timeout_s, settings.max_rows
        )
        return "\n".join(str(r) for r in result.rows) if result.rows else "(empty plan)"
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}: {exc}"


def run_sql(db_path: Path, sql: str) -> tuple[str, bool]:
    """Returns (observation, ok). A failure is fed back so the agent can repair it."""
    try:
        result = run_query(db_path, sql, settings.sql_timeout_s, settings.max_rows)
    except UnsafeQuery as exc:
        return "BLOCKED: " + str(exc), False
    except Exception as exc:
        return "ERROR: " + type(exc).__name__ + ": " + str(exc), False
    body = format_result(result.columns, result.rows)
    if result.truncated:
        body += "\n(" + str(settings.max_rows) + " row cap reached)"
    return body, True


def format_result(columns: list[str], rows: list[tuple]) -> str:
    if not rows:
        return "(0 rows)"
    header = " | ".join(columns)
    body = "\n".join(" | ".join(str(v) for v in row) for row in rows)
    return header + "\n" + body

