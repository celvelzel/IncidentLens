"""Prepare or explicitly execute a resumable, bounded-parallel development matrix.

Preparation never constructs a provider. Resume is batch-level only: it verifies
completed artifacts and continues unstarted slots. Interrupted investigations
are not loaded from diagnostic snapshots. An explicit retry creates a new attempt.
"""

import argparse
import ctypes
import hashlib
import importlib.metadata
import json
import os
import random
import signal
import subprocess
import sys
import time
from pathlib import Path

from incident_lens.evaluation.retest_provenance import retest_snapshot
from incident_lens.evaluation.run_io import append_json, atomic_json
from incident_lens.incidentbench.experiment import execution_lock
from incident_lens.incidentbench.schemas import ExperimentProtocol

PROJECT = Path(__file__).resolve().parents[1]
VARIANTS = ["single", "fixed", "dynamic_no_verifier", "full"]
# Local supervisor bounds, not service-side concurrency entitlements.
CONCURRENCY_LIMITS = {"bridge": 8, "api": 8, "subscription": 8}


def validate_concurrency(mode, jobs):
    limit = CONCURRENCY_LIMITS.get(mode)
    if limit is None or type(jobs) is not int or not 1 <= jobs <= limit:
        raise ValueError(f"{mode} concurrency must be an integer from 1 to {limit}")
    return jobs


OUTPUT_FILES = ("scope.json", "trace.json", "result.json", "report.md", "verification.json",
                "measured-usage.json", "observability/status.json")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rooted(value):
    path = (PROJECT / value).resolve()
    path.relative_to(PROJECT)
    if any(p.lower() in {"local_oracles", "private"} for p in path.relative_to(PROJECT).parts):
        raise ValueError("runtime input must not be evaluator-only data")
    return path


