"""Runs the golden set, writes a report, and enforces the CI regression gate.

Exit code 1 when execution accuracy falls more than QP_ACCURACY_TOLERANCE points
below the baseline. That is what blocks the merge.
"""

import argparse
import json
import time
from pathlib import Path

from evals import dataset, metrics
from querypilot.config import settings
from querypilot.db import run_query


def reference_rows(db_path: Path, sql: str) -> list[tuple]:
    return run_query(db_path, sql, settings.sql_timeout_s, settings.max_rows).rows


def evaluate_one(example: dataset.Example, db_path: Path, agent) -> metrics.RunRecord:
    start = time.perf_counter()
    state = agent(example.question, db_path)
    latency_ms = (time.perf_counter() - start) * 1000

    correct = False
    sql_valid = False
    if state.sql:
        try:
            predicted = reference_rows(db_path, state.sql)
            sql_valid = True
            expected = reference_rows(db_path, example.reference_sql)
            correct = metrics.execution_match(predicted, expected, example.order_matters)
        except Exception:
            sql_valid = False

    return metrics.RunRecord(
        id=example.id,
        correct=correct,
        sql_valid=sql_valid,
        repairs=state.repairs,
        repaired_to_success=state.repairs > 0 and correct,
        tool_calls=state.tool_calls,
        latency_ms=latency_ms,
        input_tokens=getattr(state, "input_tokens", 0),
        output_tokens=getattr(state, "output_tokens", 0),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, help="previous report, for the CI gate")
    parser.add_argument("--label", default="default", help="ablation name")
    parser.add_argument("--mock", action="store_true", help="force offline mock LLM")
    args = parser.parse_args()

    if args.mock:
        settings.mock_mode = True

    from querypilot.runtime import make_agent  # supplied by runtime

    agent = make_agent()
    if not args.dataset.exists():
        print(f"ERROR: Dataset not found: {args.dataset}")
        return 1

    examples = dataset.load(args.dataset)
    records = []
    for ex in examples:
        db_path = Path(settings.db_dir) / (ex.database + ".sqlite")
        if not db_path.exists():
            print(f"WARNING: Benchmark database not found: {db_path}. Run 'make benchmarks' first.")
        records.append(evaluate_one(ex, db_path, agent))

    summary = metrics.summarise(
        records,
        cost_per_1k_in=settings.cost_per_1k_in,
        cost_per_1k_out=settings.cost_per_1k_out,
    )
    summary["label"] = args.label
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(
        {"summary": summary, "records": [r.__dict__ for r in records]}, indent=2
    ))
    print(json.dumps(summary, indent=2))

    if args.baseline and args.baseline.exists():
        previous = json.loads(args.baseline.read_text())["summary"]["execution_accuracy"]
        drop = previous - summary["execution_accuracy"]
        if drop > settings.accuracy_tolerance:
            print("GATE FAILED: accuracy dropped " + str(round(drop, 2)) + " points")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
