from .arguments import DependenciesArgs, MetricsArgs
from .provider import EvidenceProvider


def query_metrics(provider: EvidenceProvider, incident_id: str, args: MetricsArgs):
    return [
        record
        for record in provider._records(incident_id, "metrics")
        if record.service == args.service
        and args.start_ts <= record.observed_at <= args.end_ts
        and (not args.metric_names or record.metadata.get("metric_name") in args.metric_names)
    ]


def get_dependencies(provider: EvidenceProvider, incident_id: str, args: DependenciesArgs):
    return [
        record
        for record in provider._records(incident_id, "topology")
        if args.service is None or record.service == args.service
    ]
