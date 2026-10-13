"""Repeat-averaged case contrasts with paired family-cluster bootstrap."""

import math
import random
from collections import defaultdict
from statistics import mean


def effective_clusters(rows):
    """Union declared families linked by a common blueprint or duplicate source."""
    parents = {}

    def find(key):
        parents.setdefault(key, key)
        if parents[key] != key:
            parents[key] = find(parents[key])
        return parents[key]

    cases = {}
    for row in rows:
        keys = [
            (field, row[field])
            for field in (
                "scenario_family_id",
                "source_blueprint_id",
                "near_duplicate_cluster_id",
                "counterfactual_pair_id",
            )
            if row.get(field)
        ]
        if not keys:
            raise ValueError("statistical source group missing")
        for key in keys[1:]:
            left, right = find(keys[0]), find(key)
            parents[max(left, right)] = min(left, right)
        cases[row["incident_id"]] = keys[0]
    return {case: ":".join(find(key)) for case, key in cases.items()}


def paired_comparison(rows, baseline, metric="root_cause_correct", *, seed=14101, samples=10000):
    if samples < 1:
        raise ValueError("bootstrap samples must be positive")
    cells = defaultdict(dict)
    grouping = effective_clusters(rows)
    for row in rows:
        if row.get("cohort", "core") != "core" or row["variant"] not in {"full", baseline}:
            continue
        if row.get(metric) is None:
            continue
        key = (grouping[row["incident_id"]], row["incident_id"])
        cell = cells[key].setdefault(row["variant"], {})
        repeat = row.get("repeat_id", 0)
        if repeat in cell:
            raise ValueError("duplicate case/variant/repeat")
        cell[repeat] = float(row[metric])
    if not cells:
        return {"baseline": baseline, "metric": metric, "status": "no_scored_pairs", "paired_n": 0}
    families = defaultdict(list)
    discordant_plus = discordant_minus = 0
    repeats = []
    for (family, case), pair in cells.items():
        if set(pair) != {"full", baseline} or set(pair["full"]) != set(pair[baseline]):
            raise ValueError(f"missing paired variant/repeat for {case}")
        full, control = mean(pair["full"].values()), mean(pair[baseline].values())
        families[family].append(full - control)
        repeats.append(len(pair["full"]))
        if len(pair["full"]) == 1 and full in (0, 1) and control in (0, 1):
            discordant_plus += full > control
            discordant_minus += full < control
    clusters = list(families.values())
    rng = random.Random(seed)
    draws = []
    for _ in range(samples):
        chosen = [rng.choice(clusters) for _ in clusters]
        draws.append(mean(value for cluster in chosen for value in cluster))
    draws.sort()
    discordance_n = discordant_plus + discordant_minus
    exact = (
        min(
            1.0,
            2
            * sum(
                math.comb(discordance_n, k)
                for k in range(min(discordant_plus, discordant_minus) + 1)
            )
            / 2**discordance_n,
        )
        if discordance_n
        else 1.0
    )
    return {
        "baseline": baseline,
        "metric": metric,
        "status": "insufficient_clusters"
        if len(clusters) < 2
        else "exploratory"
        if len(clusters) < 20
        else "estimated",
        "paired_n": len(cells),
        "family_n": len(clusters),
        "effective_source_clusters": len(clusters),
        "declared_family_n": len({r["scenario_family_id"] for r in rows}),
        "independence_status": "unreviewed"
        if any(r.get("independence_status") == "unreviewed" for r in rows)
        else "not_established",
        "repeat_counts": repeats,
        "difference": mean(v for c in clusters for v in c),
        "ci95": [draws[int((samples - 1) * 0.025)], draws[int((samples - 1) * 0.975)]]
        if len(clusters) >= 2
        else None,
        "family_differences": {k: mean(v) for k, v in families.items()},
        "exact_discordance_p": exact
        if len(clusters) >= 2 and all(n == 1 for n in repeats)
        else None,
        "exact_discordance_note": "supplementary; assumes independent cases, unlike primary family bootstrap",
        "small_family_warning": len(clusters) < 20,
        "seed": seed,
        "bootstrap_samples": samples,
    }


def analyze(rows, *, seed=14101, samples=10000):
    return [
        paired_comparison(rows, variant, seed=seed, samples=samples)
        for variant in (
            "strong_single_equivalent_tools",
            "fixed_four_equivalent_tools",
            "dynamic_no_verifier",
        )
    ]
