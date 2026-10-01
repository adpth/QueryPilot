from pathlib import Path
from querypilot.runtime import LLMResponse, make_mock_llm, make_agent
from querypilot.agent import AgentState


def test_llm_response_string_behavior():
    resp = LLMResponse("TOOL: list_tables", input_tokens=150, output_tokens=12)
    assert isinstance(resp, str)
    assert resp.startswith("TOOL:")
    assert resp.input_tokens == 150
    assert resp.output_tokens == 12
    # String manipulation preserves standard behavior
    assert resp.split()[1] == "list_tables"


def test_mock_llm_sample_questions():
    mock_llm = make_mock_llm()

    # Question 1: tracks longer than five minutes
    messages = [
        {"role": "user", "content": "How many tracks are longer than five minutes?"}
    ]
    r1 = mock_llm(messages)
    assert "list_tables" in r1

    messages.append({"role": "assistant", "content": str(r1)})
    messages.append({"role": "user", "content": "tracks\ngenres"})
    r2 = mock_llm(messages)
    assert "get_schema tracks" in r2

    messages.append({"role": "assistant", "content": str(r2)})
    messages.append({"role": "user", "content": "CREATE TABLE tracks (Milliseconds INTEGER)"})
    r3 = mock_llm(messages)
    assert "FINAL: SELECT COUNT(*) FROM tracks WHERE Milliseconds > 300000" in r3


def test_make_agent_returns_agent_state(tmp_path: Path):
    db_file = tmp_path / "dummy.sqlite"
    db_file.touch()

    def dummy_llm(messages):
        return LLMResponse("FINAL: SELECT 1", 10, 5)

    agent = make_agent(llm=dummy_llm)
    state = agent("test question", db_file)
    assert isinstance(state, AgentState)
    assert state.sql == "SELECT 1"
    assert state.input_tokens == 10
    assert state.output_tokens == 5
