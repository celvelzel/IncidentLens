"""WP-B offline metric and fail-closed boundary regression tests."""

import copy

import pytest

from incident_lens.incidentbench.readiness import evaluate_completed, evaluate_run, summarize
from incident_lens.incidentbench.schemas import BenchmarkOracle


def fixture():
    oracle = BenchmarkOracle.model_validate(
        dict(
            incident_id="incident_001",
            scenario_family_id="family",
            mechanism_id="mechanism",
            is_identifiable=True,
            true_primary_root=dict(
                culprit_service="backend",
                failure_mode="backend_pool_config_regression",
                root_cause_code="config",
            ),
            acceptable_support_sets=[dict(evidence_ids=["e1", "e2"], rationale="reference")],
            contradicting_evidence_ids=[],
            misleading_evidence_ids=[],
            required_discriminator_types=[],
            causal_sequence=[],
            identifiability_rationale="reference",
        )
    )
    state = dict(
        incident_id="incident_001",
        run_id="run",
        workflow_status="FINISHED",
        report=dict(
            status="RESOLVED",
            root_cause=dict(
                culprit_service="backend", failure_mode="backend_pool_config_regression"
            ),
            supporting_evidence_ids=["e1", "bad"],
        ),
        events=[
            dict(
                event_type="STOP", details=dict(message_type="STOP", stop_reason="DIAGNOSIS_READY")
            )
        ],
        evidence_index={"e1": {}},
    )
    record = {"incident_id": "incident_001", "evidence_id": "e1"}
    state["evidence_index"]["e1"] = record
    state["events"].insert(
        0,
        dict(
            event_type="TOOL_CALL",
            run_id="run",
            incident_id="incident_001",
            details=dict(result=dict(ok=True, records=[record])),
        ),
    )
    state["report"]["remediation_status"] = "SKIPPED"
    return dict(
        run_key="key",
        incident_id="incident_001",
        variant="full",
        repeat_id=0,
        state=state,
        usage={},
    ), oracle


def test_service_mechanism_exact_and_reference_coverage():
    raw, oracle = fixture()
    result = evaluate_run(raw, oracle)
    assert result["exact_diagnostic_match"] is True
    assert result["reference_support_set_coverage"] == 0.5
    assert result["missing_reference_ids"] == ["bad"]
    assert result["missing_support_reference_ids"] == ["e2"]
    assert result["semantic_support_status"] == "unreviewed"
    assert result["human_support_rate"] is None
    wrong = oracle.model_copy(deep=True)
    wrong.true_primary_root.culprit_service = "other"
    result = evaluate_run(raw, wrong)
    assert result["culprit_service_correct"] is False
    assert result["mechanism_correct"] is True
    assert result["exact_diagnostic_match"] is False
    assert result["outcome_classification"] == "SUCCESS + INCORRECT"


def test_abstention_and_technical_failures_have_distinct_denominators():
    raw, oracle = fixture()
    raw["state"]["report"].update(status="INCONCLUSIVE", root_cause=None)
    raw["state"]["events"][-1]["details"]["stop_reason"] = "INCONCLUSIVE"
    negative = oracle.model_copy(update={"is_identifiable": False, "acceptable_support_sets": []})
    correct = evaluate_run(raw, negative)
    incorrect = evaluate_run(raw, oracle)
    assert correct["outcome_classification"] == "INCONCLUSIVE + CORRECT_ABSTENTION"
    assert incorrect["outcome_classification"] == "INCONCLUSIVE + INCORRECT_ABSTENTION"
    failed = copy.deepcopy(raw)
    failed["state"].update(report=None, events=[], execution_error={"code": "INTERRUPTED"})
    failure = evaluate_run(failed)
    assert failure["outcome_classification"] == "TECHNICAL_FAILURE"
    assert failure["input_tokens"] is failure["output_tokens"] is failure["cost_usd"] is None
    summary = summarize([correct, incorrect, failure])[0]
    assert summary["attempted_n"] == 3
    assert summary["technical_failure"]["denominator"] == 3
    assert summary["correct_abstention"]["denominator"] == 1
    assert summary["exact_diagnostic_match"]["denominator"] == 1


