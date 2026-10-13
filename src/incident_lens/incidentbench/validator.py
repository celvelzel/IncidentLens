"""Public compatibility and evaluator-only causal/leakage audits."""

import json
import re
from collections import Counter
from difflib import SequenceMatcher

from incident_lens.orchestration.guards import cause_discriminator
from incident_lens.schemas import Hypothesis
from incident_lens.tools.provider import PUBLIC_FILES, SOURCE_FILES, EvidenceProvider

from .manifest import digest_tree
from .oracle_store import safe_path
from .schemas import BenchmarkCaseMetadata, BenchmarkOracle


def validate_dataset(dataset, oracle_root=None):
    errors = []
    coverage = Counter()
    try:
        dataset = safe_path(dataset)
        rca = dataset / "rca" if (dataset / "rca").exists() else dataset
        safe_path(rca)
        provider = EvidenceProvider(rca)
        errors.extend(provider.validate_public())
        index_path = dataset / "public_case_index.json"
        raw = json.loads(safe_path(index_path).read_bytes())
        rows = raw if isinstance(raw, list) else raw["cases"]
        metadata = [BenchmarkCaseMetadata.model_validate(row) for row in rows]
        for split in ("seed", "dev", "test"):
            for cohort in ("core", "monitoring", "ood"):
                coverage[f"{split}/{cohort}"] = 0
        pairs = Counter(
            row.counterfactual_pair_id for row in metadata if row.counterfactual_pair_id
        )
        if any(count != 2 for count in pairs.values()):
            errors.append("counterfactual group requires exactly two cases")
        ids = [row.incident_id for row in metadata]
        if len(ids) != len(set(ids)) or set(ids) != {
            case.incident_id for case in provider.list_cases()
        }:
            errors.append("case index coverage mismatch")
        for split in ("seed", "dev", "test"):
            actual = json.loads(safe_path(rca / "splits" / f"{split}_ids.json").read_bytes())
            expected = [row.incident_id for row in metadata if row.split == split]
            if len(actual) != len(set(actual)) or set(actual) != set(expected):
                errors.append("split index mismatch")
        manifest = json.loads(safe_path(dataset / "manifest.json").read_bytes())
        if manifest.get("rca_public_sha256") != digest_tree(rca):
            errors.append("manifest public bundle hash mismatch")
        if manifest.get("benchmark_version") != "incidentbench-v1":
            errors.append("manifest version mismatch")
        groups = {}
        texts = {}
        oracles = {}
        observations = {}
        for row in metadata:
            coverage[f"{row.split}/{row.cohort}"] += 1
            public = rca / "incidents" / row.incident_id / "public"
            for path in public.rglob("*"):
                safe_path(path)
                if path.is_dir() or path.name not in PUBLIC_FILES:
                    errors.append("unexpected public file")
            if digest_tree(public) != row.public_sha256:
                errors.append("public hash mismatch")
            for field in (
                "scenario_family_id",
                "source_blueprint_id",
                "near_duplicate_cluster_id",
                "counterfactual_pair_id",
            ):
                value = getattr(row, field)
                if value:
                    key = (field, value)
                    if key in groups and groups[key] != row.split:
                        errors.append(f"cross-split {field}")
                    groups[key] = row.split
            records = [
                record
                for source in (*SOURCE_FILES, "topology")
                for record in provider._records(row.incident_id, source)
            ]
            observations[row.incident_id] = sorted(
                (
                    record.source_type,
                    record.service,
                    re.sub(r"incident_\d+", "#", record.excerpt),
                    json.dumps(record.metadata, sort_keys=True),
                )
                for record in records
                if record.source_type != "topology"
            )
            normalized = " ".join(
                record.excerpt for record in records if record.source_type != "topology"
            )
            normalized = re.sub(r"incident_\d+|\d+|[0-9a-f]{16,}", "#", normalized.lower())
            texts[row.incident_id] = (row.split, normalized)
            if oracle_root is not None:
                root = safe_path(oracle_root)
                if root.is_relative_to(dataset) or dataset.is_relative_to(root):
                    raise PermissionError("oracle and public roots must be disjoint")
                oracle = BenchmarkOracle.model_validate_json(
                    safe_path(
                        root
                        / "rca"
                        / "incidents"
                        / row.incident_id
                        / "private"
                        / "benchmark_oracle.json"
                    ).read_bytes()
                )
                oracles[row.incident_id] = oracle
                if (
                    oracle.incident_id != row.incident_id
                    or oracle.scenario_family_id != row.scenario_family_id
                    or oracle.cohort != row.cohort
                    or oracle.counterfactual_pair_id != row.counterfactual_pair_id
                ):
                    errors.append("oracle metadata mismatch")
                lookup = {r.evidence_id: r for r in records}
                hypothesis = Hypothesis(
                    hypothesis_id="oracle_audit",
                    culprit_service=oracle.true_primary_root.culprit_service,
                    failure_mode=oracle.true_primary_root.failure_mode,
                )
                discriminator_records = [r for r in records if cause_discriminator(hypothesis, r)]
                if (
                    not oracle.is_identifiable
                    and discriminator_records
                    and len(
                        {r.source_type for r in records if r.service == hypothesis.culprit_service}
                    )
                    >= 2
                ):
                    errors.append(
                        "insufficient case exposes discriminator and support; human review required"
                    )
                referenced = set(oracle.contradicting_evidence_ids + oracle.misleading_evidence_ids)
                for support in oracle.acceptable_support_sets:
                    referenced.update(support.evidence_ids)
                    selected = [lookup[e] for e in support.evidence_ids if e in lookup]
                    if len({r.source_type for r in selected}) < 2:
                        errors.append("support lacks independent sources")
                    if not set(oracle.required_discriminator_types).issubset(
                        {r.source_type for r in selected}
                    ):
                        errors.append("support lacks required discriminator")
                    causes = [r for r in selected if cause_discriminator(hypothesis, r)]
                    if not causes:
                        errors.append("support lacks cause-specific discriminator")
                    symptoms = [r for r in selected if r.source_type == "logs"]
                    if (
                        causes
                        and symptoms
                        and min(r.observed_at for r in causes)
                        > max(r.observed_at for r in symptoms)
                    ):
                        errors.append("cause observation follows all support symptoms")
                    case = provider.load_case(row.incident_id)
                    if any(r.observed_at < case.started_at for r in selected):
                        errors.append("support precedes incident window")
                if not referenced.issubset(lookup):
                    errors.append("oracle references absent evidence")
                if not oracle.causal_sequence or not oracle.identifiability_rationale:
                    errors.append("missing causal rationale")
        for i, left in enumerate(metadata):
            for right in metadata[i + 1 :]:
                if (
                    left.split != right.split
                    and SequenceMatcher(
                        None, texts[left.incident_id][1], texts[right.incident_id][1]
                    ).ratio()
                    >= 0.97
                ):
                    errors.append("cross-split near-duplicate requires review")
                if (
                    oracle_root
                    and left.counterfactual_pair_id
                    and left.counterfactual_pair_id == right.counterfactual_pair_id
                ):
                    a, b = oracles[left.incident_id], oracles[right.incident_id]
                    if (
                        a.true_primary_root == b.true_primary_root
                        or observations[left.incident_id] == observations[right.incident_id]
                    ):
                        errors.append("invalid counterfactual pair")
    except (OSError, ValueError, KeyError, TypeError, PermissionError):
        errors.append("invalid benchmark resource or contract")
    return {"ok": not errors, "errors": sorted(set(errors)), "coverage": dict(coverage)}
