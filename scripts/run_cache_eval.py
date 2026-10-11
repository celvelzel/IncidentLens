"""Separate paired cache experiment; architecture evaluations must keep cache off."""

import argparse
import asyncio
import csv
import json
import os
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from dotenv import load_dotenv

from incident_lens.artifacts import save_run
from incident_lens.cache import CachePolicy, SemanticCacheAdapter, SentenceTransformerBackend
from incident_lens.llm.config import provider_options
from incident_lens.llm.mock import MockProvider
from incident_lens.llm.provider import ProviderError, RealChatProvider
from incident_lens.orchestration.graph import run_investigation
from incident_lens.tools import EvidenceProvider


def dataset_revision(root):
    """Hash public fixture contents only; never open private evaluator labels."""
    return EvidenceProvider(root).dataset_revision


def measured_summary(state, elapsed, phase, provider):
    calls = [event for event in state.events if event.event_type in {"LLM_CALL", "MODEL_FAILURE"}]
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
    load_dotenv()
    if args.provider == "mock":
        provider = MockProvider()
    else:
        provider = RealChatProvider(
            os.getenv("INCIDENT_LENS_BASE_URL"),
            os.getenv("INCIDENT_LENS_API_KEY"),
            os.getenv("INCIDENT_LENS_MODEL"),
            **provider_options(args.response_format, args.thinking, args.request_timeout),
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
        save_run(
            state,
            folder,
            args.provider,
            cache_mode="off" if active is None else args.cache_mode,
            elapsed_ms=rows[-1]["elapsed_ms"],
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
    parser.add_argument("--response-format", choices=["json_schema", "json_object"])
    parser.add_argument("--thinking", choices=["enabled", "disabled"])
    parser.add_argument("--request-timeout", type=float)
    parser.add_argument("--cache-mode", choices=["exact", "semantic"], default="semantic")
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("results/cache-experiment"))
    parser.add_argument(
        "--embedding-model",
        help="Optional locally installed SentenceTransformer model; no implicit download",
    )
    try:
        asyncio.run(experiment(parser.parse_args(argv)))
    except ProviderError as exc:
        parser.exit(2, exc.code + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
