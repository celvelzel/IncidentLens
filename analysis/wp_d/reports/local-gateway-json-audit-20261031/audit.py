"""Offline audit of the completed 20-slot snapshot; exclude later concurrent retests."""

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

OUT = Path(__file__).resolve().parent
PROJECT = OUT.parents[3]
ROOT = PROJECT / "results/v16/wp-d/local-gateway-dev5-20261031"
CUTOFF = 1793430842.838091


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def main():
    state = read(ROOT / "batch-state.json")
    gateway = Path.home() / ".config/magpie/usage.jsonl"
    routes = [json.loads(line) for line in gateway.read_text(encoding="utf-8").splitlines()]
    routes = [r for r in routes if r.get("agent") == "python-httpx"]
    rows, errors = [], []
    counts, repaired = Counter(), Counter()
    for slot, attempts in state["slots"].items():
        baseline = [a for a in attempts if a.get("ended_at_utc", float("inf")) <= CUTOFF
                    and a["status"] in ("completed", "failed")]
        a = baseline[-1]
        path = ROOT / a["path"] / "trace.json"
        trace = read(path)
        events = trace["state"]["events"]
        phases, physical = {}, {}
        failure_events = []
        for e in events:
            typ, role, d = e["event_type"], e.get("role"), e["details"]
            if typ == "TASK_RUNNING":
                phases[role] = "planning"
            elif typ == "TOOL_CALL":
                phases[role] = "analysis"
            elif typ == "PROVIDER_ATTEMPT":
                physical[d["logical_call_id"], d["http_attempt_index"]] = e
            elif typ == "PROVIDER_FAILURE_CLASSIFIED":
                detail = dict(slot=slot, event_id=e["event_id"], role=role, **d)
                errors.append(detail)
                failure_events.append(detail)
            elif typ in ("LLM_CALL", "MODEL_FAILURE"):
                phase = phases.get(role, "other") if role in ("logs", "metrics", "database", "changes", "single") else "decision_or_review"
                counts[role, phase] += 1
                if d.get("repair_requests"):
                    repaired[role, phase] += 1
                for usage in d.get("request_usage", []):
                    p = physical.get((d.get("logical_call_id"), usage["http_attempt_index"]))
                    if p is None:
                        continue
                    candidates = [r for r in routes
                                  if abs(stamp(r["t"]) - stamp(p["timestamp"])) < 0.5
                                  and r.get("out") == usage.get("completion_tokens")]
                    if len(candidates) == 1:
                        matched = candidates[0]
                        for f in failure_events:
                            if (f.get("logical_call_id"), f.get("http_attempt_index")) == (d.get("logical_call_id"), usage["http_attempt_index"]):
                                f["gateway_match"] = {k: matched.get(k) for k in ("route_id", "t", "agent", "provider", "model", "status", "out", "ep")}
        rows.append(dict(slot=slot, key=a["key"], attempt=a["path"], status=a["status"],
                         trace_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), errors=failure_events))

    probes = {}
    for prefix in ("reproduction", "control"):
        attempts = read(OUT / (prefix + "-attempts.json"))
        results = []
        for a in attempts:
            response = a["response"]
            choice = response["choices"][0]
            content = choice["message"]["content"]
            try:
                json.loads(content)
                valid_json = True
            except ValueError:
                valid_json = False
            candidates = [r for r in routes if abs(stamp(r["t"]) - stamp(a["started_at"])) < 0.5
                          and r.get("out") == response.get("usage", {}).get("completion_tokens")]
            results.append(dict(started_at=a["started_at"], status=a["status"],
                                finish_reason=choice.get("finish_reason"), valid_json=valid_json,
                                dsml="DSML" in content,
                                request_has_tools="tools" in a["request"],
                                response_has_tool_calls="tool_calls" in choice["message"],
                                message_roles=[m["role"] for m in a["request"]["messages"]],
                                content_preview=content[:170],
                                gateway_matches=[{k:r.get(k) for k in ("route_id", "t", "provider", "model", "status", "out")} for r in candidates]))
        probes[prefix] = results
    output = dict(scope="Latest terminal attempt per slot at original batch completion; later retests excluded",
                  cutoff_epoch=CUTOFF, slots=rows, outcome_counts=dict(Counter(r["status"] for r in rows)),
                  failure_counts=[dict(role=k[0], category=k[1], count=v) for k,v in Counter((e["role"],e["category"]) for e in errors).items()],
                  logical_call_counts=[dict(role=k[0], phase=k[1], count=v, calls_requiring_repair=repaired[k]) for k,v in counts.items()],
                  probes=probes)
    (OUT / "evidence.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"outcomes": output["outcome_counts"], "failure_counts": output["failure_counts"], "probes": probes}, ensure_ascii=True))


if __name__ == "__main__":
    main()
