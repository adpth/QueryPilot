"""Model client boundary and agent factory.

make_agent returns a callable (question, db_path) -> AgentState. Keeping the
model client behind this boundary means an ablation is a config change, not a
rewrite, and the eval harness can run against a stub with no API key.
"""

import logging
import os
from pathlib import Path
from typing import Any, Callable

import httpx

from querypilot.agent import AgentState, build_graph
from querypilot.config import settings

logger = logging.getLogger(__name__)


class LLMResponse(str):
    """Subclass of str that preserves token accounting metadata."""

    def __new__(cls, content: str, input_tokens: int = 0, output_tokens: int = 0):
        obj = super().__new__(cls, content)
        obj.input_tokens = input_tokens
        obj.output_tokens = output_tokens
        return obj


def make_mock_llm() -> Callable[[list[dict]], LLMResponse]:
    """Deterministic offline LLM for unit tests, local verification, and evals."""

    def mock_llm(messages: list[dict]) -> LLMResponse:
        # Estimate token counts for realistic accounting
        input_tokens = sum(len(m.get("content", "").split()) * 2 for m in messages)
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = m.get("content", "").lower()
                break

        # Check conversation history for tool responses
        all_content = " ".join(m.get("content", "") for m in messages).lower()

        # Rule-based answering for sample benchmark questions
        if "longer than five minutes" in all_content or "milliseconds > 300000" in all_content:
            if "list_tables" not in all_content:
                return LLMResponse("TOOL: list_tables", input_tokens, 5)
            if "get_schema tracks" not in all_content:
                return LLMResponse("TOOL: get_schema tracks", input_tokens, 6)
            return LLMResponse("FINAL: SELECT COUNT(*) FROM tracks WHERE Milliseconds > 300000", input_tokens, 15)

        if "genres have the most tracks" in all_content or "genres" in all_content and "tracks" in all_content:
            if "get_schema genres" not in all_content:
                return LLMResponse("TOOL: get_schema genres", input_tokens, 6)
            return LLMResponse(
                "FINAL: SELECT g.Name, COUNT(t.TrackId) AS n FROM genres g JOIN tracks t ON t.GenreId = g.GenreId GROUP BY g.Name ORDER BY n DESC LIMIT 5",
                input_tokens,
                25,
            )

        if "germany" in all_content or "invoice" in all_content:
            if "get_schema invoices" not in all_content:
                return LLMResponse("TOOL: get_schema invoices", input_tokens, 6)
            return LLMResponse(
                "FINAL: SELECT SUM(i.Total) FROM invoices i JOIN customers c ON c.CustomerId = i.CustomerId WHERE c.Country = 'Germany'",
                input_tokens,
                20,
            )

        # Generic fallback
        if "list_tables" not in all_content:
            return LLMResponse("TOOL: list_tables", input_tokens, 5)
        return LLMResponse("FINAL: SELECT 1", input_tokens, 5)

    return mock_llm


def make_openai_llm(api_key: str, model: str, base_url: str) -> Callable[[list[dict]], LLMResponse]:
    """Client for OpenAI and any OpenAI-compatible API (Groq, vLLM, Ollama, etc.)."""
    client = httpx.Client(
        base_url=base_url.rstrip("/"),
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=60.0,
    )

    def llm(messages: list[dict]) -> LLMResponse:
        url = "/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.0,
        }
        try:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            return LLMResponse(content, prompt_tokens, completion_tokens)
        except Exception as exc:
            logger.error("LLM call failed: %s", exc)
            raise

    return llm


def make_llm() -> Callable[[list[dict]], Any]:
    """Return a callable that takes a message list and returns reply text or LLMResponse."""
    api_key = settings.openai_api_key or os.environ.get("OPENAI_API_KEY")

    if settings.mock_mode or os.environ.get("QP_MOCK", "").lower() in ("1", "true"):
        return make_mock_llm()

    if api_key:
        return make_openai_llm(
            api_key=api_key,
            model=settings.model,
            base_url=settings.openai_api_base,
        )

    # If no API key configured, fall back to mock mode with warning rather than crashing
    logger.warning("No OPENAI_API_KEY found; falling back to offline mock model. Set OPENAI_API_KEY to use a live model.")
    return make_mock_llm()


def make_agent(llm: Callable[[list[dict]], Any] | None = None) -> Callable[[str, Path], AgentState]:
    """Builds and returns the agent runner."""
    model_callable = llm or make_llm()
    graph = build_graph(model_callable)

    def run(question: str, db_path: Path) -> AgentState:
        res = graph.invoke(AgentState(question=question, db_path=db_path))
        if isinstance(res, dict):
            return AgentState(
                question=res.get("question", question),
                db_path=res.get("db_path", db_path),
                messages=res.get("messages", []),
                trace=res.get("trace", []),
                sql=res.get("sql"),
                repairs=res.get("repairs", 0),
                tool_calls=res.get("tool_calls", 0),
                input_tokens=res.get("input_tokens", 0),
                output_tokens=res.get("output_tokens", 0),
            )
        return res

    return run

