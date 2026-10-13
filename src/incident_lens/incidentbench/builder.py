"""Build public observations and separate pending candidate labels from private specs."""

import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path

import yaml

from incident_lens.schemas import CasePublicInput, EvidenceRecord
from incident_lens.tools.provider import ANSWER_FIELDS, EvidenceProvider

from .family_split import split_ids
from .scenarios import encode, simulate
from .schemas import INTERFACE_VERSION, SUPPORTED_MODES, BenchmarkCaseMetadata, BenchmarkOracle

BUILDER_VERSION = "causal-world-v1"
SERVICES = {
    "gateway": ["backend"],
    "backend": ["postgres", "redis", "payment"],
    "postgres": [],
    "redis": [],
    "payment": [],
}


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


def _digest(files: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for name, content in sorted(files.items()):
        digest.update(name.encode() + b"\0" + content.encode())
    return digest.hexdigest()


def _source_digest() -> str:
    root = Path(__file__).parent
    paths = [
        root / "builder.py",
        root / "family_split.py",
        root / "schemas.py",
        *sorted((root / "scenarios").glob("*.py")),
    ]
    return _digest({p.relative_to(root).as_posix(): p.read_text(encoding="utf-8") for p in paths})


def _load(config) -> dict:
    if isinstance(config, (str, Path)):
        path = Path(config)
        result = yaml.safe_load(path.read_text(encoding="utf-8"))
        if result.get("scenario_specs"):
            source = Path(result["scenario_specs"])
            if not source.is_absolute():
                source = path.parent / source
            result["families"] = yaml.safe_load(source.read_text(encoding="utf-8"))["families"]
        return result
    return dict(config)


def _pack(world, incident_id):
    rows, roles = encode(world, incident_id)
    for row in rows:
        EvidenceRecord.model_validate_json(json.dumps(row))
    case = dict(
        incident_id=incident_id,
        title="Service observation window",
        started_at=world.started_at.isoformat(),
        services=list(SERVICES),
        observed_symptoms=["Request latency and error rate observation window"],
    )
    CasePublicInput.model_validate_json(json.dumps(case))
    files = {"incident.json": _json(case)}
    for source in ("logs", "changes", "configs", "database"):
        files[f"{source}.jsonl"] = "".join(
            json.dumps(row, sort_keys=True) + "\n" for row in rows if row["source_type"] == source
        )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=[
            "evidence_id",
            "service",
            "observed_at",
            "excerpt",
            "metric_name",
            "value",
            "unit",
        ],
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        if row["source_type"] == "metrics":
            writer.writerow(
                {key: row[key] for key in ("evidence_id", "service", "observed_at", "excerpt")}
                | row["metadata"]
            )
    files["metrics.csv"] = stream.getvalue()
    if any(marker in content for content in files.values() for marker in ANSWER_FIELDS):
        raise ValueError("public answer metadata rejected")
    return files, rows, roles


def build_dataset(config, out, oracle_root) -> dict:
    """Fresh deterministic roots; config contains externally owned causal families.

    Each family needs opaque id, source_blueprint_id, near_duplicate_cluster_id,
    split, started_at, mechanism, and variants [{id, kind, mechanism?}]. kind is
    ordinary/misleading/missing/counterfactual; paired variants additionally carry
    pair_id. Unreviewed labels always remain pending/development_visible.
    """
    output, private = Path(out).absolute(), Path(oracle_root).absolute()
    if output.exists() or private.exists():
        raise FileExistsError("builder requires fresh public and oracle output roots")
    public_resolved, private_resolved = output.resolve(), private.resolve()
    if private_resolved.is_relative_to(public_resolved) or public_resolved.is_relative_to(
        private_resolved
    ):
        raise ValueError("oracle and public roots must be disjoint")
    settings = _load(config)
    families = settings.get("families", [])
    if not families:
        raise ValueError("external causal family specifications required")
    # This initial generic encoder lineage has no independently authored holdout
    # observations. Merely renaming blueprint/cluster IDs cannot authorize leakage.
    core_splits = {f["split"] for f in families if f.get("cohort", "core") == "core"}
    if len(core_splits) > 1:
        raise ValueError("shared core encoder lineage must remain in one split")
    packs, metadata, oracles = [], [], []
    seen_families, pair_roots = set(), {}
    counter = int(settings.get("first_incident_number", 1001))
    for family in families:
        if family["id"] in seen_families:
            raise ValueError("duplicate family identity")
        seen_families.add(family["id"])
        variant_ids = set()
        for variant in family["variants"]:
            if variant["id"] in variant_ids:
                raise ValueError("duplicate variant identity")
            variant_ids.add(variant["id"])
            if variant["kind"] not in {"ordinary", "misleading", "missing", "counterfactual"}:
                raise ValueError("unknown observation intervention")
            incident_id = f"incident_{counter:04d}"
            counter += 1
            world = simulate(family, variant)
            cohort = family.get("cohort", "core")
            if world.mechanism == "healthy" and cohort != "monitoring":
                raise ValueError("healthy windows belong to monitoring")
            if world.mechanism not in SUPPORTED_MODES and cohort == "core":
                raise ValueError("unsupported mechanism belongs to OOD")
            files, rows, roles = _pack(world, incident_id)
            pair_id = variant.get("pair_id")
            if pair_id:
                pair_roots.setdefault(pair_id, []).append((world.mechanism, _digest(files)))
            identifiable = bool(roles["support"]) and cohort == "core" and not world.missing
            oracle = BenchmarkOracle.model_validate(
                dict(
                    incident_id=incident_id,
                    scenario_family_id=family["id"],
                    mechanism_id=world.mechanism,
                    counterfactual_pair_id=pair_id,
                    is_identifiable=identifiable,
                    true_primary_root=dict(
                        culprit_service=world.root_service,
                        failure_mode=world.mechanism,
                        root_cause_code=world.mechanism,
                    ),
                    acceptable_support_sets=[
                        dict(
                            evidence_ids=roles["support"],
                            rationale="Cause-specific measurement and independently encoded source "
                            "precede propagated symptoms.",
                        )
                    ]
                    if identifiable
                    else [],
                    contradicting_evidence_ids=roles["contradicting"],
                    misleading_evidence_ids=roles["misleading"],
                    required_discriminator_types=sorted(
                        {r["source_type"] for r in rows if r["evidence_id"] in roles["support"]}
                    ),
                    causal_sequence=[
                        f"Healthy baseline at {world.started_at.isoformat()}",
                        f"Resource intervention at {world.trigger_at.isoformat()}",
                        f"Dependency response at {world.symptom_at.isoformat()}",
                    ],
                    identifiability_rationale="Candidate cross-source causal discriminator present"
                    if identifiable
                    else "Discriminator absent or cohort outside RCA taxonomy",
                    cohort=cohort,
                )
            )
            meta = BenchmarkCaseMetadata.model_validate(
                dict(
                    incident_id=incident_id,
                    split=family["split"],
                    scenario_family_id=family["id"],
                    scenario_variant_id=variant["id"],
                    challenge_tags=[variant["kind"]],
                    public_sha256=_digest(files),
                    source_blueprint_id=family["source_blueprint_id"],
                    near_duplicate_cluster_id=(
                        "cluster_causal_world_v1"
                        if cohort == "core"
                        else family["near_duplicate_cluster_id"]
                    ),
                    counterfactual_pair_id=pair_id,
                    cohort=cohort,
                )
            )
            packs.append((incident_id, files))
            metadata.append(meta)
            oracles.append(oracle)
    splits = split_ids(metadata)
    for pairs in pair_roots.values():
        if len(pairs) != 2 or len({x[0] for x in pairs}) != 2 or len({x[1] for x in pairs}) != 2:
            raise ValueError("counterfactual pair must change root and public observations")
    counts = Counter(meta.cohort for meta in metadata)
    coverage = dict(
        total_cases=len(metadata),
        families=len(seen_families),
        independent_audited_families=0,
        independence_status="unreviewed",
        cohorts={k: counts[k] for k in ("core", "monitoring", "ood")},
        splits={k: len(v) for k, v in splits.items()},
        core_splits={k: sum(m.split == k and m.cohort == "core" for m in metadata) for k in splits},
        challenges={
            k: sum(k in m.challenge_tags for m in metadata)
            for k in ("ordinary", "misleading", "missing", "counterfactual")
        },
        identifiable=sum(o.is_identifiable for o in oracles),
        accepted_labels=0,
        blindness_level="development_visible",
    )
    # Everything is validated in memory before any filesystem mutation.
    output.mkdir(parents=True, exist_ok=False)
    private.mkdir(parents=True, exist_ok=False)
    for incident_id, files in packs:
        folder = output / "rca" / "incidents" / incident_id / "public"
        folder.mkdir(parents=True)
        for filename, content in files.items():
            (folder / filename).write_text(content, encoding="utf-8", newline="\n")
    topology = output / "rca" / "topology"
    topology.mkdir()
    (topology / "services.yaml").write_text(_json({"services": SERVICES}), encoding="utf-8")
    split_root = output / "rca" / "splits"
    split_root.mkdir()
    for name, ids in splits.items():
        (split_root / f"{name}_ids.json").write_text(_json(ids), encoding="utf-8")
    for oracle in oracles:
        folder = private / "rca" / "incidents" / oracle.incident_id / "private"
        folder.mkdir(parents=True)
        (folder / "benchmark_oracle.json").write_text(_json(oracle.model_dump()), encoding="utf-8")
    (output / "public_case_index.json").write_text(
        _json([m.model_dump() for m in metadata]), encoding="utf-8"
    )
    (output / "coverage.json").write_text(_json(coverage), encoding="utf-8")
    from .manifest import digest_tree

    (output / "manifest.json").write_text(
        _json(
            dict(
                benchmark_version="incidentbench-v1",
                interface_version=INTERFACE_VERSION,
                builder_version=BUILDER_VERSION,
                label_status="pending",
                source_code_sha256=_source_digest(),
                rca_public_sha256=digest_tree(output / "rca"),
                generated_at=min(
                    o.causal_sequence[0].removeprefix("Healthy baseline at ") for o in oracles
                ),
                blindness_level="development_visible",
                coverage=coverage,
            )
        ),
        encoding="utf-8",
    )
    errors = EvidenceProvider(output / "rca").validate_public()
    if errors:
        raise ValueError("generated observation contract invalid: " + "; ".join(errors))
    return coverage
