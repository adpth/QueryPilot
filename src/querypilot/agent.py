"""The agent loop: explore schema, write SQL, run it, read the error, repair.

State carries the trace so the eval harness can count tool calls and repairs
without instrumenting the model separately.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

from querypilot.config import settings
from querypilot import tools

SYSTEM_PROMPT = """You answer questions about a SQL database.

Work in steps. Available tools:
  list_tables()                -> table names
  get_schema(table)            -> CREATE TABLE statement
  sample_rows(table, n)        -> a few rows, to check value formats
  explain_query(sql)           -> query plan
  run_sql(sql)                 -> executes a read-only SELECT

Inspect the schema before writing SQL. Guessing column names wastes a turn.
If run_sql returns an error, read it and fix the query rather than restarting.

Reply with exactly one line, either:
  TOOL: <tool_name> <argument>
  FINAL: <sql>
"""


@dataclass
class AgentState:
    question: str
    db_path: Path
    messages: list[dict] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)
    sql: str | None = None
    repairs: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


def parse_action(text: str) -> tuple[Literal["tool", "final"], str, str]:
    """Parses model reply into (kind, name, argument)."""
    clean = text.strip()
    if not clean:
        return "final", "", ""

    # Strip thinking blocks if present (e.g. <think>...</think>)
    clean = re.sub(r"<think>[\s\S]*?</think>", "", clean).strip()

    lines = clean.splitlines()

    # Search for FINAL: or TOOL: in the output
    for i, line in enumerate(lines):
        line_s = line.strip()
        if line_s.upper().startswith("FINAL:"):
            first_part = line_s[6:].strip()
            rest_parts = [l.strip() for l in lines[i + 1:] if l.strip()]
            full_sql = " ".join([first_part] + rest_parts).strip()
            # Strip markdown code fences if model wrapped SQL
            full_sql = re.sub(r"^```(?:sql)?\s*", "", full_sql, flags=re.IGNORECASE)
            full_sql = re.sub(r"\s*```$", "", full_sql)
            return "final", "", full_sql.strip()

        if line_s.upper().startswith("TOOL:"):
            rest = line_s[5:].strip()
            name, _, arg = rest.partition(" ")
            return "tool", name.strip(), arg.strip()

    # Fallback to the first line
    first = lines[0].strip()
    if first.upper().startswith("FINAL:"):
        return "final", "", first[6:].strip()
    if first.upper().startswith("TOOL:"):
        rest = first[5:].strip()
        name, _, arg = rest.partition(" ")
        return "tool", name.strip(), arg.strip()

    # Treat unparseable reply as a final answer so the loop always terminates
    return "final", "", first


def call_tool(name: str, arg: str, db_path: Path) -> tuple[str, bool]:
    try:
        if name == "list_tables":
            return tools.list_tables(db_path), True
        if name == "get_schema":
            obs = tools.get_schema(db_path, arg)
            return obs, not obs.startswith("ERROR:")
        if name == "sample_rows":
            obs = tools.sample_rows(db_path, arg)
            return obs, not obs.startswith("ERROR:")
        if name == "explain_query":
            obs = tools.explain_query(db_path, arg)
            return obs, not obs.startswith("ERROR:")
        if name == "run_sql":
            return tools.run_sql(db_path, arg)
        return "unknown tool: " + name, False
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}: {exc}", False


def build_graph(llm: Callable[[list[dict]], Any]) -> Any:
    """llm takes the message list and returns the model's reply text or LLMResponse.

    Passed in rather than constructed here so evals can run against a stub.
    """
    from langgraph.graph import END, StateGraph

    def think(state: AgentState) -> AgentState:
        if not state.messages:
            state.messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": state.question},
            ]
        reply = llm(state.messages)

        # Token accounting if supported by reply object
        if hasattr(reply, "input_tokens"):
            state.input_tokens += getattr(reply, "input_tokens", 0)
        if hasattr(reply, "output_tokens"):
            state.output_tokens += getattr(reply, "output_tokens", 0)

        content = str(reply)
        state.messages.append({"role": "assistant", "content": content})
        return state

    def act(state: AgentState) -> AgentState:
        kind, name, arg = parse_action(state.messages[-1]["content"])
        if kind == "final":
            state.sql = arg
            return state
        observation, ok = call_tool(name, arg, state.db_path)
        state.tool_calls += 1
        if name == "run_sql":
            if ok:
                state.sql = arg
            else:
                state.repairs += 1
        state.trace.append({"tool": name, "arg": arg, "ok": ok, "observation": observation})
        state.messages.append({"role": "user", "content": observation})
        return state

    def next_step(state: AgentState) -> str:
        if state.sql is not None:
            return END
        if state.repairs >= settings.max_repairs:
            return END
        if state.tool_calls >= settings.max_steps:
            return END
        return "think"

    graph = StateGraph(AgentState)
    graph.add_node("think", think)
    graph.add_node("act", act)
    graph.set_entry_point("think")
    graph.add_edge("think", "act")
    graph.add_conditional_edges("act", next_step, {"think": "think", END: END})
    return graph.compile()