def frozen_inputs(plan_path, readiness=None):
    plan = read(plan_path)
    if plan["mode"] not in CONCURRENCY_LIMITS:
        raise ValueError("unsupported mode")
    protocol = ExperimentProtocol.model_validate(read(rooted(plan["protocol"])))
    if protocol.formal or protocol.provider_id != "real" or protocol.blindness_level != "development_visible":
        raise ValueError("development protocols only")
    bridge = protocol.model_id == "trae-subagent-bridge-v1"
    if bridge != (plan["mode"] == "bridge") or "SET_" in protocol.model_id:
        raise ValueError("select the actual API model before preparing; bridge identity must match mode")
    validate_concurrency(plan["mode"], protocol.jobs)
    dataset = rooted(plan["dataset"])
    index = read(dataset / "public_case_index.json")
    ids = plan["case_ids"]
    if len(ids) != len(set(ids)) or not ids or not set(ids).issubset({r["incident_id"] for r in index}):
        raise ValueError("case IDs must be distinct public-index entries")
    paths = [p for p in dataset.rglob("*") if p.is_file()]
    if any("private" in p.relative_to(dataset).parts for p in paths):
        raise ValueError("public dataset contains private inputs")
    from incident_lens.incidentbench.oracle_store import safe_path

    safe_path(dataset)
    for path in paths:
        safe_path(path)
    hashes = retest_snapshot(PROJECT)
    extra_inputs = []
    if plan["mode"] == "subscription":
        from incident_lens.llm.codex_subscription import REQUIRED_MODEL

        config = read(rooted(plan["subscription_config"]))
        receipt_path = rooted(plan["feasibility"])
        receipt = read(receipt_path)
        if (config.get("model") != REQUIRED_MODEL
            or protocol.model_id != config["model"]
            or config.get("reasoning_effort") != "low"
            or config.get("api_key_fallback") is not False
            or config.get("formal_experiment_enabled") is not False
            or config.get("transport") != "official_codex_exec"
            or config.get("billing_mode") != "chatgpt_codex_subscription"
            or config.get("investigation_request_timeout_seconds") != protocol.request_timeout):
            raise ValueError("subscription requires fixed supported model, low reasoning, no fallback and matching timeout")
        if (receipt.get("status") != "FEASIBLE_FOR_CODEX_SUBSCRIPTION_TRANSPORT"
            or not receipt.get("probes")
            or any(p.get("matched") is not True
                   or p.get("usage", {}).get("model_id") != protocol.model_id
                   for p in receipt["probes"])):
            raise ValueError("subscription requires matching successful feasibility receipt")
        extra_inputs = [rooted(plan["subscription_config"]), receipt_path]
    else:
        extra_inputs = [rooted(plan["runtime_config"])]
    for p in [*paths, Path(plan_path).resolve(), rooted(plan["protocol"]),
              *extra_inputs, PROJECT / "analysis/wp_d/serve_bridge_response.py"]:
        hashes[str(p.relative_to(PROJECT))] = digest(p)
    external = None
    if plan["mode"] == "api":
        from dotenv import load_dotenv

        load_dotenv(PROJECT / ".env", override=False)
        if readiness is None:
            raise ValueError("API preparation requires an actual --readiness record")
        record = read(readiness)
        import yaml

        runtime_config = yaml.safe_load(rooted(plan["runtime_config"]).read_text(encoding="utf-8"))
        if (record.get("model_id") != protocol.model_id
            or record.get("response_format") != protocol.response_format
            or record.get("thinking") != runtime_config.get("thinking")
            or record.get("provider_compatible") is not True):
            raise ValueError("readiness does not match protocol")
        if not all(os.getenv(k) for k in ("INCIDENT_LENS_BASE_URL", "INCIDENT_LENS_API_KEY")):
            raise ValueError("API credentials/endpoint missing; no request was made")
        if os.getenv("INCIDENT_LENS_MODEL") != protocol.model_id:
            raise ValueError("configured model does not match protocol")
        # Never persist credentials or raw endpoint URLs; credentials may rotate.
        external = {"readiness_sha256": digest(readiness),
                    "endpoint_sha256": hashlib.sha256(os.environ["INCIDENT_LENS_BASE_URL"].encode()).hexdigest(),
                    "thinking_env": os.getenv("INCIDENT_LENS_THINKING")}
    order = [{"incident": case, "variant": variant, "repeat": repeat}
             for repeat in range(protocol.repeats) for case in ids for variant in VARIANTS]
    random.Random(protocol.run_order_seed).shuffle(order)
    installed = {}
    for line in (PROJECT / "requirements.lock").read_text(encoding="utf-8").splitlines():
        if "==" in line and not line.startswith("#"):
            name = line.split("==", 1)[0].strip()
            try:
                installed[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                installed[name] = None
    return {"schema_version": 1, "plan": plan, "protocol": protocol.model_dump(mode="json"),
            "hashes": hashes, "external": external, "order": order,
            "max_concurrency": protocol.jobs,
            "concurrency": {"max_concurrent_slots": protocol.jobs,
                            "mode": plan["mode"],
                            "scope": f"{plan['mode']}_development_batch",
                            "per_slot_workflow_unchanged": True},
            "python": sys.version, "platform": sys.platform, "installed_dependencies": installed,
            "resume_policy": "verify_completed_continue_unstarted; explicit_new_attempt_for_interrupt"}


def alive(pid):
    if not pid:
        return False
    if os.name == "nt":
        # Do not use os.kill(pid, 0) on Windows. Treat a live/reused PID
        # conservatively; no running worker is killed during recovery.
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x00100000, False, pid)
        if not handle:
            if ctypes.get_last_error() == 87:
                return False
            raise RuntimeError("cannot establish prior worker exit")
        try:
            return kernel.WaitForSingleObject(handle, 0) != 0
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def artifact_hashes(out):
    return {name: digest(out / name) for name in OUTPUT_FILES}


def assess(out, key, manifest):
    verification = read(out / "verification.json")
    scope = read(out / "scope.json")
    trace = read(out / "trace.json")
    state = trace["state"]
    result = read(out / "result.json")
    if scope["incident_id"] != key["incident"] or scope["variant"] != key["variant"]:
        raise ValueError("saved scope identity mismatch")
    if scope["protocol"] != manifest["protocol"]:
        raise ValueError("saved protocol mismatch")
    if (state["incident_id"] != key["incident"] or result["run_id"] != state["run_id"]
        or result["incident_id"] != key["incident"] or trace["variant"] != key["variant"]):
        raise ValueError("saved trace/result identity mismatch")
    journal = read(out / "observability/status.json")
    healthy = not journal.get("observability", {}).get("degraded", True)
    complete = (verification.get("protocol_valid") is True
                and verification.get("source_unchanged") is True
                and verification.get("stop_completion") is True
                and verification.get("runtime_failure") is False
                and journal.get("lifecycle") == "completed" and healthy)
    return "completed" if complete else "failed"


def event(out, kind, **details):
    append_json(out / "batch-events.jsonl", {"time_utc": time.time(), "event": kind, **details})


