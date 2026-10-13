import hashlib

import pytest

from incident_lens.incidentbench.manifest import digest_tree, label_commitment
from incident_lens.incidentbench.oracle_store import OracleStore, canonical, safe_path


def completed(tmp_path):
    state = {
        "incident_id": "incident_100",
        "run_id": "run_1",
        "workflow_status": "FINISHED",
        "report": {"incident_id": "incident_100", "run_id": "run_1", "status": "INCONCLUSIVE"},
    }
    path = tmp_path / "state.json"
    path.write_bytes(canonical(state))
    state["completion_receipt"] = {
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    return state


def test_missing_completion_rejected(tmp_path):
    with pytest.raises(PermissionError, match="completed"):
        OracleStore(tmp_path).load_after_completion("incident_100", {})


@pytest.mark.parametrize(
    "mutation", ["foreign_incident", "foreign_run", "running", "state_drift", "receipt_drift"]
)
def test_receipt_binding(tmp_path, mutation):
    state = completed(tmp_path)
    if mutation == "foreign_incident":
        state["incident_id"] = "incident_101"
    elif mutation == "foreign_run":
        state["report"]["run_id"] = "run_2"
    elif mutation == "running":
        state["workflow_status"] = "RUNNING"
    elif mutation == "state_drift":
        state["extra"] = "modified"
    else:
        state["completion_receipt"]["sha256"] = "bad"
    with pytest.raises(PermissionError):
        OracleStore(tmp_path).load_after_completion("incident_100", state)


def test_traversal_and_sensitive_errors(tmp_path):
    with pytest.raises(PermissionError) as caught:
        safe_path(tmp_path / ".." / "sensitive-missing")
    assert str(tmp_path) not in str(caught.value)
    with pytest.raises(PermissionError):
        safe_path(tmp_path / "missing")


def test_ancestor_symlink(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    child = target / "child"
    child.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("OS symlink privilege unavailable")
    with pytest.raises(PermissionError):
        safe_path(link / "child")


def test_salted_commitment_drift(tmp_path):
    (tmp_path / "label.json").write_text("secret")
    before = label_commitment(tmp_path, b"a" * 32)
    assert before != label_commitment(tmp_path, b"b" * 32)
    (tmp_path / "label.json").write_text("changed")
    assert before != label_commitment(tmp_path, b"a" * 32)
    with pytest.raises(ValueError):
        label_commitment(tmp_path, b"short")


def test_digest_filename_binding(tmp_path):
    (tmp_path / "a").write_text("same")
    before = digest_tree(tmp_path)
    (tmp_path / "a").rename(tmp_path / "b")
    assert before != digest_tree(tmp_path)


def test_valid_receipt_loads_only_matching_oracle(tmp_path):
    import json

    private = tmp_path / "private-root"
    folder = private / "rca" / "incidents" / "incident_100" / "private"
    folder.mkdir(parents=True)
    label = {
        "incident_id": "incident_100",
        "scenario_family_id": "fam_1",
        "mechanism_id": "m",
        "is_identifiable": False,
        "true_primary_root": {
            "culprit_service": "backend",
            "failure_mode": "backend_pool_config_regression",
            "root_cause_code": "pool",
        },
        "acceptable_support_sets": [],
        "contradicting_evidence_ids": [],
        "misleading_evidence_ids": [],
        "required_discriminator_types": [],
        "causal_sequence": ["trigger then symptom"],
        "identifiability_rationale": "required observation missing",
    }
    (folder / "benchmark_oracle.json").write_text(json.dumps(label))
    assert (
        OracleStore(private)
        .load_after_completion("incident_100", completed(tmp_path))
        .annotator_status
        == "pending"
    )
    label["incident_id"] = "incident_101"
    (folder / "benchmark_oracle.json").write_text(json.dumps(label))
    with pytest.raises(PermissionError):
        OracleStore(private).load_after_completion("incident_100", completed(tmp_path))


def test_explicit_root_overlap_rejected(tmp_path):
    child = tmp_path / "labels"
    child.mkdir()
    with pytest.raises(PermissionError):
        OracleStore(child, public_root=tmp_path)
