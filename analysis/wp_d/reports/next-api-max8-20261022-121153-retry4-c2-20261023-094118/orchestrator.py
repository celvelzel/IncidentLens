"""Retry authorized failed slots of a frozen API batch without changing frozen inputs.

The batch runner cannot express "retry exactly these slots once" without either
re-running a just-failed attempt or rewriting the frozen manifest.  This script
therefore orchestrates the existing single-case entry point directly, reusing the
runner's provenance snapshot, artifact assessment, worker lease and stop logic.

Modes
  prepare   verify frozen inputs and original attempts; freeze a retry manifest
  execute   launch at most one new investigation per authorized slot (max 2 live)
  status    read-only progress report
  finalize  build the auditable 40-slot final selection and independent summary

Retry round 4: the ten still-failing slots, explicitly authorized on 2026-10-23.
Nine slots get attempt-004 parented on attempt-003; slot-001 gets attempt-005
parented on its round-3 attempt-004.  Concurrency is 2 by explicit user
authorization; frozen inputs, budgets and model parameters are unchanged, so
results are not strictly comparable to the original concurrency 8.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

CONTROL = Path(__file__).resolve().parent
PROJECT = CONTROL.parents[3]
BATCH = PROJECT / "results/v16/wp-d/next-api-max8-20261022-121153"
SLOTS = [
    "slot-001", "slot-004", "slot-010", "slot-020", "slot-022",
    "slot-026", "slot-028", "slot-032", "slot-035", "slot-039",
]
RETRY_ID = "next-api-max8-20261022-121153-retry4-c2-20261023-094118"
RETRY_ROUND = 4
ORIGINAL_ATTEMPT = "attempt-001"
OVERRIDE_CONCURRENCY = 2
# slot -> (parent attempt of this round, new attempt of this round)
TARGETS = {
    "slot-001": ("attempt-004", "attempt-005"),
    "slot-004": ("attempt-003", "attempt-004"),
    "slot-010": ("attempt-003", "attempt-004"),
    "slot-020": ("attempt-003", "attempt-004"),
    "slot-022": ("attempt-003", "attempt-004"),
    "slot-026": ("attempt-003", "attempt-004"),
    "slot-028": ("attempt-003", "attempt-004"),
    "slot-032": ("attempt-003", "attempt-004"),
    "slot-035": ("attempt-003", "attempt-004"),
    "slot-039": ("attempt-003", "attempt-004"),
}
FINGERPRINT_FIELDS = (
    "source_commit",
    "retest_source_sha256",
    "runtime_config_sha256",
    "dataset_revision",
    "effective_model_parameters",
)


def parent_attempt(slot):
    return TARGETS[slot][0]


def target_attempt(slot):
    return TARGETS[slot][1]

sys.path.insert(0, str(PROJECT / "src"))
sys.path.insert(0, str(PROJECT / "scripts"))

import run_wpd_batch as rwb  # noqa: E402
from incident_lens.evaluation.run_io import append_json, atomic_json  # noqa: E402
from incident_lens.incidentbench.experiment import execution_lock  # noqa: E402

OUTPUT_FILES = rwb.OUTPUT_FILES
NORMAL_REASONS = {"DIAGNOSIS_READY", "INCONCLUSIVE"}
NORMAL_OUTCOMES = {"SUCCESS", "ABSTAINED"}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc_now():
    return time.time()


def tree_hashes(root):
    root = Path(root)
    return {
        str(path.relative_to(root)).replace("\\", "/"): digest(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def verify_frozen(manifest):
    mismatches = []
    for relative, expected in manifest["hashes"].items():
        path = PROJECT / relative
        if not path.is_file():
            mismatches.append({"path": relative, "expected": expected, "actual": None})
            continue
        actual = digest(path)
        if actual != expected:
            mismatches.append({"path": relative, "expected": expected, "actual": actual})
    return {"checked": len(manifest["hashes"]), "mismatches": mismatches}


def verify_manifest_unchanged(frozen_sha256):
    actual = digest(BATCH / "batch-manifest.json")
    return actual, actual == frozen_sha256


def slot_key(manifest, slot):
    index = int(slot.split("-")[1]) - 1
    return manifest["order"][index]


VERIFICATION_FIELDS = (
    "protocol_valid", "source_unchanged", "stop_completion",
    "runtime_failure", "termination",
)


def verify_attempt_record(manifest, slot, attempt, expected_path, key, label):
    if attempt.get("path") != expected_path:
        raise ValueError(f"{slot} {label} path mismatch")
    if attempt.get("key") != key:
        raise ValueError(f"{slot} {label} key mismatch")
    if attempt.get("status") != "failed":
        raise ValueError(f"{slot} {label} state status is not failed")
    directory = BATCH / expected_path
    if not directory.is_dir():
        raise ValueError(f"{slot} {label} directory missing")
    artifacts = attempt.get("artifacts") or {}
    if set(artifacts) != set(OUTPUT_FILES):
        raise ValueError(f"{slot} {label} lacks complete artifact receipt")
    for name, expected in artifacts.items():
        if digest(directory / name) != expected:
            raise ValueError(f"{slot} {label} artifact changed: {name}")
    assessed = rwb.assess(directory, key, manifest)
    if assessed != "failed":
        raise ValueError(f"{slot} {label} is not a technical failure: {assessed}")
    return directory, artifacts


def verify_original_attempts(manifest, state, slots):
    records = {}
    for slot in slots:
        key = slot_key(manifest, slot)
        attempts = state["slots"].get(slot, [])
        parent_name = parent_attempt(slot)
        expected_count = int(parent_name.split("-")[1])
        if len(attempts) != expected_count:
            raise ValueError(
                f"{slot} expected {expected_count} saved attempts up to {parent_name}, "
                f"found {len(attempts)}"
            )
        verified = []
        for number in range(1, expected_count + 1):
            label = f"attempt-{number:03d}"
            path = f"runs/{slot}/{label}"
            directory, artifacts = verify_attempt_record(
                manifest, slot, attempts[number - 1], path, key, label
            )
            verified.append((label, directory, artifacts))
        original_label, original_dir, original_artifacts = verified[0]
        parent_label, parent_dir, _ = verified[-1]
        original_verification = read(original_dir / "verification.json")
        parent_verification = read(parent_dir / "verification.json")
        records[slot] = {
            "key": key,
            "original_attempt": f"runs/{slot}/{original_label}",
            "original_status": attempts[0]["status"],
            "original_assessed": "failed",
            "original_artifacts": original_artifacts,
            "original_verification": {
                name: original_verification.get(name) for name in VERIFICATION_FIELDS
            },
            "parent_attempt": f"runs/{slot}/{parent_label}",
            "parent_status": attempts[-1]["status"],
            "parent_assessed": "failed",
            "parent_verification": {
                name: parent_verification.get(name) for name in VERIFICATION_FIELDS
            },
            "history": [
                {"attempt": f"runs/{slot}/{label}", "status": attempts[index]["status"]}
                for index, (label, _, _) in enumerate(verified)
            ],
            "attempts": attempts,
        }
    return records


def scan_new_attempts(slot):
    path = BATCH / "runs" / slot / target_attempt(slot)
    return [path] if path.is_dir() else []


def lease_free(slot):
    directory = BATCH / "worker-leases" / slot
    if not directory.is_dir():
        return True, "lease directory absent"
    try:
        with execution_lock(directory):
            return True, "lease acquired and released"
    except ValueError:
        return False, "lease is held by another worker"
    except PermissionError as exc:
        return False, f"lease path unsafe: {exc}"


def preflight(manifest, state, slots):
    checked = {}
    for slot in slots:
        record = checked.setdefault(slot, {})
        record["new_attempt_dirs"] = [str(p.relative_to(BATCH)) for p in scan_new_attempts(slot)]
        allowed = {
            f"attempt-{number:03d}"
            for number in range(1, int(parent_attempt(slot).split("-")[1]) + 1)
        }
        record["allowed_attempt_dirs"] = sorted(allowed)
        record["unexpected_attempt_dirs"] = [
            str(p.relative_to(BATCH))
            for p in scan_attempt_dirs(slot)
            if p.name not in allowed
        ]
        record["lease_free"], record["lease_detail"] = lease_free(slot)
        record["state_attempts"] = [a.get("path") for a in state["slots"].get(slot, [])]
        record["worker_alive"] = [
            a.get("pid") for a in state["slots"].get(slot, [])
            if a.get("status") == "running" and rwb.alive(a.get("pid"))
        ]
    return checked


def assert_preflight_clean(manifest, state, slots):
    report = preflight(manifest, state, slots)
    problems = []
    for slot, record in report.items():
        if record["new_attempt_dirs"]:
            problems.append(f"{slot} already has a {target_attempt(slot)} directory")
        if record["unexpected_attempt_dirs"]:
            problems.append(f"{slot} has unexpected attempt directories")
        if not record["lease_free"]:
            problems.append(f"{slot} lease conflict: {record['lease_detail']}")
        if record["worker_alive"]:
            problems.append(f"{slot} recorded worker still alive")
    if problems:
        raise RuntimeError("; ".join(problems))
    return report


def readiness_authorization(manifest):
    external = manifest.get("external") or {}
    return {
        "readiness_sha256": external.get("readiness_sha256"),
        "endpoint_sha256": external.get("endpoint_sha256"),
        "thinking_env": external.get("thinking_env"),
        "authorization": "original batch manifest readiness record; not re-created or modified",
    }


def endpoint_sha256():
    value = os.getenv("INCIDENT_LENS_BASE_URL")
    if not value:
        raise ValueError("INCIDENT_LENS_BASE_URL is missing")
    return hashlib.sha256(value.encode()).hexdigest()


def provider_environment(manifest):
    from dotenv import load_dotenv

    load_dotenv(PROJECT / ".env", override=False)
    protocol = manifest["protocol"]
    model = os.getenv("INCIDENT_LENS_MODEL")
    if model != protocol["model_id"]:
        raise ValueError("configured model does not match frozen protocol")
    if not os.getenv("INCIDENT_LENS_API_KEY"):
        raise ValueError("INCIDENT_LENS_API_KEY is missing")
    actual_endpoint = endpoint_sha256()
    expected_endpoint = (manifest.get("external") or {}).get("endpoint_sha256")
    if expected_endpoint and actual_endpoint != expected_endpoint:
        raise ValueError("provider endpoint differs from original batch manifest")
    return {
        "model_id": model,
        "endpoint_sha256": actual_endpoint,
        "endpoint_matches_original": actual_endpoint == expected_endpoint,
        "thinking_env": os.getenv("INCIDENT_LENS_THINKING"),
        "api_key_present": True,
    }


def original_scope(slot):
    return read(BATCH / "runs" / slot / ORIGINAL_ATTEMPT / "scope.json")


def scope_fingerprint(slot, attempt):
    value = read(BATCH / "runs" / slot / attempt / "scope.json")
    return {name: value.get(name) for name in FINGERPRINT_FIELDS}


def plan_snapshot(manifest, state, slots, preflight_report):
    protocol = manifest["protocol"]
    plan = manifest["plan"]
    records = verify_original_attempts(manifest, state, slots)
    frozen = verify_frozen(manifest)
    if frozen["mismatches"]:
        raise RuntimeError(f"{len(frozen['mismatches'])} frozen inputs differ from batch manifest")
    manifest_sha256 = digest(BATCH / "batch-manifest.json")
    all_slots = [f"slot-{i + 1:03d}" for i in range(len(manifest["order"]))]
    fingerprints = {
        slot: scope_fingerprint(slot, ORIGINAL_ATTEMPT) for slot in all_slots
    }
    baseline = fingerprints[all_slots[0]]
    for slot, value in fingerprints.items():
        if value != baseline:
            raise ValueError(f"{slot} original scope fingerprint differs")
    for slot in slots:
        if scope_fingerprint(slot, parent_attempt(slot)) != fingerprints[slot]:
            raise ValueError(f"{slot} {parent_attempt(slot)} scope fingerprint differs")
    current_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=PROJECT, text=True
    ).strip()
    if current_commit != baseline["source_commit"]:
        raise ValueError("working tree commit differs from original scope source_commit")
    historical_trees = {}
    for slot in all_slots:
        for directory in scan_attempt_dirs(slot):
            historical_trees[f"{slot}/{directory.name}"] = tree_hashes(directory)
    entries = []
    for slot in slots:
        record = records[slot]
        key = record["key"]
        entries.append({
            "slot": slot,
            "key": key,
            "incident": key["incident"],
            "variant": key["variant"],
            "repeat": key["repeat"],
            "original_attempt": record["original_attempt"],
            "original_status": record["original_status"],
            "original_assessed": record["original_assessed"],
            "original_artifacts": record["original_artifacts"],
            "original_verification": record["original_verification"],
            "parent_attempt": record["parent_attempt"],
            "parent_status": record["parent_status"],
            "parent_assessed": record["parent_assessed"],
            "parent_verification": record["parent_verification"],
            "history": record["history"],
            "new_attempt": f"runs/{slot}/{target_attempt(slot)}",
            "new_attempt_exists": bool(scan_new_attempts(slot)),
        })
    return {
        "schema_version": 1,
        "retry_id": RETRY_ID,
        "retry_round": RETRY_ROUND,
        "created_at_utc": utc_now(),
        "batch_dir": str(BATCH.relative_to(PROJECT)),
        "batch_manifest_sha256": manifest_sha256,
        "frozen_inputs": {"checked": frozen["checked"], "mismatches": frozen["mismatches"]},
        "original_attempts_checked": len(slots),
        "original_attempt": ORIGINAL_ATTEMPT,
        "attempt_targets": {
            slot: {"parent": parent_attempt(slot), "target": target_attempt(slot)}
            for slot in slots
        },
        "historical_trees_before": historical_trees,
        "protocol": protocol,
        "plan": plan,
        "original_batch_max_concurrency": manifest["max_concurrency"],
        "max_concurrency": OVERRIDE_CONCURRENCY,
        "concurrency_override": {
            "authorized": True,
            "authorized_by": (
                "explicit user instruction 2026-10-23: 授权全部 10 个槽位重跑，"
                "slot-001 用 attempt-005，并发数设置为 2"
            ),
            "from": manifest["max_concurrency"],
            "to": OVERRIDE_CONCURRENCY,
            "reason": (
                "round-1 retry at concurrency 8 exhausted HTTP 429 retries; "
                "lower concurrency reduces the simultaneous request burst"
            ),
            "frozen_inputs_unchanged": True,
            "model_parameters_unchanged": True,
            "comparability_note": (
                "retry round 4 uses a different worker concurrency than the "
                "original batch; results are not a strictly fair comparison"
            ),
        },
        "drop_concurrency": False,
        "stop_on_failure": plan.get("stop_on_failure", True),
        "readiness": readiness_authorization(manifest),
        "readiness_mode": "skipped_per_original_batch_manifest",
        "provider_environment": provider_environment(manifest),
        "source_commit": current_commit,
        "retest_source_sha256": baseline["retest_source_sha256"],
        "runtime_config_sha256": baseline["runtime_config_sha256"],
        "dataset_revision": baseline["dataset_revision"],
        "effective_model_parameters": baseline["effective_model_parameters"],
        "python": sys.version,
        "platform": sys.platform,
        "slots": entries,
        "order": [entry["slot"] for entry in entries],
        "pending_slots": [e["slot"] for e in entries if not e["new_attempt_exists"]],
        "preflight": preflight_report,
        "selection_rule": "completed_resolved_or_completed_inconclusive_replaces_technical_failure_only",
    }


def cmd_prepare(args):
    manifest = read(BATCH / "batch-manifest.json")
    state = read(BATCH / "batch-state.json")
    slots = args.slots
    if len(slots) != len(set(slots)):
        raise ValueError("duplicate slots")
    expected = [f"slot-{i + 1:03d}" for i in range(len(manifest["order"]))]
    for slot in slots:
        if slot not in expected:
            raise ValueError(f"unknown slot {slot}")
        if state["slots"].get(slot, [{}])[0].get("status") != "failed":
            raise ValueError(f"{slot} is not recorded as failed")
    if manifest["max_concurrency"] != manifest["protocol"]["jobs"]:
        raise ValueError("frozen concurrency differs from protocol jobs")
    if args.max_concurrency != OVERRIDE_CONCURRENCY:
        raise ValueError(
            f"requested concurrency {args.max_concurrency} differs from "
            f"authorized retry concurrency {OVERRIDE_CONCURRENCY}"
        )
    report = assert_preflight_clean(manifest, state, slots)
    snapshot = plan_snapshot(manifest, state, slots, report)
    if snapshot["frozen_inputs"]["mismatches"]:
        raise RuntimeError("frozen input drift; refusing to prepare")
    manifest_path = CONTROL / "retry-manifest.json"
    if manifest_path.exists():
        raise ValueError("retry manifest already exists; refusing to rewrite")
    atomic_json(manifest_path, snapshot)
    (CONTROL / "retry-manifest.sha256").write_text(digest(manifest_path) + "\n", encoding="utf-8")
    state_out = {
        "schema_version": 1,
        "retry_id": RETRY_ID,
        "state": "prepared",
        "created_at_utc": snapshot["created_at_utc"],
        "max_concurrency": snapshot["max_concurrency"],
        "stop_on_failure": snapshot["stop_on_failure"],
        "slots": {
            entry["slot"]: {
                "status": "pending",
                "attempt": entry["new_attempt"],
                "parent_attempt": entry["parent_attempt"],
            }
            for entry in snapshot["slots"]
        },
        "order": [entry["slot"] for entry in snapshot["slots"]],
    }
    atomic_json(CONTROL / "retry-state.json", state_out)
    print(json.dumps({
        "mode": "prepare",
        "retry_id": RETRY_ID,
        "retry_round": RETRY_ROUND,
        "retry_manifest": str(manifest_path),
        "retry_manifest_sha256": digest(manifest_path),
        "slots": len(slots),
        "pending": len(snapshot["pending_slots"]),
        "frozen_inputs": snapshot["frozen_inputs"],
        "preflight_clean": True,
        "provider": snapshot["provider_environment"],
        "stop_on_failure": snapshot["stop_on_failure"],
        "original_batch_max_concurrency": snapshot["original_batch_max_concurrency"],
        "max_concurrency": snapshot["max_concurrency"],
        "concurrency_override": snapshot["concurrency_override"],
    }, ensure_ascii=False, indent=2))


def load_frozen_for_execute(args):
    manifest_path = CONTROL / "retry-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("retry manifest missing; run prepare first")
    expected_sha = (CONTROL / "retry-manifest.sha256").read_text(encoding="utf-8").strip()
    actual_sha = digest(manifest_path)
    if actual_sha != expected_sha:
        raise ValueError("retry manifest changed after prepare")
    frozen = read(manifest_path)
    if frozen.get("retry_id") != RETRY_ID:
        raise ValueError("retry identity mismatch")
    if frozen["provider_environment"]["endpoint_sha256"] != endpoint_sha256():
        raise ValueError("provider endpoint differs from frozen retry manifest")
    if frozen["provider_environment"]["model_id"] != os.getenv("INCIDENT_LENS_MODEL"):
        raise ValueError("provider model differs from frozen retry manifest")
    actual_manifest, unchanged = verify_manifest_unchanged(frozen["batch_manifest_sha256"])
    if not unchanged:
        raise ValueError("batch manifest changed after prepare")
    drift = verify_frozen(read(BATCH / "batch-manifest.json"))
    if drift["mismatches"]:
        raise ValueError("frozen input drift after prepare")
    state = read(BATCH / "batch-state.json")
    for name, before in frozen["historical_trees_before"].items():
        slot, attempt = name.split("/", 1)
        if tree_hashes(BATCH / "runs" / slot / attempt) != before:
            raise ValueError(f"{slot} {attempt} tree changed after prepare")
    return frozen, state, actual_manifest


def append_batch_event(kind, **details):
    append_json(BATCH / "batch-events.jsonl", {"time_utc": utc_now(), "event": kind, **details})


def update_retry_state(state_out):
    atomic_json(CONTROL / "retry-state.json", state_out)


def start_worker(frozen, state, slot, entry, launched_at):
    relative = entry["new_attempt"]
    attempt_dir = BATCH / relative
    if attempt_dir.exists():
        raise RuntimeError(f"{slot} new attempt directory already exists")
    log_dir = BATCH / "supervisor" / slot / target_attempt(slot)
    log_dir.mkdir(parents=True, exist_ok=False)
    state_attempt = {
        "path": relative,
        "status": "running",
        "pid": None,
        "key": entry["key"],
        "started_at_utc": launched_at,
        "parent_attempt": entry["parent_attempt"],
        "retry_of": entry["original_attempt"],
        "retry_id": RETRY_ID,
        "retry_round": RETRY_ROUND,
        "retry_manifest_sha256": (CONTROL / "retry-manifest.sha256").read_text(encoding="utf-8").strip(),
        "retry_reason": "authorized_technical_failure_retry_round_4",
    }
    state["slots"][slot].append(state_attempt)
    rwb.atomic_json(BATCH / "batch-state.json", state)
    append_batch_event(
        "RETRY_SLOT_START_INTENT", slot=slot, attempt=relative,
        parent_attempt=entry["parent_attempt"], retry_id=RETRY_ID,
    )
    command = [
        sys.executable, "-B", "-u",
        str(PROJECT / "scripts/retest_live_provider_fix.py"),
        "--dataset", str(PROJECT / frozen["plan"]["dataset"]),
        "--protocol", str(PROJECT / frozen["plan"]["protocol"]),
        "--incident", entry["incident"],
        "--variant", entry["variant"],
        "--out", str(attempt_dir),
        "--lease-directory", str(BATCH / "worker-leases" / slot),
        "--runtime-config", str(PROJECT / frozen["plan"]["runtime_config"]),
    ]
    state_attempt["command"] = command
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(PROJECT / "src")
    environment["PYTHONUTF8"] = "1"
    stdout_path = log_dir / "stdout.log"
    stderr_path = log_dir / "stderr.log"
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        try:
            process = subprocess.Popen(
                command,
                cwd=PROJECT,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                close_fds=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )
        except BaseException as exc:
            state_attempt.update({
                "status": "failed",
                "ended_at_utc": utc_now(),
                "exit_code": None,
                "error": f"{type(exc).__name__}: {exc}",
                "artifacts": {},
            })
            rwb.atomic_json(BATCH / "batch-state.json", state)
            append_batch_event(
                "RETRY_WORKER_START_FAILED", slot=slot, attempt=relative,
                error_type=type(exc).__name__, retry_id=RETRY_ID,
            )
            raise
    state_attempt["pid"] = process.pid
    rwb.atomic_json(BATCH / "batch-state.json", state)
    append_batch_event(
        "RETRY_SLOT_DISPATCHED", slot=slot, attempt=relative, pid=process.pid,
        parent_attempt=entry["parent_attempt"], retry_id=RETRY_ID,
    )
    return process, state_attempt


def write_provenance(frozen, entry, state_attempt, status, exit_code, error, artifacts):
    attempt_dir = BATCH / entry["new_attempt"]
    if not attempt_dir.is_dir():
        return
    payload = {
        "schema_version": 1,
        "retry_id": RETRY_ID,
        "retry_round": RETRY_ROUND,
        "retry_manifest_sha256": state_attempt["retry_manifest_sha256"],
        "concurrency_override": frozen.get("concurrency_override"),
        "slot": entry["slot"],
        "incident": entry["incident"],
        "variant": entry["variant"],
        "repeat": entry["repeat"],
        "original_attempt": entry["original_attempt"],
        "parent_attempt": entry["parent_attempt"],
        "attempt": entry["new_attempt"],
        "started_at_utc": state_attempt["started_at_utc"],
        "ended_at_utc": state_attempt.get("ended_at_utc"),
        "status": status,
        "exit_code": exit_code,
        "error": error,
        "input_fingerprints": {
            "batch_manifest_sha256": frozen["batch_manifest_sha256"],
            "retest_source_sha256": frozen["retest_source_sha256"],
            "runtime_config_sha256": frozen["runtime_config_sha256"],
            "dataset_revision": frozen["dataset_revision"],
            "effective_model_parameters": frozen["effective_model_parameters"],
        },
        "readiness_mode": frozen["readiness_mode"],
        "readiness": frozen["readiness"],
        "command": state_attempt.get("command"),
        "artifacts": artifacts,
    }
    path = attempt_dir / "retry-provenance.json"
    try:
        atomic_json(path, payload)
    except FileExistsError:
        pass


def finish_worker(frozen, state, state_out, slot, entry, process, state_attempt, cause=None):
    exit_code = process.poll()
    state_attempt["ended_at_utc"] = utc_now()
    state_attempt["exit_code"] = exit_code
    attempt_dir = BATCH / entry["new_attempt"]
    error = None
    artifacts = {}
    try:
        artifacts = rwb.artifact_hashes(attempt_dir)
    except (OSError, KeyError, ValueError) as exc:
        error = f"{type(exc).__name__}: {exc}"
    try:
        assessed = rwb.assess(attempt_dir, entry["key"], read(BATCH / "batch-manifest.json"))
    except (OSError, KeyError, ValueError) as exc:
        assessed = "failed"
        if error is None:
            error = f"{type(exc).__name__}: {exc}"
    if cause:
        status = "interrupted"
    elif exit_code == 0 and assessed == "completed":
        status = "completed"
    else:
        status = "failed"
        if exit_code not in (0, None) and error is None:
            error = f"worker exited with code {exit_code}"
    state_attempt["status"] = status
    state_attempt["assessed"] = assessed
    state_attempt["artifacts"] = artifacts
    if error:
        state_attempt["error"] = error
    state_out["slots"][slot].update({
        "status": status,
        "assessed": assessed,
        "exit_code": exit_code,
        "ended_at_utc": state_attempt["ended_at_utc"],
        "error": error,
        "artifacts": artifacts,
    })
    rwb.atomic_json(BATCH / "batch-state.json", state)
    update_retry_state(state_out)
    write_provenance(frozen, entry, state_attempt, status, exit_code, error, artifacts)
    append_batch_event(
        "RETRY_SLOT_ENDED", slot=slot, attempt=entry["new_attempt"], status=status,
        assessed=assessed, exit_code=exit_code, error=error, retry_id=RETRY_ID,
    )
    return status


def cmd_execute(args):
    frozen, state, _ = load_frozen_for_execute(args)
    retry_state = read(CONTROL / "retry-state.json")
    if retry_state.get("state") != "prepared":
        raise ValueError("retry state is not prepared; refusing to launch a second time")
    if retry_state["max_concurrency"] != frozen["max_concurrency"]:
        raise ValueError("retry state concurrency drift")
    order = [s for s in frozen["pending_slots"]]
    if not order:
        raise ValueError("no pending slots")
    if len(order) != len(set(order)):
        raise ValueError("duplicate pending slots")
    preflight_report = assert_preflight_clean(
        read(BATCH / "batch-manifest.json"), state, order
    )
    (CONTROL / "batch-state.before-retry.json").write_bytes(
        (BATCH / "batch-state.json").read_bytes()
    )
    retry_state["state"] = "running"
    retry_state["started_at_utc"] = utc_now()
    retry_state["preflight"] = preflight_report
    for slot in frozen["order"]:
        retry_state["slots"][slot]["status"] = (
            "pending" if slot in order else "not_started_no_new_attempt"
        )
    update_retry_state(retry_state)
    append_batch_event(
        "RETRY_EXECUTION_STARTED", retry_id=RETRY_ID, retry_round=RETRY_ROUND,
        retry_manifest_sha256=digest(CONTROL / "retry-manifest.json"),
        slots=frozen["order"], pending=order,
        max_concurrency=frozen["max_concurrency"],
        original_batch_max_concurrency=frozen.get("original_batch_max_concurrency"),
        concurrency_override=frozen.get("concurrency_override"),
        readiness_mode=frozen["readiness_mode"],
    )
    print(json.dumps({
        "mode": "execute", "retry_id": RETRY_ID, "pending": order,
        "max_concurrency": frozen["max_concurrency"],
        "stop_on_failure": frozen["stop_on_failure"],
    }, ensure_ascii=False, indent=2))

    entries = {e["slot"]: e for e in frozen["slots"]}
    running = {}
    index = 0
    paused = False
    stopped = False
    failure_reason = None
    shutdown_cause = "orchestrator_shutdown"
    limit = frozen["protocol"]["max_wall_seconds"] + 120
    last_heartbeat = 0.0
    error = None

    def write_retry_status(name):
        now = utc_now()
        active_entries = []
        for slot, worker in running.items():
            active_entries.append({
                "slot": slot,
                "attempt": worker["entry"]["new_attempt"],
                "worker_pid": worker["process"].pid,
                "incident": worker["entry"]["incident"],
                "variant": worker["entry"]["variant"],
                "started_at_utc": worker["started"],
                "worker_elapsed_seconds": now - worker["started"],
                "poll": worker["process"].poll(),
            })
        atomic_json(CONTROL / "retry-supervisor-status.json", {
            "schema_version": 1,
            "retry_id": RETRY_ID,
            "state": name,
            "parent_pid": os.getpid(),
            "heartbeat_utc": now,
            "max_concurrency": frozen["max_concurrency"],
            "dispatched": index,
            "pending_to_dispatch": len(order) - index,
            "active": active_entries,
            "counts": {
                status: sum(
                    1 for s in order if retry_state["slots"][s]["status"] == status
                )
                for status in ("pending", "running", "completed", "failed", "interrupted")
            },
        })

    try:
        with execution_lock(BATCH):
            while True:
                if (BATCH / "STOP_REQUESTED").exists():
                    stopped = True
                    shutdown_cause = "stop_requested"
                    failure_reason = "STOP_REQUESTED present"
                    break
                now = utc_now()
                overdue = [
                    slot for slot, worker in running.items()
                    if worker["process"].poll() is None
                    and now - worker["started"] > limit
                ]
                if overdue:
                    stopped = True
                    shutdown_cause = "wall_timeout"
                    failure_reason = "wall timeout"
                    break
                # Reap exits before filling free lanes, so an observed failure
                # stops dispatch exactly as the original supervisor does.
                finished = []
                for slot, worker in list(running.items()):
                    if worker["process"].poll() is None:
                        continue
                    status = finish_worker(
                        frozen, state, retry_state, slot, worker["entry"],
                        worker["process"], worker["state_attempt"],
                    )
                    running.pop(slot)
                    finished.append(status)
                if any(status != "completed" for status in finished):
                    failure_reason = failure_reason or "slot technical failure"
                    if frozen["stop_on_failure"]:
                        paused = True
                while not paused and index < len(order) and len(running) < frozen["max_concurrency"]:
                    if (BATCH / "STOP_REQUESTED").exists():
                        stopped = True
                        shutdown_cause = "stop_requested"
                        failure_reason = "STOP_REQUESTED present"
                        break
                    slot = order[index]
                    entry = entries[slot]
                    drift = verify_frozen(read(BATCH / "batch-manifest.json"))
                    if drift["mismatches"]:
                        stopped = True
                        shutdown_cause = "frozen_input_drift"
                        failure_reason = "frozen input drift before dispatch"
                        break
                    for running_slot in running:
                        if running[running_slot]["entry"]["original_attempt"] == entry["original_attempt"]:
                            raise RuntimeError("duplicate slot dispatch")
                    launched_at = utc_now()
                    try:
                        process, state_attempt = start_worker(
                            frozen, state, slot, entry, launched_at
                        )
                    except BaseException as exc:
                        retry_state["slots"][slot]["status"] = "failed"
                        retry_state["slots"][slot]["error"] = f"{type(exc).__name__}: {exc}"
                        update_retry_state(retry_state)
                        raise
                    index += 1
                    running[slot] = {
                        "process": process, "entry": entry, "state_attempt": state_attempt,
                        "started": launched_at,
                    }
                    retry_state["slots"][slot]["status"] = "running"
                    update_retry_state(retry_state)
                    write_retry_status("retry_running")
                if stopped:
                    break
                if not running:
                    if paused and index < len(order):
                        unstarted = order[index:]
                        append_batch_event(
                            "RETRY_PAUSED_AFTER_FAILURE", retry_id=RETRY_ID,
                            failed=[s for s in order if retry_state["slots"][s]["status"] == "failed"],
                            unstarted=unstarted,
                        )
                        retry_state.setdefault("pauses", []).append({
                            "time_utc": utc_now(),
                            "failed": [s for s in order if retry_state["slots"][s]["status"] == "failed"],
                            "unstarted": unstarted,
                        })
                        retry_state["state"] = "paused_after_failure"
                        update_retry_state(retry_state)
                        paused = False
                        append_batch_event(
                            "RETRY_RESUMED_AFTER_FAILURE", retry_id=RETRY_ID,
                            resume_slots=unstarted,
                            note="failed slots are never relaunched; each remaining slot gets one new attempt",
                        )
                        retry_state["state"] = "running"
                        update_retry_state(retry_state)
                        continue
                    if paused or index >= len(order):
                        break
                    continue
                if finished:
                    write_retry_status("retry_running")
                    continue
                if utc_now() - last_heartbeat >= 10:
                    last_heartbeat = utc_now()
                    write_retry_status("retry_paused_after_failure" if paused else "retry_running")
                time.sleep(2)
    except BaseException as exc:
        error = exc
        shutdown_cause = "supervisor_exception"
        failure_reason = failure_reason or f"{type(exc).__name__}: {exc}"
        raise
    finally:
        for slot, worker in list(running.items()):
            process = worker["process"]
            if process.poll() is None:
                rwb.stop_child(process)
                finish_worker(
                    frozen, state, retry_state, slot, worker["entry"],
                    process, worker["state_attempt"], cause=shutdown_cause,
                )
            else:
                finish_worker(
                    frozen, state, retry_state, slot, worker["entry"],
                    process, worker["state_attempt"],
                )
            running.pop(slot, None)
        if error is not None or stopped:
            retry_state["state"] = "stopped"
        elif index >= len(order):
            failed_slots = [
                s for s in order if retry_state["slots"][s]["status"] == "failed"
            ]
            retry_state["state"] = "finished_with_errors" if failed_slots else "finished"
        elif paused:
            retry_state["state"] = "paused_after_failure"
        else:
            failed_slots = [
                s for s in order if retry_state["slots"][s]["status"] == "failed"
            ]
            retry_state["state"] = "finished_with_errors" if failed_slots else "finished"
        retry_state["ended_at_utc"] = utc_now()
        retry_state["failure_reason"] = failure_reason
        for slot in order:
            if retry_state["slots"][slot]["status"] == "pending":
                retry_state["slots"][slot]["status"] = "not_started_due_to_failure_pause"
        update_retry_state(retry_state)
        write_retry_status("retry_stopped" if retry_state["state"] == "stopped" else retry_state["state"])
        append_batch_event(
            "RETRY_EXECUTION_ENDED", retry_id=RETRY_ID, state=retry_state["state"],
            failure_reason=failure_reason, launched=index,
            pending_not_started=[
                s for s in order if retry_state["slots"][s]["status"] == "not_started_due_to_failure_pause"
            ],
        )
    print(json.dumps({
        "mode": "execute", "state": retry_state["state"],
        "failure_reason": failure_reason,
        "slots": {
            s: retry_state["slots"][s]["status"] for s in frozen["order"]
        },
    }, ensure_ascii=False, indent=2))


def cmd_status(args):
    retry_state = read(CONTROL / "retry-state.json") if (CONTROL / "retry-state.json").exists() else {}
    print(json.dumps(retry_state, ensure_ascii=False, indent=2))


def usage_for_attempt(directory):
    result = {"http_requests": None, "llm_requests": None, "total_tokens": None,
              "prompt_tokens": None, "completion_tokens": None, "measured": False}
    verification_path = Path(directory) / "verification.json"
    if verification_path.is_file():
        verification = read(verification_path)
        result.update({
            "http_requests": verification.get("actual_http_requests"),
            "llm_requests": verification.get("llm_requests"),
            "total_tokens": verification.get("measured_total_tokens"),
            "prompt_tokens": verification.get("measured_prompt_tokens"),
            "completion_tokens": verification.get("measured_completion_tokens"),
            "measured": True,
        })
        return result
    measured_path = Path(directory) / "measured-usage.json"
    if measured_path.is_file():
        measured = read(measured_path)
        calls = measured.get("calls") or []
        result["http_requests"] = len(calls)
        result["llm_requests"] = len(calls)
        result["total_tokens"] = sum(
            int(call.get("total_tokens") or 0) for call in calls if isinstance(call, dict)
        )
        result["prompt_tokens"] = sum(
            int(call.get("prompt_tokens") or 0) for call in calls if isinstance(call, dict)
        )
        result["completion_tokens"] = sum(
            int(call.get("completion_tokens") or 0) for call in calls if isinstance(call, dict)
        )
        result["measured"] = True
    return result


def attempt_eligibility(directory, key, manifest, original_scope_value):
    directory = Path(directory)
    checks = {}
    artifacts = {}
    try:
        artifacts = rwb.artifact_hashes(directory)
        checks["artifacts_complete"] = True
    except (OSError, KeyError, ValueError):
        checks["artifacts_complete"] = False
    try:
        checks["assess_completed"] = rwb.assess(directory, key, manifest) == "completed"
    except (OSError, KeyError, ValueError):
        checks["assess_completed"] = False
    verification = read(directory / "verification.json") if (directory / "verification.json").is_file() else {}
    checks["protocol_valid"] = verification.get("protocol_valid") is True
    checks["source_unchanged"] = verification.get("source_unchanged") is True
    checks["stop_completion"] = verification.get("stop_completion") is True
    checks["runtime_failure_false"] = verification.get("runtime_failure") is False
    termination = verification.get("termination") or {}
    checks["termination_reason_normal"] = termination.get("reason") in NORMAL_REASONS
    checks["termination_outcome_normal"] = termination.get("outcome") in NORMAL_OUTCOMES
    journal = read(directory / "observability/status.json") if (directory / "observability/status.json").is_file() else {}
    checks["journal_completed"] = journal.get("lifecycle") == "completed"
    checks["journal_healthy"] = not journal.get("observability", {}).get("degraded", True)
    scope = read(directory / "scope.json") if (directory / "scope.json").is_file() else {}
    checks["identity"] = (
        scope.get("incident_id") == key["incident"]
        and scope.get("variant") == key["variant"]
    )
    checks["protocol_match"] = scope.get("protocol") == manifest["protocol"]
    checks["source_commit_match"] = scope.get("source_commit") == original_scope_value.get("source_commit")
    checks["retest_source_match"] = (
        scope.get("retest_source_sha256") == original_scope_value.get("retest_source_sha256")
    )
    checks["runtime_config_match"] = (
        scope.get("runtime_config_sha256") == original_scope_value.get("runtime_config_sha256")
    )
    checks["dataset_revision_match"] = (
        scope.get("dataset_revision") == original_scope_value.get("dataset_revision")
    )
    checks["effective_model_parameters_match"] = (
        scope.get("effective_model_parameters") == original_scope_value.get("effective_model_parameters")
    )
    result = read(directory / "result.json") if (directory / "result.json").is_file() else {}
    trace = read(directory / "trace.json") if (directory / "trace.json").is_file() else {}
    trace_state = trace.get("state") or {}
    checks["result_identity"] = (
        result.get("run_id") is not None
        and result.get("run_id") == trace_state.get("run_id")
        and result.get("incident_id") == key["incident"]
        and trace.get("variant") == key["variant"]
    )
    checks["result_status_normal"] = result.get("status") in {"RESOLVED", "INCONCLUSIVE"}
    return all(checks.values()), checks, artifacts, verification, scope, result


def scan_attempt_dirs(slot):
    parent = BATCH / "runs" / slot
    if not parent.is_dir():
        return []
    return sorted(
        (p for p in parent.iterdir() if p.is_dir() and p.name.startswith("attempt-")),
        key=lambda p: int(p.name.split("-")[1]),
    )


def selected_class(verification, result):
    if (
        verification.get("protocol_valid") is True
        and verification.get("source_unchanged") is True
        and verification.get("stop_completion") is True
        and verification.get("runtime_failure") is False
    ):
        if result.get("status") == "RESOLVED":
            return "completed_resolved"
        if result.get("status") == "INCONCLUSIVE":
            return "completed_inconclusive"
        return "completed_other"
    return "technical_failure"


def cmd_finalize(args):
    manifest = read(BATCH / "batch-manifest.json")
    state = read(BATCH / "batch-state.json")
    frozen = read(CONTROL / "retry-manifest.json")
    frozen_sha = (CONTROL / "retry-manifest.sha256").read_text(encoding="utf-8").strip()
    if digest(CONTROL / "retry-manifest.json") != frozen_sha:
        raise ValueError("retry manifest changed after prepare")
    assembled = []
    for index, key in enumerate(manifest["order"]):
        slot = f"slot-{index + 1:03d}"
        attempts_on_disk = scan_attempt_dirs(slot)
        attempts = state["slots"].get(slot, [])
        known = {a["path"] for a in attempts}
        for directory in attempts_on_disk:
            relative = str(directory.relative_to(BATCH)).replace("\\", "/")
            if relative not in known:
                attempts.append({"path": relative, "status": "discovered"})
        attempts = sorted(attempts, key=lambda a: int(Path(a["path"]).name.split("-")[1]))
        original = attempts[0]
        original_dir = BATCH / original["path"]
        original_scope_value = read(original_dir / "scope.json") if (original_dir / "scope.json").is_file() else {}
        original_verification = read(original_dir / "verification.json") if (original_dir / "verification.json").is_file() else {}
        original_result = read(original_dir / "result.json") if (original_dir / "result.json").is_file() else {}
        original_class = selected_class(original_verification, original_result)
        original_record = {
            "attempt": original["path"],
            "status": original.get("status"),
            "class": original_class,
            "run_id": original_result.get("run_id"),
            "artifacts": original.get("artifacts", {}),
            "verification": {
                "protocol_valid": original_verification.get("protocol_valid"),
                "source_unchanged": original_verification.get("source_unchanged"),
                "stop_completion": original_verification.get("stop_completion"),
                "runtime_failure": original_verification.get("runtime_failure"),
                "termination": original_verification.get("termination"),
            },
            "usage": usage_for_attempt(original_dir),
        }
        candidates = []
        for attempt in attempts[1:]:
            directory = BATCH / attempt["path"]
            eligible, checks, artifacts, verification, scope, result = attempt_eligibility(
                directory, key, manifest, original_scope_value
            )
            candidates.append({
                "attempt": attempt["path"],
                "state_status": attempt.get("status"),
                "eligible": eligible,
                "checks": checks,
                "class": selected_class(verification, result),
                "run_id": result.get("run_id"),
                "artifacts": artifacts,
                "usage": usage_for_attempt(directory),
                "verification": {
                    "protocol_valid": verification.get("protocol_valid"),
                    "source_unchanged": verification.get("source_unchanged"),
                    "stop_completion": verification.get("stop_completion"),
                    "runtime_failure": verification.get("runtime_failure"),
                    "termination": verification.get("termination"),
                },
            })
        # Candidates are considered chronologically for every slot, so a slot that
        # was already replaced in an earlier retry round keeps that replacement
        # even though it is not part of this round's order.
        eligible_candidates = [c for c in candidates if c["eligible"]]
        if eligible_candidates:
            selected = eligible_candidates[0]
            if original_class == "technical_failure":
                reason = "original_technical_failure_replaced_by_completed_retry"
            else:
                reason = "original_completed_not_replaced"
        else:
            selected = original_record
            if original_class == "technical_failure":
                reason = "original_technical_failure_retained_no_eligible_retry"
            else:
                reason = "original_completed_not_rerun"
        slot_usage = {"http_requests": 0, "llm_requests": 0, "total_tokens": 0,
                      "prompt_tokens": 0, "completion_tokens": 0}
        for record in [original_record, *candidates]:
            for name in slot_usage:
                value = record["usage"].get(name)
                if isinstance(value, int):
                    slot_usage[name] += value
        assembled.append({
            "slot": slot,
            "incident": key["incident"],
            "variant": key["variant"],
            "repeat": key["repeat"],
            "original_attempt": original["path"],
            "selected_attempt": selected["attempt"],
            "selected_class": selected["class"],
            "selection_reason": reason,
            "selected_run_id": selected.get("run_id"),
            "selected_usage": selected.get("usage", {}),
            "original": original_record,
            "candidates": candidates,
            "all_attempts": [r["attempt"] for r in [original_record, *candidates]],
            "slot_usage_all_attempts": slot_usage,
        })
    frozen_after = verify_frozen(manifest)
    manifest_sha_after = digest(BATCH / "batch-manifest.json")
    historical_tree_after = {
        name: tree_hashes(BATCH / "runs" / name.split("/", 1)[0] / name.split("/", 1)[1])
        for name in frozen["historical_trees_before"]
    }
    historical_trees_unchanged = historical_tree_after == frozen["historical_trees_before"]
    counts = {
        "slots": len(assembled),
        "selected_completed_resolved": sum(1 for r in assembled if r["selected_class"] == "completed_resolved"),
        "selected_completed_inconclusive": sum(1 for r in assembled if r["selected_class"] == "completed_inconclusive"),
        "selected_completed_other": sum(1 for r in assembled if r["selected_class"] == "completed_other"),
        "selected_technical_failure": sum(1 for r in assembled if r["selected_class"] == "technical_failure"),
        "replaced_slots": sum(1 for r in assembled if r["selection_reason"].startswith("original_technical_failure_replaced")),
        "retained_failed_slots": sum(1 for r in assembled if r["selection_reason"].startswith("original_technical_failure_retained")),
        "extra_attempts": sum(len(r["all_attempts"]) - 1 for r in assembled),
    }
    totals = {"http_requests": 0, "llm_requests": 0, "total_tokens": 0,
              "prompt_tokens": 0, "completion_tokens": 0}
    for record in assembled:
        for name in totals:
            totals[name] += record["slot_usage_all_attempts"].get(name, 0) or 0
    by_variant = {}
    for record in assembled:
        bucket = by_variant.setdefault(record["variant"], {
            "slots": 0, "selected_completed_resolved": 0,
            "selected_completed_inconclusive": 0, "selected_technical_failure": 0,
            "replaced_slots": 0,
        })
        bucket["slots"] += 1
        bucket[f"selected_{record['selected_class']}"] = bucket.get(
            f"selected_{record['selected_class']}", 0
        ) + 1
        if record["selection_reason"].startswith("original_technical_failure_replaced"):
            bucket["replaced_slots"] += 1
    payload = {
        "schema_version": 1,
        "retry_id": RETRY_ID,
        "retry_round": RETRY_ROUND,
        "generated_at_utc": utc_now(),
        "batch_dir": str(BATCH.relative_to(PROJECT)),
        "retry_manifest_sha256": frozen_sha,
        "original_batch_max_concurrency": frozen.get("original_batch_max_concurrency"),
        "max_concurrency": frozen["max_concurrency"],
        "concurrency_override": frozen.get("concurrency_override"),
        "counts": counts,
        "usage_all_attempts": totals,
        "by_variant": by_variant,
        "integrity": {
            "frozen_inputs_checked": frozen_after["checked"],
            "frozen_input_mismatches": frozen_after["mismatches"],
            "batch_manifest_sha256_before": frozen["batch_manifest_sha256"],
            "batch_manifest_sha256_after": manifest_sha_after,
            "batch_manifest_unchanged": manifest_sha_after == frozen["batch_manifest_sha256"],
            "historical_attempt_trees_unchanged": historical_trees_unchanged,
            "historical_attempts_checked": len(frozen["historical_trees_before"]),
            "selection_valid": (
                not frozen_after["mismatches"]
                and manifest_sha_after == frozen["batch_manifest_sha256"]
                and historical_trees_unchanged
            ),
        },
        "slots": assembled,
    }
    atomic_json(CONTROL / "final-selection.json", payload)
    with (CONTROL / "final-selection.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow([
            "slot", "incident", "variant", "repeat", "original_attempt",
            "original_class", "selected_attempt", "selected_class", "selection_reason",
            "selected_run_id", "selected_http_requests", "selected_total_tokens",
            "all_attempts", "slot_http_requests_all_attempts", "slot_total_tokens_all_attempts",
        ])
        for record in assembled:
            writer.writerow([
                record["slot"], record["incident"], record["variant"], record["repeat"],
                record["original_attempt"], record["original"]["class"],
                record["selected_attempt"], record["selected_class"], record["selection_reason"],
                record["selected_run_id"] or "",
                record["selected_usage"].get("http_requests", ""),
                record["selected_usage"].get("total_tokens", ""),
                ";".join(record["all_attempts"]),
                record["slot_usage_all_attempts"]["http_requests"],
                record["slot_usage_all_attempts"]["total_tokens"],
            ])
    with (CONTROL / "final-matrix.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow([
            "incident", "variant", "slot", "selected_attempt", "selected_class",
            "selected_run_id",
        ])
        for record in assembled:
            writer.writerow([
                record["incident"], record["variant"], record["slot"],
                record["selected_attempt"], record["selected_class"],
                record["selected_run_id"] or "",
            ])
    print(json.dumps({
        "mode": "finalize", "counts": counts, "usage_all_attempts": totals,
        "integrity": payload["integrity"],
        "outputs": [
            str((CONTROL / "final-selection.json").relative_to(PROJECT)),
            str((CONTROL / "final-selection.csv").relative_to(PROJECT)),
            str((CONTROL / "final-matrix.csv").relative_to(PROJECT)),
        ],
    }, ensure_ascii=False, indent=2))


def main():
    from dotenv import load_dotenv

    load_dotenv(PROJECT / ".env", override=False)
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["prepare", "execute", "status", "finalize"], required=True)
    parser.add_argument("--slots", nargs="+", default=SLOTS)
    parser.add_argument("--max-concurrency", type=int, default=OVERRIDE_CONCURRENCY)
    args = parser.parse_args()
    if args.mode == "prepare":
        cmd_prepare(args)
    elif args.mode == "execute":
        cmd_execute(args)
    elif args.mode == "status":
        cmd_status(args)
    else:
        cmd_finalize(args)


if __name__ == "__main__":
    main()
