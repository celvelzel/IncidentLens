"""Separate paired cache experiment; architecture evaluations must keep cache off."""

import argparse
import asyncio
import csv
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from incident_lens.cache import CachePolicy, SemanticCacheAdapter, SentenceTransformerBackend
from incident_lens.llm.mock import MockProvider
from incident_lens.llm.provider import RealChatProvider
from incident_lens.orchestration.graph import run_investigation


def dataset_revision(root):
    """Hash public fixture contents only; never open private evaluator labels."""
    digest = hashlib.sha256()
    files = sorted((root / "incidents").glob("*/public/*")) + sorted((root / "topology").glob("*"))
    for path in files:
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return "data-" + digest.hexdigest()


def measured_summary(state, elapsed, phase, provider):
    calls = [event for event in state.events if event.event_type == "LLM_CALL"]
    hits = [event for event in state.events if event.event_type == "CACHE_HIT"]
    misses = [event for event in state.events if event.event_type == "CACHE_MISS"]
    tokens = [event.details.get("total_tokens") for event in calls]
    return dict(
        phase=phase,
        provider=provider,
        model_id=calls[0].details.get("model_id") if calls else None,
        run_id=state.run_id,
        incident_id=state.incident_id,
        status=state.report.status,
        llm_calls=state.llm_calls_used,
        tool_calls=state.tool_calls_used,
        tokens=sum(tokens) if tokens and all(token is not None for token in tokens) else None,
        cost=None,
        elapsed_ms=elapsed * 1000,
        cache_hits=len(hits),
        cache_misses=len(misses),
        cache_hit_rate=len(hits) / (len(hits) + len(misses)) if hits or misses else None,
        llm_calls_avoided=sum(event.details.get("llm_calls_avoided", 0) for event in hits),
        # Semantic correctness of claims needs human review; no invented zero.
        semantic_error_reuse_rate=None,
    )


async def experiment(args):
    if args.provider == "mock":
        provider = MockProvider()
    else:
        provider = RealChatProvider(
            os.getenv("LLM_ENDPOINT"), os.getenv("LLM_API_KEY"), os.getenv("LLM_MODEL")
        )
    args.out.mkdir(parents=True, exist_ok=True)
    embedder = SentenceTransformerBackend(args.embedding_model) if args.embedding_model else None
    cache = SemanticCacheAdapter(
        CachePolicy(mode=args.cache_mode),
        args.out / ("cache-" + uuid4().hex + ".sqlite"),
        dataset_revision(args.data_root),
        embedder,
    )
    rows = []
    states = []
    for phase, active in [("off", None), ("cold", cache), ("warm", cache)]:
        started = perf_counter()
        state = await run_investigation(args.case, provider, data_root=args.data_root, cache=active)
        rows.append(measured_summary(state, perf_counter() - started, phase, args.provider))
        states.append(state)
        folder = args.out / phase
        folder.mkdir(exist_ok=True)
        (folder / "trace.json").write_text(state.model_dump_json(indent=2), encoding="utf-8")
        (folder / "result.json").write_text(
            state.report.model_dump_json(indent=2), encoding="utf-8"
        )
    comparable = [
        {
            key: value
            for key, value in state.report.model_dump(mode="json").items()
            if key != "run_id"
        }
        for state in states
    ]
    summary = dict(
        results=rows,
        identical_reports=comparable[0] == comparable[1] == comparable[2],
        label="Offline mock correctness/timing only"
        if args.provider == "mock"
        else "Measured real-provider cache experiment",
        limits="Small paired sample; cache gain is separate from agent architecture quality. Unknown tokens/cost remain null.",
    )
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with (args.out / "case-level.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(summary, indent=2))
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="incident_001")
    parser.add_argument("--provider", choices=["mock", "real"], default="mock")
    parser.add_argument("--cache-mode", choices=["exact", "semantic"], default="semantic")
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("results/cache-experiment"))
    parser.add_argument(
        "--embedding-model",
        help="Optional locally installed SentenceTransformer model; no implicit download",
    )
    asyncio.run(experiment(parser.parse_args(argv)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
