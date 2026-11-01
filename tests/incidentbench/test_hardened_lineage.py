"""The hardened lineage must raise discriminative difficulty without breaking contracts.

These tests pin the properties the difficulty levers rely on, so a future edit
cannot quietly soften them back into the frozen v1 encodings:

* every hardened case still satisfies the public observation contract and the
  full causal audit;
* boundary cases sit *on* the mechanism contract rather than comfortably beyond
  it, while still carrying a genuine cause-specific discriminator;
* competing cases expose a rival symptom that is never itself a discriminator;
* the frozen v1 lineage cannot silently acquire levers.
"""

from types import SimpleNamespace

import pytest

from incident_lens.incidentbench.builder import build_dataset
from incident_lens.incidentbench.scenarios.hardened import (
    DIFFICULTIES,
    MECHANISM_SERVICE,
    RIVALS,
)
from incident_lens.incidentbench.schemas import BenchmarkOracle, SUPPORTED_MODES
from incident_lens.incidentbench.validator import validate_dataset
from incident_lens.llm.mock import MockProvider, classify
from incident_lens.orchestration.graph import run_investigation
from incident_lens.orchestration.guards import cause_discriminator
from incident_lens.tools.provider import EvidenceProvider

SOURCES = ("logs", "metrics", "changes", "configs", "database")


def hardened_config(lever="boundary", mechanisms=None):
    mechanisms = mechanisms or sorted(SUPPORTED_MODES)
    families = []
    for index, mechanism in enumerate(mechanisms):
        variants = [
            dict(id=f"v_{index}_ordinary", kind="ordinary", difficulty=lever),
            dict(id=f"v_{index}_missing", kind="missing", difficulty=lever),
            dict(id=f"v_{index}_misleading", kind="misleading", difficulty=lever),
        ]
        families.append(
            dict(
                id=f"fam_{index:03d}",
                source_blueprint_id=f"bp_{index:03d}",
                near_duplicate_cluster_id=f"cluster_{index:03d}",
                split="dev",
                started_at=f"2026-11-{index + 1:02}T09:00:00+00:00",
                mechanism=mechanism,
                demand=155 + index * 7,
                capacity=100,
                trigger_seconds=21 + index * 11,
                propagation_seconds=7 + index * 3,
                variants=variants,
            )
        )
    return dict(encoder_lineage="causal-world-v2-hardened", families=families)


def records_of(provider, incident_id):
    return [
        record
        for source in SOURCES
        for record in provider._records(incident_id, source)
    ]


def oracles_of(root):
    return {
        path.parent.parent.name: BenchmarkOracle.model_validate_json(path.read_text())
        for path in sorted(root.rglob("benchmark_oracle.json"))
    }


@pytest.mark.parametrize("lever", DIFFICULTIES)
def test_hardened_arms_validate_and_stay_pending(tmp_path, lever):
    public, oracle = tmp_path / lever / "public", tmp_path / lever / "oracle"
    coverage = build_dataset(hardened_config(lever), public, oracle)
    result = validate_dataset(public, oracle)
    assert result["ok"], result["errors"]
    assert coverage["encoder_lineage"] == "causal-world-v2-hardened"
    assert coverage["accepted_labels"] == coverage["independent_audited_families"] == 0
    assert coverage["blindness_level"] == "development_visible"
    assert coverage["difficulty_levers"][lever] == len(SUPPORTED_MODES) * 3
    for label in oracles_of(oracle).values():
        assert label.annotator_status == "pending" and not label.reviewer_ids


@pytest.mark.parametrize("lever", ["boundary", "competing"])
def test_hardened_identifiable_cases_keep_a_real_discriminator(tmp_path, lever):
    public, oracle = tmp_path / lever / "public", tmp_path / lever / "oracle"
    build_dataset(hardened_config(lever), public, oracle)
    provider = EvidenceProvider(public / "rca")
    for incident_id, label in oracles_of(oracle).items():
        if not label.is_identifiable:
            continue
        index = {r.evidence_id: r for r in records_of(provider, incident_id)}
        hypothesis = SimpleNamespace(**label.true_primary_root.model_dump())
        supporting = label.acceptable_support_sets[0].evidence_ids
        assert len({index[e].source_type for e in supporting}) >= 2
        assert any(cause_discriminator(hypothesis, index[e]) for e in supporting)
        assert any(classify(index[e].model_dump(mode="json")) for e in supporting)


@pytest.mark.parametrize(
    "mechanism, expected",
    [
        # Boundary cases sit on the contract, not comfortably beyond it.
        ("backend_resource_saturation", 91),
        ("postgres_lock_contention", 1001),
        ("postgres_slow_query", 3001),
        ("payment_external_timeout", 3000),
    ],
)
def test_boundary_measurements_sit_on_the_contract(tmp_path, mechanism, expected):
    public, oracle = tmp_path / "public", tmp_path / "oracle"
    build_dataset(hardened_config("boundary", [mechanism]), public, oracle)
    provider = EvidenceProvider(public / "rca")
    label = next(iter(oracles_of(oracle).values()))
    support = label.acceptable_support_sets[0].evidence_ids
    index = {r.evidence_id: r for r in records_of(provider, label.incident_id)}
    values = [
        index[e].metadata.get("value", index[e].metadata.get("duration_ms")) for e in support
    ]
    assert expected in values


