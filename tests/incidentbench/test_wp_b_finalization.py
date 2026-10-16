"""WP-B reference acceptance is separate from authentic review and formal sealing."""

import json
import runpy
import subprocess
from pathlib import Path

import pytest

from incident_lens.incidentbench.builder import build_dataset
from incident_lens.incidentbench.manifest import digest_tree

ROOT = Path(__file__).resolve().parents[2]
MODULE = runpy.run_path(str(ROOT / "scripts/finalize_wp_b_dataset.py"))


@pytest.fixture
def corpus(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("local_oracles/\nresults/\n")
    subprocess.run(["git", "add", ".gitignore"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.org",
                    "commit", "-qm", "fixture"], cwd=tmp_path, check=True)
    config = runpy.run_path(str(ROOT / "tests/incidentbench/test_generation.py"))[
        "development_config"]()
    build_dataset(config, tmp_path / "data/incidentbench_v1",
                  tmp_path / "local_oracles/incidentbench_v1")
    config["first_incident_number"] = 3001
    config["families"] = config["families"][:2]
    for row in config["families"]:
        row["split"] = "dev"
        row["id"] += "_dev"
    build_dataset(config, tmp_path / "data/incidentbench_v16_dev",
                  tmp_path / "local_oracles/incidentbench_v16_dev")
    return tmp_path


def test_inventory_safe_reproducible_and_original_bytes(corpus):
    before = digest_tree(corpus / "data"), digest_tree(corpus / "local_oracles")
    public, private = MODULE["inventory"](corpus)
    assert len(public["cases"]) == len(private["cases"]) == 30
    assert MODULE["inventory"](corpus) == (public, private)
    assert before == (digest_tree(corpus / "data"), digest_tree(corpus / "local_oracles"))
    assert public["reference_label_policy"]["formal_sealed"] is False
    assert public["reference_label_policy"]["status"] == "project_accepted"
    text = json.dumps(public)
    for field in ("true_primary_root", "acceptable_support_sets", "misleading_evidence_ids",
                  "reviewer_ids", "causal_sequence"):
        assert field not in text
    assert public["shared_cross_split_groups"]
    assert all(row["oracle"]["annotator_status"] == "pending" for row in private["cases"])


def test_inventory_rejects_hash_drift(corpus):
    path = corpus / "data/incidentbench_v1/rca/incidents/incident_1001/public/logs.jsonl"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="validation failed"):
        MODULE["inventory"](corpus)


def test_pilot_preserves_public_and_oracle_bytes(corpus):
    public = corpus / "results/pilot"
    private = corpus / "local_oracles/pilot"
    result = MODULE["prepare_pilot"](corpus, public, private)
    assert result["case_ids"] == ["incident_1001", "incident_1002", "incident_1003"]
    assert result["validation"]["ok"]
    for case in result["case_ids"]:
        relative = Path("rca/incidents") / case
        assert digest_tree(public / relative) == digest_tree(
            corpus / "data/incidentbench_v1" / relative)
        assert digest_tree(private / relative) == digest_tree(
            corpus / "local_oracles/incidentbench_v1" / relative)
    with pytest.raises(FileExistsError):
        MODULE["prepare_pilot"](corpus, public, private)


def test_evaluator_output_requires_ignored_local_oracles(corpus):
    with pytest.raises(PermissionError):
        MODULE["private_destination"](corpus / "docs/answers.json", corpus, [])
    destination = corpus / "local_oracles/freeze/inventory.json"
    assert MODULE["private_destination"](destination, corpus, []) == destination


def test_write_refuses_overwrite(tmp_path):
    path = tmp_path / "freeze.json"
    MODULE["write_new"](path, {"status": "project_accepted"})
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        MODULE["write_new"](path, {"status": "changed"})
    assert path.read_bytes() == before
