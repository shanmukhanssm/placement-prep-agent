"""evals.run — the eval-plan.md runner: `python -m evals.run --layer <layers>`.

`--layer` takes one layer (1-5), a comma-separated list (e.g. `1,2` — one run,
one results table, one exit code), or `all` for the full suite.

Prints a results table and saves it (JSON + markdown) under `evals/results/`.
Exit code 0 = every requested layer green; 1 = a red/invalid gate (STOP the
pipeline — eval-plan red rule). Layer 5 always runs each golden case ×3.

A borderline L2/L3 result (within one case of the threshold) triggers exactly ONE
layer rerun per the flakiness policy; the second result stands either way.
"""

from __future__ import annotations

import argparse
import sys

LAYER_CHOICES = ("1", "2", "3", "4", "5")


def _parse_layers(parser: argparse.ArgumentParser, value: str) -> list[int]:
    """`--layer` value → ordered layer numbers; `all` = 1-5.

    Per-token validation: every comma-separated token must be 1-5; anything else
    (including duplicates) is an argparse error (exit 2).
    """
    if value == "all":
        return [1, 2, 3, 4, 5]
    layers: list[int] = []
    for token in value.split(","):
        token = token.strip()
        if token not in LAYER_CHOICES:
            parser.error(
                f"argument --layer: invalid choice: '{token}' "
                "(choose from 1-5, a comma-separated list like '1,2', or 'all')"
            )
        number = int(token)
        if number in layers:
            parser.error(f"argument --layer: duplicate layer: '{token}'")
        layers.append(number)
    return layers


def _borderline(result) -> bool:
    """eval-plan flakiness rule: within one case of the threshold → one rerun."""
    greens = sum(1 for row in result.rows if row.passed is True)
    invalids = result.provider_faults
    reds = len(result.rows) - greens - invalids
    if result.layer == 2:
        return reds == 1 and invalids == 0  # 23/24 intent
    if result.layer == 3:
        return reds == 1 and invalids == 0  # one anchor sitting on a band edge
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="evals.run",
        description="placement-prep-agent eval suite (context/eval-plan.md)",
    )
    parser.add_argument(
        "--layer",
        required=True,
        help="eval layer to run: 1-5, a comma-separated list (e.g. '1,2'), or 'all'",
    )
    args = parser.parse_args(argv)

    # .env BEFORE anything imports prep_agent.config (same contract as __main__)
    from evals.harness import load_env, save_results

    load_env()

    layer_numbers = _parse_layers(parser, args.layer)
    modules = {
        1: "evals.layer1",
        2: "evals.layer2",
        3: "evals.layer3",
        4: "evals.layer4",
        5: "evals.layer5",
    }

    results = []
    for number in layer_numbers:
        module = __import__(modules[number], fromlist=["run"])
        result = module.run()
        if result.passed is False and _borderline(result):
            # flakiness policy: exactly one rerun; the second result stands
            result.notes.append(
                "borderline result — flakiness policy triggered exactly one rerun; "
                "second result stands"
            )
            rerun = module.run()
            result.rows = rerun.rows
            result.notes.append(f"rerun outcome: {'PASS' if rerun.passed else 'RED'}")
        results.append(result)
        status = "PASS" if result.passed else "RED"
        print(f"[L{number}] {result.name}: {status} — {result.summary()}")

    from evals.harness import render_results_table

    label = f"layers {args.layer}"
    table = render_results_table(results, label)
    print()
    print(table)
    saved = save_results(results, label)
    print(f"results saved: {saved}")

    gate = "PASS" if all(result.passed for result in results) else "RED"
    print(f"Gate: {gate}")
    return 0 if gate == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
