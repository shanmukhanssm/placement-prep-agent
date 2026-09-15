"""Deterministic eval graders — every deciding check is code, never an LLM.

Per eval-plan.md: "Graders are deterministic code wherever a right answer is
knowable (Layers 1, 2, 4, and every Layer-5 property). The LLM appears only as
the judge *under test* in Layer 3 — never as the grader that decides a gate."
"""
