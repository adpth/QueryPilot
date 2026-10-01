PYTHON ?= $(shell if [ -f .venv/bin/python ]; then echo .venv/bin/python; elif command -v python3 >/dev/null 2>&1; then echo python3; else echo python; fi)

.PHONY: install test eval eval-mock benchmarks api lint

install:
	pip install -e ".[dev]"

benchmarks:
	$(PYTHON) scripts/setup_benchmarks.py

test:
	$(PYTHON) -m pytest -v

eval: benchmarks
	$(PYTHON) -m evals.runner --dataset evals/data/sample.jsonl --out reports/latest.json

eval-mock: benchmarks
	$(PYTHON) -m evals.runner --dataset evals/data/sample.jsonl --out reports/latest.json --mock

api:
	$(PYTHON) -m uvicorn querypilot.api:app --reload

