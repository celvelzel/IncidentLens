"""Inventory existing bytes; project acceptance never changes formal label provenance."""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import yaml

from incident_lens.incidentbench.manifest import check_private_git, digest_tree
from incident_lens.incidentbench.oracle_store import canonical, safe_path
from incident_lens.incidentbench.schemas import BenchmarkOracle, ExperimentProtocol
from incident_lens.incidentbench.validator import validate_dataset
from incident_lens.tools.provider import SOURCE_FILES, EvidenceProvider

DATASETS = {"seed": "incidentbench_v1", "dev": "incidentbench_v16_dev"}
POLICY = {
    "status": "project_accepted",
    "authorization": "OWNER_REVIEW_ACCEPTED",
    "authorization_date": "2026-10-16",
    "basis": "Project owner explicitly accepted the existing Seed20 and Dev10 references.",
    "label_scope": "course_project_development_reference",
    "formal_sealed": False,
    "independent_double_review": False,
    "blindness_level": "development_visible",
}


def read(path):
    return json.loads(safe_path(path).read_bytes())


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


def private_destination(path, repository, public_roots):
    path = Path(path).absolute()
    # Check every existing ancestor before creating anything (including Windows reparse points).
    ancestor = path
    while not ancestor.exists():
        ancestor = ancestor.parent
    safe_path(ancestor)
    resolved = path.resolve()
    if not resolved.is_relative_to(repository / "local_oracles"):
        raise PermissionError("evaluator output must be under repository local_oracles")
    if any(resolved.is_relative_to(p) or p.is_relative_to(resolved) for p in public_roots):
        raise PermissionError("evaluator output overlaps public data")
    relative = resolved.relative_to(repository).as_posix()
    if subprocess.run(
        ["git", "check-ignore", "-q", "--", relative], cwd=repository
    ).returncode:
        raise PermissionError("evaluator output must be ignored")
    return resolved


