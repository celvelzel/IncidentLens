"""Keep all declared source relatives together; independence is not inferred from labels."""

from collections import defaultdict


def validate_family_split(cases) -> None:
    """Reject split leakage of families, blueprints, duplicates and interventions."""
    groups = defaultdict(set)
    incident_ids = set()
    for item in cases:
        row = item.model_dump() if hasattr(item, "model_dump") else item
        if row["incident_id"] in incident_ids:
            raise ValueError("duplicate incident identity")
        incident_ids.add(row["incident_id"])
        if row["split"] not in {"seed", "dev", "test"}:
            raise ValueError("unknown split")
        for key in (
            "scenario_family_id", "source_blueprint_id", "near_duplicate_cluster_id",
            "counterfactual_pair_id",
        ):
            if row.get(key):
                groups[key, row[key]].add(row["split"])
    if any(len(splits) > 1 for splits in groups.values()):
        raise ValueError("source relatives cross dataset splits")


def split_ids(cases) -> dict[str, list[str]]:
    validate_family_split(cases)
    result = {name: [] for name in ("seed", "dev", "test")}
    for item in cases:
        row = item.model_dump() if hasattr(item, "model_dump") else item
        result[row["split"]].append(row["incident_id"])
    return {key: sorted(value) for key, value in result.items()}
