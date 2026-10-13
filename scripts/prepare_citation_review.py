import argparse
import json
from pathlib import Path

from incident_lens.incidentbench.citation_review import prepare_review_bundle, review_coverage

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--out", required=True)
args = parser.parse_args()
rows = [
    json.loads(line) for line in Path(args.input).read_text(encoding="utf-8").splitlines() if line
]
bundle = prepare_review_bundle([row.get("state", row) for row in rows])
out = Path(args.out)
out.mkdir(parents=True, exist_ok=False)
(out / "citation-review-bundle.jsonl").write_text(
    "".join(json.dumps(row) + "\n" for row in bundle), encoding="utf-8"
)
(out / "review-coverage.json").write_text(
    json.dumps(review_coverage(bundle, []), indent=2), encoding="utf-8"
)
