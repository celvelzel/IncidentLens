"""Generate development data from locally controlled scenario specifications."""

import argparse
import json

from incident_lens.incidentbench.builder import build_dataset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--oracle-root", required=True,
                        help="Fresh evaluator-only root outside the public dataset")
    args = parser.parse_args()
    print(json.dumps(build_dataset(args.config, args.out, args.oracle_root), sort_keys=True))


if __name__ == "__main__":
    main()
