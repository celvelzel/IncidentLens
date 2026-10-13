"""Read-only category slices from the public database evidence pack."""

from .arguments import DatabaseArgs
from .provider import EvidenceProvider

DATABASE_CATEGORIES = {
    "get_db_connections": "connections",
    "get_db_active_sessions": "active_sessions",
    "get_db_lock_waits": "lock_waits",
    "get_db_slow_queries": "slow_queries",
    "get_db_health_metrics": "health_metrics",
}


def _query(category):
    def query(provider: EvidenceProvider, incident_id: str, args: DatabaseArgs):
        return [
            record
            for record in provider._records(incident_id, "database")
            if record.service == args.service
            and args.start_ts <= record.observed_at <= args.end_ts
            and record.metadata["category"] == category
        ]

    return query


DATABASE_HANDLERS = {name: _query(category) for name, category in DATABASE_CATEGORIES.items()}
get_db_connections = DATABASE_HANDLERS["get_db_connections"]
get_db_active_sessions = DATABASE_HANDLERS["get_db_active_sessions"]
get_db_lock_waits = DATABASE_HANDLERS["get_db_lock_waits"]
get_db_slow_queries = DATABASE_HANDLERS["get_db_slow_queries"]
get_db_health_metrics = DATABASE_HANDLERS["get_db_health_metrics"]