def test_boundary_pool_reduction_is_only_one_slot(tmp_path):
    public, oracle = tmp_path / "public", tmp_path / "oracle"
    build_dataset(
        hardened_config("boundary", ["backend_pool_config_regression"]), public, oracle
    )
    provider = EvidenceProvider(public / "rca")
    label = next(iter(oracles_of(oracle).values()))
    index = {r.evidence_id: r for r in records_of(provider, label.incident_id)}
    config = next(
        index[e] for e in label.acceptable_support_sets[0].evidence_ids
        if index[e].source_type == "configs"
    )
    # The contract needs *a* reduction below concurrency; magnitude reasoning
    # ("a real outage needs a dramatic cut") must fail here.
    assert "20 -> 18" in config.excerpt
    assert int(config.excerpt.split("concurrency=")[1]) > 18


def test_competing_rivals_are_visible_but_never_confirmable(tmp_path):
    public, oracle = tmp_path / "public", tmp_path / "oracle"
    build_dataset(hardened_config("competing"), public, oracle)
    provider = EvidenceProvider(public / "rca")
    labels = oracles_of(oracle)
    seen_rivals = 0
    for incident_id, label in labels.items():
        if not label.is_identifiable or label.misleading_evidence_ids:
            continue
        rival = RIVALS[label.true_primary_root.failure_mode]
        rival_service = MECHANISM_SERVICE[rival]
        rival_hypothesis = SimpleNamespace(
            culprit_service=rival_service, failure_mode=rival
        )
        rival_records = [
            r for r in records_of(provider, incident_id) if r.service == rival_service
        ]
        rival_hits = [r for r in rival_records if cause_discriminator(rival_hypothesis, r)]
        if rival_service != label.true_primary_root.culprit_service:
            assert rival_records, "competing arm must expose the rival"
            seen_rivals += 1
        # A rival symptom never satisfies the rival's own acceptance contract.
        assert not rival_hits, f"{incident_id}: rival became confirmable"
    assert seen_rivals >= 2


def test_competing_misleading_change_lands_on_the_culprit_service(tmp_path):
    public, oracle = tmp_path / "public", tmp_path / "oracle"
    build_dataset(
        hardened_config("competing", ["backend_pool_config_regression"]), public, oracle
    )
    provider = EvidenceProvider(public / "rca")
    labels = oracles_of(oracle)
    misleading = [label for label in labels.values() if label.misleading_evidence_ids]
    assert misleading
    for label in misleading:
        index = {r.evidence_id: r for r in records_of(provider, label.incident_id)}
        distractors = [index[e] for e in label.misleading_evidence_ids]
        assert all(r.service == label.true_primary_root.culprit_service for r in distractors)
        assert all(r.source_type == "changes" for r in distractors)


def test_v1_lineage_refuses_a_difficulty_lever(tmp_path):
    config = hardened_config("boundary", ["redis_unavailable"])
    config["encoder_lineage"] = "causal-world-v1"
    with pytest.raises(ValueError, match="no difficulty levers"):
        build_dataset(config, tmp_path / "public", tmp_path / "oracle")
    assert not (tmp_path / "public").exists()


def test_unknown_lineage_is_rejected_before_writing(tmp_path):
    config = hardened_config("boundary", ["redis_unavailable"])
    config["encoder_lineage"] = "causal-world-v3"
    with pytest.raises(ValueError, match="encoder lineage"):
        build_dataset(config, tmp_path / "public", tmp_path / "oracle")
    assert not (tmp_path / "public").exists()


@pytest.mark.asyncio
async def test_hardened_boundary_case_still_resolves_and_missing_abstains(tmp_path):
    public, oracle = tmp_path / "public", tmp_path / "oracle"
    build_dataset(hardened_config("boundary", ["backend_resource_saturation"]), public, oracle)
    labels = oracles_of(oracle)
    ordinary = next(
        label.incident_id
        for label in labels.values()
        if label.is_identifiable and not label.misleading_evidence_ids
    )
    missing = next(label.incident_id for label in labels.values() if not label.is_identifiable)
    complete = await run_investigation(
        ordinary, MockProvider(), data_root=public / "rca", cache=None
    )
    assert complete.report.status == "RESOLVED"
    assert complete.report.root_cause.failure_mode == "backend_resource_saturation"
    abstained = await run_investigation(
        missing, MockProvider(), data_root=public / "rca", cache=None
    )
    assert abstained.report.status == "INCONCLUSIVE"
