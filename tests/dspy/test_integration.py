"""Security boundaries and real DSPy optimizer integration using explicit mock fixtures."""

import asyncio
import copy
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pytest

from experiments.dspy.data import Sample, extract_events, load_samples, split_gate
from experiments.dspy.provider import RequestCap, make_provider
from experiments.dspy.replay import false_refutations
from incident_lens.agents.service import analyze, verify
from incident_lens.llm import MockProvider
from incident_lens.prompts.resolver import PromptResolver, digest
from incident_lens.prompts.snapshots import SnapshotRecorder


def require_dspy():
    # Pytest can expose tests/dspy as a namespace package. Import success alone
    # does not establish that the optional DSPy SDK distribution is installed.
    try:
        version("dspy")
    except PackageNotFoundError:
        pytest.skip("requires the optional DSPy SDK; install incident-lens[dspy]")
    return pytest.importorskip("dspy", minversion="3.0.4")


def context(incident="opaque"):
    return dict(role="changes", run_id="run", incident_id=incident,
                allowed_tools=["query_changes", "get_config_diff"])


def task():
    return dict(task_id="task", role="changes", question="Inspect configuration change",
                allowed_tools=["query_changes", "get_config_diff"], filters={},
                reason="Compare causes", expected_discriminator="Actual pool settings")


def records(incident="opaque"):
    return [dict(evidence_id="diff", incident_id=incident, source_type="configs", service="backend",
                 observed_at="2026-01-01T00:00:00Z", source_path="public/configs.jsonl",
                 excerpt="DB_POOL_MAX reduced from 20 to 2", metadata={})]


def samples(tmp_path):
    provider = MockProvider()
    events = []
    provider.snapshot_observer = events.append
    for incident in ("train-incident", "dev-incident"):
        asyncio.run(analyze(provider, context(incident), task(), records(incident)))
    result = []
    for index, (request, response) in enumerate(zip(events[::2], events[1::2])):
        result.append(Sample(sample_id=str(index), stage="analysis", role="changes",
                             payload=request["payload"], output_schema=request["schema"],
                             system_prompt=request["system_prompt"],
                             prompt_metadata=request["prompt_metadata"], source_sha256=digest([]),
                             split="train" if index == 0 else "dev",
                             # Synthetic contract fixture, never a real human-reviewed label.
                             annotation={"expected": response["output"]}))
    return result


def bundle(reviewed=False):
    from incident_lens.prompts.resolver import PromptBundle
    base = PromptResolver()
    value = PromptBundle(version="test", base_prompt_version=base.base_version,
                         base_prompt_sha256=base.base_hash, optimizer="manual",
                         training_data_sha256=digest([]),
                         tasks={"analysis": {"instructions": "Preserve unresolved alternatives."}})
    if reviewed:
        value.status = "reviewed"
        value.reviewer = "test-fixture"
        value.review_evidence = "unit-test-only"
    return value.model_dump(mode="json")


