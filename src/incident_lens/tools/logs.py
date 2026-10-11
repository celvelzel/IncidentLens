from .arguments import LogsArgs
from .provider import EvidenceProvider


def query_logs(provider: EvidenceProvider, incident_id: str, args: LogsArgs):
    return [
        record
        for record in provider._records(incident_id, "logs")
        if record.service == args.service
        and args.start_ts <= record.observed_at <= args.end_ts
        and (args.severity is None or record.metadata.get("severity") == args.severity)
        and (args.contains is None or args.contains in record.excerpt)
    ]
