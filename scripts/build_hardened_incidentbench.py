"""Build the hardened 36-case development cohort (causal-world-v2-hardened).

The frozen ``data/incidentbench_v16_dev`` (10 cases, ``causal-world-v1``) is left
untouched. This script authors a *separate* cohort whose public observations are
harder to discriminate:

* every one of the seven supported mechanisms appears at four difficulty levers
  (standard / boundary / competing / missing);
* three confusable pairs are encoded as counterfactual twins, so the same
  service and symptom signature resolves to a different root depending only on
  the public observations;
* two misleading cases place the late noncausal change on the culprit's own
  service rather than on the gateway.

Labels remain candidate-only: ``development_visible``, zero accepted labels,
zero independent audits. The public bundle is tracked; the private oracle root
is gitignored and must never be read at runtime or quoted in docs.

Run from the repository root::

    .venv/Scripts/python.exe scripts/build_hardened_incidentbench.py
"""

import json
from pathlib import Path

from incident_lens.incidentbench.builder import build_dataset
from incident_lens.incidentbench.manifest import digest_tree

DATASET = Path("data/incidentbench_v2_hardened")
ORACLE = Path("local_oracles/incidentbench_v2_hardened")

#: Mechanisms and the four levers each family encodes.
LEVERS = (
    ("standard", dict(kind="ordinary", difficulty="standard")),
    ("boundary", dict(kind="ordinary", difficulty="boundary")),
    ("competing", dict(kind="ordinary", difficulty="competing")),
    ("missing", dict(kind="missing", difficulty="boundary")),
)

MECHANISMS = (
    "backend_pool_config_regression",
    "postgres_connection_exhaustion",
    "postgres_lock_contention",
    "postgres_slow_query",
    "redis_unavailable",
    "payment_external_timeout",
    "backend_resource_saturation",
)

#: Confusable twins: the public signature is shared, the root is not.
PAIRS = (
    ("backend_pool_config_regression", "postgres_connection_exhaustion"),
    ("postgres_lock_contention", "postgres_slow_query"),
    ("redis_unavailable", "payment_external_timeout"),
)

#: Two misleading cases; both put the noncausal change on the culprit service.
MISLEADING = ("backend_pool_config_regression", "postgres_lock_contention")


def families():
    result = []
    for index, mechanism in enumerate(MECHANISMS):
        variants = [
            dict(id=f"v2_{index}_{lever}", **spec) for lever, spec in LEVERS
        ]
        if mechanism in MISLEADING:
            variants.append(dict(id=f"v2_{index}_misleading", kind="misleading",
                                 difficulty="competing"))
        result.append(
            dict(
                id=f"fam_v2_{index:03d}",
                source_blueprint_id=f"bp_v2_{index:03d}",
                near_duplicate_cluster_id=f"cluster_v2_{index:03d}",
                split="dev",
                started_at=f"2026-11-{1 + index:02}T09:00:00+00:00",
                mechanism=mechanism,
                demand=155 + index * 7,
                capacity=100,
                trigger_seconds=21 + index * 11,
                propagation_seconds=7 + index * 3,
                variants=variants,
            )
        )
    for index, (left, right) in enumerate(PAIRS):
        variants = [
            dict(id=f"v2_pair{index}_a", kind="counterfactual",
                 pair_id=f"pair_v2_{index}", mechanism=left, difficulty="competing"),
            dict(id=f"v2_pair{index}_b", kind="counterfactual",
                 pair_id=f"pair_v2_{index}", mechanism=right, difficulty="competing"),
        ]
        result.append(
            dict(
                id=f"fam_v2_pair{index}",
                source_blueprint_id=f"bp_v2_pair{index}",
                near_duplicate_cluster_id=f"cluster_v2_pair{index}",
                split="dev",
                started_at=f"2026-11-{8 + index:02}T09:00:00+00:00",
                mechanism=left,
                demand=210 + index * 9,
                capacity=100,
                trigger_seconds=45 + index * 13,
                propagation_seconds=11 + index * 2,
                variants=variants,
            )
        )
    return result


def config():
    return dict(
        encoder_lineage="causal-world-v2-hardened",
        first_incident_number=4001,
        families=families(),
    )


def main():
    spec = config()
    expected = sum(len(family["variants"]) for family in spec["families"])
    if not 30 <= expected <= 40:
        raise SystemExit(f"cohort size {expected} outside the 30-40 target")
    coverage = build_dataset(spec, DATASET, ORACLE)
    (ORACLE / "authoring_spec.json").write_text(
        json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    summary = dict(
        coverage=coverage,
        public_sha256=digest_tree(DATASET),
        private_sha256=digest_tree(ORACLE),
        total_cases=expected,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


if __name__ == "__main__":
    main()
