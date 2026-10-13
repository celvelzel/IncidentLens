"""Public-only offline evidence loader. No runtime private-oracle interface."""

import csv
import hashlib
import json
import re
import stat
from pathlib import Path

import yaml

from incident_lens.schemas import CasePublicInput, EvidenceRecord

PUBLIC_FILES = frozenset(
    {
        "incident.json",
        "logs.jsonl",
        "metrics.csv",
        "changes.jsonl",
        "configs.jsonl",
        "database.jsonl",
    }
)
SOURCE_FILES = {
    "logs": "logs.jsonl",
    "metrics": "metrics.csv",
    "changes": "changes.jsonl",
    "configs": "configs.jsonl",
    "database": "database.jsonl",
}
CASE_ID = re.compile(r"^incident_[0-9]{3,}$")
METADATA_FIELDS = {
    "database": frozenset(
        {
            "category",
            "metric_name",
            "value",
            "unit",
            "connection_count",
            "connection_limit",
            "pool_in_use",
            "pool_limit",
            "session_id",
            "state",
            "wait_event",
            "blocked_by",
            "duration_ms",
            "query_fingerprint",
            "health_status",
        }
    ),
    "logs": frozenset({"severity", "request_id", "origin"}),
    "changes": frozenset({"change_id", "change_type"}),
    "configs": frozenset({"change_id"}),
    "metrics": frozenset({"metric_name", "value", "unit"}),
}
ANSWER_FIELDS = (
    "root_cause_code",
    "culprit_service",
    "failure_mode",
    "decisive_evidence_ids",
    "misleading_evidence_ids",
    "is_identifiable",
    "generator_seed",
)


class EvidenceProvider:
    def __init__(self, root: str | Path = "data"):
        candidate = Path(root).absolute()
        if self._link(candidate):
            raise PermissionError("dataset root cannot be a symlink or junction")
        self._root = candidate.resolve(strict=True)
        if not self._root.is_dir():
            raise ValueError("dataset root must be a directory")

    @staticmethod
    def _link(path: Path) -> bool:
        info = path.lstat()
        return path.is_symlink() or bool(
            getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        )

    def _safe_path(self, *parts: str) -> Path:
        path = self._root
        for part in parts:
            if part in ("", ".", "..") or "/" in part or "\\" in part or ":" in part:
                raise PermissionError("invalid path component")
            path = path / part
            if self._link(path):
                raise PermissionError("symlinks and junctions are not public evidence")
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(self._root):
            raise PermissionError("path escapes dataset root")
        return resolved

    def _public_path(self, incident_id: str, filename: str) -> Path:
        if not CASE_ID.fullmatch(incident_id) or filename not in PUBLIC_FILES:
            raise PermissionError("only fixed public evidence files are accessible")
        return self._safe_path("incidents", incident_id, "public", filename)

    def list_cases(self) -> list[CasePublicInput]:
        directory = self._safe_path("incidents")
        return [
            self.load_case(path.name)
            for path in sorted(directory.iterdir())
            if CASE_ID.fullmatch(path.name)
        ]

    def load_case(self, incident_id: str) -> CasePublicInput:
        case = CasePublicInput.model_validate_json(
            self._public_path(incident_id, "incident.json").read_text(encoding="utf-8")
        )
        if case.incident_id != incident_id:
            raise ValueError("public incident identity mismatch")
        return case

    def validate_public(self) -> list[str]:
        """Validate publicly visible packs without reading split files or private oracles."""
        errors = []
        seen = set()
        try:
            cases = self.list_cases()
        except (OSError, ValueError, PermissionError):
            return ["public incident summaries cannot be loaded"]
        for case in cases:
            try:
                records = [
                    record
                    for source in (*SOURCE_FILES, "topology")
                    for record in self._records(case.incident_id, source)
                ]
                ids = {record.evidence_id for record in records}
                if len(ids) != len(records) or seen.intersection(ids):
                    errors.append(f"{case.incident_id}: duplicate evidence IDs")
                seen.update(ids)
                public_text = "\n".join(
                    self._public_text(case.incident_id, name) for name in PUBLIC_FILES
                )
                if any(marker in public_text for marker in ANSWER_FIELDS):
                    errors.append(f"{case.incident_id}: public answer metadata found")
            except (OSError, ValueError, KeyError, TypeError):
                errors.append(f"{case.incident_id}: invalid public evidence")
        return errors

    @property
    def dataset_revision(self) -> str:
        digest = hashlib.sha256()
        for case in self.list_cases():
            for filename in sorted(PUBLIC_FILES):
                digest.update(f"{case.incident_id}/{filename}\0".encode())
                digest.update(self._public_text(case.incident_id, filename).encode())
        digest.update(self._safe_path("topology", "services.yaml").read_bytes())
        return digest.hexdigest()

    def _public_text(self, incident_id: str, filename: str) -> str:
        try:
            return self._public_path(incident_id, filename).read_text(encoding="utf-8")
        except FileNotFoundError:
            if filename == "database.jsonl":
                return ""
            raise

    def _records(self, incident_id: str, source_type: str) -> list[EvidenceRecord]:
        case = self.load_case(incident_id)
        if source_type == "topology":
            raw = yaml.safe_load(
                self._safe_path("topology", "services.yaml").read_text(encoding="utf-8")
            )
            records = []
            for service, dependencies in raw["services"].items():
                if service not in case.services:
                    continue
                data = dict(
                    evidence_id=f"{incident_id}-T-{service}",
                    incident_id=incident_id,
                    source_type="topology",
                    service=service,
                    observed_at=case.started_at.isoformat(),
                    source_path="topology/services.yaml",
                    excerpt=f"{service} depends on: {', '.join(dependencies) or 'none'}",
                    metadata={"dependencies": dependencies},
                )
                records.append(EvidenceRecord.model_validate_json(json.dumps(data)))
            return records
        if source_type not in SOURCE_FILES:
            raise PermissionError("unknown evidence source")
        filename = SOURCE_FILES[source_type]
        if source_type == "metrics":
            path = self._public_path(incident_id, filename)
            with path.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            records = []
            for row in rows:
                data = dict(
                    evidence_id=row["evidence_id"],
                    incident_id=incident_id,
                    source_type="metrics",
                    service=row["service"],
                    observed_at=row["observed_at"],
                    source_path="public/metrics.csv",
                    excerpt=row["excerpt"],
                    metadata={
                        "metric_name": row["metric_name"],
                        "value": float(row["value"]),
                        "unit": row["unit"],
                    },
                )
                records.append(EvidenceRecord.model_validate_json(json.dumps(data)))
        else:
            records = [
                EvidenceRecord.model_validate_json(line)
                for line in self._public_text(incident_id, filename).splitlines()
                if line.strip()
            ]
        if any(
            record.incident_id != incident_id
            or record.source_type != source_type
            or record.source_path != f"public/{filename}"
            or record.service not in case.services
            for record in records
        ):
            raise ValueError("evidence provenance does not match public source")
        if len({record.evidence_id for record in records}) != len(records):
            raise ValueError("duplicate evidence IDs")
        if any(
            not set(record.metadata).issubset(METADATA_FIELDS[source_type]) for record in records
        ):
            raise ValueError("metadata must contain only raw observation fields")
        if source_type == "database" and any(
            record.metadata.get("category")
            not in {
                "connections",
                "active_sessions",
                "lock_waits",
                "slow_queries",
                "health_metrics",
            }
            for record in records
        ):
            raise ValueError("database evidence requires a known observation category")
        return records
