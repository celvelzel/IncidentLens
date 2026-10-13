"""Small disclosed development fixtures, never held-out causal blueprints."""

from types import SimpleNamespace

import pytest

from incident_lens.incidentbench.builder import build_dataset
from incident_lens.incidentbench.schemas import BenchmarkOracle
from incident_lens.llm.mock import MockProvider, classify
from incident_lens.orchestration.graph import run_investigation
from incident_lens.orchestration.guards import cause_discriminator
from incident_lens.tools.provider import ANSWER_FIELDS, EvidenceProvider


def development_config():
    mechanisms = [
        ("backend_pool_config_regression", "postgres_connection_exhaustion"),
        ("postgres_lock_contention", "postgres_slow_query"),
        ("redis_unavailable", "payment_external_timeout"),
        ("backend_resource_saturation", "payment_external_timeout"),
    ]
    families = []
    for i, (base, intervention) in enumerate(mechanisms):
        families.append(dict(id=f"fam_{i:03d}", source_blueprint_id=f"blueprint_{i:03d}",
            # All share development-only encoders. Never assert unseen-template Test.
            near_duplicate_cluster_id="cluster_development", split="seed",
            started_at="2026-10-01T12:00:00+00:00", mechanism=base,
            trigger_seconds=10 + i * 13, propagation_seconds=4 + i * 2,
            demand=120 + i * 10, capacity=100,
            variants=[dict(id=f"var_{i}_{kind}", kind=kind)
                      for kind in ("ordinary", "misleading", "missing")]
                + [dict(id=f"var_{i}_a", kind="counterfactual", pair_id=f"pair_{i}"),
                   dict(id=f"var_{i}_b", kind="counterfactual", pair_id=f"pair_{i}",
                        mechanism=intervention)]))
    return {"families": families}


def read_oracles(root):
    return [BenchmarkOracle.model_validate_json(p.read_text())
            for p in sorted(root.rglob("benchmark_oracle.json"))]


def tree_bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_deterministic_causal_generation_and_compatibility(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    a, b = tmp_path / "a", tmp_path / "b"
    coverage = build_dataset(development_config(), first, a)
    assert build_dataset(development_config(), second, b) == coverage
    assert tree_bytes(first) == tree_bytes(second)
    assert tree_bytes(a) == tree_bytes(b)
    assert coverage["families"] == 4 and coverage["total_cases"] == 20
    assert coverage["core_splits"] == {"seed": 20, "dev": 0, "test": 0}
    assert coverage["accepted_labels"] == 0
    provider = EvidenceProvider(first / "rca")
    assert provider.validate_public() == []
    for oracle in read_oracles(a):
        assert oracle.annotator_status == "pending" and not oracle.reviewer_ids
        case = provider.load_case(oracle.incident_id)
        records = [r for source in ("logs", "metrics", "changes", "configs", "database")
                   for r in provider._records(case.incident_id, source)]
        index = {r.evidence_id: r for r in records}
        if oracle.is_identifiable:
            supporting = oracle.acceptable_support_sets[0].evidence_ids
            assert len({index[e].source_type for e in supporting}) >= 2
            assert all(index[e].observed_at >= case.started_at for e in supporting)
            hypothesis = SimpleNamespace(**oracle.true_primary_root.model_dump())
            assert any(cause_discriminator(hypothesis, index[e]) for e in supporting)
            assert any(classify(index[e].model_dump(mode="json")) for e in supporting)
        else:
            assert not oracle.acceptable_support_sets
            assert not any(classify(r.model_dump(mode="json")) for r in records)
    text = "\n".join(p.read_text() for p in (first / "rca").rglob("*") if p.is_file())
    assert not any(field in text for field in ANSWER_FIELDS)
    assert "benchmark_oracle" not in text and "blueprint" not in text


def test_counterfactuals_change_public_discriminator_not_only_labels(tmp_path):
    public, oracle = tmp_path / "public", tmp_path / "oracle"
    build_dataset(development_config(), public, oracle)
    provider = EvidenceProvider(public / "rca")
    pairs = {}
    for label in read_oracles(oracle):
        if label.counterfactual_pair_id:
            pairs.setdefault(label.counterfactual_pair_id, []).append(label)
    for a, b in pairs.values():
        assert a.true_primary_root != b.true_primary_root
        observations = []
        for label in (a, b):
            observations.append([(r.source_type, r.service, r.excerpt, r.metadata)
                                 for source in ("logs", "metrics", "configs", "database")
                                 for r in provider._records(label.incident_id, source)])
        assert observations[0] != observations[1]


@pytest.mark.parametrize("overlap", ["same", "inside", "ancestor"])
def test_public_oracle_overlap_refused_before_writing(tmp_path, overlap):
    public = tmp_path / "dataset"
    oracle = public if overlap == "same" else (
        public / "private" if overlap == "inside" else tmp_path)
    with pytest.raises((ValueError, FileExistsError)):
        build_dataset(development_config(), public, oracle)
    assert not public.exists()


def test_existing_output_and_invalid_interventions_do_not_mutate(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    sentinel = out / "preserve.txt"
    sentinel.write_text("keep")
    with pytest.raises(FileExistsError):
        build_dataset(development_config(), out, tmp_path / "oracle")
    assert sentinel.read_text() == "keep"
    config = development_config()
    config["families"][0]["variants"][-1].pop("mechanism")
    with pytest.raises(ValueError, match="counterfactual"):
        build_dataset(config, tmp_path / "fresh", tmp_path / "private")
    assert not (tmp_path / "fresh").exists()


def test_renaming_family_ids_cannot_turn_shared_encoders_into_holdout(tmp_path):
    config = development_config()
    config["families"][1]["split"] = "test"
    config["families"][1]["near_duplicate_cluster_id"] = "renamed"
    with pytest.raises(ValueError, match="encoder lineage"):
        build_dataset(config, tmp_path / "data", tmp_path / "labels")
    assert not (tmp_path / "data").exists()


def test_monitoring_ood_separate_counts(tmp_path):
    config = development_config()
    for i, (mode, cohort) in enumerate((("healthy", "monitoring"), ("clock_skew", "ood"))):
        config["families"].append(dict(id=f"fam_extra_{i}", source_blueprint_id=f"bp_extra_{i}",
            near_duplicate_cluster_id=f"dup_extra_{i}", split="dev", cohort=cohort,
            mechanism=mode, started_at="2026-10-01T12:00:00+00:00",
            variants=[dict(id=f"extra_{i}", kind="ordinary")]))
    result = build_dataset(config, tmp_path / "data", tmp_path / "labels")
    assert result["cohorts"] == {"core": 20, "monitoring": 1, "ood": 1}
    assert result["core_splits"]["dev"] == 0


@pytest.mark.asyncio
async def test_actual_mock_observations_support_rca_and_missing_abstention(tmp_path):
    build_dataset(development_config(), tmp_path / "data", tmp_path / "labels")
    complete = await run_investigation("incident_1016", MockProvider(),
                                       data_root=tmp_path / "data" / "rca", cache=None)
    assert complete.report is not None
    assert complete.report.status == "RESOLVED"
    assert complete.report.root_cause.failure_mode == "backend_resource_saturation"
    missing = await run_investigation("incident_1013", MockProvider(),
                                      data_root=tmp_path / "data" / "rca", cache=None)
    assert missing.report is not None and missing.report.status == "INCONCLUSIVE"