def test_bundle_review_version_and_rollback():
    original = PromptResolver()
    assert original.resolve("analysis", "original") == "original"
    with pytest.raises(ValueError, match="reviewed"):
        PromptResolver(bundle())
    value = bundle(True)
    resolver = PromptResolver(value)
    value["tasks"]["analysis"]["instructions"] = "Mutation after load"
    assert "Mutation" not in resolver.resolve("analysis", "original")
    assert resolver.resolve("plan", "original") == "original"
    assert resolver.bundle_hash != original.bundle_hash
    value["base_prompt_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="incompatible"):
        PromptResolver(value)


@pytest.mark.asyncio
async def test_bundle_cannot_bypass_dynamic_citations_or_identity():
    class Bad(MockProvider):
        async def structured_call(self, role, system_prompt, payload, output_model):
            output, usage = await super().structured_call(role, system_prompt, payload, output_model)
            value = output.model_dump(mode="json")
            value["hypotheses"][0]["against_ids"] = ["unobserved"]
            return output_model.model_validate(value), usage

    provider = Bad()
    provider.prompt_resolver = PromptResolver(bundle(True))
    with pytest.raises(ValueError) as error:
        await analyze(provider, context(), task(), records())
    assert "against_ids" in str(error.value.errors()[0]["loc"])


@pytest.mark.asyncio
async def test_verifier_citations_remain_bound_to_fetched_evidence():
    class Bad(MockProvider):
        async def structured_call(self, role, system_prompt, payload, output_model):
            output, usage = await super().structured_call(role, system_prompt, payload, output_model)
            value = output.model_dump(mode="json")
            value["cited_evidence_ids"] = ["unobserved"]
            return output_model.model_validate(value), usage


    provider = Bad()
    provider.prompt_resolver = PromptResolver(bundle(True))
    hypothesis, _ = await analyze(MockProvider(), context(), task(), records())
    with pytest.raises(ValueError) as error:
        await verify(provider, {"evidence_index": {}, "hypotheses": [
            h.model_dump(mode="json") for h in hypothesis.hypotheses]})
    assert "cited_evidence_ids" in str(error.value.errors()[0]["loc"])


@pytest.mark.asyncio
async def test_snapshot_capture_is_before_call_and_extraction_is_pending(tmp_path):
    provider = MockProvider()
    provider.snapshot_observer = SnapshotRecorder(tmp_path / "events.jsonl")
    await analyze(provider, context(), task(), records())
    events = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert [e["phase"] for e in events] == ["request", "result"]
    assert "output" not in events[0]
    assert "records" in events[0]["payload"]
    assert extract_events(tmp_path / "events.jsonl", tmp_path / "data.jsonl") == 1
    rows = load_samples(tmp_path / "data.jsonl")
    assert rows[0].annotation.status == "pending"
    with pytest.raises(ValueError, match="two reviewers"):
        load_samples(tmp_path / "data.jsonl", reviewed=True)


def test_no_oracle_or_family_leakage(tmp_path):
    rows = samples(tmp_path)
    split_gate(rows[:1], rows[1:])
    with pytest.raises(ValueError, match="disjoint families"):
        split_gate(rows[:1], rows[1:], independent=True)
    with pytest.raises(ValueError, match="overlap"):
        split_gate(rows[:1], rows[:1])
    from experiments.dspy.data import validate_payload
    snapshot = rows[0].model_input()
    snapshot["payload"] = dict(snapshot["payload"], ground_truth={"culprit": "backend"})
    with pytest.raises(ValueError):
        validate_payload(snapshot)


@pytest.mark.parametrize("optimizer", ["manual", "LabeledFewShot", "BootstrapFewShot", "MIPROv2"])
def test_dspy_compiler_and_exact_export_parity(tmp_path, optimizer):
    dspy = require_dspy()

    from experiments.dspy.optimize import (
        IncidentAdapter,
        compile_bundle,
        verify_export,
    )

    rows = samples(tmp_path)
    cap = RequestCap(100)
    provider = make_provider("mock", cap)
    artifact, program, lm = compile_bundle(rows, provider, "analysis", optimizer,
                                           shots=1, trials=2, engineering_fixture=True)
    assert artifact.status == "candidate"
    assert verify_export(program, lm, artifact, rows[1])["equivalent"]
    tampered = artifact.model_copy(deep=True)
    tampered.tasks["analysis"].instructions += " A changed exported instruction."
    with pytest.raises(ValueError, match="wire mismatch"):
        verify_export(program, lm, tampered, rows[1])
    with dspy.context(lm=lm, adapter=IncidentAdapter()):
        result = program(snapshot=rows[1].model_input())
    assert result.output["finding"]["incident_id"] == "dev-incident"
    assert cap.used <= 100
    Path(tmp_path / "ledger.json").write_text(json.dumps(lm.ledger))


@pytest.mark.asyncio
async def test_cap_survives_run_guard_rebinding():
    provider = make_provider("mock", RequestCap(1))
    calls = []
    provider.request_guard = lambda: calls.append("runtime-permit")
    await analyze(provider, context(), task(), records())
    with pytest.raises(RuntimeError, match="cap exhausted"):
        await analyze(provider, context(), task(), records())
    assert calls == ["runtime-permit"]


def test_false_refutation_metric_penalizes_rejecting_supported_alternative(tmp_path):
    reference = samples(tmp_path)[0].annotation.expected
    bad = copy.deepcopy(reference)
    bad["hypotheses"][0]["against_ids"] = ["diff"]
    bad["hypotheses"][0]["status"] = "REJECTED"
    assert false_refutations(reference, bad) == 1


def test_prompt_bundles_partition_the_real_cache_namespace(tmp_path):
    from types import SimpleNamespace

    from incident_lens.cache.policy import CachePolicy
    from incident_lens.cache.semantic import SemanticCacheAdapter

    cache = SemanticCacheAdapter(CachePolicy(), tmp_path / "cache.db", "revision")
    ctx = SimpleNamespace(workspace_id="workspace", incident_id="incident", role="changes")
    assignment = SimpleNamespace(role="changes")
    provider = MockProvider()
    before = cache.namespace(ctx, assignment, [], provider)
    provider.prompt_resolver = PromptResolver(bundle(True))
    after = cache.namespace(ctx, assignment, [], provider)
    assert before.prompt_version != after.prompt_version
    provider.prompt_resolver = PromptResolver()
    assert cache.namespace(ctx, assignment, [], provider) == before


def test_compiler_refuses_pending_labels_outside_explicit_fixture_mode(tmp_path):
    require_dspy()
    from experiments.dspy.optimize import compile_bundle

    with pytest.raises(ValueError, match="two reviewers"):
        compile_bundle(samples(tmp_path), MockProvider(), "analysis", "LabeledFewShot")


@pytest.mark.asyncio
async def test_module_failure_is_wrong_but_unknown_schema_and_cost(tmp_path):
    from experiments.dspy.evaluate import evaluate

    class Unavailable(MockProvider):
        async def structured_call(self, *args):
            raise TimeoutError()

    rows = await asyncio.to_thread(samples, tmp_path)
    report = await evaluate(rows, Unavailable, {"A0": PromptResolver()}, engineering_fixture=True)
    assert len(report["rows"]) == 1
    row = report["rows"][0]
    assert row["judgment_exact_match"] == 0
    assert row["schema_success"] is None
    assert row["false_refutations"] is None
    assert row["usage"].get("total_tokens") is None
