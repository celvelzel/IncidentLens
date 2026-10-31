"""Authoritative physical-request counts for round 8.

verification.json carries actual_http_requests (physical, including retries);
measured-usage.json carries logical calls. Sum both, per slot and overall.
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

tot_phys = 0
tot_logical = 0
for slot in sorted(round8):
    d = BATCH / round8[slot]["path"]
    v = json.loads((d / "verification.json").read_text(encoding="utf-8-sig"))
    mu = json.loads((d / "measured-usage.json").read_text(encoding="utf-8-sig"))
    phys = v.get("actual_http_requests")
    logical = len(mu.get("calls") or [])
    tok = v.get("measured_total_tokens")
    tot_phys += phys or 0
    tot_logical += logical
    print(f"{slot} {round8[slot]['path']}: physical={phys} logical={logical} tokens={tok}")

print(f"\nTOTAL physical HTTP = {tot_phys}, logical calls = {tot_logical}")
