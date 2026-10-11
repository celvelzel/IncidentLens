# Responsibility and implementation evidence

Human names/contributions require team confirmation and their own evidence.
This matrix maps requested roles to generated implementation, not student authorship.

| Role | Responsibility | Evidence |
| --- | --- | --- |
| Lead / Integrator | Schema, LangGraph, gates, CLI, integration | 67e7a2d, 9576668; integration commits |
| Data & Tools | Fixtures, RBAC, issued-context ledger | 27deaa0 |
| Agent Implementation | Providers, role services, public Mock | 858573c, 16be152 |
| Evaluation | Four baselines and after-run scoring | 5d03a98 |
| UI | Streamlit, Replay, download | UI integration commit and independent AppTest review |
| Independent QA | Read-only adverse reproductions and acceptance | docs/acceptance/P7.md |

Isolated cache implementation was integrated as 7fdf08d. Lead revalidated and
fixed integration against current main. No PR or remote push was performed.

Continuation evidence: 00d8c93 bounded experiments; 5928131/198f12c failure-aware
scoring and Verifier STOP; 0d24227 publication/reconciliation guards; dbc54c5 and
5aaf783 saved-artifact analysis. Independent QA recomputed complete dev/test
artifacts separately from judging model quality. Human ownership remains unconfirmed.
