"""Read-only SQLite access with a statement timeout and a row cap.

Every query the agent generates goes through run_query. Nothing else opens a
connection, so the guardrails cannot be bypassed by a tool that forgets them.
"""

import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

WRITE_TOKENS = {
    "insert", "update", "delete", "drop", "alter", "create",
    "truncate", "attach", "detach", "pragma", "vacuum",
}


class UnsafeQuery(Exception):
    """Raised when a generated statement is not a read-only SELECT."""


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    truncated: bool
    elapsed_ms: float


def strip_sql_literals_and_comments(sql: str) -> str:
    """Removes comments and string literals so keywords inside strings aren't falsely flagged."""
    # Line comments: -- ...
    cleaned = re.sub(r"--[^\n]*", " ", sql)
    # Block comments: /* ... */
    cleaned = re.sub(r"/\*[\s\S]*?\*/", " ", cleaned)
    # String literals: '...' with escaped ''
    cleaned = re.sub(r"'(?:''|[^'])*'", "''", cleaned)
    return cleaned


def assert_read_only(sql: str) -> None:
    stripped = sql.strip().rstrip(";")
    if not stripped:
        raise UnsafeQuery("empty query")

    # Check for multiple statements outside of comments/strings
    check_text = strip_sql_literals_and_comments(stripped)
    if ";" in check_text:
        raise UnsafeQuery("multiple statements are not allowed")

    first = check_text.split(None, 1)[0].lower()
    if first not in {"select", "with", "explain"}:
        raise UnsafeQuery("only SELECT/WITH is allowed, got: " + first)

    # Check for REPLACE INTO specifically (scalar replace() function is allowed)
    normalized_spacing = " ".join(check_text.lower().split())
    if "replace into" in normalized_spacing:
        raise UnsafeQuery("write keyword in query: replace into")

    tokens = {t.strip("(),;").lower() for t in check_text.split()}
    banned = tokens & WRITE_TOKENS
    if banned:
        raise UnsafeQuery("write keyword in query: " + ", ".join(sorted(banned)))


def connect(db_path: Path, timeout_s: int) -> sqlite3.Connection:
    conn = sqlite3.connect("file:" + str(db_path) + "?mode=ro", uri=True)
    # Interrupt long queries instead of letting the agent hang the eval run.
    deadline = time.monotonic() + timeout_s
    conn.set_progress_handler(lambda: time.monotonic() > deadline, 10_000)
    return conn


def run_query(db_path: Path, sql: str, timeout_s: int, max_rows: int) -> QueryResult:
    assert_read_only(sql)
    conn = connect(db_path, timeout_s)
    try:
        start = time.perf_counter()
        cursor = conn.execute(sql)
        rows = cursor.fetchmany(max_rows + 1)
        elapsed_ms = (time.perf_counter() - start) * 1000
        columns = [d[0] for d in cursor.description] if cursor.description else []
        truncated = len(rows) > max_rows
        return QueryResult(columns, rows[:max_rows], truncated, elapsed_ms)
    finally:
        conn.close()
