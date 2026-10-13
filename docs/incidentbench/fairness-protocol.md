# Equivalent-tool experiment protocol

The runner invokes the existing Graph sequentially, randomizing the full case/repeat/variant schedule with the locked seed. Each run receives a fresh provider, budget and run identity, cache off, database-equivalent tools and the benchmark RCA workflow. Fixed-four explicitly opts into the lead's four-specialist schedule; legacy fixed remains unchanged.

Provider identity, model, temperature and recovery configuration must remain equal across runs. Actual physical requests, retries, repair requests and missing tokens come from MeasuredProvider, not budget limits. Raw state is written and fsynced before an oracle receipt is attached and before evaluator access. Failed runs retain unique keys and stay in denominators. Fresh outputs refuse overwrite. Run IDs include a persisted experiment UUID, so separate experiments have separate identities.

Explicit `--resume` supports offline MockProvider experiments under the same source/data/protocol/model/parameter/evaluator locks and exact seeded schedule. An OS-backed file lock prevents concurrent writers. Completed and failed keys are never executed again. Durable raw records missing scores are scored once without a model call; a durable state missing a raw ledger record is retained with unknown usage. STARTED attempts with no durable state become saved ERROR/INTERRUPTED records with request/token/latency counts null, then only unstarted keys continue. This policy is saved before the first run. Existing derived files are compared, never overwritten; a completed resume validates all derived outputs and makes no provider calls. Changed labels, receipts, order or locks are rejected. Truncated JSONL lines are retained and require explicit audit rather than automatic deletion. Real-provider resume remains unsupported.

Seed/Dev pending labels produce **provisional** scores. Development Test never reads labels, including during later analysis. Formal execution is deliberately blocked while independent acceptance and sealing readiness are pending (`FORMAL_RUNNER_PENDING`). Real CLI validates explicit project credentials and model, requires an external `--readiness` JSON containing matching `model_id`, `response_format` and `provider_compatible=true`, and has no fallback to mock. It performs no automatic paid probe. Compatibility does not establish RCA quality. No human scores exist without validated review records.

Example offline commands (from the repository root):

```powershell
.venv\Scripts\python.exe scripts/run_incidentbench.py --dataset data/incidentbench_v1 --split seed --provider mock --oracle-root local_oracles/incidentbench_v1 --out results/incidentbench/v1/mock-seed
.venv\Scripts\python.exe scripts/analyze_incidentbench.py --input results/incidentbench/v1/mock-seed/raw-runs.jsonl --oracle-root local_oracles/incidentbench_v1 --out results/incidentbench/v1/mock-seed-analysis
# Resume the same offline experiment, preserving all completed and failed attempts:
.venv\Scripts\python.exe scripts/run_incidentbench.py --dataset data/incidentbench_v1 --split seed --provider mock --oracle-root local_oracles/incidentbench_v1 --out results/incidentbench/v1/mock-seed --resume
```

Analysis requires the original dataset/source/config lock, exact saved states and artifact digests. If original runs were scored, supplied labels must match their saved per-run oracle digest and review version. Without evaluator labels, reanalysis is explicitly unscored. Persisted paths bind completion receipts to their original location; relocating artifacts currently requires retaining those original state files.
