"""Evaluator-only oracle access, bound to a persisted completed run."""

import hashlib
import json
import re
import stat
from pathlib import Path

from .schemas import BenchmarkOracle


def safe_path(value):
    """Reject links/reparse points in every ancestor, including the root."""
    path = Path(value).absolute()
    if ".." in Path(value).parts:
        raise PermissionError("unsafe evaluator path")
    try:
        for part in (*reversed(path.parents), path):
            info = part.lstat()
            if (
                part.is_symlink()
                or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
            ):
                raise PermissionError("unsafe evaluator path")
        return path.resolve(strict=True)
    except OSError:
        raise PermissionError("evaluator resource unavailable") from None


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


class OracleStore:
    def __init__(self, root, public_root=None):
        self.root = safe_path(root)
        if not self.root.is_dir():
            raise PermissionError("invalid evaluator root")
        if public_root is not None:
            public = safe_path(public_root)
            if self.root.is_relative_to(public) or public.is_relative_to(self.root):
                raise PermissionError("oracle root overlaps runtime data")
        # An oracle may never be inside a public evidence tree.
        if any(
            p.name in {"public", "data", "incidentbench_v1"}
            for p in self.root.parents
            if p.name != "local_oracles"
        ):
            # Versioned private roots under local_oracles are allowed.
            if "local_oracles" not in self.root.parts:
                raise PermissionError("oracle root overlaps runtime data")
        if (self.root / "topology").exists() or (self.root / "public_case_index.json").exists():
            raise PermissionError("oracle root overlaps runtime data")

    def load_after_completion(self, incident_id, completed_state):
        if not re.fullmatch(r"incident_[0-9]{3,}", incident_id):
            raise PermissionError("invalid oracle identity")
        state = dict(completed_state)
        receipt = state.pop("completion_receipt", None)
        report = state.get("report") or {}
        if (
            state.get("incident_id") != incident_id
            or not state.get("run_id")
            or report.get("incident_id") != incident_id
            or report.get("run_id") != state["run_id"]
            or report.get("status") not in {"RESOLVED", "INCONCLUSIVE", "ERROR"}
            or state.get("workflow_status") not in {"FINISHED", "FAILED"}
            or not receipt
        ):
            raise PermissionError("oracle requires matching completed run")
        try:
            raw = safe_path(receipt["path"]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != receipt["sha256"] or canonical(
                json.loads(raw)
            ) != canonical(state):
                raise PermissionError("completion receipt mismatch")
            candidate = (
                self.root / "rca" / "incidents" / incident_id / "private" / "benchmark_oracle.json"
            )
            if not safe_path(candidate).is_relative_to(self.root):
                raise PermissionError("oracle resource escapes evaluator root")
            oracle = BenchmarkOracle.model_validate_json(safe_path(candidate).read_bytes())
            if oracle.incident_id != incident_id:
                raise PermissionError("oracle identity mismatch")
            return oracle
        except (OSError, ValueError, KeyError, TypeError):
            raise PermissionError("invalid evaluator completion or oracle") from None
