"""Paired module evaluation: counts and per-case changes, no significance claims."""

from time import perf_counter

from pydantic import ValidationError

from incident_lens.prompts.resolver import digest

from .replay import false_refutations, replay, semantic_score


async def evaluate(samples, provider_factory, resolvers, *, split="dev", engineering_fixture=False):
    if not engineering_fixture:
        from .data import validate_annotations
        validate_annotations(samples)
    if "A0" not in resolvers:
        raise ValueError("paired evaluation requires an A0 baseline")
    selected = [s for s in samples if s.split == split]
    if not selected:
        raise ValueError("evaluation split is empty")
    rows = []
    for sample in selected:
        for name, resolver in resolvers.items():
            provider = provider_factory()
            started = perf_counter()
            row = {"sample_id": sample.sample_id, "stage": sample.stage, "arm": name,
                   "cluster": sample.cluster, "source": "mock" if
                   provider.model_id.startswith("deterministic-") else "model",
                   **resolver.metadata()}
            schema_success = None
            try:
                output, usage = await replay(provider, sample.model_input(), resolver)
                schema_success = True
                output = output.model_dump(mode="json")
                row.update(schema_success=True, judgment_exact_match=semantic_score(
                    sample.stage, sample.annotation.expected, output), usage=usage,
                    false_refutations=false_refutations(sample.annotation.expected, output)
                    if sample.stage == "analysis" else None, output=output)
            except Exception as exc:
                if isinstance(exc, ValidationError) or getattr(exc, "code", "") in {
                        "STRUCTURED_OUTPUT_INVALID", "SCHEMA_VALIDATION_FAILED"}:
                    schema_success = False
                row.update(schema_success=schema_success, judgment_exact_match=0.0,
                           false_refutations=None, error_type=type(exc).__name__,
                           usage=getattr(exc, "usage", {}))
            row["elapsed_ms"] = (perf_counter() - started) * 1000
            rows.append(row)
    pairs = []
    baseline = {(r["sample_id"]): r for r in rows if r["arm"] == "A0"}
    for name in resolvers:
        if name == "A0":
            continue
        comparisons = [(baseline[r["sample_id"]], r) for r in rows if r["arm"] == name]
        pairs.append({"arm": name, "n": len(comparisons),
                      "improved": sum(b["judgment_exact_match"] > a["judgment_exact_match"]
                                      for a, b in comparisons),
                      "regressed": sum(b["judgment_exact_match"] < a["judgment_exact_match"]
                                       for a, b in comparisons),
                      "missing_refutation_pairs": sum(a["false_refutations"] is None
                                                       or b["false_refutations"] is None
                                                       for a, b in comparisons
                                                       if a["stage"] == "analysis")})
    return {"rows": rows, "paired": pairs, "data_sha256": digest([
        s.model_dump(mode="json") for s in selected]),
        "status": "engineering_only_quality_not_established",
        "notes": ["Citation-relation metric does not grade free-text explanations.",
                  "Shared synthetic clusters do not establish generalization.",
                  "No independent held-out test or statistical significance claimed."]}
