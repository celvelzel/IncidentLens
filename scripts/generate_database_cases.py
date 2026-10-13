"""Generate additive, deterministic database fixtures without rewriting legacy cases."""

import argparse
import json
from pathlib import Path

from generate_cases import build_case, write_json, write_jsonl


def generate_database_cases(root="data"):
    root = Path(root)
    for number, kind in ((37, 1), (38, 0), (39, 1), (40, 0)):
        incident_id = build_case(root, number, kind, "database", missing=number == 40)
        public = root / "incidents" / incident_id / "public"
        case = json.loads((public / "incident.json").read_text())
        observations = {
            37: [
                (
                    "connections",
                    "Database connections at server capacity",
                    {"connection_count": 100, "connection_limit": 100},
                ),
                (
                    "active_sessions",
                    "New sessions rejected because connection slots are exhausted",
                    {
                        "session_id": "session-37",
                        "state": "rejected",
                        "wait_event": "connection_slots",
                    },
                ),
            ],
            38: [
                (
                    "connections",
                    "Database has ample free connections",
                    {"connection_count": 12, "connection_limit": 100},
                ),
                (
                    "health_metrics",
                    "Database availability normal",
                    {
                        "health_status": "healthy",
                        "metric_name": "availability",
                        "value": 1,
                        "unit": "ratio",
                    },
                ),
            ],
            39: [
                (
                    "lock_waits",
                    "Session blocked behind a long running transaction",
                    {
                        "session_id": "session-39",
                        "blocked_by": "session-38",
                        "wait_event": "transaction_lock",
                        "duration_ms": 45000,
                    },
                ),
                (
                    "slow_queries",
                    "Query waits on transaction lock for 45 seconds",
                    {
                        "query_fingerprint": "select-order",
                        "duration_ms": 45000,
                        "wait_event": "transaction_lock",
                    },
                ),
                (
                    "connections",
                    "Database connection capacity remains available",
                    {"connection_count": 20, "connection_limit": 100},
                ),
            ],
            40: [],
        }[number]
        records = [
            dict(
                evidence_id=f"{incident_id}-DB{i:03d}",
                incident_id=incident_id,
                source_type="database",
                service="postgres",
                observed_at=case["started_at"],
                source_path="public/database.jsonl",
                excerpt=text,
                metadata={"category": category, **metadata},
            )
            for i, (category, text, metadata) in enumerate(observations, 1)
        ]
        write_jsonl(public / "database.jsonl", records)
        oracle_path = root / "incidents" / incident_id / "private" / "ground_truth.json"
        oracle = json.loads(oracle_path.read_text())
        if number == 39:
            # Remove inherited exhaustion discriminators: this fixture measures lock contention.
            for filename in ("logs.jsonl", "metrics.csv"):
                text = (public / filename).read_text()
                if filename == "logs.jsonl":
                    rows = [json.loads(line) for line in text.splitlines() if line]
                    for row in rows:
                        if row["evidence_id"] == f"{incident_id}-L001":
                            row["excerpt"] = (
                                "transaction lock contention; session blocked and query waited 45 seconds"
                            )
                        elif row["evidence_id"] == f"{incident_id}-L002":
                            row["excerpt"] = "database query timeout waiting for transaction lock"
                    write_jsonl(public / filename, rows)
                else:
                    import csv

                    with (public / filename).open(newline="") as stream:
                        reader = csv.DictReader(stream)
                        fields = reader.fieldnames
                        rows = [row for row in reader if row["service"] != "postgres"]
                    with (public / filename).open("w", newline="") as stream:
                        writer = csv.DictWriter(stream, fields)
                        writer.writeheader()
                        writer.writerows(rows)
            oracle.update(
                root_cause_code="database_transaction_lock_contention",
                culprit_service="postgres",
                failure_mode="postgres_lock_contention",
                decisive_evidence_ids=[f"{incident_id}-L001"]
                + [r["evidence_id"] for r in records[:2]],
                causal_chain=[
                    "Long transaction blocks sessions",
                    "Queries wait on lock",
                    "Backend requests time out",
                ],
            )
        elif number in (37, 38):
            oracle["decisive_evidence_ids"] += [r["evidence_id"] for r in records]
        write_json(oracle_path, oracle)
    ids = [f"incident_{number:03d}" for number in range(37, 41)]
    write_json(root / "splits" / "database_ids.json", ids)
    return ids


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="data")
    print(json.dumps(generate_database_cases(parser.parse_args().root)))
