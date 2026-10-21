"""DSPy uses a custom Adapter with the exact production task renderer and provider.

Never interpret an arbitrary native DSPy program as a plain prompt string. Only
this adapter's instructions and demonstrations can be exported to our format.
"""

import asyncio
from pathlib import Path
from time import perf_counter

import dspy
from pydantic import create_model

from incident_lens.prompts.resolver import (
    FORMAT,
    Demonstration,
    PromptBundle,
    PromptResolver,
    TaskPrompt,
    canonical,
    digest,
)
from incident_lens.schemas import StrictModel

from .replay import replay, semantic_score

INITIAL_INSTRUCTION = (
    "Assess causal evidence. Distinguish support for a candidate, direct contradiction of an "
    "alternative, and missing evidence. Preserve unresolved competitors and causal uncertainty. "
    "Return the complete required structured judgment using only current observations."
)


class TaskSignature(dspy.Signature):
    """Assess causal evidence and return the required structured judgment."""

    snapshot: dict = dspy.InputField(desc="Public pre-decision state")
    output: dict = dspy.OutputField(desc="Complete structured AnalysisOutput or Review")


def task_prompt(signature, demos):
    return TaskPrompt(instructions=signature.instructions, demonstrations=[
        Demonstration(inputs=d["snapshot"], output=d["output"]) for d in demos
    ])


def candidate(stage, task, *, optimizer="manual", training_hash=None):
    base = PromptResolver()
    return PromptBundle(version="offline-candidate", base_prompt_version=base.base_version,
                        base_prompt_sha256=base.base_hash, optimizer=optimizer,
                        training_data_sha256=training_hash or digest([]), tasks={stage: task})


class ProviderLM(dspy.BaseLM):
    def __init__(self, provider):
        super().__init__(model=provider.model_id, temperature=provider.temperature, cache=False)
        self.provider = provider
        self.ledger = []

    def __call__(self, *args, **kwargs):
        raise RuntimeError("ProviderLM requires IncidentAdapter; no implicit DSPy transport")

    def copy(self, **kwargs):
        # Bootstrap may request temperature changes. Never silently change experiment settings.
        import copy
        result = copy.copy(self)
        result.kwargs = dict(self.kwargs, **kwargs)
        return result


class IncidentAdapter(dspy.Adapter):
    def __call__(self, lm, lm_kwargs, signature, demos, inputs):
        if not isinstance(lm, ProviderLM):
            raise TypeError("IncidentAdapter requires ProviderLM")
        started = perf_counter()
        is_task = set(signature.input_fields) == {"snapshot"}
        try:
            if is_task:
                snapshot = inputs["snapshot"]
                bundle = candidate(snapshot["stage"], task_prompt(signature, demos))
                resolver = PromptResolver(bundle.model_dump(mode="json"), allow_candidate=True)
                output, usage = asyncio.run(replay(lm.provider, snapshot, resolver))
                result = {"output": output.model_dump(mode="json")}
            else:
                # MIPRO proposals also pass the original structured boundary and request cap.
                schema = create_model("OptimizerProposal", __base__=StrictModel, **{
                    name: (field.annotation, ...) for name, field in signature.output_fields.items()
                })
                output, usage = asyncio.run(lm.provider.structured_call(
                    "offline_optimizer", signature.instructions,
                    {"inputs": inputs, "demonstrations": [dict(d) for d in demos],
                     "input_fields": {k: str(v) for k, v in signature.input_fields.items()}}, schema,
                ))
                result = output.model_dump(mode="json")
            lm.ledger.append({"kind": "task" if is_task else "proposal", "usage": usage,
                              "elapsed_ms": (perf_counter() - started) * 1000, "failed": False})
            return [result]
        except BaseException as exc:
            lm.ledger.append({"kind": "task" if is_task else "proposal",
                              "error_type": type(exc).__name__, "failed": True,
                              "usage": getattr(exc, "usage", {}),
                              "elapsed_ms": (perf_counter() - started) * 1000})
            raise


def metric(example, prediction, trace=None):
    try:
        return semantic_score(example.snapshot["stage"], example.output, prediction.output)
    except (KeyError, TypeError, ValueError):
        return 0.0


