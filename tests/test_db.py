import sqlite3
from pathlib import Path

import pytest

from querypilot.db import UnsafeQuery, assert_read_only, run_query


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "t.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE items (id INTEGER, name TEXT)")
    conn.executemany("INSERT INTO items VALUES (?, ?)", [(1, "a"), (2, "b"), (3, "c")])
    conn.commit()
    conn.close()
    return path


@pytest.mark.parametrize("sql", [
    "DROP TABLE items",
    "UPDATE items SET name = 'x'",
    "SELECT 1; DROP TABLE items",
    "INSERT INTO items VALUES (4, 'd')",
    "",
])
def test_write_statements_are_rejected(sql):
    with pytest.raises(UnsafeQuery):
        assert_read_only(sql)


def test_select_and_cte_are_allowed():
    assert_read_only("SELECT * FROM items")
    assert_read_only("WITH x AS (SELECT 1) SELECT * FROM x")


def test_row_cap_marks_truncation(db):
    result = run_query(db, "SELECT * FROM items", timeout_s=5, max_rows=2)
    assert len(result.rows) == 2
    assert result.truncated is True


def test_connection_is_read_only(db):
    from querypilot.db import connect
    conn = connect(db, 5)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("INSERT INTO items VALUES (9, 'z')")
    conn.close()
