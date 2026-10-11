"""Command-line entry point (P0: environment and contract checks)."""

import argparse
import json
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
    else:
        args.out.mkdir(parents=True, exist_ok=True)
        for model in CONTRACTS:
            (args.out / f"{model.__name__}.json").write_text(
                json.dumps(model.model_json_schema(), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        print(f"Exported {len(CONTRACTS)} contracts to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
