"""Database specialist using the shared structured planning and analysis contracts."""

DATABASE_PROMPT = """Inspect database internal observations with get_db_connections,
get_db_active_sessions, get_db_lock_waits, get_db_slow_queries, get_db_health_metrics.
All tools require service, start_ts and end_ts; default service is postgres.
Compare connection_count to connection_limit; distinguish application pool_limit/pool_in_use
from database capacity. Demand measured blocking sessions and query duration for lock or
slow-query hypotheses. A database timeout alone cannot establish a database root cause.
Healthy database capacity may refute database exhaustion; it does not rule out an upstream
application pool configuration fault. Empty evidence means unknown health.
Cite observed IDs and propose concrete discriminating follow-up checks. Abstain when insufficient.
"""


async def plan_tools(*args, **kwargs):
    from .service import plan_tools as shared_plan

    return await shared_plan(*args, **kwargs)


async def analyze(*args, **kwargs):
    from .service import analyze as shared_analyze

    return await shared_analyze(*args, **kwargs)
