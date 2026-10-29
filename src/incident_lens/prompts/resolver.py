"""Explicit immutable prompt selection. No environment lookup or global switching."""

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import Field

from incident_lens.schemas import StrictModel

FORMAT = "incidentlens-task-json-v1"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class Demonstration(StrictModel):
    inputs: dict
    output: dict


class TaskPrompt(StrictModel):
    instructions: str = Field(min_length=1, max_length=16000)
    demonstrations: list[Demonstration] = Field(default_factory=list, max_length=8)


class PromptBundle(StrictModel):
    format: Literal["incidentlens-task-json-v1"] = FORMAT
    version: str = Field(min_length=1, max_length=128)
    base_prompt_version: str
    base_prompt_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    optimizer: Literal["manual", "LabeledFewShot", "BootstrapFewShot", "MIPROv2"]
    status: Literal["candidate", "reviewed"] = "candidate"
    reviewer: str = ""
    review_evidence: str = ""
    training_data_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    optimization_provenance: dict = Field(default_factory=dict)
    # Selection is by stage, never by caller-supplied role: planning is untouched.
    tasks: dict[Literal["analysis", "verify"], TaskPrompt] = Field(min_length=1)


def render_task(task):
    """Same representation during optimization and deployment, including demos."""
    if not isinstance(task, TaskPrompt):
        task = TaskPrompt.model_validate(task)
    return (
        "\nTask guidance (subordinate to all safety, ACL and output constraints):\n"
        + task.instructions
        + ("\nIllustrative input/output examples, not observations for the current incident:\n"
           + canonical([d.model_dump(mode="json") for d in task.demonstrations])
           if task.demonstrations else "")
    )


class PromptResolver:
    def __init__(self, bundle=None, *, allow_candidate=False):
        from incident_lens.agents.service import PROMPT_VERSION, ROLE_PROMPTS, SYSTEM_PROMPT

        self.base_version = PROMPT_VERSION
        self.base_hash = digest({"system": SYSTEM_PROMPT, "roles": ROLE_PROMPTS})
        self._bundle_json = None
        if bundle is not None:
            bundle = PromptBundle.model_validate(bundle)
            if (bundle.base_prompt_version != self.base_version
                    or bundle.base_prompt_sha256 != self.base_hash):
                raise ValueError("bundle is incompatible with the frozen base prompt")
            if not allow_candidate and (bundle.status != "reviewed" or not bundle.reviewer.strip()
                                        or not bundle.review_evidence.strip()):
                raise ValueError("runtime requires a reviewed bundle and review evidence")
            self._bundle_json = canonical(bundle.model_dump(mode="json"))
        self.bundle_hash = digest(json.loads(self._bundle_json)) if self._bundle_json else self.base_hash
        self.version = bundle.version if bundle is not None else self.base_version
        self.optimizer = bundle.optimizer if bundle is not None else "original"

    @classmethod
    def load(cls, path, **kwargs):
        return cls(json.loads(Path(path).read_text(encoding="utf-8")), **kwargs)

    def resolve(self, stage, baseline):
        if not self._bundle_json:
            return baseline
        tasks = json.loads(self._bundle_json)["tasks"]
        return baseline + render_task(tasks[stage]) if stage in tasks else baseline

    def metadata(self):
        return {"prompt_version": self.version, "prompt_bundle_sha256": self.bundle_hash,
                "prompt_base_sha256": self.base_hash, "prompt_optimizer": self.optimizer,
                "prompt_format": FORMAT}


def resolver_for(provider):
    return getattr(provider, "prompt_resolver", None) or PromptResolver()
