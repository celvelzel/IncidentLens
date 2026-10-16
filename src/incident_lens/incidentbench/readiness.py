"""Offline course-project evaluation; never changes runtime or formal label status."""

import hashlib
from collections import Counter
from pathlib import Path
from uuid import UUID

from incident_lens.evaluation.metrics import report_citations

from .experiment import canonical, load_cases, read_json, read_jsonl, run_identity, run_order
from .manifest import create_lock, digest_tree
from .oracle_store import OracleStore, safe_path
from .schemas import ExperimentProtocol
from .scorer import score_benchmark_run


def evaluate_run(raw, oracle=None):
    """Reference coverage is syntactic coverage, not human semantic grounding."""
    state = raw["state"]
    usage = raw.get("usage", {})
    result = score_benchmark_run(state, oracle)
    ok = result["technical_completion"]
    root = (state.get("report") or {}).get("root_cause") or {}
    eligible = oracle is not None and oracle.is_identifiable
    service = (
        bool(
            ok
            and result["resolved"]
            and root.get("culprit_service") == oracle.true_primary_root.culprit_service
        )
        if eligible
        else None
    )
    mechanism = (
        bool(
            ok
            and result["resolved"]
            and root.get("failure_mode") == oracle.true_primary_root.failure_mode
        )
        if eligible
        else None
    )
    reason = result.get("termination_reason") or ""
    error = (state.get("execution_error") or {}).get("code", "")
    if not ok:
        if result.get("protocol_valid") is False or error == "PROTOCOL_MISMATCH":
            outcome = "PROTOCOL_INVALID"
        elif "BUDGET" in reason or "BUDGET" in error:
            outcome = "BUDGET_EXHAUSTED"
        elif (
            usage.get("provider_failures")
            or result.get("unrecovered_model_failure_count")
            or "PROVIDER" in reason
            or "MODEL" in reason
            or "PROVIDER" in error
            or error == "STRUCTURED_OUTPUT_INVALID"
        ):
            outcome = "PROVIDER_FAILURE"
        else:
            outcome = "TECHNICAL_FAILURE"
    elif result["abstained"]:
        outcome = "INCONCLUSIVE + " + (
            "UNLABELLED"
            if oracle is None
            else "INCORRECT_ABSTENTION"
            if oracle.is_identifiable
            else "CORRECT_ABSTENTION"
        )
    else:
        outcome = "SUCCESS + " + (
            "UNLABELLED"
            if oracle is None
            else "CORRECT"
            if eligible and service and mechanism
            else "INCORRECT"
        )
    citations = set(report_citations(state.get("report")))
    known = set()
    for event in state.get("events", []):
        if (
            event.get("event_type") != "TOOL_CALL"
            or event.get("run_id") != state.get("run_id")
            or event.get("incident_id") != state.get("incident_id")
        ):
            continue
        tool_result = event.get("details", {}).get("result", {})
        if tool_result.get("ok") is True:
            for record in tool_result.get("records", []):
                eid = record.get("evidence_id")
                if record.get("incident_id") == state.get("incident_id") and record == state.get(
                    "evidence_index", {}
                ).get(eid):
                    known.add(eid)
    valid_citations = citations & known
    sets = [set(s.evidence_ids) for s in oracle.acceptable_support_sets] if oracle else []
    best = max(sets, key=lambda s: len(valid_citations & s) / len(s)) if sets else None
    result.update(
        run_key=raw["run_key"],
        incident_id=raw["incident_id"],
        variant=raw["variant"],
        repeat_id=raw["repeat_id"],
        outcome_classification=outcome,
        culprit_service_correct=service,
        mechanism_correct=mechanism,
        exact_diagnostic_match=bool(service and mechanism) if eligible else None,
        technical_failure=not ok,
        false_diagnosis=bool(ok and result["resolved"] and not (eligible and service and mechanism))
        if oracle
        else None,
        incorrect_abstention=bool(result["abstained"]) if eligible else None,
        missing_reference_ids=sorted(citations - known),
        citations_outside_reference_support_sets=sorted(citations - set().union(*sets))
        if sets
        else None,
        reference_support_set_coverage=len(valid_citations & best) / len(best) if best else None,
        missing_support_reference_ids=sorted(best - valid_citations) if best else None,
        semantic_support_status="unreviewed",
        logical_requests=usage.get("logical_structured_calls"),
        physical_http_attempts=usage.get("actual_http_requests"),
        transport_retries=usage.get("transport_retries"),
        task_retries=usage.get("task_retries"),
        timeout_count=usage.get("timeout_count"),
        observed_timeout_failures=sum(
            e.get("event_type") == "MODEL_FAILURE"
            and "TIMEOUT" in str(e.get("details", {}).get("code", ""))
            for e in state.get("events", [])
        ),
        tool_calls=sum(e.get("event_type") == "TOOL_CALL" for e in state.get("events", [])),
        execution_time_ms=raw.get("latency_ms"),
        input_tokens=usage.get("prompt_tokens"),
        output_tokens=usage.get("completion_tokens"),
        cost_usd=usage.get("cost_usd"),
    )
    return result


