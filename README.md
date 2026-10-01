# QueryPilot

An agent that answers questions about a SQL database by exploring the schema, writing a query, running it, reading its own errors, and repairing. Shipped with an eval harness that measures whether the answers are actually right, and a CI gate that blocks merges when accuracy drops.

The agent is the smaller half of this repo. The eval harness is the point.

## Why the harness matters more than the agent

Most LLM applications validate structure: a schema parser catches malformed JSON and everyone moves on. That says nothing about whether the answer was correct. QueryPilot measures correctness against reference queries on a public benchmark, so the accuracy number is reproducible by someone who has never seen this repo.

## What runs right now

```bash
pip install -e ".[dev]"
make benchmarks    # Restores benchmark database (Chinook)
pytest -v          # 37 tests passing, covers agents, tools, runtime, API, and metrics
make eval          # Runs sample evaluation and produces reports/latest.json
```

Working out of the box:
- Read-only SQLite sandbox and security guardrails
- All five tools with resilient argument parsing and error feedback
- Model runtime supporting OpenAI, OpenAI-compatible endpoints, and an offline mock mode
- Token accounting and cost-per-query tracking
- Complete evaluation harness and CI regression gate
- FastAPI REST service (`GET /health`, `POST /ask`)

## Layout

```
src/querypilot/
  db.py        read-only connection, statement timeout, row cap, comment/literal stripping
  tools.py     list_tables, get_schema, sample_rows, explain_query, run_sql
  agent.py     LangGraph loop with repair path, step budget guard, and token tracking
  runtime.py   model client boundary with OpenAI and offline mock mode
  api.py       POST /ask and GET /health
evals/
  metrics.py   execution accuracy, repair rate, tool efficiency, latency, token accounting & cost
  dataset.py   golden set loader
  runner.py    runs the set, writes a report, enforces the CI gate
scripts/
  setup_benchmarks.py  downloads or populates benchmark SQLite databases
.github/workflows/
  evals.yml    GitHub Actions CI with testing, benchmark setup, and eval gate
```

## Safety model

Everything the agent generates goes through `run_query`. Nothing else opens a connection.

- Connections use SQLite's `mode=ro` URI, so a write fails at the driver even if it slips past the parser
- `assert_read_only` rejects anything that is not `SELECT`, `WITH`, or `EXPLAIN`, rejects multiple statements outside string literals, strips comments and string literals, and rejects write keywords anywhere in statement bodies while preserving scalar functions like `replace()`
- A progress handler interrupts queries past the timeout, so one runaway join cannot stall an eval run
- Results are capped and truncation is reported rather than silently dropped

Two overlapping layers, because a text check alone is guessable and a driver flag alone gives the model no feedback it can repair from.

## Metrics

| Metric | Definition |
|---|---|
| Execution accuracy | Agent's result set matches the reference query's (with numeric float tolerance) |
| Valid SQL rate | Share of runs whose final query executed at all |
| Self-repair rate | Of runs that hit an error, the share that recovered and ended correct |
| Avg / median tool calls | Efficiency. A correct answer in twelve steps is a bad answer. |
| Latency p50 / p95 | Wall clock per question |
| Cost per query | From model-reported token counts |

Result sets are compared rather than query text, so a differently written but correct query still counts as correct. Row order is enforced only when the reference query contains `ORDER BY`. Numeric values are evaluated with precision tolerance so int/float equivalence (`1` and `1.0`) and float arithmetic drift (`0.1 + 0.2` and `0.3`) compare accurately.

## Benchmark

Run `make benchmarks` to generate the default Chinook benchmark database at `benchmarks/databases/chinook.sqlite`.

The sample benchmark set is in `evals/data/sample.jsonl`, and the golden benchmark set is in `evals/data/golden.jsonl`:

```json
{"id": "…", "database": "…", "question": "…", "reference_sql": "…"}
```

## The CI gate

```bash
python -m evals.runner \
  --dataset evals/data/golden.jsonl \
  --out reports/pr.json \
  --baseline reports/baseline.json
```

Exits 1 when execution accuracy falls more than `QP_ACCURACY_TOLERANCE` points below the baseline, which fails the workflow and blocks the merge. `reports/baseline.json` is committed and updated when accepting deliberate changes.

## Quickstart Commands

```bash
make benchmarks     # Set up Chinook SQLite database
make test           # Run complete pytest test suite (37 tests)
make eval           # Run evaluation on sample set
make eval-mock      # Run evaluation forced in offline mock mode
make api            # Launch FastAPI development server on http://localhost:8000
```

