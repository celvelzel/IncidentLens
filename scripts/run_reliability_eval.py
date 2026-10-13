"""Run reproducible offline V1.3 paired provider and runtime guard experiments."""

import argparse
import asyncio
import csv
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from incident_lens.evaluation.reliability_metrics import aggregate_reliability

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "reliability_scenarios", ROOT / "tests/reliability/scenarios.py"
)
fixtures = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = fixtures
spec.loader.exec_module(fixtures)

# These execute existing domain/runtime assertions, outside the provider-only ablation.
RUNTIME_CHECKS = {
    "F11": [
        "tests/cache/test_semantic.py::test_forged_citation_rejected_even_with_matching_integrity_digest"
    ],
    "F12": ["tests/reliability/test_runtime_boundaries.py::test_two_production_calls_final_permit"],
    "F15": [
        "tests/integration/test_provider_runtime_v13.py::test_stage_guard_isolation_measured_last_permit_and_retry",
        "tests/integration/test_recovery_concurrency_v13.py::test_task_retries_share_global_permits_and_unique_identity",
    ],
    "F18": [
        "tests/integration/test_termination_scoring.py::test_normal_stop_has_consistent_terminal_result_and_credit"
    ],
    "F19": [
        "tests/integration/test_termination_scoring.py::test_evidence_insufficiency_abstains_normally"
    ],
    "F20": [
        "tests/cache/test_semantic.py::test_actual_cold_warm_graph_calls_and_grounding",
        "tests/integration/test_artifacts.py::test_replay_roundtrip_without_provider",
        "tests/integration/test_workflow_v12.py::test_normal_snapshot_stops_without_diagnosis_or_remediation",
    ],
}


