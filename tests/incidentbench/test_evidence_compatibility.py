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
