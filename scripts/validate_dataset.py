"""Dataset/evaluation maintenance script; permitted to inspect private oracles."""

import argparse
import json
import re
from pathlib import Path

from incident_lens.tools.provider import PUBLIC_FILES, EvidenceProvider

FORBIDDEN_MARKERS = (
    "root_cause_code",
    "culprit_service",
    "failure_mode",
    "decisive_evidence_ids",
    "misleading_evidence_ids",
    "is_identifiable",
    "generator_seed",
)


def validate_dataset(root: str | Path = "data") -> list[str]:
    root = Path(root)
    errors = []
    all_ids = set()
    try:
        provider = EvidenceProvider(root)
        cases = provider.list_cases()
    except Exception as error:
        return [f"dataset cannot be loaded: {type(error).__name__}"]
    split_ids = {}
    for split in ("seed", "dev", "test"):
        try:
            ids = json.loads((root / "splits" / f"{split}_ids.json").read_text(encoding="utf-8"))
            if (
                not isinstance(ids, list)
                or any(not isinstance(item, str) for item in ids)
                or len(ids) != len(set(ids))
            ):
                errors.append(f"{split}: malformed or duplicate split IDs")
            else:
                split_ids[split] = ids
        except (OSError, ValueError):
            errors.append(f"{split}: cannot read split")
    flattened = [item for ids in split_ids.values() for item in ids]
    if len(flattened) != len(set(flattened)):
        errors.append("split overlap")
    if set(flattened) != {case.incident_id for case in cases}:
        errors.append("split IDs do not cover cases exactly")
    for case in cases:
        incident_id = case.incident_id
        try:
            records = [
                record
                for source in ("logs", "metrics", "changes", "configs", "topology")
                for record in provider._records(incident_id, source)
            ]
            ids = {record.evidence_id for record in records}
            if len(ids) != len(records) or all_ids.intersection(ids):
                errors.append(f"{incident_id}: duplicate evidence IDs")
            all_ids.update(ids)
            truth = json.loads(
                (root / "incidents" / incident_id / "private" / "ground_truth.json").read_text(
                    encoding="utf-8"
                )
            )
            for key in ("root_cause_code", "culprit_service", "failure_mode"):
                if not isinstance(truth.get(key), str) or not re.fullmatch(
                    r"[a-z][a-z0-9_]*", truth[key]
                ):
                    errors.append(f"{incident_id}: invalid oracle {key}")
            if truth.get("culprit_service") not in case.services:
                errors.append(f"{incident_id}: invalid culprit service")
            if not isinstance(truth.get("is_identifiable"), bool):
                errors.append(f"{incident_id}: is_identifiable must be boolean")
            if not truth.get("causal_chain") or not all(
                isinstance(item, str) and item for item in truth["causal_chain"]
            ):
                errors.append(f"{incident_id}: causal chain required")
            for key in ("decisive_evidence_ids", "misleading_evidence_ids"):
                values = truth.get(key)
                if not isinstance(values, list) or not values or not set(values).issubset(ids):
                    errors.append(f"{incident_id}: invalid oracle evidence {key}")
            if truth.get("split") not in split_ids or incident_id not in split_ids.get(
                truth.get("split"), []
            ):
                errors.append(f"{incident_id}: oracle split mismatch")
            public_text = "\n".join(
                provider._public_path(incident_id, filename).read_text(encoding="utf-8")
                for filename in PUBLIC_FILES
            )
            for marker in FORBIDDEN_MARKERS + tuple(
                truth.get(key, "") for key in ("root_cause_code", "failure_mode")
            ):
                if marker and marker in public_text:
                    errors.append(f"{incident_id}: public answer marker {marker}")
            counts = {
                source: sum(record.source_type == source for record in records)
                for source in ("logs", "metrics", "changes", "configs")
            }
            if (
                not 20 <= counts["logs"] <= 60
                or not 5 <= counts["metrics"] <= 15
                or not 3 <= counts["changes"] + counts["configs"] <= 8
            ):
                errors.append(f"{incident_id}: observation counts outside fixture bounds")
            # Causal change precedes errors; downstream symptom follows the first causal error.
            causal_errors = [
                record.observed_at
                for record in records
                if record.source_type == "logs"
                and record.service == truth["culprit_service"]
                and record.metadata.get("severity") == "ERROR"
            ]
            if not causal_errors:
                errors.append(f"{incident_id}: no culprit error observation")
            if any(
                record.observed_at < case.started_at
                for record in records
                if record.source_type == "logs"
                and record.service == "gateway"
                and record.metadata.get("severity") == "ERROR"
            ):
                errors.append(f"{incident_id}: gateway errors precede incident onset")
        except Exception as error:
            errors.append(f"{incident_id}: invalid pack ({type(error).__name__})")
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="data")
    args = parser.parse_args()
    failures = validate_dataset(args.root)
    print(json.dumps({"ok": not failures, "errors": failures}, indent=2))
    raise SystemExit(bool(failures))
