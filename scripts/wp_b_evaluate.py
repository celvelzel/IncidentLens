"""Rescore completed experiments locally without invoking a model or Graph."""

import argparse

from incident_lens.incidentbench.readiness import evaluate_completed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--oracle-root", required=True)
    parser.add_argument("--historical-source-root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--repository", required=True)
    args = parser.parse_args()
    rows = evaluate_completed(
        args.experiment,
        args.dataset,
        args.oracle_root,
        args.out,
        args.historical_source_root,
        args.repository,
    )
    print(f"Evaluated {len(rows)} persisted attempts; private output saved.")


if __name__ == "__main__":
    main()
