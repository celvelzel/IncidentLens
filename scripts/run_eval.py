"""Run cache-off comparisons; real mode never falls back to mock."""

import argparse
import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from incident_lens.evaluation import VARIANTS, evaluate_split
from incident_lens.llm import MockProvider, ProviderError, RealChatProvider
from incident_lens.schemas import Budget


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("seed", "dev", "test"), default="seed")
    parser.add_argument("--variant", choices=("all", *VARIANTS), default="all")
    parser.add_argument("--provider", choices=("mock", "real"), default="mock")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--max-rounds", type=int, default=4)
    parser.add_argument("--max-tool-calls", type=int, default=12)
    parser.add_argument("--max-llm-calls", type=int, default=16)
    parser.add_argument("--max-wall-seconds", type=float, default=90)
    parser.add_argument("--max-tokens", type=int)
    args = parser.parse_args(argv)
    load_dotenv()
    try:
        budget = Budget(
            max_rounds=args.max_rounds,
            max_tool_calls=args.max_tool_calls,
            max_llm_calls=args.max_llm_calls,
            max_wall_seconds=args.max_wall_seconds,
            max_tokens=args.max_tokens,
        )
        if args.provider == "real":
            base_url = os.getenv("INCIDENT_LENS_BASE_URL", "")
            api_key = os.getenv("INCIDENT_LENS_API_KEY", "")
            model = os.getenv("INCIDENT_LENS_MODEL", "")
            # Configuration validation happens before dataset execution or any request.
            RealChatProvider(base_url, api_key, model)

            def factory():
                return RealChatProvider(base_url, api_key, model, temperature=0)
        else:
            factory = MockProvider
        rows, totals = asyncio.run(
            evaluate_split(
                args.data_root,
                args.split,
                VARIANTS if args.variant == "all" else (args.variant,),
                factory,
                args.out,
                budget=budget,
                provider_name=args.provider,
            )
        )
    except (ProviderError, ValueError, OSError) as exc:
        print(
            json.dumps(
                {"error": exc.code if isinstance(exc, ProviderError) else type(exc).__name__}
            )
        )
        return 2
    print(
        json.dumps(
            {
                "provider": args.provider,
                "source": "mock" if args.provider == "mock" else "model",
                "runs": len(rows),
                "variants": len(totals),
                "cache_mode": "off",
            }
        )
    )
    return 1 if any(r["execution_error"] or r["evaluation_error"] for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
