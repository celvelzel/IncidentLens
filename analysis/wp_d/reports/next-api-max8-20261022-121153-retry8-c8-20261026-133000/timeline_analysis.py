"""Reconstruct the round-8 request timeline to test whether 429s correlate with
concurrency width or request rate.

Each PROVIDER_ATTEMPT event is one physical HTTP request; a PROVIDER_FAILURE_CLASSIFIED
event shortly after marks a failed attempt. Rebuilds the system-wide schedule across
all 10 round-8 attempts and asks: when each 429 happened, how many slots were alive,
how many requests were in flight, and what the rolling 60 s request rate was.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

BATCH = Path("results/v16/wp-d/next-api-max8-20261022-121153")
RETRY_ID = "next-api-max8-20261022-121153-retry8-c8-20261026-133000"

state = json.loads((BATCH / "batch-state.json").read_text(encoding="utf-8-sig"))
round8 = {
    slot: attempts[-1]
    for slot, attempts in state["slots"].items()
    if attempts and attempts[-1].get("retry_id") == RETRY_ID
}


def load_events(attempt_path):
    files = sorted((BATCH / attempt_path / "observability").glob("events-*.jsonl"))
    out = []
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
    return out


def ts(recorded):
    return datetime.fromisoformat(recorded)


requests = []  # (time, slot, attempt_idx, failed)
for slot, attempt in round8.items():
    events = load_events(attempt["path"])
    pending = []
    for e in events:
        kind = e.get("kind")
        when = ts(e["recorded_at"])
        if kind == "PROVIDER_ATTEMPT":
            pending.append(when)
        elif kind == "PROVIDER_FAILURE_CLASSIFIED":
            if pending:
                started = pending.pop(0)
                requests.append((started, when, slot, True))
        elif kind == "PROVIDER_CALL_COMPLETED":
            if pending:
                started = pending.pop(0)
                requests.append((started, when, slot, False))

requests.sort(key=lambda r: r[0])
total = len(requests)
fails = [r for r in requests if r[3]]
oks = [r for r in requests if not r[3]]
print(f"physical requests reconstructed: {total} (ok {len(oks)}, 429 {len(fails)})")

span = (requests[-1][1] - requests[0][0]).total_seconds()
print(f"span: {span:.0f} s -> mean rate {total / span * 60:.1f} req/min")

# rolling 60s rate curve
bucket = []
for r in requests:
    while bucket and (r[0] - bucket[0]).total_seconds() > 60:
        bucket.pop(0)
    bucket.append(r[0])
peak = 0
matrix = []
for r in requests:
    while bucket and (r[0] - bucket[0]).total_seconds() > 60:
        bucket.pop(0)
    peak = max(peak, len(bucket))
print(f"peak rolling 60 s request rate: {peak} req/min")

# in-flight at each request start (requests whose window overlaps this start)
starts = [r[0] for r in requests]
ends = [r[1] for r in requests]
inflight_at_fail = []
for r in fails:
    t = r[0]
    n = sum(1 for a, b in zip(starts, ends) if a <= t < b)
    inflight_at_fail.append(n)
inflight_at_ok = []
for r in oks:
    t = r[0]
    n = sum(1 for a, b in zip(starts, ends) if a <= t < b)
    inflight_at_ok.append(n)
print(f"in-flight at 429 starts: {sorted(inflight_at_fail)}")
print(f"in-flight at ok starts: min {min(inflight_at_ok)}, median {sorted(inflight_at_ok)[len(inflight_at_ok)//2]}, max {max(inflight_at_ok)}")

# slots alive at each 429
alive_counts = []
for r in fails:
    t = r[0]
    n = 0
    for slot, attempt in round8.items():
        events = load_events(attempt["path"])
        first = events[0]["recorded_at"]
        last = events[-1]["recorded_at"]
        if ts(first) <= t <= ts(last):
            n += 1
    alive_counts.append((t.strftime("%H:%M:%S"), r[1].strftime("%H:%M:%S"), n))
print("\n429 events (start time, classified time, slots alive then):")
for row in alive_counts:
    print(f"  {row[0]} -> {row[1]}  alive={row[2]}")

# gap between successive 429s
print("\ngaps between successive 429 starts (s):")
for i in range(1, len(fails)):
    print(f"  {i}: {(fails[i][0] - fails[i-1][0]).total_seconds():.1f}")
