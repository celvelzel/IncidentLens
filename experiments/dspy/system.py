"""Run the existing oracle-isolated evaluation under paired prompt conditions."""

import random

from incident_lens.evaluation.runner import evaluate_split
from incident_lens.prompts.resolver import digest
from incident_lens.schemas import Budget

from .provider import make_provider


async def evaluate_system(data_root, split, arms, cap, out, *, kind="mock", seed=21,
                          max_calls=32):
    if split not in {"seed", "dev"}:
        raise ValueError("independent held-out test requires a separate frozen protocol")
    variants = ("full", "single", "fixed", "dynamic_no_verifier")
    order = list(arms)
    random.Random(seed).shuffle(order)
    all_rows = []
    for arm in order:
        def factory():
            provider = make_provider(kind, cap)
            provider.prompt_resolver = arms[arm]
            return provider

        rows, _ = await evaluate_split(data_root, split, variants, factory, out / arm,
                                        Budget(max_llm_calls=max_calls, max_wall_seconds=300),
                                        provider_name=kind, jobs=1)
        all_rows.extend(dict(row, arm=arm) for row in rows)
    baseline = {(r["incident_id"], r["variant"]): r for r in all_rows if r["arm"] == "A0"}
    pairs = []
    for row in all_rows:
        if row["arm"] == "A0":
            continue
        base = baseline[(row["incident_id"], row["variant"])]
        pairs.append({"incident_id": row["incident_id"], "variant": row["variant"],
                      "arm": row["arm"], "root_cause_before": base.get("root_cause_correct"),
                      "root_cause_after": row.get("root_cause_correct"),
                      "abstention_before": base.get("correct_abstention"),
                      "abstention_after": row.get("correct_abstention"),
                      "request_delta": row["llm_requests"] - base["llm_requests"],
                      "tool_delta": (row["tool_calls"] - base["tool_calls"])
                      if row.get("tool_calls") is not None and base.get("tool_calls") is not None
                      else None})
    return {"status": "engineering_only_quality_not_established", "source": kind,
            "seed": seed, "arm_order": order, "rows": all_rows, "paired": pairs,
            "config_sha256": digest({"arms": {a: r.metadata() for a, r in arms.items()},
                                     "split": split, "variants": variants, "max_calls": max_calls}),
            "semantic_review": "pending; ID existence is not semantic grounding"}
