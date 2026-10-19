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
    print(json.dumps(status, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
