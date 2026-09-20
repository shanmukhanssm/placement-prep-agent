# placement-prep-agent — developer commands (ponytail-minimal, no magic).
#
# Interpreter: PY defaults to python3. Either activate the venv first or override:
#   make check PY=.venv/bin/python
#
# Eval layer model (context/eval-plan.md):
#   L1    = deterministic pytest — hermetic, so `make evals` is green offline.
#   L2-L5 = live LLM layers — need LLM_API_KEY / LLM_BASE_URL / LLM_MODEL
#           (see .env.example); they only run where a key exists.
#   Select layers with EVAL_LAYERS (passed to `python -m evals.run --layer`):
#     make evals EVAL_LAYERS=2      # one live layer
#     make evals EVAL_LAYERS=1,2    # comma list — ONE run, one results table
#     make evals EVAL_LAYERS=all    # full suite (L5 golden cases run x3)

PY ?= python3

EVAL_LAYERS ?= 1

.PHONY: help lint type test evals check

help:
	@echo "lint   - ruff check ."
	@echo "type   - mypy --strict src"
	@echo "test   - pytest -q"
	@echo "evals  - eval runner: EVAL_LAYERS=1 (default, offline) | 2-5 | list | all"
	@echo "check  - lint + type + test + evals — the standing pre-push gate"

lint:
	@echo "== ruff =="
	$(PY) -m ruff check .

type:
	@echo "== mypy --strict src =="
	$(PY) -m mypy --strict src

test:
	@echo "== pytest =="
	$(PY) -m pytest -q

evals:
	@echo "== evals — layers $(EVAL_LAYERS) =="
	$(PY) -m evals.run --layer $(EVAL_LAYERS)

# Standing pre-push gate (build-plan.md H3). Each step is a separate .PHONY
# prerequisite: make runs them in order (serial) and stops at the first failure.
check: lint type test evals
