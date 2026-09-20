# Eval Results — Final Gate Evidence

Only the **final GREEN run per layer** is kept here; intermediate RED and historical
runs were pruned. Each file is the markdown report printed by `python -m evals.run --layer <n>`.

| File | Layer | Gate |
|------|-------|------|
| `eval-run-20260915-185608.md` | L1 Tool & Unit | PASS |
| `eval-run-20260915-185412.md` | L2 Intent Classification (24/24) | PASS |
| `eval-run-20260915-185544.md` | L3 Judge Consistency (12/12) | PASS |
| `eval-run-20260915-190417.md` | L4 Number Integrity (16/16) | PASS |
| `eval-run-20260915-190728.md` | L5 Golden E2E (G1-G3 × 3 runs, 9/9) | PASS |

Re-run the suite yourself: `python -m evals.run --layer all` (requires a filled `.env`).
