"""Run genuine paired Graph investigations; real credentials stay project-local."""

import argparse
import asyncio
import json
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

from incident_lens.incidentbench.experiment import load_cases, run_experiment
from incident_lens.incidentbench.schemas import ExperimentProtocol
from incident_lens.llm import MockProvider
from incident_lens.llm.config import provider_options
from incident_lens.llm.provider import RealChatProvider


async def run(args):
    if args.out.exists():
        raise FileExistsError("experiment output already exists")
    _, _, cases = load_cases(args.dataset, args.split)
    if not cases:
        raise ValueError("empty split")
    project = Path(__file__).resolve().parents[1]
    load_dotenv(project / ".env", override=False)
    config = yaml.safe_load((project / "configs/system.yaml").read_text(encoding="utf-8"))
    values = yaml.safe_load(args.protocol.read_text(encoding="utf-8")) if args.protocol else {}
    if args.provider:
        values["provider_id"] = args.provider
    if values.get("provider_id", "mock") == "mock":
        values.setdefault("model_id", MockProvider.model_id)
        if values["model_id"] != MockProvider.model_id:
            raise ValueError("mock model must exactly match protocol")
        factory = MockProvider
    else:
        endpoint, key, model = (
            os.getenv(k)
            for k in ("INCIDENT_LENS_BASE_URL", "INCIDENT_LENS_API_KEY", "INCIDENT_LENS_MODEL")
        )
        if not all((endpoint, key, model)):
            raise ValueError("real provider configuration missing")
        if values.get("model_id") != model:
            raise ValueError("real model must exactly match frozen protocol")
        protocol_preview = ExperimentProtocol.model_validate(values)
        options = provider_options(
            protocol_preview.response_format, None, protocol_preview.request_timeout
        )

        def factory():
            return RealChatProvider(
                endpoint,
                key,
                model,
                temperature=protocol_preview.temperature,
                structured_repair_retries=config.get("structured_repair_retries", 1),
                recovery=config.get("provider_recovery", {}),
                **options,
            )

        if protocol_preview.formal:
            raise ValueError("formal readiness pending independent acceptance and sealing")
        if not args.readiness:
            raise ValueError(
                "real development pilot requires an external provider readiness record"
            )
        readiness = json.loads(args.readiness.read_text(encoding="utf-8"))
        if (
            readiness.get("model_id") != model
            or readiness.get("provider_compatible") is not True
            or readiness.get("response_format") != protocol_preview.response_format
        ):
            raise ValueError("provider readiness does not match protocol")
    protocol = ExperimentProtocol.model_validate(values)
    lock = (
        json.loads(args.protocol_lock.read_text(encoding="utf-8")) if args.protocol_lock else None
    )
    rows = await run_experiment(
        args.dataset, args.split, factory, args.out, protocol, args.oracle_root, protocol_lock=lock
    )
    print(json.dumps({"runs": len(rows), "source": protocol.provider_id, "out": str(args.out)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--split", choices=("seed", "dev", "test"), required=True)
    parser.add_argument("--variant", choices=("all",), default="all")
    parser.add_argument("--provider", choices=("mock", "real"))
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--protocol-lock", type=Path)
    parser.add_argument("--readiness", type=Path)
    parser.add_argument("--oracle-root", type=Path)
    parser.add_argument("--cache-mode", choices=("off",), default="off")
    parser.add_argument("--jobs", type=int, choices=(1,), default=1)
    parser.add_argument("--out", required=True, type=Path)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
