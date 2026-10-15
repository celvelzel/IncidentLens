"""Read public inputs and saved retests offline; never instantiate a provider."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from incident_lens.artifacts import load_replay
from incident_lens.evaluation.retest_provenance import retest_snapshot, snapshot_changes
from incident_lens.evaluation.termination import normalize_termination
from incident_lens.incidentbench.schemas import ExperimentProtocol


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_artifact(directory, project, expected):
    """Technical screening is never certification of real HTTP or semantic correctness."""
    required = ("trace.json", "result.json", "report.md", "verification.json", "scope.json")
    missing = [name for name in required if not (directory / name).is_file()]
    result = {"path": str(directory.resolve()), "missing": missing,
              "evidence_level": "UNIT", "live_verified": False, "g1_accepted": False,
              "semantic_review": None, "technical_matches_expectation": False}
    if missing:
        return result
    trace, state = load_replay(directory / "trace.json")
    raw = state.model_dump(mode="json")
    terminal = normalize_termination(raw)
    verification = read_json(directory / "verification.json")
    scope = read_json(directory / "scope.json")
    before = scope.get("retest_source_sha256")
    drift = snapshot_changes(before, retest_snapshot(project)) if before else None
    report = raw["report"]
    reasons = []
    origin = scope.get("execution_origin", "unknown")
    if origin in {"mock", "MockTransport", "FileQueueBridge", "continuation"}:
        reasons.append("nonlive_execution_origin")
    http_requests = verification.get("actual_http_requests")
    if (not isinstance(http_requests, int) or isinstance(http_requests, bool)
            or http_requests <= 0):
        reasons.append("no_measured_http_requests")
    if verification.get("bridge_requests", 0) or verification.get("new_http_requests") == 0:
        reasons.append("bridge_or_offline_continuation")
    if trace["provider"] != "real":
        reasons.append("mock_provider")
        result["evidence_level"] = "OFFLINE_MOCK"
    # A real envelope can also contain HTTP MockTransport or checkpoint continuation.
    # No saved legacy envelope authenticates execution origin; leave live_verified false.
    if not terminal["protocol_valid"] or not terminal["stop_completion"]:
        reasons.append("incomplete_stop_protocol")
    if terminal["runtime_failure"]:
        reasons.append("technical_failure")
    if drift is None or drift or verification.get("source_unchanged") is not True:
        reasons.append("source_drift_or_missing_lock")
    if verification.get("source_drift") != []:
        reasons.append("recorded_source_drift_or_missing_lock")
    if expected == "positive" and raw["incident_id"] != "incident_2001":
        reasons.append("unexpected_incident")
    if expected == "negative" and raw["incident_id"] != "incident_2002":
        reasons.append("unexpected_incident")
    if read_json(directory / "result.json") != report:
        reasons.append("result_trace_mismatch")
    if not (directory / "report.md").read_text(encoding="utf-8").strip():
        reasons.append("empty_report")
    positive = (report["status"] == "RESOLVED" and bool(report.get("root_cause"))
                and bool(report.get("supporting_evidence_ids"))
                and terminal["termination_reason"] == "DIAGNOSIS_READY")
    negative = (report["status"] == "INCONCLUSIVE" and report.get("root_cause") is None
                and terminal["termination_reason"] == "INCONCLUSIVE")
    if not (positive if expected == "positive" else negative):
        reasons.append("unexpected_diagnosis_outcome")
    result.update(incident_id=raw["incident_id"], expected=expected, termination=terminal,
                  source_drift=drift, blockers=sorted(set(reasons)),
                  technical_matches_expectation=not reasons,
                  provenance_status="UNVERIFIED_EXECUTION_ORIGIN",
                  artifact_sha256={name: digest(directory / name) for name in required})
    return result


def prepare_inputs(dataset, protocol_path, project, output):
    protocol = ExperimentProtocol.model_validate_json(protocol_path.read_text(encoding="utf-8-sig"))
    if protocol.formal or protocol.provider_id != "real" or protocol.cache_mode != "off":
        raise ValueError("requires nonformal real development protocol with cache off")
    if protocol.blindness_level != "development_visible":
        raise ValueError("requires development-visible protocol")
    public = dataset / "rca"
    # Enumerate and hash only the public runtime subtree; never traverse evaluator roots.
    if not public.is_dir() or public.is_symlink():
        raise ValueError("missing public RCA dataset")
    hashes = {}
    for path in sorted(public.rglob("*")):
        if path.is_symlink():
            raise ValueError("linked public data is not supported")
        if path.is_file():
            if "private" in path.relative_to(public).parts or "oracle" in path.name.lower():
                raise ValueError("private data in public runtime tree")
            hashes[str(path.relative_to(public))] = digest(path)
    for incident in ("incident_2001", "incident_2002"):
        if not (public / "incidents" / incident / "public").is_dir():
            raise ValueError(f"missing public case {incident}")
    commands = [[sys.executable, str(project / "scripts/retest_live_provider_fix.py"),
                 "--dataset", str(dataset.resolve()), "--protocol", str(protocol_path.resolve()),
                 "--incident", incident, "--variant", "full", "--out",
                 str(output / f"live-{incident}-REPLACE-WITH-UNIQUE-ID")]
                for incident in ("incident_2001", "incident_2002")]
    return {"dataset": str(dataset.resolve()), "public_sha256": hashes,
            "protocol": protocol.model_dump(mode="json"), "protocol_sha256": digest(protocol_path),
            "commands_argv_NOT_EXECUTED": commands,
            "configuration_match": "NOT_CHECKED_NO_CREDENTIAL_READ",
            "live_gate": "BLOCKED_AWAITING_USER", "real_requests": 0,
            "approval_required": "model/config and total request/token/cost/wall limits"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--positive-artifact", type=Path, action="append", default=[])
    parser.add_argument("--negative-artifact", type=Path, action="append", default=[])
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    args.out.mkdir(parents=True, exist_ok=False)
    try:
        report = prepare_inputs(args.dataset, args.protocol, project, args.out)
        report["source_sha256"] = retest_snapshot(project)
        report["artifacts"] = []
        for expected, paths in (("positive", args.positive_artifact),
                                ("negative", args.negative_artifact)):
            for path in paths:
                try:
                    report["artifacts"].append(inspect_artifact(path, project, expected))
                except (ValueError, OSError, KeyError, TypeError) as error:
                    report["artifacts"].append({"path": str(path), "g1_accepted": False,
                                                "error_type": type(error).__name__})
        code = 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        report = {"preflight": "FAIL", "error_type": type(error).__name__, "real_requests": 0}
        code = 1
    (args.out / "preflight.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.out.resolve()), "real_requests": 0, "exit_code": code}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
