# Run Guide

This guide is the operational reference for IncidentLens 1.6.1. It covers installation, the
offline Mock workflow, architecture variants, replay, the dashboard, real-provider
configuration, budgets, saved artifacts, tests and submission packaging. The CLI
subcommands and flags shown here were checked against `python -m incident_lens.cli --help`
and `python -m incident_lens.cli run --help`.

For design rationale see [Architecture](ARCHITECTURE.md); for results see
[Evaluation](EVALUATION.md). The frozen contracts in `docs/reference/protocol.md` remain
normative only where they do not conflict with the current implementation; the current
default wall-clock budget is 600 seconds, not the older 90-second draft value.

## 1. Prerequisites

| Requirement | Detail |
| --- | --- |
| Python | 3.11 or newer; the project is verified on Windows with Python 3.13 |
| Shell | PowerShell 7 or Windows PowerShell, or a POSIX shell such as bash |
| Disk | Enough space for the virtual environment and one run's artifacts (small) |
| Network | Not required for the offline Mock provider; required only to install dependencies or call a real provider |
| Provider credentials | Not required for Mock; a real run needs a compatible OpenAI-style endpoint, model name and key |

The repository pins runtime and development dependencies in `requirements.lock`. Installing
with the lock file first and the project in editable mode second keeps the environment
reproducible.

## 2. Install

### PowerShell

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.lock
.venv\Scripts\python.exe -m pip install -e '.[dev]'
```

### bash

```bash
python -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install -e '.[dev]'
```

If `python` does not resolve to a supported interpreter on Windows, create the environment
with the launcher instead:

```powershell
py -3.13 -m venv .venv
```

### Verify the environment and data

```powershell
.venv\Scripts\python.exe -m incident_lens.cli check-environment
.venv\Scripts\python.exe -m incident_lens.cli validate-data
.venv\Scripts\python.exe -m incident_lens.cli list-cases
```

`check-environment` prints installed versions for the package, LangGraph, Pydantic and
Streamlit. It currently prints a stale display string `"incident-lens": "0.1.0"` even though
the package version is 1.6.1; treat the field as a known display defect, not the project
version.

`validate-data` checks the public incident packs against the expected filenames and contracts.
`list-cases` lists the public case identifiers. Neither command reads private benchmark
oracles.

`export-schemas` regenerates the JSON Schema contracts under `contracts/` from the Pydantic
models, and is only needed when a schema changes:

```powershell
.venv\Scripts\python.exe -m incident_lens.cli export-schemas
```

Commit the regenerated `contracts/` alongside the model change; a stale contract is a review
defect, not a runtime one.

## 3. Offline Mock quick start

Mock is the default provider. It is deterministic over the supplied public evidence, makes no
network request and estimates nothing about real diagnostic quality.

```powershell
.venv\Scripts\python.exe -m incident_lens.cli run `
  --case incident_001 `
  --provider mock `
  --variant dynamic `
  --cache-mode off `
  --out results/quickstart
```

The same command on one line:

```powershell
.venv\Scripts\python.exe -m incident_lens.cli run --case incident_001 --provider mock --variant dynamic --cache-mode off --out results/quickstart
```

`--case` and `--out` are required. The output directory is created if it does not exist.
The CLI **refuses** an existing non-empty `--out` directory, and refuses a symlink, so every
run needs its own path — pick a unique directory per run rather than reusing one. This guard
is deliberate: it stops a run from overwriting earlier evidence. After completion, inspect:

```text
results/quickstart/
  report.md      human-readable report
  result.json    structured result and report payload
  trace.json     full replayable run trace
```

Render the saved trace without invoking the graph, tools or provider:

```powershell
.venv\Scripts\python.exe -m incident_lens.cli replay --trace results/quickstart/trace.json
```

`incident_001` is an ordinary identifiable case and normally resolves. For the abstention
path, run an evidence-missing case such as `incident_006`:

```powershell
.venv\Scripts\python.exe -m incident_lens.cli run --case incident_006 --provider mock --variant dynamic --cache-mode off --out results/demo006
```

The report should be `INCONCLUSIVE`: the public pack omits a discriminator needed by the
cited-or-abstain contract. This is correct behaviour, not a crash or a provider error.

## 4. Architecture variants

The runtime accepts exactly four variant names.

