"""placement-prep-agent eval suite — Phase 4.1 (context/eval-plan.md).

Five layers, one metric per pattern:
  L1 tool & unit evals (deterministic pytest)      — `python -m evals.run --layer 1`
  L2 intent-classification evals (live router)     — `--layer 2`
  L3 judge-consistency evals (live judges)         — `--layer 3`
  L4 number-integrity evals (nodes + fixtures)     — `--layer 4`
  L5 golden end-to-end cases G1-G3, each x3        — `--layer 5`
`--layer all` runs the full suite; every run is recorded under `evals/results/`.
"""