def inventory(repository):
    """Return an allowlisted public freeze and a separate evaluator-only full inventory."""
    repository = safe_path(repository)
    source_root = Path(__file__).resolve().parents[1]
    protocol_path = source_root / "configs/incidentbench-protocol.yaml"
    protocol = ExperimentProtocol.model_validate(yaml.safe_load(protocol_path.read_bytes()))
    public = {"dataset_version": "wp-b-project-accepted-v1", "reference_label_policy": POLICY,
              "source_commit": subprocess.check_output(
                  ["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip(),
              "finalizer_source_commit": subprocess.check_output(
                  ["git", "rev-parse", "HEAD"], cwd=source_root, text=True).strip(),
              "finalizer_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "protocol_sha256": hashlib.sha256(
                  canonical(protocol.model_dump(mode="json"))).hexdigest(),
              "protocol_file_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
              "datasets": {}, "cases": [], "limitations": [
                  "Shared causal-world-v1 encoder; no independent-family or blind-test claim.",
                  "Competing hypotheses have no separate annotation field; not inferred as truth."]}
    private = {"reference_label_policy": POLICY, "cases": []}
    ids, fingerprints, normalized = set(), defaultdict(list), {}
    groups = defaultdict(set)
    for split, name in DATASETS.items():
        dataset = safe_path(repository / "data" / name)
        oracle_root = safe_path(repository / "local_oracles" / name)
        check_private_git(oracle_root, repository)
        audits = {"public": validate_dataset(dataset),
                  "privileged": validate_dataset(dataset, oracle_root)}
        if any(not result["ok"] for result in audits.values()):
            raise ValueError(f"{split} validation failed: {audits}")
        rows = read(dataset / "public_case_index.json")
        rows = rows if isinstance(rows, list) else rows["cases"]
        expected = 20 if split == "seed" else 10
        if len(rows) != expected or any(row["split"] != split for row in rows):
            raise ValueError("expected existing Seed20 and Dev10")
        oracle_paths = set(oracle_root.rglob("benchmark_oracle.json"))
        expected_paths = {oracle_root / "rca" / "incidents" / row["incident_id"] /
                          "private" / "benchmark_oracle.json" for row in rows}
        if oracle_paths != expected_paths:
            raise ValueError("oracle file/index mismatch")
        provider = EvidenceProvider(dataset / "rca")
        for row in rows:
            incident_id = row["incident_id"]
            if incident_id in ids:
                raise ValueError("duplicate incident across datasets")
            ids.add(incident_id)
            records = [record for source in SOURCE_FILES
                       for record in provider._records(incident_id, source)]
            evidence_ids = [record.evidence_id for record in records]
            if len(evidence_ids) != len(set(evidence_ids)):
                raise ValueError("duplicate evidence ID")
            normalized[incident_id] = (split, re.sub(
                r"incident_\d+|\d+|[0-9a-f]{16,}", "#",
                " ".join(record.excerpt for record in records).lower()))
            oracle = BenchmarkOracle.model_validate(read(
                oracle_root / "rca" / "incidents" / incident_id / "private" /
                "benchmark_oracle.json"))
            # Public output uses public index fields only: never oracle-derived answers/support.
            public["cases"].append({**row, "generator_lineage": "causal-world-v1",
                                    "reference_label_status": "project_accepted"})
            private["cases"].append({**row, "oracle": oracle.model_dump(mode="json"),
                                     "competing_hypotheses": None,
                                     "competing_hypotheses_status": "not separately annotated"})
            fingerprints[row["public_sha256"]].append(incident_id)
            for field in ("scenario_family_id", "source_blueprint_id",
                          "near_duplicate_cluster_id", "counterfactual_pair_id"):
                if row.get(field):
                    groups[(field, row[field])].add(split)
        public["datasets"][split] = {
            "public_path": f"data/{name}", "oracle_path": f"local_oracles/{name}",
            "case_count": len(rows), "manifest_sha256": hashlib.sha256(
                (dataset / "manifest.json").read_bytes()).hexdigest(),
            "public_sha256": digest_tree(dataset), "oracle_sha256": digest_tree(oracle_root),
            "validation": audits,
        }
    public["exact_public_duplicates"] = [v for v in fingerprints.values() if len(v) > 1]
    public["cross_split_near_duplicates"] = [
        {"left": left, "right": right, "normalized_excerpt_similarity": similarity}
        for left, (left_split, left_text) in normalized.items()
        for right, (right_split, right_text) in normalized.items()
        if left < right and left_split != right_split
        and (similarity := SequenceMatcher(None, left_text, right_text).ratio()) >= 0.97]
    public["shared_cross_split_groups"] = [
        {"field": key[0], "value": key[1], "splits": sorted(splits)}
        for key, splits in sorted(groups.items()) if len(splits) > 1]
    # Shared groups are disclosed limitations, not grounds for rewriting owner-approved labels.
    public["shared_encoder_lineage"] = "causal-world-v1"
    return public, private


def prepare_pilot(repository, public_out, private_out):
    """Copy original Seed ordinary/misleading/missing bytes into a three-case pilot."""
    repository = safe_path(repository)
    source = repository / "data" / DATASETS["seed"]
    private_source = repository / "local_oracles" / DATASETS["seed"]
    private_out = private_destination(
        private_out, repository, [source, private_source, Path(public_out).resolve()])
    public_out = Path(public_out).absolute()
    if not public_out.resolve().is_relative_to(repository / "results"):
        raise PermissionError("pilot public output must be under repository results")
    ancestor = public_out.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    safe_path(ancestor)
    if public_out.exists() or private_out.exists():
        raise FileExistsError("pilot outputs must be fresh")
    rows = read(source / "public_case_index.json")
    selected = [next(row for row in rows if tag in row["challenge_tags"])
                for tag in ("ordinary", "misleading", "missing")]
    public_out.mkdir(parents=True)
    private_out.mkdir(parents=True)
    shutil.copytree(source / "rca" / "topology", public_out / "rca" / "topology")
    for row in selected:
        relative = Path("rca/incidents") / row["incident_id"]
        shutil.copytree(source / relative / "public", public_out / relative / "public")
        shutil.copytree(private_source / relative, private_out / relative)
    for split in ("seed", "dev", "test"):
        write_new(public_out / "rca/splits" / f"{split}_ids.json",
                  [row["incident_id"] for row in selected if row["split"] == split])
    coverage = read(source / "coverage.json")
    coverage.update(total_cases=3, families=len({r["scenario_family_id"] for r in selected}),
                    cohorts={"core": 3, "monitoring": 0, "ood": 0},
                    splits={"seed": 3, "dev": 0, "test": 0},
                    core_splits={"seed": 3, "dev": 0, "test": 0},
                    challenges=dict(Counter(tag for r in selected for tag in r["challenge_tags"])),
                    identifiable=2)
    manifest = read(source / "manifest.json")
    manifest.update(coverage=coverage, rca_public_sha256=digest_tree(public_out / "rca"))
    write_new(public_out / "public_case_index.json", selected)
    write_new(public_out / "coverage.json", coverage)
    write_new(public_out / "manifest.json", manifest)
    audit = validate_dataset(public_out, private_out)
    if not audit["ok"]:
        raise ValueError(f"pilot audit failed: {audit}")
    return {"case_ids": [r["incident_id"] for r in selected],
            "public_sha256": digest_tree(public_out), "oracle_sha256": digest_tree(private_out),
            "validation": audit}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    parser.add_argument("--evaluator-out", type=Path, required=True)
    parser.add_argument("--pilot-public-out", type=Path)
    parser.add_argument("--pilot-oracle-out", type=Path)
    args = parser.parse_args()
    repository = safe_path(args.repository)
    if bool(args.pilot_public_out) != bool(args.pilot_oracle_out):
        parser.error("both pilot paths are required")
    roots = [repository / category / name for category in ("data", "local_oracles")
             for name in DATASETS.values()]
    evaluator_out = private_destination(args.evaluator_out, repository, roots)
    if args.public_out.exists() or evaluator_out.exists():
        raise FileExistsError("inventory outputs must be fresh")
    public, private = inventory(repository)
    if args.pilot_public_out:
        public["pilot"] = prepare_pilot(repository, args.pilot_public_out, args.pilot_oracle_out)
    write_new(evaluator_out, private)
    write_new(args.public_out, public)
    print(json.dumps({"cases": len(public["cases"]), "status": "project_accepted"}))


if __name__ == "__main__":
    main()
