"""Run with python -m experiments.dspy --help from the repository root."""

import argparse
import asyncio
import json
from pathlib import Path

from incident_lens.prompts.resolver import PromptResolver, canonical

from .data import extract_events, load_samples
from .provider import RequestCap, make_provider


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--root", type=Path, default=Path("."))
    audit.add_argument("--out", required=True)
    system = sub.add_parser("system")
    system.add_argument("--data-root", type=Path, default=Path("data"))
    system.add_argument("--split", choices=("seed", "dev"), default="dev")
    system.add_argument("--provider", choices=("mock", "real"), default="mock")
    system.add_argument("--max-requests", type=int, required=True)
    system.add_argument("--max-calls", type=int, default=32)
    system.add_argument("--bundle", action="append", default=[])
    system.add_argument("--out", required=True)
    extract = sub.add_parser("extract")
    extract.add_argument("--events", required=True)
    extract.add_argument("--out", required=True)
    for name in ("optimize", "evaluate"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--data", required=True)
        cmd.add_argument("--provider", choices=("mock", "real"), default="mock")
        cmd.add_argument("--max-requests", type=int, required=True)
        cmd.add_argument("--out", required=True)
        if name == "optimize":
            cmd.add_argument("--stage", choices=("analysis", "verify"), required=True)
            cmd.add_argument("--optimizer", choices=("manual", "LabeledFewShot", "BootstrapFewShot",
                                                     "MIPROv2"), required=True)
            cmd.add_argument("--shots", type=int, default=2)
            cmd.add_argument("--seed", type=int, default=21)
            cmd.add_argument("--trials", type=int, default=8)
        else:
            cmd.add_argument("--bundle", action="append", default=[], help="ARM=path to candidate")
            cmd.add_argument("--split", choices=("dev", "test"), default="dev")
    args = parser.parse_args()
    if args.command == "audit":
        from .audit import audit_retained
        print(json.dumps(audit_retained(args.root, args.out)))
        return
    if args.command == "extract":
        print(json.dumps({"samples": extract_events(args.events, args.out)}))
        return
    samples = load_samples(args.data, reviewed=True) if args.command != "system" else None
    cap = RequestCap(args.max_requests)
    def factory():
        return make_provider(args.provider, cap)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    if args.command == "system":
        from .system import evaluate_system
        arms = {"A0": PromptResolver()}
        for entry in args.bundle:
            arm, path = entry.split("=", 1)
            if arm in arms:
                raise ValueError("duplicate or reserved experiment arm")
            arms[arm] = PromptResolver.load(path, allow_candidate=True)
        report = asyncio.run(evaluate_system(args.data_root, args.split, arms, cap, out,
                                             kind=args.provider, max_calls=args.max_calls))
    elif args.command == "optimize":
        from .optimize import compile_bundle, save_bundle, verify_export
        bundle, program, lm = compile_bundle(samples, factory(), args.stage, args.optimizer,
                                             shots=args.shots, seed=args.seed, trials=args.trials)
        save_bundle(out / "candidate.json", bundle)
        report = {"export_parity": verify_export(program, lm, bundle, next(
            s for s in samples if s.stage == args.stage and s.split == "dev")),
            "ledger": lm.ledger, "source": args.provider, "config": vars(args),
            "status": "candidate_requires_real_evaluation_and_review"}
    else:
        from .data import split_gate
        from .evaluate import evaluate
        if args.split == "test":
            split_gate([s for s in samples if s.split in {"train", "dev"}],
                       [s for s in samples if s.split == "test"], independent=True)
        resolvers = {"A0": PromptResolver()}
        for entry in args.bundle:
            arm, path = entry.split("=", 1)
            if arm == "A0" or arm in resolvers:
                raise ValueError("duplicate or reserved experiment arm")
            resolvers[arm] = PromptResolver.load(path, allow_candidate=True)
        report = asyncio.run(evaluate(samples, factory, resolvers, split=args.split))
    report["actual_requests"] = cap.used
    (out / "report.json").write_text(canonical(report) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(out / "report.json"), "actual_requests": cap.used}))


if __name__ == "__main__":
    main()