def compile_bundle(samples, provider, stage, optimizer, *, shots=2, seed=21, trials=8,
                   engineering_fixture=False):
    from .data import split_gate, validate_annotations

    if not engineering_fixture:
        validate_annotations(samples)
    if optimizer not in {"manual", "LabeledFewShot", "BootstrapFewShot", "MIPROv2"}:
        raise ValueError("unsupported optimizer")
    if not 0 <= shots <= 8:
        raise ValueError("shots must be between 0 and 8")
    train = [s for s in samples if s.stage == stage and s.split == "train"]
    dev = [s for s in samples if s.stage == stage and s.split == "dev"]
    split_gate(train, dev)
    def examples(rows):
        return [dspy.Example(snapshot=s.model_input(), output=s.annotation.expected)
                                 .with_inputs("snapshot") for s in rows]
    training, validation = examples(train), examples(dev)
    student = dspy.Predict(TaskSignature.with_instructions(INITIAL_INSTRUCTION))
    lm = ProviderLM(provider)
    with dspy.context(lm=lm, adapter=IncidentAdapter()):
        if optimizer == "manual":
            student.demos = training[:shots]
        elif optimizer == "LabeledFewShot":
            student = dspy.LabeledFewShot(k=shots).compile(student, trainset=training, sample=True)
        elif optimizer == "BootstrapFewShot":
            student = dspy.BootstrapFewShot(metric=metric, max_bootstrapped_demos=shots,
                                            max_labeled_demos=0, max_rounds=1, max_errors=2).compile(
                                                student, trainset=training)
        else:
            student = dspy.MIPROv2(metric=metric, prompt_model=lm, task_model=lm, auto=None,
                                   num_candidates=3, num_threads=1, max_errors=2, seed=seed,
                                   max_bootstrapped_demos=0, max_labeled_demos=shots).compile(
                                       student, trainset=training, valset=validation,
                                       num_trials=trials, minibatch=False,
                                       requires_permission_to_run=False)
    bundle = candidate(stage, task_prompt(student.signature, student.demos), optimizer=optimizer,
                       training_hash=digest([s.model_dump(mode="json") for s in train]))
    bundle.optimization_provenance = {
        "dspy_version": dspy.__version__, "model_id": provider.model_id,
        "model_parameters": getattr(provider, "model_parameters", {"temperature": provider.temperature}),
        "validation_data_sha256": digest([s.model_dump(mode="json") for s in dev]),
        "shots": shots, "seed": seed, "trials": trials,
        "engineering_fixture": engineering_fixture,
        "note": "LabeledFewShot uses DSPy 3.0.4 internal seed 0; MIPRO uses configured seed.",
    }
    return bundle, student, lm


def save_bundle(path, bundle):
    Path(path).write_text(canonical(bundle.model_dump(mode="json")) + "\n", encoding="utf-8")


def verify_export(student, lm, bundle, sample):
    """Check exact effective messages+schema+payload; no model request is needed."""
    from incident_lens.llm.structured_output import output_messages, strict_schema

    class Capture:
        model_id = "capture"
        temperature = 0.0

        def __init__(self):
            self.wires = []

        async def structured_call(self, role, system_prompt, user_payload, output_model):
            self.wires.append({"role": role, "messages": output_messages(
                system_prompt, user_payload, strict_schema(output_model))})
            # Stop before inference. The captured wire is all that is being compared.
            raise Captured()

    class Captured(Exception):
        pass

    capture = Capture()
    snapshot = sample.model_input()
    with dspy.context(lm=ProviderLM(capture), adapter=IncidentAdapter()):
        try:
            student(snapshot=snapshot)
        except Captured:
            pass
    try:
        asyncio.run(replay(capture, snapshot, PromptResolver(
            bundle.model_dump(mode="json"), allow_candidate=True)))
    except Captured:
        pass
    wires = capture.wires
    if len(wires) != 2 or wires[0] != wires[1]:
        raise ValueError("native/export wire mismatch")
    return {"format": FORMAT, "wire_sha256": digest(wires[0]), "equivalent": True,
            "scope": "this custom Adapter only; transport configuration must also match"}
