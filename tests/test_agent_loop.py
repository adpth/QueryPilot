import sqlite3
from pathlib import Path
import pytest
from querypilot.agent import AgentState, build_graph
from querypilot.runtime import LLMResponse
from querypilot.config import settings


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE users (id INTEGER, name TEXT)")
    conn.executemany("INSERT INTO users VALUES (?, ?)", [(1, "Alice"), (2, "Bob")])
    conn.commit()
    conn.close()
    return path


def test_agent_completes_in_one_step(test_db: Path):
    def simple_llm(messages: list[dict]):
        return LLMResponse("FINAL: SELECT COUNT(*) FROM users", 50, 10)

    graph = build_graph(simple_llm)
    state = graph.invoke(AgentState(question="How many users?", db_path=test_db))
    assert state["sql"] == "SELECT COUNT(*) FROM users"
    assert state["input_tokens"] == 50
    assert state["output_tokens"] == 10
    assert state["tool_calls"] == 0


def test_agent_explores_then_finalizes(test_db: Path):
    responses = [
        LLMResponse("TOOL: get_schema users", 40, 5),
        LLMResponse("FINAL: SELECT name FROM users", 60, 10),
    ]
    call_idx = 0

    def multi_step_llm(messages: list[dict]):
        nonlocal call_idx
        resp = responses[call_idx]
        call_idx += 1
        return resp

    graph = build_graph(multi_step_llm)
    state = graph.invoke(AgentState(question="List users", db_path=test_db))
    assert state["sql"] == "SELECT name FROM users"
    assert state["tool_calls"] == 1
    assert state["input_tokens"] == 100
    assert state["output_tokens"] == 15
    assert len(state["trace"]) == 1
    assert state["trace"][0]["tool"] == "get_schema"


def test_agent_stops_at_max_steps(test_db: Path, monkeypatch):
    monkeypatch.setattr(settings, "max_steps", 2)

    def looping_llm(messages: list[dict]):
        return LLMResponse("TOOL: list_tables", 10, 5)

    graph = build_graph(looping_llm)
    state = graph.invoke(AgentState(question="Loop", db_path=test_db))
    # Stopped because max_steps reached
    assert state["tool_calls"] == 2
    assert state["sql"] is None


def test_agent_self_repairs_after_sql_error(test_db: Path):
    responses = [
        LLMResponse("TOOL: run_sql SELECT bad_col FROM users", 30, 10),  # Error
        LLMResponse("FINAL: SELECT name FROM users", 50, 10),  # Repaired
    ]
    call_idx = 0

    def repairing_llm(messages: list[dict]):
        nonlocal call_idx
        resp = responses[call_idx]
        call_idx += 1
        return resp

    graph = build_graph(repairing_llm)
    state = graph.invoke(AgentState(question="Get names", db_path=test_db))
    assert state["sql"] == "SELECT name FROM users"
    assert state["repairs"] == 1
    assert state["tool_calls"] == 1
