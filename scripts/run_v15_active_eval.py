"""Run controlled public Seed CAES diagnostics; research gates fail closed."""

import argparse
import asyncio
import json
from pathlib import Path

from incident_lens.evaluation.active_evidence.runner import run_experiment
from incident_lens.evaluation.active_evidence.variants import VARIANTS, ActiveProtocol
from incident_lens.llm import MockProvider


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", required=True, type=Path)
    p.add_argument("--split", required=True, choices=("seed", "dev", "test"))
    p.add_argument("--variants", nargs="+", choices=list(VARIANTS), default=None)
    p.add_argument("--provider", choices=("mock", "real"), default=None)
    p.add_argument("--policy", choices=list(dict.fromkeys(VARIANTS.values())))
    p.add_argument("--protocol", type=Path)
    p.add_argument("--cache-mode", choices=("off",), default="off")
    p.add_argument("--jobs", type=int, choices=(1,), default=1)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument(
        "--resume",
        action="store_true",
        help="resume verified Mock-only ledger without rerunning attempted records",
    )
    a = p.parse_args()
    values = (
        json.loads(a.protocol.read_bytes())
        if a.protocol
        else json.loads((a.out / "protocol.json").read_bytes())
        if a.resume
        else {}
    )
    if a.variants is not None:
        values["variants"] = a.variants
    if a.provider is not None:
        values["provider_id"] = a.provider
    if a.policy:
        values["variants"] = [
            v for v in values.get("variants", list(VARIANTS)) if VARIANTS[v] == a.policy
        ]
    protocol = ActiveProtocol.model_validate(values)
    rows = asyncio.run(
        run_experiment(a.dataset, a.split, MockProvider, a.out, protocol, resume=a.resume)
    )
    print(json.dumps(dict(runs=len(rows), out=str(a.out), status="engineering_only")))


if __name__ == "__main__":
    main()
