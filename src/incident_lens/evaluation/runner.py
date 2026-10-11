"""Execute comparable runs; private oracles enter only after execution ends."""

import csv
import hashlib
import json
import re
import stat
import time
from pathlib import Path

from incident_lens.llm import LLMProvider, MockProvider
from incident_lens.orchestration.graph import run_investigation
from incident_lens.schemas import Budget
from incident_lens.tools import EvidenceProvider

from .metrics import VARIANTS, aggregate, score_completed

SPLITS = ("seed", "dev", "test")
CASE_ID = re.compile(r"^incident_[0-9]{3,}$")


def safe_file(root, *parts):
    """No links, junctions or escaped paths in split and private-oracle reads."""
    root = Path(root).absolute()
    path = root
    for part in (None, *parts):
        if part is not None:
            if part in ("", ".", "..") or any(c in part for c in ("/", "\\", ":")):
                raise ValueError("invalid evaluation path component")
            path /= part
        info = path.lstat()
        if (
            path.is_symlink()
            or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise ValueError("evaluation paths cannot contain links or junctions")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("evaluation path escapes dataset")
    return path


def load_split(data_root, split):
    if split not in SPLITS:
        raise ValueError("unknown split")
    ids = json.loads(
        safe_file(data_root, "splits", split + "_ids.json").read_text(encoding="utf-8")
    )
    if (
        not isinstance(ids, list)
        or not ids
        or any(not isinstance(i, str) or not CASE_ID.fullmatch(i) for i in ids)
        or len(ids) != len(set(ids))
    ):
        raise ValueError("split must contain unique neutral incident IDs")
    return ids


def load_oracle_after_run(data_root, incident_id, state):
    if state.get("report") is None or state["incident_id"] != incident_id:
        raise ValueError("oracle requires the matching completed run")
    if not CASE_ID.fullmatch(incident_id):
        raise ValueError("invalid incident ID")
    oracle = json.loads(
        safe_file(data_root, "incidents", incident_id, "private", "ground_truth.json").read_text(
            encoding="utf-8"
        )
    )
    for key in ("is_identifiable", "culprit_service", "failure_mode"):
        if key not in oracle:
            raise ValueError("incomplete evaluation oracle")
    return oracle


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class MeasuredProvider(LLMProvider):
    """Keep usage from failed calls without capturing request contents or secrets."""

    def __init__(self, delegate):
        self.delegate = delegate
        self.model_id = delegate.model_id
        self.temperature = delegate.temperature
        self.calls = []
        # The graph shallow-copies providers to isolate each run's budget guard.
        # Keep counters shared with that copy, just like the call records.
        self._measurement = {"actual_requests": 0}
        self.source = "mock" if isinstance(delegate, MockProvider) else "model"

    @property
    def actual_requests(self):
        return self._measurement["actual_requests"]

    async def structured_call(self, role, system_prompt, user_payload, output_model):
        def guard():
            if self.request_guard is not None:
                self.request_guard()
            self._measurement["actual_requests"] += 1

        self.delegate.request_guard = guard
        self.delegate.token_observer = self.token_observer
        before = self.actual_requests
        try:
            result, usage = await self.delegate.structured_call(
                role, system_prompt, user_payload, output_model
            )
            self.calls.append(dict(usage=usage, failed=False))
            return result, usage
        except BaseException as exc:
            usage = dict(getattr(exc, "usage", {}))
            usage.setdefault("llm_calls", self.actual_requests - before)
            self.calls.append(dict(usage=usage, failed=True))
            raise


def usage_metrics(provider, state):
    def token_sum(key):
        values = [c["usage"].get(key) for c in provider.calls]
        if not values or any(v is None for v in values):
            return None
        return sum(values)

    failed_tools = sum(
        e["event_type"] == "TOOL_CALL" and e.get("details", {}).get("result", {}).get("ok") is False
        for e in state.get("events", [])
    )
    return dict(
        llm_requests=provider.actual_requests,
        prompt_tokens=token_sum("prompt_tokens"),
        completion_tokens=token_sum("completion_tokens"),
        total_tokens=token_sum("total_tokens"),
        cost_usd=None,
        failed_calls=sum(c["failed"] for c in provider.calls) + failed_tools,
        failed_model_calls=sum(c["failed"] for c in provider.calls),
        failed_tool_calls=failed_tools,
    )


def write_csv(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


async def evaluate_split(
    data_root, split, variants, provider_factory, out, budget=None, provider_name="mock"
):
    if provider_name not in ("mock", "real"):
        raise ValueError("provider must be mock or real")
    variants = tuple(variants)
    if (
        not variants
        or len(set(variants)) != len(variants)
        or any(v not in VARIANTS for v in variants)
    ):
        raise ValueError("invalid evaluation variants")
    ids = load_split(data_root, split)
    budget = budget or Budget()
    public_provider = EvidenceProvider(data_root)
    revision = public_provider.dataset_revision
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rows, raw = [], []
    reference_config = None
    for incident_id in ids:
        initial = public_provider.load_case(incident_id).model_dump(mode="json")
        for variant in variants:
            if public_provider.dataset_revision != revision:
                raise ValueError("public dataset changed during evaluation")
            provider = MeasuredProvider(provider_factory())
            if (provider_name == "mock") != (provider.source == "mock"):
                raise ValueError("requested provider does not match actual provider")
            config = dict(
                provider=provider_name,
                source=provider.source,
                model_id=provider.model_id,
                temperature=provider.temperature,
                budget=budget.model_dump(mode="json"),
                dataset_revision=revision,
                cache_mode="off",
                semantic_cache_attached=False,
            )
            if reference_config is None:
                reference_config = config
            elif config != reference_config:
                raise ValueError("provider or budget configuration changed between variants")
            started = time.monotonic()
            execution_error = None
            try:
                # None is explicit even if CACHE_MODE or historical SQLite files exist.
                completed = await run_investigation(
                    incident_id,
                    provider,
                    data_root=data_root,
                    budget=budget.model_copy(deep=True),
                    variant=variant,
                    cache=None,
                )
                state = completed.model_dump(mode="json")
                if state.get("report") is None:
                    raise ValueError("run returned no report")
            except Exception as exc:
                execution_error = type(exc).__name__
                state = dict(
                    incident_id=incident_id,
                    evidence_index={},
                    events=[],
                    report=dict(status="ERROR", root_cause=None, stop_reason=execution_error),
                    tool_calls_used=None,
                )
            elapsed = (time.monotonic() - started) * 1000
            if public_provider.dataset_revision != revision:
                raise ValueError("public dataset changed during execution")
            # Private truth cannot enter graph construction, prompts or tool dispatch.
            try:
                oracle = load_oracle_after_run(data_root, incident_id, state)
                scores = score_completed(state, oracle)
                evaluation_error = None
            except (OSError, ValueError, KeyError, TypeError) as exc:
                oracle = None
                evaluation_error = type(exc).__name__
                scores = dict(
                    identifiable=None,
                    root_cause_correct=None,
                    correct_abstention=None,
                    misleading_case=None,
                    misleading_correct=None,
                    citation_count=0,
                    valid_citation_count=0,
                    citation_existence_validity=None,
                    unsupported_claim_rate=None,
                    semantic_review_status="unreviewed",
                )
            root = state["report"].get("root_cause")
            row = dict(
                incident_id=incident_id,
                variant=variant,
                split=split,
                source=provider.source,
                provider=provider_name,
                model_id=provider.model_id,
                temperature=provider.temperature,
                cache_mode="off",
                config_sha256=digest(config),
                initial_public_sha256=digest(initial),
                dataset_revision=revision,
                status=state["report"]["status"],
                predicted_service=root["culprit_service"] if root else None,
                predicted_failure_mode=root["failure_mode"] if root else None,
                tool_calls=state.get("tool_calls_used"),
                latency_ms=elapsed,
                stop_reason=state["report"].get("stop_reason"),
                execution_error=execution_error,
                evaluation_error=evaluation_error,
                **usage_metrics(provider, state),
                **scores,
            )
            rows.append(row)
            raw.append(
                dict(
                    metrics=row,
                    fairness=config,
                    initial_public=initial,
                    state=state,
                    measured_calls=provider.calls,
                    oracle_scoring_fields={
                        k: oracle.get(k)
                        for k in (
                            "is_identifiable",
                            "culprit_service",
                            "failure_mode",
                            "misleading_evidence_ids",
                        )
                    }
                    if oracle
                    else None,
                )
            )
            # Persist every completed case so an interrupted paid run remains auditable.
            with (out / "raw-runs.jsonl").open(
                "a" if len(raw) > 1 else "w", encoding="utf-8"
            ) as stream:
                stream.write(json.dumps(raw[-1], ensure_ascii=False) + "\n")
            write_csv(out / "case-level.csv", rows)
    totals = aggregate(rows)
    write_csv(out / "aggregate.csv", totals)
    lines = [
        "# Evaluation error analysis",
        "",
        f"Split: {split}; actual provider: {provider_name}.",
        "Mock results are offline smoke checks, not real-model accuracy evidence."
        if provider_name == "mock"
        else "These results come from actual configured provider attempts; failed calls remain in the denominator.",
        "",
        "Caching was forced off. Identifiable accuracy, unidentifiable abstention and misleading identifiable accuracy use separate denominators.",
        "Citation validity measures reference existence in current shared evidence; semantic claim support is unreviewed.",
        "Unknown token and USD cost values are blank. No tariff or real-model cost was invented.",
        "",
        "| Variant | Runs | Correct / identifiable | Correct abstention / unidentifiable |",
        "| --- | ---: | ---: | ---: |",
    ]
    for item in totals:
        lines.append(
            f"| {item['variant']} | {item['runs']} | {item['root_cause_correct']} / {item['identifiable_denominator']} | {item['correct_abstentions']} / {item['unidentifiable_denominator']} |"
        )
    lines += ["", "## Cases requiring review", ""]
    failures = [
        r
        for r in rows
        if r.get("root_cause_correct") is False
        or r.get("correct_abstention") is False
        or r.get("execution_error")
        or r.get("evaluation_error")
    ]
    lines += [
        f"- {r['incident_id']} / {r['variant']}: {r['status']}; {r['stop_reason']}; execution={r['execution_error'] or 'none'}, evaluation={r['evaluation_error'] or 'none'}."
        for r in failures
    ] or ["No automatically scored failure; human semantic review remains pending."]
    (out / "error-analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows, totals