def summarize(rows):
    output = []
    for variant in sorted({r["variant"] for r in rows}):
        group = [r for r in rows if r["variant"] == variant]
        item = {
            "variant": variant,
            "attempted_n": len(group),
            "labelled_n": sum(r.get("label_status") != "unscored" for r in group),
            "unlabelled_n": sum(r.get("label_status") == "unscored" for r in group),
            "technical_failure_n": sum(r["technical_failure"] for r in group),
            "outcomes": dict(Counter(r["outcome_classification"] for r in group)),
        }
        for name in (
            "culprit_service_correct",
            "mechanism_correct",
            "exact_diagnostic_match",
            "root_cause_correct",
            "correct_abstention",
            "incorrect_abstention",
            "false_diagnosis",
            "technical_failure",
        ):
            values = [r[name] for r in group if r.get(name) is not None]
            item[name] = {
                "numerator": sum(values),
                "denominator": len(values),
                "rate": sum(values) / len(values) if values else None,
            }
        output.append(item)
    return output


def validate_completed(experiment, dataset, historical_source_root):
    """Validate all public artifacts and receipts before any OracleStore access."""
    experiment = safe_path(experiment)
    protocol = ExperimentProtocol.model_validate(read_json(experiment / "protocol.json"))
    context = read_json(experiment / "experiment-context.json")
    if str(UUID(context["experiment_id"])) != context["experiment_id"]:
        raise ValueError("invalid experiment identity")
    root, _, cases = load_cases(dataset, context["split"])
    if root != safe_path(context["dataset_root"]):
        raise ValueError("dataset context mismatch")
    lock = read_json(experiment / "protocol.lock.json")
    if lock != read_json(experiment / "manifest-lock.json"):
        raise ValueError("manifest lock mismatch")
    current = create_lock(root, protocol)
    historical = safe_path(historical_source_root)
    for key, directory in (
        ("source_sha256", "src"),
        ("scripts_sha256", "scripts"),
        ("prompt_sha256", "prompts"),
        ("config_sha256", "configs"),
    ):
        if lock.get(key) != digest_tree(
            historical / directory, source_only=directory in {"src", "scripts"}
        ):
            raise ValueError(f"historical {key} mismatch")
    dependencies = hashlib.sha256()
    for name in ("pyproject.toml", "requirements.lock"):
        path = historical / name
        dependencies.update(name.encode() + b"\0")
        dependencies.update(safe_path(path).read_bytes() if path.exists() else b"ABSENT")
    if dependencies.hexdigest() != lock.get("dependency_lock_sha256"):
        raise ValueError("historical dependency lock mismatch")
    for key in (
        "public_sha256",
        "protocol_sha256",
        "installed_dependencies",
        "python_version",
        "version",
    ):
        if lock.get(key) != current[key]:
            raise ValueError(f"locked {key} mismatch")
    digests = read_json(experiment / "artifact-digests.json")
    required = {"raw-runs.jsonl", "scores.jsonl", "protocol.json", "experiment-context.json"}
    if set(digests) != required:
        raise ValueError("incomplete artifact digest ledger")
    for name, digest in digests.items():
        if hashlib.sha256(safe_path(experiment / name).read_bytes()).hexdigest() != digest:
            raise ValueError("artifact digest mismatch")
    order = [list(row) for row in run_order([c.incident_id for c in cases], protocol)]
    if read_json(experiment / "run-order.json") != order:
        raise ValueError("run order mismatch")
    raws = read_jsonl(experiment / "raw-runs.jsonl")
    scores = read_jsonl(experiment / "scores.jsonl")
    progress = read_jsonl(experiment / "progress.jsonl")
    if len(raws) != len(order) or len(scores) != len(order) or len(progress) != 2 * len(order):
        raise ValueError("partial completed ledger")
    metadata = {c.incident_id: c.model_dump(mode="json") for c in cases}
    for index, ((incident, repeat, variant), raw, score) in enumerate(zip(order, raws, scores)):
        key = f"{incident}.{variant}.repeat-{repeat}"
        run_id = run_identity(context["experiment_id"], key)
        if (
            any(
                raw.get(k) != v
                for k, v in {
                    "run_key": key,
                    "incident_id": incident,
                    "repeat_id": repeat,
                    "variant": variant,
                    "run_id": run_id,
                    "metadata": metadata[incident],
                }.items()
            )
            or score.get("run_key") != key
        ):
            raise ValueError("raw/score identity or metadata mismatch")
        state = dict(raw["state"])
        receipt = state.pop("completion_receipt")
        path = safe_path(experiment / "states" / f"{key}.json")
        if (
            safe_path(receipt["path"]) != path
            or canonical(state) != path.read_bytes()
            or hashlib.sha256(path.read_bytes()).hexdigest() != receipt["sha256"]
            or state.get("incident_id") != incident
            or state.get("run_id") != run_id
            or state.get("workflow_status") not in {"FINISHED", "FAILED"}
        ):
            raise ValueError("completion receipt mismatch")
        for offset, status in enumerate(("STARTED", "DURABLE")):
            event = progress[index * 2 + offset]
            if (
                event.get("run_key") != key
                or event.get("run_id") != run_id
                or event.get("status") != status
            ):
                raise ValueError("progress identity/order mismatch")
            if status == "DURABLE" and event.get("receipt") != receipt:
                raise ValueError("progress receipt mismatch")
    return (
        root,
        raws,
        {
            "historical_execution_lock": lock,
            "current_evaluator_lock": current,
            "historical_runtime_reexecuted": False,
        },
    )


