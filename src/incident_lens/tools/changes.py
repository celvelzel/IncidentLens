from .arguments import ChangesArgs, ConfigDiffArgs
from .errors import QueryNotFoundError
from .provider import EvidenceProvider


def query_changes(provider: EvidenceProvider, incident_id: str, args: ChangesArgs):
    return [
        record
        for record in provider._records(incident_id, "changes")
        if (args.service is None or record.service == args.service)
        and (args.start_ts is None or record.observed_at >= args.start_ts)
        and (args.end_ts is None or record.observed_at <= args.end_ts)
        and (args.change_type is None or record.metadata.get("change_type") == args.change_type)
    ]


def get_config_diff(provider: EvidenceProvider, incident_id: str, args: ConfigDiffArgs):
    changes = provider._records(incident_id, "changes")
    if not any(record.metadata.get("change_id") == args.change_id for record in changes):
        raise QueryNotFoundError("change does not exist")
    return [
        record
        for record in provider._records(incident_id, "configs")
        if record.metadata.get("change_id") == args.change_id
    ]