def write_csv(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(
            {key: "NULL" if value is None else value for key, value in row.items()} for row in rows
        )


async def evaluate(output):
    output.mkdir(parents=True, exist_ok=False)
    baseline_class, baseline_source = fixtures.frozen_provider(ROOT)
    rows, events, matrix = [], [], []
    for scenario in fixtures.SCENARIOS:
        for variant in ("R0", "R1", "R2", "R3"):
            row, case_events, _ = await fixtures.run_case(scenario, variant, baseline_class)
            rows.append(row)
            events.extend(case_events)
            matrix.append(
                dict(
                    case_id=scenario.case_id,
                    variant=variant,
                    scope="provider",
                    passed=expected(row, scenario, variant),
                    expected=expectation(scenario, variant),
                    observed_completed=row["completed"],
                    observed_requests=row["actual_http_requests"],
                    category=row["category"],
                )
            )
    for case_id, nodes in RUNTIME_CHECKS.items():
        junit = output / f"{case_id}-runtime.xml"
        cmd = [sys.executable, "-m", "pytest", "-q", *nodes, f"--junitxml={junit}"]
        run = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=os.environ | {"PYTHONPATH": str(ROOT / "src")},
        )
        (output / f"{case_id}-runtime.log").write_text(run.stdout + run.stderr, encoding="utf-8")
        cases = ET.parse(junit).findall(".//testcase") if junit.exists() else []
        passed = (
            run.returncode == 0
            and bool(cases)
            and not any(
                case.find("failure") is not None
                or case.find("error") is not None
                or case.find("skipped") is not None
                for case in cases
            )
        )
        rows.append(
            dict(
                case_id=case_id,
                variant="runtime",
                scope="runtime_assertion",
                completed=None,
                actual_http_requests=None,
                total_tokens=None,
                measured_total_tokens=None,
                tokens_complete=None,
                error_code=None,
                category=None,
                repair_requests=None,
                transport_retries=None,
                stop_reason=None,
                cost=None,
                rca_accuracy=None,
                assertion_passed=passed,
                assertion_count=len(cases),
            )
        )
        matrix.append(
            dict(
                case_id=case_id,
                variant="runtime",
                scope="runtime_assertion",
                passed=passed,
                expected="existing runtime assertions pass",
                evidence=";".join(nodes),
                observed_completed=None,
                observed_requests=None,
                category=None,
            )
        )
    protocol = dict(
        model=fixtures.MODEL,
        response_format="json_schema",
        temperature=0,
        max_structured_repairs=1,
        max_physical_attempts_per_call=4,
        max_transport_retries=2,
        min_request_time_seconds=1.0,
        schedule=fixtures.schedule_manifest(),
        runtime_checks=RUNTIME_CHECKS,
        prompt=fixtures.PROMPT,
        input=fixtures.INPUT,
        schema=fixtures.CoordinatorDecision.model_json_schema(),
        jobs=1,
        network="httpx.MockTransport only",
        cache="off for provider ablations",
    )
    manifest = dict(
        source_revision=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        baseline_revision=fixtures.BASELINE,
        baseline_source_sha256=hashlib.sha256(baseline_source).hexdigest(),
        protocol_sha256=fixtures.digest(protocol),
        prompt_sha256=fixtures.digest(fixtures.PROMPT),
        schema_sha256=fixtures.digest(protocol["schema"]),
        dataset_sha256=fixtures.digest(protocol["schedule"]),
        provider_source_sha256=hashlib.sha256(
            (ROOT / "src/incident_lens/llm/provider.py").read_bytes()
        ).hexdigest(),
        git_dirty=bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
        experiment_type="deterministic offline fault injection",
        real_provider_calls=0,
    )
    (output / "baseline-provider.py").write_bytes(baseline_source)
    for name, data in (("manifest.json", manifest), ("protocol.json", protocol)):
        (output / name).write_text(json.dumps(data, indent=2), encoding="utf-8")
    write_csv(output / "case-level.csv", rows)
    write_csv(output / "aggregate.csv", aggregate_reliability(rows))
    write_csv(output / "fault-matrix.csv", matrix)
    with (output / "provider-attempts.jsonl").open("w", encoding="utf-8") as stream:
        for event in events:
            stream.write(json.dumps(event, sort_keys=True) + "\n")
    failures = [row for row in matrix if not row["passed"]]
    (output / "error-analysis.md").write_text(
        "# Offline reliability error analysis\n\n"
        f"Matrix assertions: {len(matrix) - len(failures)}/{len(matrix)} passed.\n\n"
        "HTTP/auth/schema/budget failure outcomes are intentional injected results, not assertion failures. "
        "R0 is frozen V1.2 source, including its length/envelope behavior. R1 hard guards still enforce "
        "budgets but lack recovery snapshots. R2/R3 can deny infeasible retries before sleep. "
        "Targeted and generic repairs receive the same corrected fixture, so this experiment does not "
        "establish a targeted-prompt quality benefit. Provider logical-call completion is not investigation "
        "completion or RCA accuracy. Runtime test evidence is separate and has unknown request/token totals. "
        "NULL aggregate tokens include failed dispatched attempts; measured tokens are a lower bound. "
        "Latency includes host overhead in R0 and injected time in R1-R3 and is not comparable.\n\n"
        + (json.dumps(failures, indent=2) if failures else "No unmet matrix expectations.\n"),
        encoding="utf-8",
    )
    (output / "README.md").write_text(
        "# Reliability artifacts\n\n"
        "Reproduce from the checkout root with PYTHONPATH=src and the project Python environment:\n\n"
        "`python scripts/run_reliability_eval.py --out results/v13-eval/NEW-ID`\n\n"
        "The output directory must not exist. Compare protocol/source hashes before combining experiments. "
        "Recompute aggregates from provider-scope case-level rows; runtime XML/logs contain assertion evidence. "
        "No live API, billing or RCA quality experiment was performed.\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            dict(
                cases=len(rows),
                matrix_passed=len(matrix) - len(failures),
                matrix_total=len(matrix),
                output=str(output),
            )
        )
    )
    return 1 if failures else 0


def expectation(scenario, variant):
    success, attempts = expected_outcome(scenario.case_id, variant)
    return f"completed={success}; actual_http_requests={attempts}"


def expected_outcome(case_id, variant):
    new = variant != "R0"
    table = {
        "F01": (True, 1),
        "F02": (new, 2 if new else 1),
        "F03": (False, 1),
        "F04": (new, 3 if new else 1),
        "F05": (False, 1),
        "F06": (False, 1),
        "F07": (new, 2 if new else 1),
        "F08": (True, 2),
        "F09": (True, 2),
        "F10": (False, 2),
        "F13": (False, 1),
        "F14": (False, 1),
        "F16": (True, 1),
        "F17": (True, 2 if new else 1),
        "F21": (False, 1),
        "F22": (False, 1),
        "F23": (False, 1),
        "F24": (False, 1),
        "F25": (new, 3 if new else 1),
        "F26": (False, 1),
        "F27": (False, 1),
        "F28": (True, 2),
        "F29": (new, 4 if new else 1),
        "F30": (False, 4 if new else 1),
    }
    return table[case_id]


def expected(row, scenario, variant):
    return (row["completed"], row["actual_http_requests"]) == expected_outcome(
        scenario.case_id, variant
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("--out must name a new directory; historical artifacts are never overwritten")
    raise SystemExit(asyncio.run(evaluate(args.out.resolve())))
