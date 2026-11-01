"""Recalibrate the evidence-gap cost guard from the frozen WP-D traces.

Read-only: never writes to the frozen artifacts. Replays the guard's own
predicate over every saved trace so the default threshold is derived from
measurements instead of intuition.

The guard asks one question each round: did any candidate gain a *cause-specific
discriminator*? Replaying that faithfully means folding hypothesis updates from
``DECISION`` and ``MERGE`` events in order, then applying the same predicate
``graph.InvestigationRun.discriminator_candidates`` uses.

Usage (from the repository root):

    .venv/Scripts/python.exe analysis/wp_d/reports/evidence-gap-calibration-20261101/recalibrate.py
"""

import json
import sys
from pathlib import Path

BATCH = Path("results/v16/wp-d/full40-local-gateway-c4-20261031")
ALIASES = {"dynamic_no_verifier": "dynamic", "no_verifier": "dynamic"}
UNIDENTIFIABLE = {"incident_3003", "incident_3008"}


def canonical(name):
    return ALIASES.get(name, name)


def hypothesis(row):
    from incident_lens.schemas import Hypothesis

    return Hypothesis.model_validate(row)


def apply(hypotheses, updates):
    """Fold coordinator updates into the current board, matching ``coordinate``."""
    by_id = {h.hypothesis_id: h for h in map(hypothesis, hypotheses)}
    for row in updates or []:
        candidate = hypothesis(row)
        by_id[candidate.hypothesis_id] = candidate
    return [by_id[key] for key in sorted(by_id)]


def discriminator_candidates(state):
    """The guard's predicate, over the frozen ``evidence_index`` payloads."""
    from incident_lens.orchestration.guards import cause_discriminator
    from incident_lens.schemas import EvidenceRecord

    index = {
        key: EvidenceRecord.model_validate_json(json.dumps(row))
        for key, row in state.get("evidence_index", {}).items()
    }
    found = []
    for h in state.get("hypotheses", []):
        if any(
            cause_discriminator(h, index[eid])
            for eid in h.support_ids
            if eid in index
        ):
            found.append(h.hypothesis_id)
    return found


def replay(trace):
    """Return the per-decision gap streak and where a discriminator first appears.

    The trace only stores the *final* board, so the replay must rebuild it from
    ``MERGE`` events alone. Starting from the saved state would credit every
    round with evidence that only arrived later.
    """
    saved = trace["state"]
    observed = {}
    state = {"hypotheses": [], "evidence_index": {}}
    streak = 0
    rows = []
    tokens = 0
    llm_calls = 0
    for event in saved["events"]:
        kind = event["event_type"]
        details = event.get("details") or {}
        if kind == "LLM_CALL":
            tokens += details.get("total_tokens") or 0
            llm_calls += details.get("llm_calls") or 0
            continue
        # Evidence is first *observed* by a successful tool call, then *published*
        # only for the IDs a finding or hypothesis cites (``merge_results``).
        # Rebuilding from MERGE findings alone misses every uncited record, which
        # is why an earlier replay wrongly saw no discriminator on a RESOLVED case.
        if kind == "TOOL_CALL":
            for row in (details.get("result") or {}).get("records") or []:
                if isinstance(row, dict) and row.get("evidence_id"):
                    observed[row["evidence_id"]] = row
            continue
        if kind == "MERGE":
            state = {**state, "hypotheses": apply(state["hypotheses"], details.get("hypotheses"))}
            cited = set()
            for row in details.get("findings") or []:
                cited.update(row.get("evidence_ids") or [])
            for h in state["hypotheses"]:
                cited.update(h.support_ids + h.against_ids)
            state = {
                **state,
                "evidence_index": {
                    **state["evidence_index"],
                    **{eid: observed[eid] for eid in cited if eid in observed},
                },
            }
            continue
        if kind != "DECISION":
            continue
        decision = details.get("decision") or {}
        state = {
            **state,
            "hypotheses": apply(state.get("hypotheses", []), decision.get("hypothesis_updates")),
        }
        action = decision.get("action")
        if action != "INVESTIGATE":
            rows.append({"action": action, "streak": streak, "decisive": True,
                         "tokens": tokens, "llm_calls": llm_calls})
            continue
        decisive = bool(discriminator_candidates(state))
        streak = 0 if decisive else streak + 1
        rows.append({"action": action, "streak": streak, "decisive": decisive,
                     "tokens": tokens, "llm_calls": llm_calls})
    # Self-check: the replay must end on the board the trace actually saved.
    assert set(state["evidence_index"]) == set(saved["evidence_index"]), (
        f"{saved['incident_id']}: replay did not reconstruct the evidence board"
    )
    return rows, {"tokens": tokens, "llm_calls": llm_calls}


