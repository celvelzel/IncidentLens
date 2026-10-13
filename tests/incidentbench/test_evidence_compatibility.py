import pytest

from incident_lens.incidentbench.manifest import create_lock, verify_lock
from incident_lens.incidentbench.schemas import ExperimentProtocol
from incident_lens.incidentbench.validator import validate_dataset


def test_public_validation_unavailable_root_sanitized(tmp_path):
    result = validate_dataset(tmp_path / "private-sensitive-missing")
    assert not result["ok"]
    assert str(tmp_path) not in str(result)


def test_lock_rejects_data_and_protocol_drift(tmp_path):
    (tmp_path / "public").write_text("original")
    protocol = ExperimentProtocol()
    lock = create_lock(tmp_path, protocol)
    assert not lock["sealed"]
    assert verify_lock(lock, tmp_path, protocol)
    with pytest.raises(ValueError):
        verify_lock(lock, tmp_path, protocol.model_copy(update={"run_order_seed": 99}))
    (tmp_path / "public").write_text("changed")
    with pytest.raises(ValueError):
        verify_lock(lock, tmp_path, protocol)


def test_source_digest_ignores_import_artifacts(tmp_path):
    from incident_lens.incidentbench.manifest import digest_tree

    (tmp_path / "module.py").write_text("x=1")
    before = digest_tree(tmp_path, source_only=True)
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "module.pyc").write_bytes(b"ephemeral")
    assert before == digest_tree(tmp_path, source_only=True)
    assert before != digest_tree(tmp_path)


def test_formal_seal_rejects_development_and_fake_readiness(tmp_path):
    from incident_lens.incidentbench.manifest import seal_dataset

    with pytest.raises(ValueError):
        seal_dataset(tmp_path, ExperimentProtocol(), tmp_path, tmp_path / "salt", {})


def test_private_git_unignored_and_tracked_rejected(tmp_path):
    import subprocess

    from incident_lens.incidentbench.manifest import check_private_git

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    labels = tmp_path / "labels"
    labels.mkdir()
    (labels / "secret.json").write_text("secret")
    with pytest.raises(PermissionError):
        check_private_git(labels, tmp_path)
    (tmp_path / ".gitignore").write_text("labels/")
    assert check_private_git(labels, tmp_path)
    subprocess.run(["git", "add", "-f", "labels/secret.json"], cwd=tmp_path, check=True)
    with pytest.raises(PermissionError):
        check_private_git(labels, tmp_path)


@pytest.fixture
def benchmark_fixture(tmp_path):
    import json
    import shutil
    from pathlib import Path

    from incident_lens.incidentbench.manifest import digest_tree

    base = Path(__file__).resolve().parents[2]
    dataset = tmp_path / "dataset"
    public = dataset / "rca" / "incidents" / "incident_001" / "public"
    shutil.copytree(base / "data" / "incidents" / "incident_001" / "public", public)
    shutil.copytree(base / "data" / "topology", dataset / "rca" / "topology")
    incident = json.loads((public / "incident.json").read_text())
    incident["started_at"] = "2026-10-01T13:00:00+00:00"
    (public / "incident.json").write_text(json.dumps(incident))
    splits = dataset / "rca" / "splits"
    splits.mkdir()
    for split in ("seed", "dev", "test"):
        (splits / (split + "_ids.json")).write_text(
            json.dumps(["incident_001"] if split == "seed" else [])
        )
    row = {
        "incident_id": "incident_001",
        "split": "seed",
        "scenario_family_id": "fam_1",
        "scenario_variant_id": "v1",
        "challenge_tags": ["ordinary"],
        "public_sha256": digest_tree(public),
        "source_blueprint_id": "source_1",
        "near_duplicate_cluster_id": "cluster_1",
    }
    (dataset / "public_case_index.json").write_text(json.dumps([row]))
    private = tmp_path / "labels"
    folder = private / "rca" / "incidents" / "incident_001" / "private"
    folder.mkdir(parents=True)
    oracle = {
        "incident_id": "incident_001",
        "scenario_family_id": "fam_1",
        "mechanism_id": "pool",
        "is_identifiable": True,
        "true_primary_root": {
            "culprit_service": "backend",
            "failure_mode": "backend_pool_config_regression",
            "root_cause_code": "pool",
        },
        "acceptable_support_sets": [
            {
                "evidence_ids": ["incident_001-D001", "incident_001-L001"],
                "rationale": "cause then symptom",
            }
        ],
        "contradicting_evidence_ids": [],
        "misleading_evidence_ids": [],
        "required_discriminator_types": ["configs", "logs"],
        "causal_sequence": ["cause", "symptom"],
        "identifiability_rationale": "configuration and symptom discriminated",
    }
    label = folder / "benchmark_oracle.json"
    label.write_text(json.dumps(oracle))
    (dataset / "manifest.json").write_text(
        json.dumps(
            {
                "benchmark_version": "incidentbench-v1",
                "rca_public_sha256": digest_tree(dataset / "rca"),
            }
        )
    )
    return dataset, private, public, label


def test_public_never_reads_corrupt_private(benchmark_fixture):
    dataset, private, public, label = benchmark_fixture
    label.write_text("invalid private JSON")
    assert validate_dataset(dataset)["ok"]
    assert not validate_dataset(dataset, private)["ok"]


def test_privileged_support_and_split_negative_cases(benchmark_fixture):
    import json

    dataset, private, public, label = benchmark_fixture
    assert validate_dataset(dataset, private)["ok"]
    oracle = json.loads(label.read_text())
    oracle["acceptable_support_sets"][0]["evidence_ids"] = [
        "incident_001-L001",
        "incident_001-L002",
    ]
    label.write_text(json.dumps(oracle))
    audit = validate_dataset(dataset, private)
    assert "support lacks cause-specific discriminator" in audit["errors"]
    assert "support lacks independent sources" in audit["errors"]
    (dataset / "rca" / "splits" / "seed_ids.json").write_text("[]")
    assert "split index mismatch" in validate_dataset(dataset)["errors"]


def test_nested_public_files_rejected(benchmark_fixture):
    dataset, private, public, label = benchmark_fixture
    nested = public / "hidden"
    nested.mkdir()
    (nested / "incident.json").write_text("{}")
    assert "unexpected public file" in validate_dataset(dataset)["errors"]


def test_manifest_digest_detects_topology_drift(benchmark_fixture):
    dataset, private, public, label = benchmark_fixture
    topology = dataset / "rca" / "topology" / "services.yaml"
    topology.write_text(topology.read_text() + "\n# drift")
    assert "manifest public bundle hash mismatch" in validate_dataset(dataset)["errors"]


def test_builder_public_privileged_contract_integration(tmp_path):

    from incident_lens.incidentbench.builder import build_dataset

    config = {
        "families": [
            {
                "id": "fam_1",
                "source_blueprint_id": "blueprint_1",
                "near_duplicate_cluster_id": "cluster_1",
                "split": "seed",
                "started_at": "2026-10-01T12:00:00+00:00",
                "mechanism": "backend_pool_config_regression",
                "variants": [
                    {"id": "ordinary", "kind": "ordinary"},
                    {"id": "missing", "kind": "missing"},
                ],
            }
        ]
    }
    dataset, private = tmp_path / "dataset", tmp_path / "labels"
    build_dataset(config, dataset, private)
    assert validate_dataset(dataset)["ok"]
    result = validate_dataset(dataset, private)
    assert result["ok"], result["errors"]
