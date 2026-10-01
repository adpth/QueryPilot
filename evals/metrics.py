"""Metrics. Every number the README claims is computed here.

Execution accuracy is the headline: does the agent's SQL return the same rows
as the reference SQL? Comparing result sets rather than query text means a
differently-written but correct query still counts as correct.
"""

from dataclasses import dataclass
from statistics import median
from typing import Any


def normalise_cell(val: Any, precision: int = 4) -> Any:
    """Normalizes cell values: handles numeric equivalence, float drift, and None."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return round(float(val), precision)
    if isinstance(val, str):
        val_str = val.strip()
        try:
            return round(float(val_str), precision)
        except ValueError:
            return val_str
    return str(val)


def row_sort_key(row: tuple) -> tuple:
    """Safe comparison key for rows containing None and heterogeneous types."""
    return tuple((0, "") if v is None else (1, str(v)) for v in row)


def normalise(rows: list[tuple], order_matters: bool) -> list[tuple]:
    """Normalizes result rows for execution accuracy comparison."""
    normed = [tuple(normalise_cell(v) for v in row) for row in rows]
    return normed if order_matters else sorted(normed, key=row_sort_key)


def execution_match(
    predicted: list[tuple], reference: list[tuple], order_matters: bool
) -> bool:
    return normalise(predicted, order_matters) == normalise(reference, order_matters)


@dataclass
class RunRecord:
    """One question, one attempt."""

    id: str
    correct: bool
    sql_valid: bool
    repairs: int
    repaired_to_success: bool
    tool_calls: int
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(int(p * len(ordered)), len(ordered) - 1)
    return ordered[index]


def summarise(records: list[RunRecord], cost_per_1k_in: float = 0.0,
              cost_per_1k_out: float = 0.0) -> dict:
    if not records:
        return {"n": 0}
    n = len(records)
    needed_repair = [r for r in records if r.repairs > 0]
    latencies = [r.latency_ms for r in records]
    tokens_in = sum(r.input_tokens for r in records)
    tokens_out = sum(r.output_tokens for r in records)
    return {
        "n": n,
        "execution_accuracy": round(100 * sum(r.correct for r in records) / n, 2),
        "valid_sql_rate": round(100 * sum(r.sql_valid for r in records) / n, 2),
        "self_repair_rate": round(
            100 * sum(r.repaired_to_success for r in needed_repair) / len(needed_repair), 2
        ) if needed_repair else None,
        "avg_tool_calls": round(sum(r.tool_calls for r in records) / n, 2),
        "median_tool_calls": median(r.tool_calls for r in records),
        "latency_p50_ms": round(percentile(latencies, 0.50), 1),
        "latency_p95_ms": round(percentile(latencies, 0.95), 1),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_per_query_usd": round(
            (tokens_in / 1000 * cost_per_1k_in + tokens_out / 1000 * cost_per_1k_out) / n, 6
        ),
    }
