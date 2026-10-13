import argparse
import json

from incident_lens.incidentbench.validator import validate_dataset

parser = argparse.ArgumentParser()
parser.add_argument("--dataset", required=True)
parser.add_argument("--mode", choices=["public", "privileged"], default="public")
parser.add_argument("--oracle-root")
args = parser.parse_args()
if args.mode == "privileged" and not args.oracle_root:
    parser.error("privileged validation requires evaluator root")
result = validate_dataset(args.dataset, args.oracle_root if args.mode == "privileged" else None)
print(json.dumps(result, indent=2))
raise SystemExit(0 if result["ok"] else 1)