| CLI value | Display name | What changes |
| --- | --- | --- |
| `dynamic` | Dynamic | Coordinator selects one or two specialists per round; deterministic Merge and FinalizeGate; no independent verifier. Runtime default. |
| `full` | Dynamic (with verifier) | Same dynamic selection plus an independent Verifier review loop before finalization. |
| `fixed` | Fixed-4 | One fixed batch of logs, metrics, database and changes specialists, then coordinate/merge/finalize. |
| `single` | Single | One identity plans, investigates and self-reflects; verify is self-review, not independent review. |

```powershell
.venv\Scripts\python.exe -m incident_lens.cli run --case incident_001 --provider mock --variant single  --cache-mode off --out results/demo-single
.venv\Scripts\python.exe -m incident_lens.cli run --case incident_001 --provider mock --variant fixed   --cache-mode off --out results/demo-fixed
.venv\Scripts\python.exe -m incident_lens.cli run --case incident_001 --provider mock --variant dynamic --cache-mode off --out results/demo-dynamic
.venv\Scripts\python.exe -m incident_lens.cli run --case incident_001 --provider mock --variant full    --cache-mode off --out results/demo-full
```

`dynamic_no_verifier` and `no_verifier` are frozen historical aliases normalized to
`dynamic`. They exist so old saved protocols and traces keep replaying; do not use them for
new experiments. Benchmark condition names are separately frozen as
`strong_single_equivalent_tools`, `fixed_four_equivalent_tools`, `dynamic_no_verifier` and
`full`.

## 5. Replay

Replay reads a saved `trace.json` and reconstructs the timeline. It does not call the graph,
tools or provider.

```powershell
.venv\Scripts\python.exe -m incident_lens.cli replay --trace results/quickstart/trace.json
```

