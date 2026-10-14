# V1.5 source publication scope

The publication merges the existing remote V1.4 documentation without rewriting its
history, updates both READMEs with CAES architecture/usage/limits, and includes the
authoritative V1.5 implementation specification. README content describes durable
features and setup; dated experiment/acceptance evidence stays in this documentation.

The example YAML now uses actual CLI budget keys (`tool_calls_limit`, `llm_calls_limit`,
`time_limit_seconds`) and quotes `cache_mode: "off"`. This is a configuration-example
correction; the runtime implementation remains unchanged from2611182. A CLI run using
the example verifies the configured24model-call limit. Historical experiment locks
belong to their original source/config snapshots; modifying even an unused example
configuration invalidates a subsequent frozen resume by design. Do not overwrite or
relabel those historical ledgers.

Published small acceptance artifacts under `results/v15/final-20261014/` include the
clean full850pass/3skip log and JUnit, lint/format logs, engineering summary, CAES schema
and delivery/hash manifests. Full raw experiment ledgers, recorded states/traces,
intermediate failures, old checkpoints, wheel/installation environments and caches are
retained locally. Their absence from the remote repository is not a claim that they
did not exist or that failed attempts passed. Reproduce new public Seed diagnostics
with the documented scripts and fresh output directories; full saved-ledger replay
requires the corresponding locally retained raw batch.

Formal P4/P5/Frozen Test/real-provider evidence remains BLOCKED_BY_UPSTREAM. No public
source release is represented as a successful research release or efficacy result.
No private Oracle, credentials, `.env`, unrelated PDF scratch directory, or unrelated
V1.4 acceptance artifacts are added in this publication.