def test_public_output_and_overwrite_refused_before_oracle_access(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("oracle accessed before output validation")

    monkeypatch.setattr("incident_lens.incidentbench.readiness.OracleStore", forbidden)
    with pytest.raises(PermissionError):
        evaluate_completed("missing", "missing", "missing", tmp_path / "public", "missing")
    out = tmp_path / "local_oracles" / "existing"
    out.mkdir(parents=True)
    with pytest.raises(PermissionError):
        evaluate_completed("missing", "missing", "missing", out, "missing")


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    import hashlib
    from types import SimpleNamespace

    from incident_lens.incidentbench import readiness as module
    from incident_lens.incidentbench.experiment import (
        canonical,
        durable_write,
        run_identity,
        run_order,
    )
    from incident_lens.incidentbench.manifest import digest_tree
    from incident_lens.incidentbench.schemas import ExperimentProtocol

    dataset = tmp_path / "dataset"
    dataset.mkdir()
    history = tmp_path / "history"
    history.mkdir()
    for name in ("src", "scripts", "configs", "prompts"):
        (history / name).mkdir()
    experiment = tmp_path / "experiment"
    (experiment / "states").mkdir(parents=True)
    protocol = ExperimentProtocol()
    context = dict(
        experiment_id="00000000-0000-0000-0000-000000000001",
        dataset_root=str(dataset),
        split="seed",
    )
    metadata = {"incident_id": "incident_001", "split": "seed"}
    case = SimpleNamespace(incident_id="incident_001", model_dump=lambda **kwargs: metadata)
    monkeypatch.setattr(module, "load_cases", lambda *args: (dataset.resolve(), dataset, [case]))
    lock = {key: "fixture" for key in ("public_sha256", "protocol_sha256", "python_version")}
    lock.update(installed_dependencies={}, version=1)
    for key, folder in (
        ("source_sha256", "src"),
        ("scripts_sha256", "scripts"),
        ("config_sha256", "configs"),
        ("prompt_sha256", "prompts"),
    ):
        lock[key] = digest_tree(history / folder)
    lock["dependency_lock_sha256"] = hashlib.sha256(
        b"pyproject.toml\0ABSENTrequirements.lock\0ABSENT"
    ).hexdigest()
    monkeypatch.setattr(module, "create_lock", lambda *args: lock.copy())
    order = run_order(["incident_001"], protocol)
    raws, scores, progress = [], [], []
    for incident, repeat, variant in order:
        key = f"{incident}.{variant}.repeat-{repeat}"
        run_id = run_identity(context["experiment_id"], key)
        state = dict(
            incident_id=incident,
            run_id=run_id,
            workflow_status="FAILED",
            report=None,
            execution_error={"code": "INTERRUPTED"},
            events=[],
        )
        path = experiment / "states" / f"{key}.json"
        durable_write(path, state)
        receipt = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        raws.append(
            dict(
                run_key=key,
                incident_id=incident,
                repeat_id=repeat,
                variant=variant,
                run_id=run_id,
                metadata=metadata,
                state=dict(state, completion_receipt=receipt),
            )
        )
        scores.append(dict(run_key=key))
        progress.extend(
            [
                dict(run_key=key, run_id=run_id, status="STARTED"),
                dict(run_key=key, run_id=run_id, status="DURABLE", receipt=receipt),
            ]
        )
    for name, data in (
        ("protocol.json", protocol.model_dump(mode="json")),
        ("experiment-context.json", context),
        ("protocol.lock.json", lock),
        ("manifest-lock.json", lock),
        ("run-order.json", order),
    ):
        durable_write(experiment / name, data)
    for name, rows in (
        ("raw-runs.jsonl", raws),
        ("scores.jsonl", scores),
        ("progress.jsonl", progress),
    ):
        (experiment / name).write_bytes(b"".join(canonical(row) + b"\n" for row in rows))

    def digest():
        import json

        (experiment / "artifact-digests.json").write_text(
            json.dumps(
                {
                    name: hashlib.sha256((experiment / name).read_bytes()).hexdigest()
                    for name in (
                        "raw-runs.jsonl",
                        "scores.jsonl",
                        "protocol.json",
                        "experiment-context.json",
                    )
                }
            )
        )

    digest()
    return experiment, dataset, history, digest


def test_complete_failed_ledger_validates_without_loading_labels(ledger):
    from incident_lens.incidentbench.readiness import validate_completed

    experiment, dataset, history, _ = ledger
    _, raws, provenance = validate_completed(experiment, dataset, history)
    assert len(raws) == 4
    assert provenance["historical_runtime_reexecuted"] is False


@pytest.mark.parametrize(
    "corruption", ["digest", "receipt", "order", "metadata", "partial", "progress"]
)
def test_corrupt_ledger_refused_before_oracle_access(ledger, monkeypatch, tmp_path, corruption):
    import json

    from incident_lens.incidentbench.experiment import canonical

    experiment, dataset, history, digest = ledger
    if corruption == "digest":
        with (experiment / "raw-runs.jsonl").open("ab") as stream:
            stream.write(b"{}\n")
    elif corruption == "order":
        (experiment / "run-order.json").write_text("[]")
    else:
        name = "progress.jsonl" if corruption == "progress" else "raw-runs.jsonl"
        rows = [json.loads(line) for line in (experiment / name).read_bytes().splitlines()]
        if corruption == "receipt":
            rows[0]["state"]["completion_receipt"]["sha256"] = "0" * 64
        elif corruption == "metadata":
            rows[0]["metadata"] = {}
        elif corruption == "partial":
            rows.pop()
        elif corruption == "progress":
            rows.reverse()
        (experiment / name).write_bytes(b"".join(canonical(row) + b"\n" for row in rows))
        digest()

    def forbidden(*args, **kwargs):
        pytest.fail("oracle accessed for corrupted ledger")

    monkeypatch.setattr("incident_lens.incidentbench.readiness.OracleStore", forbidden)
    from types import SimpleNamespace

    monkeypatch.setattr(
        "incident_lens.incidentbench.readiness.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=b""),
    )
    labels = tmp_path / "labels"
    labels.mkdir()
    with pytest.raises(ValueError):
        evaluate_completed(
            experiment, dataset, labels, tmp_path / "local_oracles" / "out", history, tmp_path
        )


@pytest.mark.parametrize(
    "error, category",
    [
        ("BUDGET_EXHAUSTED", "BUDGET_EXHAUSTED"),
        ("PROVIDER_TIMEOUT", "PROVIDER_FAILURE"),
        ("STRUCTURED_OUTPUT_INVALID", "PROVIDER_FAILURE"),
        ("PROTOCOL_MISMATCH", "PROTOCOL_INVALID"),
    ],
)
def test_failure_categories_preserve_attempts(error, category):
    raw, oracle = fixture()
    raw["state"].update(report=None, events=[], execution_error={"code": error})
    result = evaluate_run(raw, oracle)
    assert result["outcome_classification"] == category
    assert summarize([result])[0]["technical_failure"] == {
        "numerator": 1,
        "denominator": 1,
        "rate": 1,
    }


def test_unobserved_index_entry_cannot_cover_reference_set():
    raw, oracle = fixture()
    raw["state"]["events"] = raw["state"]["events"][-1:]
    result = evaluate_run(raw, oracle)
    assert result["reference_support_set_coverage"] == 0
    assert result["missing_reference_ids"] == ["bad", "e1"]


@pytest.mark.parametrize("destination", ["docs/local_oracles/out", "local_oracles/labels/out"])
def test_nested_public_or_oracle_overlapping_output_rejected(tmp_path, monkeypatch, destination):
    from types import SimpleNamespace

    labels = tmp_path / "local_oracles" / "labels"
    labels.mkdir(parents=True)
    monkeypatch.setattr(
        "incident_lens.incidentbench.readiness.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=b""),
    )

    def forbidden(*args, **kwargs):
        pytest.fail("oracle accessed before private destination validation")

    monkeypatch.setattr("incident_lens.incidentbench.readiness.OracleStore", forbidden)
    with pytest.raises(PermissionError):
        evaluate_completed(
            "missing", "missing", labels, tmp_path / destination, "missing", tmp_path
        )


def test_unrecovered_model_failure_without_usage_is_provider_failure():
    raw, _ = fixture()
    raw["state"].update(report=None, events=[dict(event_type="MODEL_FAILURE", details={})])
    assert evaluate_run(raw)["outcome_classification"] == "PROVIDER_FAILURE"


def test_acceptance_binds_exact_oracle_and_public_bytes(tmp_path):
    import json

    from incident_lens.incidentbench.manifest import digest_tree
    from incident_lens.incidentbench.readiness import validate_acceptance

    public, labels = tmp_path / "public", tmp_path / "labels"
    public.mkdir()
    labels.mkdir()
    candidate = labels / "benchmark_oracle.json"
    candidate.write_text('{"candidate": "original"}')
    acceptance = tmp_path / "acceptance.json"
    acceptance.write_text(
        json.dumps(
            {
                "reference_label_policy": {
                    "status": "project_accepted",
                    "authorization": "OWNER_REVIEW_ACCEPTED",
                },
                "datasets": {
                    "seed": {
                        "public_sha256": digest_tree(public),
                        "oracle_sha256": digest_tree(labels),
                    }
                },
            }
        )
    )
    result = validate_acceptance(acceptance, "seed", public, labels)
    assert result["accepted_oracle_sha256"] == digest_tree(labels)
    candidate.write_text('{"candidate": "changed"}')
    with pytest.raises(ValueError, match="hash mismatch"):
        validate_acceptance(acceptance, "seed", public, labels)
    with pytest.raises(ValueError, match="hash mismatch"):
        validate_acceptance(acceptance, "dev", public, labels)
