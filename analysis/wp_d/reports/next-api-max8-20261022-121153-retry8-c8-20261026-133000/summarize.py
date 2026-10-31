"""Summarize round-8 retry outcomes from the frozen batch state and event log.

Counts successful vs failed provider calls per attempt; a call with a recorded
total_tokens is a successful response (429 responses carry no usage).
"""

import json
from pathlib import Path

BATCH = Path("results/v16/wp-d/next-api-max8-20261022-121153")
RETRY_ID = "next-api-max8-20261022-121153-retry8-c8-20261026-133000"

state = json.loads((BATCH / "batch-state.json").read_text(encoding="utf-8-sig"))
round8 = {
    slot: attempts[-1]
    for slot, attempts in state["slots"].items()
    if attempts and attempts[-1].get("retry_id") == RETRY_ID
}

print(f"round-8 attempts: {len(round8)}")
total_http = 0
total_tokens = 0
rows = []
for slot in sorted(round8):
    attempt = round8[slot]
    d = BATCH / attempt["path"]
    v = json.loads((d / "verification.json").read_text(encoding="utf-8-sig"))
    mu = json.loads((d / "measured-usage.json").read_text(encoding="utf-8-sig"))
    calls = mu.get("calls") or []
    http = len(calls)
    ok = [c for c in calls if isinstance(c, dict) and not c.get("failed")]
    bad = [c for c in calls if isinstance(c, dict) and c.get("failed")]
    tokens = sum(
        int((c.get("usage") or {}).get("total_tokens") or 0)
        for c in calls
        if isinstance(c, dict)
    )
    total_http += http
    total_tokens += tokens
    details = v.get("provider_failure_details") or []
    statuses = sorted({str(fd.get("provider_http_status")) for fd in details})
    rows.append({
        "slot": slot,
        "attempt": attempt["path"],
        "stage": (v.get("termination") or {}).get("failure_stage"),
        "http": http,
        "ok": len(ok),
        "bad": len(bad),
        "tokens": tokens,
        "statuses": statuses,
    })

for r in rows:
    print(
        f"{r['slot']} {r['attempt']}: stage={r['stage']} http={r['http']} "
        f"ok={r['ok']} bad={r['bad']} tokens={r['tokens']} statuses={r['statuses']}"
    )

print(f"\nround-8 totals: {total_http} HTTP, {total_tokens} measured tokens")
