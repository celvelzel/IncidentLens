"""Read one diagnostic status snapshot without invoking providers or tools."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path, help="Retest output directory")
    args = parser.parse_args()
    if (args.out / "batch-state.json").is_file():
        state = json.loads((args.out / "batch-state.json").read_bytes())
        latest = {slot: attempts[-1] for slot, attempts in state["slots"].items() if attempts}
        supervisor = args.out / "supervisor-status.json"
        status = {"scope": "batch status only; no automatic resume or provider calls",
                  "latest_attempts": latest,
                  "supervisor": json.loads(supervisor.read_bytes()) if supervisor.is_file() else None,
                  "stop_requested": (args.out / "STOP_REQUESTED").exists()}
        if isinstance(status["supervisor"], dict):
            status["batch_state"] = status["supervisor"].get("state")
            status["active_worker_count"] = len(status["supervisor"].get("active", []))
            status["batch_counts"] = status["supervisor"].get("counts")
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return
    root = args.out / "observability"
    status = json.loads((root / "status.json").read_text(encoding="utf-8"))
    heartbeat = status.get("heartbeat_at", status["started_at"])
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(heartbeat)).total_seconds()
    status["heartbeat_age_seconds"] = round(age, 1)
    status["heartbeat_missing"] = status["lifecycle"] == "running" and age > 30
    status["liveness_note"] = "Heartbeat is advisory; stale status does not establish crash cause."
    if status.get("checkpoint"):
        checkpoint = json.loads((root / status["checkpoint"]).read_text(encoding="utf-8"))
        digest = hashlib.sha256()
        remaining = checkpoint["event_bytes"]
        with (root / "events-0001.jsonl").open("rb") as handle:
            while remaining:
                chunk = handle.read(min(65536, remaining))
                if not chunk:
                    break
                digest.update(chunk)
                remaining -= len(chunk)
        status["checkpoint_prefix_valid"] = (
            not remaining and digest.hexdigest() == checkpoint["event_sha256"]
        )
    bridge = args.out / "_bridge"
    if bridge.is_dir():
        pending = []
        for request in sorted((bridge / "requests").glob("*.json")):
            if not (bridge / "responses" / request.name).exists():
                pending.append({"request_id": request.stem, "bytes": request.stat().st_size,
                                "needs_chunked_read": request.stat().st_size > 60 * 1024})
        status["pending_bridge_requests"] = pending
    print(json.dumps(status, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