def first_firing(rows, threshold):
    """Index of the first INVESTIGATE decision at which the guard would stop."""
    for position, row in enumerate(rows):
        if row["action"] == "INVESTIGATE" and row["streak"] >= threshold:
            return position
    return None


def projected(rows, totals, threshold):
    """Tokens and calls the run would have spent had the guard fired.

    A stop at decision ``i`` means the run never dispatches that round's tasks
    nor asks the coordinator for another decision, so the cost is everything
    spent up to and including decision ``i``.
    """
    stop = first_firing(rows, threshold)
    if stop is None:
        return totals["tokens"], totals["llm_calls"]
    return rows[stop]["tokens"], rows[stop]["llm_calls"]


def main():
    traces = sorted(BATCH.glob("runs/slot-*/attempt-*/trace.json"))
    if not traces:
        sys.exit(f"no traces under {BATCH}")

    cases = {}
    for path in traces:
        trace = json.loads(path.read_text(encoding="utf-8"))
        variant = canonical(trace["variant"])
        incident = trace["state"]["incident_id"]
        rows, totals = replay(trace)
        cases.setdefault((incident, variant), []).append((path, rows, totals))

    print(f"source: {BATCH} (read-only), {len(traces)} traces\n")
    print("Dynamic group: longest run of investigator rounds without a discriminator")
    print("| case | decisions | max streak | first discriminator | outcome |")
    print("| --- | ---: | ---: | ---: | --- |")

    dynamic = []
    for (incident, variant), entries in sorted(cases.items()):
        if variant != "dynamic":
            continue
        for path, rows, totals in entries:
            first = next(
                (i for i, r in enumerate(rows) if r["action"] == "INVESTIGATE" and r["decisive"]),
                None,
            )
            peak = max((r["streak"] for r in rows if r["action"] == "INVESTIGATE"), default=0)
            report = json.loads(path.read_text(encoding="utf-8"))["state"]["report"]
            outcome = report.get("status")
            dynamic.append(
                {
                    "incident": incident,
                    "rows": rows,
                    "peak": peak,
                    "first": first,
                    "outcome": outcome,
                    "totals": totals,
                    "path": path,
                }
            )
            print(
                f"| {incident} | {len(rows)} | {peak} | "
                f"{'-' if first is None else first} | {outcome} |"
            )

    print("\nThreshold sweep over the dynamic group (identifiable cases must never fire):")
    print("| threshold | fires on | identifiable false positives |")
    print("| --- | ---: | --- |")
    for threshold in range(1, 9):
        hits = [r["incident"] for r in dynamic if first_firing(r["rows"], threshold) is not None]
        wrong = [h for h in hits if h not in UNIDENTIFIABLE]
        print(f"| {threshold} | {', '.join(sorted(hits)) or 'none'} | {', '.join(sorted(wrong)) or 'none'} |")

    print("\nCost at each threshold (dynamic group; only false-positive-free rows matter):")
    print("| threshold | per-case token change | batch total | batch change |")
    print("| --- | --- | ---: | ---: |")
    base_total = sum(r["totals"]["tokens"] for r in dynamic)
    for threshold in range(3, 9):
        wrong = [
            r["incident"]
            for r in dynamic
            if first_firing(r["rows"], threshold) is not None
            and r["incident"] not in UNIDENTIFIABLE
        ]
        projected_total = sum(projected(r["rows"], r["totals"], threshold)[0] for r in dynamic)
        changes = []
        for r in dynamic:
            if r["incident"] in UNIDENTIFIABLE:
                before = r["totals"]["tokens"]
                after = projected(r["rows"], r["totals"], threshold)[0]
                changes.append(f"{r['incident']} {before:,.0f}->{after:,.0f} ({(after-before)/before*100:+.1f}%)")
        flag = " **FP**" if wrong else ""
        print(
            f"| {threshold}{flag} | {'; '.join(changes)} | {projected_total:,.0f} "
            f"| {(projected_total-base_total)/base_total*100:+.1f}% |"
        )

    print("\nThe same sweep over every variant, to prove the guard is variant-agnostic")
    print("(``fixed`` is excluded in the runtime, so only single/dynamic/full count):")
    for variant in ("single", "dynamic", "full"):
        peaks = sorted(
            (
                incident,
                max(
                    (r["streak"] for r in rows if r["action"] == "INVESTIGATE"),
                    default=0,
                ),
            )
            for (incident, name), entries in cases.items()
            if name == variant
            for _, rows, _totals in entries
        )
        safe = max((peak for incident, peak in peaks if incident not in UNIDENTIFIABLE), default=0)
        print(f"  {variant}: largest non-unidentifiable peak = {safe}")


if __name__ == "__main__":
    main()
