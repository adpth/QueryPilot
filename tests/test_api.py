from pathlib import Path
from fastapi.testclient import TestClient
import pytest
from querypilot.api import app
from querypilot.config import settings
import sqlite3

client = TestClient(app)


@pytest.fixture
def mock_db_env(tmp_path: Path, monkeypatch):
    db_file = tmp_path / "testdb.sqlite"
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE items (id INTEGER, name TEXT)")
    conn.execute("INSERT INTO items VALUES (1, 'Widget')")
    conn.commit()
    conn.close()

    monkeypatch.setattr(settings, "db_dir", tmp_path)
    monkeypatch.setattr(settings, "mock_mode", True)
    return db_file


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "model" in data
    assert "db_dir" in data


def test_ask_missing_database():
    response = client.post("/ask", json={"question": "count items", "database": "nonexistent_db"})
    assert response.status_code == 404
    assert "unknown database" in response.json()["detail"]


def test_ask_valid_database(mock_db_env):
    response = client.post("/ask", json={"question": "count items", "database": "testdb"})
    assert response.status_code == 200
    data = response.json()
    assert "sql" in data
    assert "tool_calls" in data
    assert "repairs" in data
    assert "trace" in data
    assert "input_tokens" in data
    assert "output_tokens" in data