def evaluate_completed(experiment, dataset, oracle_root, out, historical_source_root):
    """Write private evaluator output once; a failed state remains in the denominator."""
    out = Path(out).absolute()
    if "local_oracles" not in out.parts or out.exists():
        raise PermissionError("output must be a new evaluator-only local_oracles directory")
    ancestor = out.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    safe_path(ancestor)
    root, raws, provenance = validate_completed(experiment, dataset, historical_source_root)
    if out.resolve().is_relative_to(root) or root.is_relative_to(out.resolve()):
        raise PermissionError("evaluator output overlaps public data")
    store = OracleStore(oracle_root, public_root=root)
    rows = []
    for raw in raws:
        oracle = None
        error = None
        if raw["metadata"]["split"] != "test" and raw["state"].get("report"):
            try:
                oracle = store.load_after_completion(raw["incident_id"], raw["state"])
            except PermissionError as exc:
                error = str(exc)
        row = evaluate_run(raw, oracle)
        row["label_load_error"] = error
        rows.append(row)
    out.mkdir(parents=True, exist_ok=False)
    from .experiment import durable_write

    durable_write(
        out / "evaluation.json",
        {
            "rows": rows,
            "aggregate": summarize(rows),
            "provenance": provenance,
            "reference_label_policy": "candidate_reference; see external owner acceptance",
            "formal_independent_review": "unchanged; not asserted",
            "coverage_policy": "reference coverage only; not semantic support",
        },
    )
    return rows
