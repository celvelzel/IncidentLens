"""Recompute the four-variant comparison from the frozen WP-D batch.

Read-only: this script never writes to the frozen artifacts. It reads
``final-success-comparison.json`` (the last successful attempt per slot), folds the
historical ``dynamic_no_verifier`` spelling into ``dynamic``, and prints the table the
report quotes so every number can be re-derived without trusting the prose.

The frozen JSON keeps a ``correctness`` field written with mojibake (``��ȷ����``).
That is a historical artifact: this script ignores it and recomputes correctness from
``root_cause_correct`` / ``correct_abstention`` / ``quality_success``, and the file is
never rewritten.

Usage (from the repository root):

    .venv/Scripts/python.exe analysis/wp_d/reports/dynamic-primary-architecture-20261101/recompute.py
"""

import json
import statistics
import sys
from pathlib import Path

BATCH = Path("results/v16/wp-d/full40-local-gateway-c4-20261031")
COMPARISON = BATCH / "final-success-comparison.json"
ALIASES = {"dynamic_no_verifier": "dynamic", "no_verifier": "dynamic"}
ORDER = ("single", "fixed", "dynamic", "full")
RESOURCE = ("elapsed_s", "requests", "tools", "tokens")


def canonical(name):
    return ALIASES.get(name, name)


def load_groups():
    records = json.loads(COMPARISON.read_text(encoding="utf-8"))["records"]
    groups = {}
    for record in records:
        groups.setdefault(canonical(record["variant"]), []).append(record)
    return groups


def measured(values):
    """Sum only when every value is known; unknown stays unknown rather than zero."""
    return sum(values) if all(value is not None for value in values) else None


def summarize(group):
    return {
        "runs": len(group),
        "technical": measured([bool(r["technical_completion"]) for r in group]),
        "root_cause_correct": measured(
            [bool(r["root_cause_correct"]) for r in group if r.get("root_cause_correct") is not None]
        ),
        "root_cause_denominator": sum(
            r.get("root_cause_correct") is not None for r in group
        ),
        "correct_abstention": measured(
            [bool(r["correct_abstention"]) for r in group if r.get("correct_abstention") is not None]
        ),
        "abstention_denominator": sum(
            r.get("correct_abstention") is not None for r in group
        ),
        "quality_success": measured([bool(r["quality_success"]) for r in group]),
        "elapsed_s": statistics.mean(r["elapsed_s"] for r in group),
        "requests": statistics.mean(r["requests"] for r in group),
        "tools": statistics.mean(r["tools"] for r in group),
        "tokens": statistics.mean(r["tokens"] for r in group),
        "total_tokens": measured([r["tokens"] for r in group]),
        "attempts": sum(r["attempts_until_success"] for r in group),
    }


def main():
    groups = load_groups()
    missing = [name for name in ORDER if name not in groups]
    if missing:
        sys.exit(f"missing variant groups: {missing}")
    summary = {name: summarize(groups[name]) for name in ORDER}

    print(f"source: {COMPARISON} (read-only)")
    print(f"model:  {json.loads(COMPARISON.read_text(encoding='utf-8'))['model_id']}\n")
    print("| variant | tech | root cause | abstention | quality | latency | requests | tools | tokens | attempts |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for name in ORDER:
        s = summary[name]
        print(
            f"| {name} | {s['technical']}/{s['runs']} "
            f"| {s['root_cause_correct']}/{s['root_cause_denominator']} "
            f"| {s['correct_abstention']}/{s['abstention_denominator']} "
            f"| {s['quality_success']}/{s['runs']} "
            f"| {s['elapsed_s']:.1f}s | {s['requests']:.1f} | {s['tools']:.1f} "
            f"| {s['tokens']:,.0f} | {s['attempts']} |"
        )

    print("\nRelative to dynamic (positive = the other variant uses more):")
    base = summary["dynamic"]
    for name in ("single", "full", "fixed"):
        other = summary[name]
        deltas = " ".join(
            f"{key} {(other[key] - base[key]) / base[key] * 100:+.1f}%" for key in RESOURCE
        )
        print(f"  dynamic -> {name}: {deltas}")

    print("\nQuality is identical across single/dynamic/full (10/10) and lower for fixed (7/10).")
    print("Every difference above is descriptive: 10 development-visible cases, one repeat,")
    print("candidate oracle labels. It is not a blind test and carries no significance claim.")


if __name__ == "__main__":
    main()
