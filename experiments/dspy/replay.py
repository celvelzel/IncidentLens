"""Replay through the original Analysis/Verifier functions and all domain validators."""

import copy

from incident_lens.agents import service

from .data import validate_payload


async def replay(provider, snapshot, resolver=None):
    validate_payload(snapshot)
    provider = copy.copy(provider)
    if resolver is not None:
        provider.prompt_resolver = resolver
    p = snapshot["payload"]
    if snapshot["stage"] == "analysis":
        return await service.analyze(provider, p["context"], p["task"], p["records"])
    return await service.verify(provider, p)


def judgments(stage, output):
    """Compare citation relations to adjudicated gold, ignoring prose and runtime IDs.

    This metric cannot grade free-text explanations or establish end-to-end RCA quality.
    """
    if stage == "analysis":
        if len({(h["culprit_service"], h["failure_mode"]) for h in output["hypotheses"]}) != len(output["hypotheses"]):
            raise ValueError("duplicate cause judgments")
        return {(h["culprit_service"], h["failure_mode"]):
                (h["status"], frozenset(h["support_ids"]), frozenset(h["against_ids"]))
                for h in output["hypotheses"]}
    return {"review": (output["verdict"], output["target_hypothesis_id"],
                       frozenset(output["cited_evidence_ids"]),
                       bool(output.get("requested_checks")), bool(output.get("contradictions")))}


def semantic_score(stage, expected, output):
    gold, actual = judgments(stage, expected), judgments(stage, output)
    # All reviewed relations must match; additions and omissions are errors.
    return float(gold == actual)


def false_refutations(expected, output):
    gold = judgments("analysis", expected)
    errors = 0
    for key, (status, _, against) in judgments("analysis", output).items():
        reference = gold.get(key)
        errors += int(bool(against - (reference[2] if reference else frozenset()))
                      or (status == "REJECTED" and (reference is None or reference[0] != "REJECTED")))
    return errors
