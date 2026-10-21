"""Capture actual decision inputs; never synthesize pre-state from a final trace."""

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import Field

from incident_lens.prompts.resolver import canonical, digest
from incident_lens.schemas import StrictModel


class EvidenceRelation(StrictModel):
    culprit_service: str
    failure_mode: str
    evidence_id: str
    relation: Literal["supports", "directly_refutes", "insufficient", "irrelevant", "unknown"]
    rationale: str = Field(min_length=1)


class Annotation(StrictModel):
    status: Literal["pending", "reviewed"] = "pending"
    reviewers: list[str] = Field(default_factory=list)
    adjudication: str = ""
    # The expected structured judgment must be human-reviewed, never a model label.
    expected: dict = Field(default_factory=dict)
    rationale: str = ""
    relations: list[EvidenceRelation] = Field(default_factory=list)
    abstention: Literal["appropriate", "inappropriate", "not_applicable", "unknown"] = "unknown"
    error_owner: Literal["analysis", "verify", "coordinator", "system", "none", "unknown"] = "unknown"
    prompt_fixable: Literal["yes", "no", "unknown"] = "unknown"


class Sample(StrictModel):
    sample_id: str
    stage: Literal["analysis", "verify"]
    role: str
    payload: dict
    output_schema: dict
    system_prompt: str
    prompt_metadata: dict
    source_sha256: str
    # Conservatively shared until a reviewer establishes independent provenance.
    family: str = "shared-synthetic-generator"
    cluster: str = "shared-synthetic-generator"
    split: Literal["train", "dev", "test", "unassigned"] = "unassigned"
    annotation: Annotation = Field(default_factory=Annotation)

    def model_input(self):
        return {"stage": self.stage, "role": self.role, "payload": self.payload}


def load_samples(path, *, reviewed=False):
    rows = [Sample.model_validate(json.loads(line)) for line in
            Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    if len({s.sample_id for s in rows}) != len(rows):
        raise ValueError("duplicate sample IDs")
    for sample in rows:
        validate_payload(sample.model_input())
    if reviewed:
        validate_annotations(rows)
    return rows


def validate_annotations(samples):
    import jsonschema

    for sample in samples:
        a = sample.annotation
        if (a.status != "reviewed" or len(set(a.reviewers)) < 2
                or any(not r.strip() for r in a.reviewers)
                or not a.adjudication.strip() or not a.rationale.strip() or not a.expected):
            raise ValueError("two reviewers, adjudication, rationale and expected output required")
        jsonschema.Draft202012Validator(sample.output_schema).validate(a.expected)
        if sample.stage == "analysis":
            relations = {(r.culprit_service, r.failure_mode, r.evidence_id): r.relation
                         for r in a.relations}
            for h in a.expected["hypotheses"]:
                for field, label in (("support_ids", "supports"), ("against_ids", "directly_refutes")):
                    if any(relations.get((h["culprit_service"], h["failure_mode"], eid)) != label
                           for eid in h[field]):
                        raise ValueError("gold citations require adjudicated semantic relation labels")
                if h["status"] == "REJECTED" and not h["against_ids"]:
                    raise ValueError("gold rejection requires direct contrary evidence")
            f, c, t = a.expected["finding"], sample.payload["context"], sample.payload["task"]
            if any(f[k] != c[k] for k in ("run_id", "incident_id")) or (
                    f["task_id"] != t["task_id"] or f["role"] != t["role"]):
                raise ValueError("reviewed expected finding has a different runtime identity")


def validate_payload(snapshot):
    """Accept only service-shaped inputs. Annotation/provenance never reach the model."""
    if set(snapshot) != {"stage", "role", "payload"}:
        raise ValueError("invalid model input envelope")
    p = snapshot["payload"]
    if snapshot["stage"] == "analysis":
        allowed = {"context", "task", "records", "failure_mode_taxonomy",
                   "allowed_evidence_ids", "citation_rule"}
        if set(p) != allowed:
            raise ValueError("analysis input must be an exact captured service payload")
    elif snapshot["stage"] == "verify":
        from incident_lens.schemas import InvestigationState
        allowed = set(InvestigationState.model_fields) | {
            "variant", "benchmark_rca", "workflow_profile", "database_enabled", "role_tool_acl",
            "failure_mode_taxonomy", "candidate_assessments", "investigation_budget",
            "last_finalization_feedback", "query_history", "tool_argument_schemas",
        }
        if set(p) - allowed or p.get("events", []):
            raise ValueError("verifier input must be a public pre-decision state without events")
    else:
        raise ValueError("unsupported optimization stage")
    actual_role = (p["context"]["role"] if snapshot["stage"] == "analysis"
                   else "single" if p.get("variant") == "single" else "verifier")
    if snapshot["role"] != actual_role:
        raise ValueError("snapshot role disagrees with runtime identity")
    # Reject obvious oracle/label additions recursively; public excerpts stay opaque data.
    forbidden = {"ground_truth", "oracle", "private", "annotation", "expected_output",
                 "is_identifiable", "root_cause_label"}

    def check(value):
        if isinstance(value, dict):
            if forbidden.intersection(value):
                raise ValueError("private labels cannot enter decision payloads")
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)
    check(p)


def extract_events(path, out):
    raw = Path(path).read_bytes()
    events = [json.loads(line) for line in raw.splitlines() if line.strip()]
    samples = {}
    for e in events:
        if e.get("phase") != "request":
            continue
        key = digest({"stage": e["stage"], "payload": e["payload"], "schema": e["schema"]})
        samples[key] = Sample(sample_id=key, stage=e["stage"], role=e["role"],
                              payload=e["payload"], output_schema=e["schema"],
                              system_prompt=e["system_prompt"],
                              prompt_metadata=e["prompt_metadata"], source_sha256=hashlib.sha256(raw).hexdigest())
    target = Path(out)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as handle:
        for sample in samples.values():
            handle.write(canonical(sample.model_dump(mode="json")) + "\n")
    return len(samples)


def split_gate(train, dev, *, independent=False):
    if not train or not dev:
        raise ValueError("nonempty train and dev required")
    if {s.sample_id for s in train} & {s.sample_id for s in dev}:
        raise ValueError("train/dev sample overlap")
    def incident(s):
        return s.payload.get("context", s.payload).get("incident_id")
    if {incident(s) for s in train} & {incident(s) for s in dev}:
        raise ValueError("train/dev incident overlap")
    if independent and ({s.cluster for s in train} & {s.cluster for s in dev}
                        or {s.family for s in train} & {s.family for s in dev}):
        raise ValueError("independent evaluation requires disjoint families and clusters")
