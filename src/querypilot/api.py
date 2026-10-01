"""HTTP API surface. Exposes the QueryPilot agent over REST."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from querypilot.config import settings
from querypilot.runtime import make_agent

app = FastAPI(title="QueryPilot", description="Agentic text-to-SQL API")

# Default agent instance
_agent_runner = None


def get_agent():
    global _agent_runner
    if _agent_runner is None:
        _agent_runner = make_agent()
    return _agent_runner


class AskRequest(BaseModel):
    question: str
    database: str


class AskResponse(BaseModel):
    sql: str | None
    tool_calls: int
    repairs: int
    trace: list[dict]
    input_tokens: int = 0
    output_tokens: int = 0


class HealthResponse(BaseModel):
    status: str
    model: str
    db_dir: str
    mock_mode: bool


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        model=settings.model,
        db_dir=str(settings.db_dir),
        mock_mode=settings.mock_mode or not bool(settings.openai_api_key),
    )


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    db_path = Path(settings.db_dir) / (req.database + ".sqlite")
    if not db_path.exists():
        raise HTTPException(404, f"unknown database: {req.database} (searched at {db_path})")

    agent = get_agent()
    state = agent(req.question, db_path)

    return AskResponse(
        sql=state.sql,
        tool_calls=state.tool_calls,
        repairs=state.repairs,
        trace=state.trace,
        input_tokens=getattr(state, "input_tokens", 0),
        output_tokens=getattr(state, "output_tokens", 0),
    )

