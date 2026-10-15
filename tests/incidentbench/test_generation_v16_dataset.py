"""Public V16 development release integrity; private answers stay outside fixtures."""

import json
from pathlib import Path

from incident_lens.incidentbench.validator import validate_dataset
from incident_lens.tools.provider import ANSWER_FIELDS

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "incidentbench_v16_dev"


def test_v16_public_development_contract():
    assert validate_dataset(DATA)["ok"]
    coverage = json.loads((DATA / "coverage.json").read_text())
    assert coverage["splits"] == {"seed": 0, "dev": 10, "test": 0}
    assert coverage["accepted_labels"] == coverage["independent_audited_families"] == 0
    assert all(
        coverage["challenges"][kind] >= 2
        for kind in ("ordinary", "misleading", "missing", "counterfactual")
    )
    rows = json.loads((DATA / "public_case_index.json").read_text())
    assert {r["near_duplicate_cluster_id"] for r in rows} == {"cluster_causal_world_v1"}
    pairs = {}
    for row in rows:
        if row["counterfactual_pair_id"]:
            pairs.setdefault(row["counterfactual_pair_id"], []).append(row)
    assert len(pairs) == 2
    assert all(
        len(pair) == 2 and len({r["public_sha256"] for r in pair}) == 2 for pair in pairs.values()
    )


def test_v16_public_bundle_excludes_private_metadata():
    for path in (DATA / "rca").rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert not any(marker in text for marker in ANSWER_FIELDS)
            assert "benchmark_oracle" not in text
            assert "local_oracles" not in text
    assert not list(DATA.rglob("benchmark_oracle.json"))
