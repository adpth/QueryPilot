import sqlite3
from pathlib import Path
import pytest
from querypilot import tools


@pytest.fixture
def sample_db(tmp_path: Path) -> Path:
    path = tmp_path / "sample.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE tracks (id INTEGER, name TEXT, duration INTEGER)")
    conn.executemany(
        "INSERT INTO tracks VALUES (?, ?, ?)",
        [(1, "Track A", 200), (2, "Track B", 350), (3, "Track C", 400)],
    )
    conn.commit()
    conn.close()
    return path


def test_list_tables(sample_db: Path):
    tables = tools.list_tables(sample_db)
    assert "tracks" in tables


def test_get_schema(sample_db: Path):
    schema = tools.get_schema(sample_db, "tracks")
    assert "CREATE TABLE tracks" in schema
    assert "no table named" in tools.get_schema(sample_db, "nonexistent")
    # Table with quotes
    assert "CREATE TABLE tracks" in tools.get_schema(sample_db, "'tracks'")


def test_sample_rows(sample_db: Path):
    rows = tools.sample_rows(sample_db, "tracks", n=2)
    assert "Track A" in rows
    assert "Track B" in rows
    # Multi-word table and limit argument
    rows_with_limit = tools.sample_rows(sample_db, "tracks 1")
    assert "Track A" in rows_with_limit
    assert "Track B" not in rows_with_limit


def test_explain_query(sample_db: Path):
    plan = tools.explain_query(sample_db, "SELECT * FROM tracks")
    assert plan != ""


def test_run_sql(sample_db: Path):
    body, ok = tools.run_sql(sample_db, "SELECT COUNT(*) FROM tracks")
    assert ok is True
    assert "3" in body

    # Unsafe query blocked
    blocked_body, ok = tools.run_sql(sample_db, "DROP TABLE tracks")
    assert ok is False
    assert "BLOCKED:" in blocked_body

    # Syntax error reported as feedback
    err_body, ok = tools.run_sql(sample_db, "SELECT * FROM nonexistent")
    assert ok is False
    assert "ERROR:" in err_body
