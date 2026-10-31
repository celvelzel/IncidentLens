"""Post round-8 integrity check: frozen inputs vs batch manifest, no live workers."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

# this script lives at <project>/analysis/wp_d/reports/<round-dir>/, so
# parents[4] is the project root (same depth the orchestrator reaches via
# CONTROL = Path(__file__).parent then CONTROL.parents[3])
PROJECT = Path(__file__).resolve().parents[4]
BATCH = PROJECT / "results/v16/wp-d/next-api-max8-20261022-121153"
manifest = json.loads((BATCH / "batch-manifest.json").read_text(encoding="utf-8-sig"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


mismatches = []
for relative, expected in manifest["hashes"].items():
    path = PROJECT / relative
    if not path.is_file():
        mismatches.append({"path": relative, "expected": expected, "actual": None})
        continue
    actual = digest(path)
    if actual != expected:
        mismatches.append({"path": relative, "expected": expected, "actual": actual})

print(f"frozen inputs checked: {len(manifest['hashes'])}, mismatches: {len(mismatches)}")
for m in mismatches:
    print("  MISMATCH:", m)

commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT, text=True).strip()
scope = json.loads((BATCH / "runs/slot-001/attempt-001/scope.json").read_text(encoding="utf-8"))
print("git HEAD:", commit)
print("git HEAD matches original scope source_commit:", commit == scope["source_commit"])

state = json.loads((BATCH / "batch-state.json").read_text(encoding="utf-8-sig"))
live = []
for slot, attempts in state["slots"].items():
    for a in attempts:
        if a.get("status") == "running" and a.get("pid"):
            try:
                os.kill(a["pid"], 0)
                live.append((slot, a["path"], a["pid"]))
            except (OSError, ProcessLookupError):
                pass
print("live workers recorded as running:", live)

stop = (BATCH / "STOP_REQUESTED").exists()
print("STOP_REQUESTED present:", stop)
print("batch manifest sha256:", digest(BATCH / "batch-manifest.json"))
