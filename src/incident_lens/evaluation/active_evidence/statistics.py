"""Reuse source-clustered bootstrap, keeping missing costs out of savings."""

from incident_lens.incidentbench.statistics import paired_comparison


def analyze(rows, *, seed=15101, samples=10000):
    keys = [(r["incident_id"], r["variant"], r.get("repeat_id", 0)) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate case/variant/repeat")
    results = []
    for baseline in ("B1", "B1c", "B2", "B3", "B0"):
        for metric in (
            "root_cause_correct",
            "total_tokens",
            "actual_http_requests",
            "tool_calls",
            "latency_ms",
        ):
            pair = [
                dict(r, variant="full" if r["variant"] == "B4" else r["variant"])
                for r in rows
                if r["variant"] in {"B4", baseline}
            ]
            if not pair:
                continue
            # Missing observations drop their complete matched repeat, never become zero.
            cells = {(r["incident_id"], r.get("repeat_id", 0)): [] for r in pair}
            for r in pair:
                cells[(r["incident_id"], r.get("repeat_id", 0))].append(r)
            complete = [
                r
                for cell in cells.values()
                if len(cell) == 2 and all(x.get(metric) is not None for x in cell)
                for r in cell
            ]
            result = paired_comparison(complete, baseline, metric, seed=seed, samples=samples)
            result["missing_or_unpaired_repeat_n"] = sum(
                len(c) != 2 or any(x.get(metric) is None for x in c) for c in cells.values()
            )
            if result.get("effective_source_clusters", 0) < 2:
                result["ci95"] = None
                result["ci_reason"] = "fewer_than_two_independent_source_clusters"
            results.append(result)
    return results