The bundled web dashboard can also replay any retained trace under `results/**/trace.json`.
Replay is confined to that pattern; arbitrary filesystem paths are not served. See
[Architecture](ARCHITECTURE.md#9-replay-and-the-web-layer) for the trust boundary.

## 6. Web dashboard

Start the bundled Starlette dashboard:

```powershell
.venv\Scripts\python.exe -m incident_lens.cli web
```

Defaults are host `127.0.0.1` and port `8022`, so the URL is `http://127.0.0.1:8022`.
To use another port:

```powershell
.venv\Scripts\python.exe -m incident_lens.cli web --port 8767
```

The interface has six views: overview, new investigation, trace library, run detail, system
design and evaluation. The UI text is Chinese; identifiers remain in English. Run detail
exposes the investigation timeline, hypothesis board, evidence registry, findings and
root-cause report. Replays are labelled `Recorded Replay` and the offline provider is
labelled `Mock`. Live runs launched from the UI are written under `results/ui/<run_id>/`.

The evaluation view (`#/evaluation`) is a **static snapshot** of the recorded hardened batch
`full144-hardened-c4-20261101`, hard-coded in
`src/incident_lens/web/static/js/knowledge.js`; it is not a live feed and does not read
evaluation truth from disk. Show `docs/EVALUATION.md` or the saved hardened-batch report for
the full tables and boundaries.

A retained Streamlit dashboard can be started separately:

```powershell
.venv\Scripts\python.exe -m streamlit run src/incident_lens/ui/app.py
```

## 7. Real provider configuration

Real runs use an OpenAI-compatible chat-completions endpoint. Start from the template and
never commit the resulting `.env`:

```powershell
Copy-Item .env.example .env
```

```bash
cp .env.example .env
```

Edit `.env` locally. The template contains no credentials and must remain blank in version
control.

| Variable | Purpose | Mock default |
| --- | --- | --- |
| `INCIDENT_LENS_MODEL` | Provider model identifier | blank |
| `INCIDENT_LENS_API_KEY` | Bearer credential; local secret only | blank |
| `INCIDENT_LENS_BASE_URL` | OpenAI-compatible base URL | blank |
| `INCIDENT_LENS_RESPONSE_FORMAT` | `json_schema` or `json_object` | `json_schema` |
| `INCIDENT_LENS_THINKING` | `enabled`, `disabled`, or blank for provider default | blank |
| `INCIDENT_LENS_REQUEST_TIMEOUT` | Per-request timeout in seconds | `180` |
| `CACHE_MODE` | `off`, `exact` or `semantic` | `off` |
| `CACHE_SIMILARITY_THRESHOLD` | Semantic-cache similarity threshold | `0.95` |
| `CACHE_TTL_HOURS` | Cache entry lifetime | `24` |
| `CACHE_EMBEDDING_MODEL` | Cache embedding backend | `fake` |
| `CACHE_DB_PATH` | SQLite cache location | `results/cache.sqlite` |

Run with an explicitly selected provider:

```powershell
.venv\Scripts\python.exe -m incident_lens.cli run --case incident_001 --provider real --variant dynamic --cache-mode off --out results/real001
```

The exact model identifier, endpoint compatibility and response-format support are provider
responsibilities. The project does not silently substitute Mock for a failed real request.
If the endpoint rejects `json_schema`, try `--response-format json_object`; structured-output
repair is bounded to one retry.

Diagnostic-quality claims in this repository come from the recorded development batches, not
from any real-provider run you perform locally. Do not describe a local run as a new
benchmark result without preserving the full protocol, artifacts and scoring boundary.

## 8. Run options and budgets

| Option | Meaning |
| --- | --- |
| `--case` | Public incident identifier, required |
| `--provider` | `mock` or `real` |
| `--variant` | `single`, `fixed`, `dynamic` or `full` |
| `--out` | Output directory, required; use a new path to preserve earlier evidence |
| `--data-root` | Public incident root; default `data` |
| `--config` | Runtime configuration; default `configs/system.yaml` |
| `--cache-mode` | `off`, `exact` or `semantic`; config default is off |
| `--cache-db` | Cache database path |
| `--max-rounds` | Investigation round cap |
| `--max-tool-calls` | Tool-query cap |
| `--max-llm-calls` | Logical LLM-request cap; retries and repair consume usage |
| `--max-seconds` | Wall-clock cap in seconds |
| `--max-tokens` | Optional token cap |
| `--response-format` | `json_schema` or `json_object` |
| `--thinking` | `enabled` or `disabled` |
| `--request-timeout` | Per-request timeout in seconds |
| `--profile` | `legacy_rca` or `incident_response` |
| `--selection-policy` | Dynamic assignment policy: `current_dynamic`, `active_evidence`, `active_no_cost`, `active_no_discrimination` or `first_eligible` |
| `--shadow-caes` | Compute CAES-style shadow selection without changing execution |
| `--monitor-mode` | `legacy`, `manual_snapshot` or `offline_replay` |
| `--snapshot` | JSON list of public evidence observations for snapshot workflows |

Two shipped profiles set different defaults:

| Setting | `configs/system.yaml` (`legacy_rca`) | `configs/incident-response.yaml` (`incident_response`) |
| --- | ---: | ---: |
| Rounds | 4 | 6 |
| Tool calls | 12 | 24 |
| Logical LLM calls | 16 | 24 |
| Wall clock | 600 s | 600 s |
| Monitoring | off; graph starts at coordinate | off in shipped config; legacy or snapshot modes selectable |
| Database tools | enabled (default) | enabled |
| Remediation | off | `PLAN_ONLY`, at most 2 proposals |
| Task attempts | 2 | 2 |
| Continue on partial failure | yes | yes |
| Recovery | disabled | disabled |

The legacy profile inherits the schema defaults for task attempts and partial-failure
continuation because `configs/system.yaml` declares no `task_runtime` block; both profiles
therefore resolve to 2 attempts and continue-on-partial-failure. Database tools are enabled
by default in both profiles — the difference is that `incident-response.yaml` additionally
enables the database specialist in its routing policy.

CLI overrides replace the profile values for that run. Budget exhaustion is a runtime failure
with `BUDGET_EXHAUSTED`; ordinary evidence insufficiency is a normal `INCONCLUSIVE` result.
Do not raise budgets to convert an intended abstention into a conclusion. Any experimental
comparison must hold budgets equal across variants and record the effective settings.

For an incident-response run:

```powershell
.venv\Scripts\python.exe -m incident_lens.cli run --case incident_001 --config configs/incident-response.yaml --profile incident_response --provider mock --variant dynamic --cache-mode off --out results/response001
```

## 9. Artifact layout

| Path | Contents |
| --- | --- |
| `<out>/trace.json` | Events, state snapshot, report and termination record; the replay input |
| `<out>/result.json` | Structured run result and report payload |
| `<out>/report.md` | Human-readable report with citations |
| `results/ui/<run_id>/` | Runs started from the bundled dashboard |
| `results/acceptance/` | Small tracked acceptance baselines, including a frozen-alias trace |
| `results/cache.sqlite` | Optional local explanation cache; never a source of evidence |
| `analysis/wp_d/reports/hardened144-20261101/` | Tracked hardened-batch report and recomputation script |

`trace.json` is the unit of reproduction for a single run. It contains public observations and
decisions, not hidden reasoning or secrets. Treat retained traces as evidence: do not edit
them to make a demo look better, and do not present a replayed trace as a live run.

## 10. Tests

A fresh full-suite run is required before submission. The recorded run is
`1179 passed, 3 skipped in 450.01s`, exit 0, on 2026-11-02 against the tree that ships this
documentation (`results/pytest-current.log`). It is a point-in-time record, not a standing
guarantee: re-run it after any change to source, tests, configuration or web assets. Record
the command, date, interpreter, collected count, failures, errors and skips in the release
acceptance record.

```powershell
.venv\Scripts\python.exe -m pytest -q
```

A targeted run can be used while developing, but it does not replace the full suite:

```powershell
.venv\Scripts\python.exe -m pytest tests/integration/test_cli.py -q
```

Static checks, if used, are separate from test results:

```powershell
.venv\Scripts\python.exe -m ruff check src tests
```

## 11. IncidentBench reproduction

The full benchmark workflow has its own guide:
[IncidentBench](incidentbench/README.md). The runner requires an editable source
checkout, a dataset root containing `manifest.json` and `rca/`, an evaluator oracle root for
scored runs, and fresh output directories.

```powershell
.venv\Scripts\python.exe scripts/validate_incidentbench.py --dataset data/incidentbench_v2_hardened --mode public
.venv\Scripts\python.exe scripts/run_incidentbench.py --dataset data/incidentbench_v2_hardened --split dev --variant all --provider mock --cache-mode off --jobs 1 --out results/incidentbench/hardened-mock
```

Use `--oracle-root <path>` only when you have the separate evaluator root; public validation
does not need it. The hardened 36-case development set is `data/incidentbench_v2_hardened`
with cases `incident_4001`–`incident_4036`. Its labels are candidate labels with
`annotator_status: pending`; scores from it are provisional.

The recorded four-architecture statistics were produced with non-default round, tool,
request and timeout budgets. Reproducing the numbers requires the recorded settings
and the same provider/model, not just the commands. Treat
`analysis/wp_d/reports/hardened144-20261101/` as the authoritative record of what was run.

## 12. Troubleshooting

| Symptom | Likely cause | Action |
| --- | --- | --- |
| `python` not found | Interpreter not on PATH | Use `py -3.13 -m venv .venv` on Windows |
| `No module named incident_lens` | Project not installed in the active environment | Run the editable install with the same `.venv` interpreter |
| `FileNotFoundError` for a case | Wrong `--data-root` or case identifier | Run `list-cases` and confirm the dataset root |
| Old and new artifacts mixed | Reused a populated `--out` directory | Choose a fresh `--out`; do not delete retained evidence casually |
| `INCONCLUSIVE` on an ordinary case | Evidence failed a deterministic gate | Inspect the report and trace; this may be correct |
| `BUDGET_EXHAUSTED` | A configured cap was reached | Inspect events before changing budgets; record any override |
| Real provider 401/403 | Missing or invalid credential | Set the key only in `.env` or the process environment |
| Real provider schema error | Endpoint lacks `json_schema` support | Try `--response-format json_object` |
| Port already in use | Another dashboard is running | `web --port 8767` |
| Web replay finds no traces | No `results/**/trace.json` retained | Run a case or point the trace library at an existing results tree |
| `check-environment` shows 0.1.0 | Stale display string | Ignore; package metadata and `pyproject.toml` say 1.6.1 |

## 13. Submission packaging

The course recommends the archive name `COMP5584+GroupProject+Group5.zip`. Build the archive
from a clean checkout, not from a working tree full of local runs.

Include:

- source under `src/`, tests, `scripts/`, `configs/`, and `data/` public packs and metadata
  only; never an evaluator oracle root;
- `pyproject.toml`, `requirements.lock`, `README.md`, `README.zh-CN.md`, `docs/`, and the
  tracked analysis report;
- the `presentation/` directory, including `IncidentLens_Final.pptx`, its PDF export and
  rendered slides, plus any completed contribution statement;
- a fresh test and acceptance record produced for the final tree.

Exclude:

- `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`;
- `.env`, keys, tokens, provider logs and any local credential store;
- `results/` except small artifacts deliberately retained as evidence;
- `results/cache.sqlite`, temporary archives and operating-system clutter.

Verify the archive opens from a clean extraction, the install commands in this guide still
work, and no secret appears in the file list or file contents. A demo video is not produced by
this documentation task; if the group records one, follow [Demo Guide](DEMO_GUIDE.md) and
keep it outside the source archive unless the submission instructions say otherwise.
