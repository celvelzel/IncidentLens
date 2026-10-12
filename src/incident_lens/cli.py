"""Investigation, replay and public-data validation command-line entry point."""

import argparse
import asyncio
import json
import os
import sys
import time
from importlib.metadata import version
from pathlib import Path

from incident_lens import __version__
from incident_lens.cache.policy import CacheNamespace, CachePolicy
from incident_lens.schemas import (
    Budget,
    CasePublicInput,
    CoordinatorDecision,
    EvidenceRecord,
    Finding,
    Hypothesis,
    InvestigationState,
    InvestigationTask,
    RCAReport,
    Review,
    ToolResult,
    TraceEvent,
)
from incident_lens.security.context import AgentContext

CONTRACTS = [
    CasePublicInput,
    EvidenceRecord,
    ToolResult,
    InvestigationTask,
    Finding,
    Hypothesis,
    Review,
    CoordinatorDecision,
    RCAReport,
    InvestigationState,
    Budget,
    TraceEvent,
    AgentContext,
    CachePolicy,
    CacheNamespace,
]


def main(argv=None):
    parser = argparse.ArgumentParser(prog="incident-lens")
    parser.add_argument("--version", action="version", version=f"IncidentLens {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check-environment")
    cases = sub.add_parser("list-cases")
    cases.add_argument("--data-root", type=Path, default=Path("data"))
    validate = sub.add_parser("validate-data")
    validate.add_argument("--data-root", type=Path, default=Path("data"))
    run = sub.add_parser("run")
    run.add_argument("--case", required=True)
    run.add_argument("--provider", choices=["mock", "real"], default="mock")
    run.add_argument(
        "--variant", choices=["full", "single", "fixed", "dynamic_no_verifier"], default="full"
    )
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--data-root", type=Path, default=Path("data"))
    run.add_argument("--config", type=Path, default=Path("configs/system.yaml"))
    run.add_argument("--cache-mode", choices=["off", "exact", "semantic"], default=None)
    run.add_argument("--cache-db", type=Path, default=None)
    run.add_argument("--max-rounds", type=int)
    run.add_argument("--max-tool-calls", type=int)
    run.add_argument("--max-llm-calls", type=int)
    run.add_argument("--max-seconds", type=float)
    run.add_argument("--max-tokens", type=int)
    run.add_argument("--response-format", choices=["json_schema", "json_object"])
    run.add_argument("--thinking", choices=["enabled", "disabled"])
    run.add_argument("--request-timeout", type=float)
    replay = sub.add_parser("replay")
    replay.add_argument("--trace", type=Path, required=True)
    web = sub.add_parser("web")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8022)
    export = sub.add_parser("export-schemas")
    export.add_argument("--out", type=Path, default=Path("docs/contracts"))
    args = parser.parse_args(argv)
    if args.command == "check-environment":
        print(
            json.dumps(
                {
                    name: version(name)
                    for name in ["incident-lens", "langgraph", "pydantic", "streamlit"]
                },
                indent=2,
            )
        )
    elif args.command == "export-schemas":
        args.out.mkdir(parents=True, exist_ok=True)
        for model in CONTRACTS:
            (args.out / f"{model.__name__}.json").write_text(
                json.dumps(model.model_json_schema(), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        print(f"Exported {len(CONTRACTS)} contracts to {args.out}")
    elif args.command == "replay":
        from incident_lens.artifacts import load_replay
        from incident_lens.orchestration.report import render_report

        _, state = load_replay(args.trace)
        print("Recorded Replay — no provider calls")
        print(render_report(state.report))
    elif args.command == "web":
        from incident_lens.web.__main__ import main as web_main

        return web_main(["--host", args.host, "--port", str(args.port)])
    elif args.command in {"list-cases", "validate-data"}:
        from incident_lens.tools import EvidenceProvider

        provider = EvidenceProvider(args.data_root)
        if args.command == "list-cases":
            for case in provider.list_cases():
                print(f"{case.incident_id}\t{case.title}\t{case.started_at.isoformat()}")
        else:
            errors = provider.validate_public()
            print(json.dumps({"ok": not errors, "errors": errors}, indent=2))
            return 1 if errors else 0
    elif args.command == "run":
        import yaml
        from dotenv import load_dotenv

        from incident_lens.artifacts import save_run
        from incident_lens.llm.config import provider_options
        from incident_lens.llm.mock import MockProvider
        from incident_lens.llm.provider import ProviderError, RealChatProvider
        from incident_lens.orchestration.graph import run_investigation

        load_dotenv()
        try:
            config = (
                yaml.safe_load(args.config.read_text(encoding="utf-8"))
                if args.config.exists()
                else {}
            )
            if not isinstance(config, dict):
                raise ValueError("system config must be a mapping")
            cache_mode = (
                args.cache_mode or os.getenv("CACHE_MODE") or config.get("cache_mode", "off")
            )
            CachePolicy(mode=cache_mode)
            budget = Budget(
                max_rounds=args.max_rounds
                if args.max_rounds is not None
                else config.get("max_rounds", 4),
                max_tool_calls=args.max_tool_calls
                if args.max_tool_calls is not None
                else config.get("tool_calls_limit", 12),
                max_llm_calls=args.max_llm_calls
                if args.max_llm_calls is not None
                else config.get("llm_calls_limit", 16),
                max_wall_seconds=args.max_seconds
                if args.max_seconds is not None
                else float(config.get("time_limit_seconds", 90)),
                max_tokens=args.max_tokens
                if args.max_tokens is not None
                else config.get("max_tokens"),
            )
            provider = (
                MockProvider()
                if args.provider == "mock"
                else RealChatProvider(
                    os.getenv("INCIDENT_LENS_BASE_URL"),
                    os.getenv("INCIDENT_LENS_API_KEY"),
                    os.getenv("INCIDENT_LENS_MODEL"),
                    structured_repair_retries=config.get("structured_repair_retries", 1),
                    **provider_options(args.response_format, args.thinking, args.request_timeout),
                )
            )
            cache = None
            if cache_mode != "off":
                from incident_lens.cache.embeddings import SentenceTransformerBackend
                from incident_lens.cache.semantic import SemanticCacheAdapter
                from incident_lens.tools import EvidenceProvider

                policy = CachePolicy(
                    mode=cache_mode,
                    similarity_threshold=float(os.getenv("CACHE_SIMILARITY_THRESHOLD", "0.95")),
                    ttl_hours=float(os.getenv("CACHE_TTL_HOURS", "24")),
                )
                cache = SemanticCacheAdapter(
                    policy,
                    args.cache_db or os.getenv("CACHE_DB_PATH", "results/cache.sqlite"),
                    EvidenceProvider(args.data_root).dataset_revision,
                    None
                    if os.getenv("CACHE_EMBEDDING_MODEL", "fake") == "fake"
                    else SentenceTransformerBackend(os.getenv("CACHE_EMBEDDING_MODEL")),
                )
            started = time.monotonic()
            state = asyncio.run(
                run_investigation(
                    args.case, provider, args.data_root, budget, args.variant, cache=cache
                )
            )
            save_run(
                state,
                args.out,
                args.provider,
                args.variant,
                cache_mode,
                (time.monotonic() - started) * 1000,
            )
            print(
                json.dumps(
                    {
                        "status": state.report.status,
                        "run_id": state.run_id,
                        "tool_calls": state.tool_calls_used,
                        "llm_calls": state.llm_calls_used,
                        "artifacts": str(args.out.resolve()),
                    },
                    indent=2,
                )
            )
        except ProviderError as exc:
            print(exc.code, file=sys.stderr)
            return 2
        except (ValueError, OSError) as exc:
            print(f"{type(exc).__name__}: configuration/data/trace error", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
