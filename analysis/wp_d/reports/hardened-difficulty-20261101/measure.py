"""Measure whether the hardened lineage is harder to discriminate, and by how much.

The mock provider cannot answer this: it is a fixed rule policy that reads the
same contract predicates as ``guards.cause_discriminator``, so it is invariant
across encoder arms (verified: 3 correct / 4 wrong on all four arms). Difficulty
has to be measured against readers that *can* get it wrong.

Two readers are scored per case:

* ``contract`` -- reads the acceptance contract literally (``cause_discriminator``
  plus the category/blocker rules). This is the reader the pipeline is meant to
  approximate; it should be unaffected by the levers.
* ``magnitude`` -- the common shortcut: "a real outage shows a dramatic number".
  It requires a large margin past each reading threshold (CPU >= 95%, pool cut
  of at least half, connections over the cap by 20%, lock wait >= 2000ms, slow
  query >= 4000ms, payment latency >= 4000ms) and otherwise falls back to the
  loudest symptom. On the frozen v1 encodings every case clears that margin;
  on the hardened boundary encodings none of them do.

A drop in ``magnitude`` accuracy with a flat ``contract`` accuracy is the claim:
the observations got harder to read, not unreadable. It says nothing about
production incidents, blind performance, or any model other than these two
deterministic readers.

Run from the repository root::

    .venv/Scripts/python.exe analysis/wp_d/reports/hardened-difficulty-20261101/measure.py
"""

import json
import sys
from pathlib import Path

from incident_lens.incidentbench.scenarios.hardened import MECHANISM_SERVICE
from incident_lens.orchestration.guards import cause_discriminator
from incident_lens.schemas import Hypothesis
from incident_lens.tools.provider import EvidenceProvider

SOURCES = ("logs", "metrics", "changes", "configs", "database")
MECHANISMS = sorted(MECHANISM_SERVICE)


def records(provider, incident_id):
    return [r for source in SOURCES for r in provider._records(incident_id, source)]


def contract_reader(case_records):
    """Answer with the mechanism whose acceptance contract any record satisfies."""
    for mechanism in MECHANISMS:
        hypothesis = Hypothesis(
            hypothesis_id="probe",
            culprit_service=MECHANISM_SERVICE[mechanism],
            failure_mode=mechanism,
        )
        if any(cause_discriminator(hypothesis, r) for r in case_records):
            return mechanism
    return None


def _metric(case_records, service, names):
    for record in case_records:
        name = str(record.metadata.get("metric_name", ""))
        if record.source_type == "metrics" and record.service == service and name in names:
            return record.metadata.get("value")
    return None


def magnitude_reader(case_records):
    """Answer with the most dramatic number, ignoring where the contract sits."""
    cpu = _metric(case_records, "backend", {"cpu_percent", "thread_utilization"})
    if isinstance(cpu, (int, float)) and cpu >= 95:
        return "backend_resource_saturation"

    for record in case_records:
        if record.source_type != "configs":
            continue
        text = record.excerpt
        if "db_pool_max" not in text or "->" not in text:
            continue
        before, after = (float(x) for x in text.split("db_pool_max")[1].split(";")[0]
                         .split("->")[0:1] + [text.split("->")[1].split(";")[0]])
        if before > 0 and after <= before / 2:
            return "backend_pool_config_regression"

    for record in case_records:
        if record.source_type != "database":
            continue
        count = record.metadata.get("connection_count")
        limit = record.metadata.get("connection_limit")
        if (
            record.metadata.get("category") == "connections"
            and isinstance(count, (int, float)) and isinstance(limit, (int, float))
            and limit > 0 and count >= limit * 1.2
        ):
            return "postgres_connection_exhaustion"
        duration = record.metadata.get("duration_ms")
        if isinstance(duration, (int, float)) and record.metadata.get("blocked_by"):
            if duration >= 2000:
                return "postgres_lock_contention"
        elif isinstance(duration, (int, float)) and record.metadata.get("category") == "slow_queries":
            if duration >= 4000:
                return "postgres_slow_query"

    availability = _metric(case_records, "redis", {"availability"})
    if availability == 0:
        return "redis_unavailable"
    latency = _metric(case_records, "payment", {"p95_latency_ms", "latency_ms"})
    if isinstance(latency, (int, float)) and latency >= 4000:
        return "payment_external_timeout"
    return None


READERS = {"contract": contract_reader, "magnitude": magnitude_reader}


def score(dataset, oracle_root, reader):
    provider = EvidenceProvider(Path(dataset) / "rca")
    oracles = {
        p.parent.parent.name: json.loads(p.read_text())
        for p in Path(oracle_root).rglob("benchmark_oracle.json")
    }
    correct = wrong = abstained = 0
    for incident_id, oracle in oracles.items():
        case_records = records(provider, incident_id)
        answer = reader(case_records)
        truth = oracle["true_primary_root"]
        if not oracle["is_identifiable"]:
            abstained += answer is None
            continue
        if answer == truth["failure_mode"]:
            correct += 1
        else:
            wrong += 1
    return dict(correct=correct, wrong=wrong, abstained=abstained)


def main():
    arms = {
        "v1_frozen_10case": ("data/incidentbench_v16_dev", "local_oracles/incidentbench_v16_dev"),
        "v2_hardened_36case": (
            "data/incidentbench_v2_hardened",
            "local_oracles/incidentbench_v2_hardened",
        ),
    }
    result = {}
    for arm, (dataset, oracle) in arms.items():
        result[arm] = {name: score(dataset, oracle, reader) for name, reader in READERS.items()}
    print(json.dumps(result, indent=1, sort_keys=True))
    return result


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
