"""Generate mechanical mock evidence, NEVER human gold or a quality success claim."""

import argparse
import asyncio
import json
from pathlib import Path

from incident_lens.llm import MockProvider
from incident_lens.orchestration.graph import run_investigation
from incident_lens.prompts.resolver import PromptResolver, canonical
from incident_lens.prompts.snapshots import SnapshotRecorder
from incident_lens.schemas import Budget

from .data import extract_events, load_samples
from .evaluate import evaluate
from .optimize import compile_bundle, save_bundle, verify_export
from .provider import RequestCap, make_provider
from .system import evaluate_system


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=False)

    async def capture():
        for case in ("incident_001", "incident_002"):
            provider = MockProvider()
            provider.snapshot_observer = SnapshotRecorder(out / "decision-events.jsonl")
            await run_investigation(case, provider, data_root="data", budget=Budget(), variant="full")
    asyncio.run(capture())
    extract_events(out / "decision-events.jsonl", out / "pending-samples.jsonl")
    samples = load_samples(out / "pending-samples.jsonl")
    events = [json.loads(line) for line in (out / "decision-events.jsonl").read_text().splitlines()]
    requests = {e["snapshot_id"]: e for e in events if e["phase"] == "request"}
    expected = {}
    from incident_lens.prompts.resolver import TaskPrompt, digest
    for e in events:
        if e["phase"] == "result":
            r = requests[e["snapshot_id"]]
            expected[digest({"stage": r["stage"], "payload": r["payload"], "schema": r["schema"]})] = e["output"]
    for sample in samples:
        sample.split = "train" if sample.payload.get("context", sample.payload)["incident_id"] == "incident_001" else "dev"
        sample.annotation.expected = expected[sample.sample_id]
        # Annotation stays pending: a deterministic model response is not human gold.
    cap = RequestCap(10000)
    arms, exports = {"A0": PromptResolver()}, []
    for stage in ("analysis", "verify"):
        for name, optimizer in (("A1", "manual"), ("A2", "BootstrapFewShot"),
                                ("A3", "MIPROv2")):
            bundle, program, lm = compile_bundle(samples, make_provider("mock", cap), stage,
                                                 optimizer, shots=1, trials=2, engineering_fixture=True)
            filename = name + "-" + stage + ".json"
            save_bundle(out / filename, bundle)
            exports.append({"arm": name, "stage": stage,
                            **verify_export(program, lm, bundle, next(
                                s for s in samples if s.stage == stage and s.split == "dev"))})
            # Combine both stage artifacts for a complete-system smoke.
            if name in arms:
                previous = json.loads(arms[name]._bundle_json)
                bundle.tasks.update({k: TaskPrompt.model_validate(v) for k, v in previous["tasks"].items()})
            arms[name] = PromptResolver(bundle.model_dump(mode="json"), allow_candidate=True)
    module_report = asyncio.run(evaluate(samples, lambda: make_provider("mock", cap), arms,
                                                engineering_fixture=True))
    (out / "module-report.json").write_text(canonical(module_report) + "\n", encoding="utf-8")
    report = asyncio.run(evaluate_system(Path("data"), "dev", arms, cap, out / "system",
                                          kind="mock"))
    report.update(exports=exports, captured_snapshots=len(samples), request_permits=cap.used,
                  module_rows=len(module_report["rows"]), module_pairs=module_report["paired"],
                  label_provenance="deterministic mock fixture; pending human review")
    (out / "summary.json").write_text(canonical(report) + "\n", encoding="utf-8")
    print(json.dumps({"snapshots": len(samples), "system_runs": len(report["rows"]),
                      "request_permits": cap.used, "status": report["status"]}))


if __name__ == "__main__":
    main()
