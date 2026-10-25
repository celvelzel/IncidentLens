"""Isolated HPC WP-D orchestration; existing experiment implementation is unchanged."""
import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=PROJECT, text=True).strip()


def clean_checkout():
    if git("status", "--porcelain", "--untracked-files=normal"):
        raise ValueError("HPC checkout must be clean; commit changes before freezing")
    return git("rev-parse", "HEAD")


def session_path(run_id):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", run_id):
        raise ValueError("run ID must be a simple unique name")
    return PROJECT / "results" / "hpc-wpd" / run_id


def initialize(run_id, model, jobs):
    if not model or model != model.strip() or "SET_" in model:
        raise ValueError("an exact API model ID is required")
    if type(jobs) is not int or not 1 <= jobs <= 8:
        raise ValueError("jobs must be 1..8")
    commit = clean_checkout()
    plan = read(PROJECT / "configs/wp_d/api-plan.json")
    protocol = read(PROJECT / plan["protocol"])
    if model == protocol["model_id"]:
        raise ValueError("HPC experiment requires the newly selected model")
    protocol.update(model_id=model, jobs=jobs, protocol_id=f"wpd-hpc-{run_id}")
    root = session_path(run_id)
    root.mkdir(parents=True, exist_ok=False)
    inputs = root / "inputs"
    inputs.mkdir()
    write(inputs / "protocol.json", protocol)
    (inputs / "runtime.yaml").write_bytes((PROJECT / plan["runtime_config"]).read_bytes())
    plan.update(protocol=str((inputs / "protocol.json").relative_to(PROJECT)),
                runtime_config=str((inputs / "runtime.yaml").relative_to(PROJECT)))
    write(inputs / "plan.json", plan)
    files = [*inputs.iterdir(), PROJECT / "hpc/run_wpd.py"]
    write(root / "session.json", {
        "schema_version": 1, "run_id": run_id, "source_commit": commit,
        "model_id": model, "jobs": jobs, "slots": 40,
        "hashes": {str(p.relative_to(PROJECT)): sha(p) for p in files},
        "comparison": "new model and HPC environment; separate development experiment",
    })
    return root


def validate(root):
    session = read(root / "session.json")
    if clean_checkout() != session["source_commit"]:
        raise ValueError("commit changed; restore pinned checkout or create a fresh experiment")
    if any(sha(PROJECT / p) != expected for p, expected in session["hashes"].items()):
        raise ValueError("HPC session inputs changed")
    return session


def environment(session):
    # Deliberately do not load a repository .env: HPC credentials are injected by the job.
    endpoint = os.environ.get("INCIDENT_LENS_BASE_URL", "")
    if urlparse(endpoint).hostname != "discovery-api.intern-ai.org.cn":
        raise ValueError("set the original provider's INCIDENT_LENS_BASE_URL")
    if not os.environ.get("INCIDENT_LENS_API_KEY"):
        raise ValueError("INCIDENT_LENS_API_KEY is required")
    configured = os.environ.get("INCIDENT_LENS_MODEL")
    if configured and configured != session["model_id"]:
        raise ValueError("INCIDENT_LENS_MODEL conflicts with this HPC session")
    if os.environ.get("INCIDENT_LENS_THINKING") not in (None, "", "disabled"):
        raise ValueError("thinking must remain disabled")
    os.environ["INCIDENT_LENS_MODEL"] = session["model_id"]
    os.environ["INCIDENT_LENS_THINKING"] = "disabled"
    return endpoint


async def probe(root, session):
    import yaml
    from pydantic import BaseModel, ConfigDict

    from incident_lens.llm.config import provider_options
    from incident_lens.llm.provider import RealChatProvider

    class Probe(BaseModel):
        model_config = ConfigDict(extra="forbid")
        ok: bool

    target = root / "readiness.json"
    if target.exists():
        raise FileExistsError("readiness already exists; do not overwrite it")
    endpoint = environment(session)
    config = yaml.safe_load((root / "inputs/runtime.yaml").read_text(encoding="utf-8"))
    protocol = read(root / "inputs/protocol.json")
    provider = RealChatProvider(
        endpoint, os.environ["INCIDENT_LENS_API_KEY"], session["model_id"],
        temperature=protocol["temperature"],
        structured_repair_retries=config["structured_repair_retries"],
        recovery=config["provider_recovery"],
        **provider_options(protocol["response_format"], config["thinking"],
                           protocol["request_timeout"]),
    )
    try:
        result, usage = await provider.structured_call(
            "coordinator", "Return the requested JSON object.", {"request": "Return ok=true"}, Probe)
        if result.ok is not True:
            raise ValueError("probe did not return ok=true")
    except Exception as exc:
        # Do not persist raw exceptions, request headers, endpoint credentials or project evidence.
        from datetime import datetime, timezone
        failure = root / ("probe-failed-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + ".json")
        write(failure, {"provider_compatible": False, "error_type": type(exc).__name__,
                        "model_id": session["model_id"]})
        raise RuntimeError("provider readiness failed; no batch was started") from None
    write(target, {"provider_compatible": True, "model_id": session["model_id"],
                   "response_format": protocol["response_format"], "thinking": config["thinking"],
                   "source_commit": session["source_commit"],
                   "endpoint_sha256": hashlib.sha256(endpoint.encode()).hexdigest(),
                   "actual_http_requests": usage.get("actual_http_requests"),
                   "measured_total_tokens": usage.get("measured_total_tokens")})


def batch(root, session, mode, resume=False):
    endpoint = environment(session)
    readiness = read(root / "readiness.json")
    if (readiness.get("source_commit") != session["source_commit"]
            or readiness.get("endpoint_sha256") != hashlib.sha256(endpoint.encode()).hexdigest()):
        raise ValueError("readiness belongs to another commit/endpoint")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    command = [sys.executable, str(PROJECT / "scripts/run_wpd_batch.py"),
               "--plan", str(root / "inputs/plan.json"), "--out", str(root / "batch"),
               "--readiness", str(root / "readiness.json"),
               "--prepare" if mode == "prepare" else "--execute"]
    if resume:
        command.append("--resume")
    return subprocess.call(command, cwd=PROJECT, env=env)


def summary(root):
    batch_root = root / "batch"
    manifest = read(batch_root / "batch-manifest.json")
    state = read(batch_root / "batch-state.json")
    rows = []
    for i, identity in enumerate(manifest["order"], 1):
        slot = f"slot-{i:03d}"
        attempts = state["slots"].get(slot, [])
        latest = attempts[-1] if attempts else {}
        rows.append({"slot": slot, **identity, "status": latest.get("status", "unstarted"),
                     "attempt": latest.get("path")})
    from collections import Counter
    payload = {"slots": rows, "counts": dict(Counter(r["status"] for r in rows))}
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["init", "probe", "prepare", "run", "resume", "summary"])
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--model", default="Atria-Dawn", help="Exact API ID; validated by a live probe")
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args(argv)
    if args.mode == "init":
        print(initialize(args.run_id, args.model, args.jobs))
        return 0
    root = session_path(args.run_id)
    if args.mode == "summary":
        summary(root)
        return 0
    session = validate(root)
    if args.mode == "probe":
        asyncio.run(probe(root, session))
        return 0
    return batch(root, session, "prepare" if args.mode == "prepare" else "execute",
                 resume=args.mode == "resume")


if __name__ == "__main__":
    raise SystemExit(main())