def stop_child(process):
    if process.poll() is not None:
        return
    try:
        process.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
        process.wait(timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        if os.name == "nt":
            # A subscription worker owns Codex descendants. Stop its tree before
            # terminating the Python parent, otherwise those calls can outlive it.
            try:
                result = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                        timeout=10, check=False)
                if result.returncode == 0:
                    process.wait(timeout=10)
                    return
            except (OSError, subprocess.TimeoutExpired):
                pass
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def execute(args, manifest):
    out = args.out.resolve()
    state_path = out / "batch-state.json"
    state = read(state_path)
    plan = manifest["plan"]
    concurrency = manifest.get("max_concurrency", 1)
    validate_concurrency(plan["mode"], concurrency)
    if "jobs" in manifest.get("protocol", {}) and concurrency != manifest["protocol"]["jobs"]:
        raise ValueError("frozen concurrency does not match protocol jobs")
    planned = len(manifest["order"])
    expected_slots = [f"slot-{index + 1:03d}" for index in range(planned)]
    if list(state["slots"]) != expected_slots[:len(state["slots"])]:
        raise ValueError("batch state must be a prefix of the frozen schedule")
    # Verify every saved attempt, including those completed out of schedule order.
    for index, key in enumerate(manifest["order"]):
        slot = expected_slots[index]
        attempts = state["slots"].get(slot, [])
        for prior in attempts:
            if prior["status"] not in {"running", "completed", "failed", "interrupted"}:
                raise ValueError("unknown saved attempt status")
            directory = (out / prior["path"]).resolve()
            directory.relative_to(out)
            if prior.get("key") != key:
                raise ValueError("saved slot identity mismatch")
            if prior["status"] == "completed" and set(prior.get("artifacts", {})) != set(OUTPUT_FILES):
                raise ValueError("completed slot lacks a complete artifact receipt")
            for name, expected in prior.get("artifacts", {}).items():
                if name not in OUTPUT_FILES:
                    raise ValueError("unknown artifact receipt path")
                if digest(directory / name) != expected:
                    raise ValueError("saved attempt artifact changed")
            if prior["status"] == "completed" and assess(directory, key, manifest) != "completed":
                raise ValueError("saved completed slot no longer validates")
            if prior["status"] == "running":
                if alive(prior.get("pid")):
                    raise RuntimeError("previous worker is still alive; wait/stop it before resume")
                # Worker may have durably finished after its parent disappeared.
                try:
                    prior["status"] = assess(directory, key, manifest)
                    prior["artifacts"] = artifact_hashes(directory)
                except (OSError, ValueError, KeyError):
                    prior["status"] = "interrupted"
                event(out, "WORKER_RECONCILED", slot=slot, status=prior["status"])
                atomic_json(state_path, state)
    pending = []
    for index, key in enumerate(manifest["order"]):
        slot = expected_slots[index]
        attempts = state["slots"].get(slot, [])
        if attempts:
            latest = attempts[-1]
            if latest["status"] == "completed":
                continue
            if latest["status"] == "failed":
                # Finished failures are retained and not retried by resume.
                if not getattr(args, "retry_failed", False):
                    continue
            elif not getattr(args, "retry_interrupted", False):
                raise RuntimeError("interrupted slot requires explicit --retry-interrupted; new attempt only")
        pending.append({"slot": slot, "key": key})
    execution = {"started_at_utc": time.time(), "max_concurrency": concurrency,
                 "resume": bool(getattr(args, "resume", False)),
                 "planned_slots": planned, "pending_slots": len(pending)}
    state["max_concurrency"] = concurrency
    state["execution_started_at_utc"] = state.get("execution_started_at_utc",
                                                  execution["started_at_utc"])
    state.setdefault("executions", []).append(execution)
    atomic_json(state_path, state)
    batch_started = time.monotonic()
    limit = manifest["protocol"]["max_wall_seconds"] + 120
    active = {}
    paused = False
    interrupted = False
    stop_cause = None

    def latest_counts():
        latest = {slot: attempts[-1] for slot, attempts in state["slots"].items() if attempts}
        return {
            "planned": planned,
            "started_slots": len(latest),
            "completed_slots": sum(a["status"] == "completed" for a in latest.values()),
            "failed_slots": sum(a["status"] == "failed" for a in latest.values()),
            "interrupted_slots": sum(a["status"] == "interrupted" for a in latest.values()),
            "active_slots": len(active),
        }

    def write_status(name):
        now_wall = time.time()
        entries = []
        for slot in expected_slots:
            entry = active.get(slot)
            if entry is None:
                continue
            entries.append({
                "slot": slot,
                "attempt": entry["relative"],
                "worker_pid": entry["process"].pid,
                "incident": entry["key"]["incident"],
                "variant": entry["key"]["variant"],
                "repeat": entry["key"]["repeat"],
                "started_at_utc": entry["started_at_utc"],
                "worker_elapsed_seconds": time.monotonic() - entry["started_monotonic"],
                "heartbeat_utc": now_wall,
            })
        atomic_json(out / "supervisor-status.json", {
            "schema_version": 2, "state": name, "parent_pid": os.getpid(),
            "max_concurrency": concurrency, "heartbeat_utc": now_wall,
            "batch_started_at_utc": execution["started_at_utc"],
            "counts": latest_counts(), "active": entries,
            "note": "Supervisor heartbeat is not investigation progress; active lists every live worker."})

    def start(item):
        # Input freeze is re-checked before every dispatch; drift stops all lanes.
        if frozen_inputs(args.plan, args.readiness) != manifest:
            raise ValueError("input drift during execution; refusing next slot")
        slot, key = item["slot"], item["key"]
        attempts = state["slots"].setdefault(slot, [])
        relative = f"runs/{slot}/attempt-{len(attempts) + 1:03d}"
        attempt = {"path": relative, "status": "running", "pid": None, "key": key,
                   "started_at_utc": time.time(),
                   "parent_attempt": attempts[-1]["path"] if attempts else None}
        attempts.append(attempt)
        atomic_json(state_path, state)
        event(out, "SLOT_START_INTENT", slot=slot, attempt=relative)
        directory = out / relative
        directory.parent.mkdir(parents=True, exist_ok=True)
        # Per-slot worker lease prevents an orphan worker and its replacement
        # from executing concurrently, including the parent-startup crash window.
        lease = out / "worker-leases" / slot
        lease.mkdir(parents=True, exist_ok=True)
        script = {"bridge": "retest_subagent_bridge.py", "api": "retest_live_provider_fix.py",
                  "subscription": "run_codex_subscription_case.py"}[plan["mode"]]
        command = [sys.executable, "-B", "-u", str(PROJECT / "scripts" / script),
                   "--dataset", str(rooted(plan["dataset"])),
                   "--protocol", str(rooted(plan["protocol"])),
                   "--incident", key["incident"], "--variant", key["variant"],
                   "--out", str(directory), "--lease-directory", str(lease)]
        if plan["mode"] == "subscription":
            command += ["--config", str(rooted(plan["subscription_config"])),
                        "--feasibility", str(rooted(plan["feasibility"])),
                        "--execute-development-case"]
        else:
            command += ["--runtime-config", str(rooted(plan["runtime_config"]))]
        if plan["mode"] == "api":
            command += ["--readiness", str(args.readiness.resolve())]
        env = dict(os.environ, PYTHONPATH=str(PROJECT / "src"), PYTHONUTF8="1")
        logs = out / "supervisor" / slot / f"attempt-{len(attempts):03d}"
        logs.mkdir(parents=True, exist_ok=False)
        stdout = (logs / "stdout.log").open("xb")
        stderr = (logs / "stderr.log").open("xb")
        try:
            process = subprocess.Popen(command, cwd=PROJECT, env=env, stdout=stdout, stderr=stderr,
                                       creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
        except BaseException as exc:
            stdout.close()
            stderr.close()
            attempt.update(status="failed", ended_at_utc=time.time(), exit_code=None, artifacts={})
            atomic_json(state_path, state)
            event(out, "WORKER_START_FAILED", slot=slot, attempt=relative,
                  error_type=type(exc).__name__)
            raise
        attempt["pid"] = process.pid
        active[slot] = {"slot": slot, "key": key, "attempt": attempt, "directory": directory,
                        "relative": relative, "logs": logs, "process": process,
                        "stdout": stdout, "stderr": stderr,
                        "started_monotonic": time.monotonic(),
                        "started_at_utc": attempt["started_at_utc"]}
        atomic_json(state_path, state)

    def finish(slot, cause=None):
        entry = active.pop(slot)
        process, attempt = entry["process"], entry["attempt"]
        attempt["ended_at_utc"] = time.time()
        attempt["exit_code"] = process.poll()
        attempt["interrupted"] = cause is not None
        if cause:
            attempt["stop_cause"] = cause
        try:
            attempt["status"] = assess(entry["directory"], entry["key"], manifest)
            attempt["artifacts"] = artifact_hashes(entry["directory"])
        except (OSError, ValueError, KeyError):
            attempt["status"] = "interrupted" if cause else "failed"
        if attempt["exit_code"] != 0 and attempt["status"] == "completed":
            attempt["status"] = "failed"
        for stream in (entry["stdout"], entry["stderr"]):
            try:
                stream.close()
            except OSError:
                pass
        atomic_json(entry["logs"] / "exit.json", {
            "exit_code": attempt["exit_code"], "status": attempt["status"],
            "interrupted": cause is not None, "stop_cause": cause})
        atomic_json(state_path, state)
        event(out, "SLOT_ENDED", slot=slot, status=attempt["status"],
              path=entry["relative"], stop_cause=cause)
        return attempt["status"]

    try:
        write_status("batch_running")
        while True:
            if (out / "STOP_REQUESTED").exists():
                interrupted, stop_cause = True, "stop_requested"
                event(out, "BATCH_STOP_REQUESTED", active=sorted(active))
                break
            now = time.monotonic()
            overdue = [slot for slot, entry in active.items()
                       if entry["process"].poll() is None
                       and now - entry["started_monotonic"] > limit]
            if overdue:
                interrupted, stop_cause = True, "wall_timeout"
                event(out, "BATCH_WALL_TIMEOUT", slots=sorted(overdue))
                break
            # Reap exits before filling free lanes, so observed failures stop dispatch.
            finished = [slot for slot, entry in active.items()
                        if entry["process"].poll() is not None]
            for slot in finished:
                status = finish(slot)
                if status != "completed" and plan.get("stop_on_failure", True):
                    paused = True
            while not paused and len(active) < concurrency and pending:
                if (out / "STOP_REQUESTED").exists():
                    break
                # A worker may have exited while freezing inputs for another launch.
                if any(entry["process"].poll() is not None for entry in active.values()):
                    break
                start(pending[0])
                pending.pop(0)
                write_status("batch_running")
            if not active:
                if pending and not paused:
                    continue
                break
            write_status("batch_paused_after_failure" if paused else "batch_running")
            if finished:
                continue
            time.sleep(2)
    except BaseException as exc:
        event(out, "SUPERVISOR_EXCEPTION", error_type=type(exc).__name__, active=sorted(active))
        for slot in list(active):
            stop_child(active[slot]["process"])
        for slot in list(active):
            finish(slot, cause="supervisor_exception")
        write_status("batch_stopped")
        execution["ended_at_utc"] = time.time()
        execution["outcome"] = "batch_stopped"
        execution["stop_cause"] = "supervisor_exception"
        execution["counts"] = latest_counts()
        atomic_json(state_path, state)
        raise
    if interrupted:
        for slot in list(active):
            stop_child(active[slot]["process"])
        for slot in list(active):
            finish(slot, cause=stop_cause)
        write_status("batch_stopped")
        execution["ended_at_utc"] = time.time()
        execution["outcome"] = "batch_stopped"
        execution["stop_cause"] = stop_cause
        execution["elapsed_seconds"] = time.monotonic() - batch_started
        execution["counts"] = latest_counts()
        atomic_json(state_path, state)
        event(out, "BATCH_STOPPED", stop_cause=stop_cause)
        return 130
    latest = {slot: attempts[-1] for slot, attempts in state["slots"].items() if attempts}
    unfinished = [slot for slot in expected_slots
                  if slot not in latest or latest[slot]["status"] != "completed"]
    final_state = "batch_paused_after_failure" if paused else (
        "batch_finished" if not unfinished else "batch_finished_with_errors")
    write_status(final_state)
    execution["ended_at_utc"] = time.time()
    execution["outcome"] = final_state
    execution["elapsed_seconds"] = time.monotonic() - batch_started
    execution["counts"] = latest_counts()
    atomic_json(state_path, state)
    event(out, "BATCH_PAUSED_AFTER_FAILURE" if paused else "BATCH_FINISHED",
          slots=planned, noncompleted_slots=unfinished)
    return 1 if (paused or unfinished) else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--retry-interrupted", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--readiness", type=Path)
    args = parser.parse_args()
    manifest = frozen_inputs(args.plan.resolve(), args.readiness)
    if args.prepare:
        if args.resume or args.retry_interrupted or args.retry_failed:
            raise ValueError("prepare cannot resume/retry")
        args.out.mkdir(parents=True, exist_ok=False)
        atomic_json(args.out / "batch-manifest.json", manifest, exclusive=True)
        atomic_json(args.out / "batch-state.json",
                    {"schema_version": 1, "slots": {},
                     "max_concurrency": manifest["max_concurrency"]})
        event(args.out, "PREPARED_NOT_EXECUTED", slots=len(manifest["order"]))
        print("Prepared only; zero model/tool calls.")
        return 0
    if not args.out.is_dir():
        raise ValueError("prepare a fresh output before execute")
    with execution_lock(args.out):
        if read(args.out / "batch-manifest.json") != manifest:
            raise ValueError("frozen input/environment drift; prepare a new batch")
        if read(args.out / "batch-state.json")["slots"] and not args.resume:
            raise ValueError("existing attempts require --resume")
        return execute(args, manifest)


if __name__ == "__main__":
    raise SystemExit(main())
