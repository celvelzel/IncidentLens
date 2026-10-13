import argparse
import json
from pathlib import Path

import yaml

from incident_lens.incidentbench.manifest import create_lock, seal_dataset
from incident_lens.incidentbench.schemas import ExperimentProtocol

parser = argparse.ArgumentParser()
parser.add_argument("--dataset", required=True)
parser.add_argument("--protocol", required=True)
parser.add_argument("--out", required=True)
parser.add_argument("--development-snapshot", action="store_true")
parser.add_argument("--oracle-root")
parser.add_argument("--salt-path")
parser.add_argument("--readiness")
args = parser.parse_args()
protocol = ExperimentProtocol.model_validate(
    yaml.safe_load(Path(args.protocol).read_text(encoding="utf-8"))
)
if args.development_snapshot:
    lock = create_lock(args.dataset, protocol)
else:
    if not all([args.oracle_root, args.salt_path, args.readiness]):
        parser.error("formal seal requires private labels, private salt, and readiness record")
    lock = seal_dataset(
        args.dataset,
        protocol,
        args.oracle_root,
        args.salt_path,
        json.loads(Path(args.readiness).read_text(encoding="utf-8")),
    )
out = Path(args.out)
out.mkdir(parents=True, exist_ok=False)
(out / "protocol.lock.json").write_text(json.dumps(lock, indent=2), encoding="utf-8")
print(json.dumps({"sealed": lock["sealed"], "public_sha256": lock["public_sha256"]}))
