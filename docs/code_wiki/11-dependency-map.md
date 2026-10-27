# 11 · 依赖关系图

本页给出模块间依赖方向（谁 import 谁）、外部依赖、文件与数据依赖，以及反向依赖禁令。用于架构评审与重构。

## 1. 分层依赖（向下）

```text
接口/<入口> 层
  cli.py
  web/server.py · web/__main__.py
  ui/app.py
  scripts/*.py
        │  只依赖下一层
        ▼
编排层  orchestration/
  graph.py · budget.py · permits.py · runtime.py · merge.py · guards.py
  recovery.py · observability.py · report.py · config.py · active_investigation/
        │
        ▼
角色层  agents/
  service.py · monitoring.py · remediation.py · database.py
        │
  ┌─────┴──────┬─────────────┬──────────────┐
  ▼            ▼             ▼              ▼
能力层       能力层        契约层          安全层
llm/        tools/         schemas/       security/
           (自绘)          (叶子，被所有层依赖)
            │
            ▼
         数据 data/
```

## 2. 模块级 import 图

### 2.1 `orchestration/graph.py`（中枢）

```python
from langgraph.graph import END, START, StateGraph
from incident_lens.orchestration.budget import BudgetExceeded, CallBudget
from incident_lens.orchestration.guards import (
    cause_discriminator, evidence_fingerprint,
    finalize_errors, review_fingerprint, reviewed_finalization_ready)
from incident_lens.orchestration.merge import merge_results
from incident_lens.orchestration.report import observed_chain
from incident_lens.schemas import (Budget, CoordinatorDecision, InvestigationState, ...)
from incident_lens.schemas.workflow import WorkflowOptions, termination_result
```

graph.py **只依赖**：orchestration 兄弟模块、`schemas`、`langgraph`。工具/Provider/安全类是在方法内延迟导入（如 `ToolRegistry`、`ContextAuthority` 由调用方注入，`run_investigation` 内装配）。

### 2.2 `agents/service.py`

```python
from incident_lens.agents.database import DATABASE_PROMPT
from incident_lens.llm.provider import ProviderError, json_payload
from incident_lens.schemas import (CoordinatorDecision, Finding, Hypothesis, InvestigationTask, Review, StrictModel)
from incident_lens.security.context import ROLE_TOOL_ACL
from incident_lens.tools.arguments import ARGUMENT_MODELS
```

`agents/` → `llm`、`schemas`、`security`、`tools`；**不** import 编排层。

### 2.3 `tools/evidence provider`

```python
# tools/provider.py
from incident_lens.schemas.contracts import EvidenceRecord
# 只读 data/，不依赖编排/agents/llm（安全边界）
```

### 2.4 `evaluation/runner.py`

```python
from incident_lens.agents.service import PROMPT_VERSION
from incident_lens.llm import LLMProvider, MockProvider
from incident_lens.llm.usage import aggregate_usage
from incident_lens.orchestration.graph import run_investigation
from incident_lens.schemas import Budget
from incident_lens.tools import EvidenceProvider
from .metrics import VARIANTS, aggregate, score_completed, score_without_oracle
```

`evaluation/` → 各核心包（消费侧），运行时**不**反向依赖 `evaluation`。

### 2.5 `incidentbench/experiment.py`

```python
from incident_lens.evaluation.runner import MeasuredProvider, csv_rows, usage_metrics, write_csv
from incident_lens.orchestration.graph import run_investigation
from incident_lens.schemas import Budget
from incident_lens.schemas.workflow import WorkflowOptions
from .schemas import ExperimentProtocol
from .scorer import aggregate, score_benchmark_run
```

`incidentbench/` → `evaluation`（复用 MeasuredProvider/写 CSV）+ `orchestration` + `schemas`。

### 2.6 `incidentbench/builder.py`

```python
from incident_lens.schemas import CasePublicInput, EvidenceRecord
from incident_lens.tools.provider import ANSWER_FIELDS, EvidenceProvider
from .family_split import split_ids
from .scenarios import encode, simulate
```

## 3. 禁止的反向依赖（不可违反）

| 依赖方向 | 原因 |
| --- | --- |
| `schemas` 不得 import `orchestration/agents/tools/llm/security/evaluation` | 契约层是叶子；任何循环都会破坏 `StrictModel` 初始化 |
| `llm` 不得 import `orchestration/graph` 或 `agents` | Provider 是被注入者，不持有运行时 |
| `tools` 不得 import `agents/llm/orchestration` | 工具是只读、无状态的数据访问层 |
| `security` 不得 import `tools` 实现细节（除了类型契约） | 保持独立可测 |
| 运行时不得 import `evaluation/incidentbench` | 评估只在运行结束后消费产物 |
| `web/server.py` 不读 `evaluation` oracle | `docs/contracts` 头注释"never reads evaluation truth" |

> 例外：`schemas/active_config.py` 独立于 `contracts.py`，是为了打破 `agents/policy` 与 `orchestration` 之间的潜在环，允许 CAES 严格依赖 `active_config` 作为扇出叶子。

## 4. 外部依赖清单

### 4.1 运行时依赖（`pyproject.toml` + `requirements.lock`）

| 包 | 版本 | 用途 |
| --- | --- | --- |
| `langgraph` | 1.2.14 | StateGraph 编排 |
| `pydantic` | 2.14.0 | StrictModel 契约 |
| `PyYAML` | 6.0.3 | 配置解析 |
| `httpx` | 0.28.1 | OpenAI 兼容 HTTP 调用 |
| `python-dotenv` | 1.2.4 | `.env` 加载 |
| `numpy` | 2.2.6 | 指标 CSV / 统计 |
| `pandas` | 3.0.6 | 评估 CSV 读写（`requirements.lock` 传递） |
| `streamlit` | 1.65.0 | 可选仪表盘（`ui/`） |
| `starlette` | 1.7.0 | Web API |
| `uvicorn` | 0.54.0 | Web 服务器 |

`requirements.lock` 还固定了 langgraph 的传递依赖（`langchain-core==1.6.9`、`langgraph-checkpoint==4.2.0`、`langgraph-sdk==0.4.6`、`langsmith==0.14.7` 等），CI 以 lock 为准。

### 4.2 开发/测试依赖

`pytest==9.1.1`、`pytest-asyncio==1.4.0`、`ruff==0.17.0`；前端 `playwright==1.56.1`（Node 侧）。

### 4.3 可选运行依赖

`SentenceTransformerBackend`（semantic 缓存）在首次需要时懒加载，不在基础 dependencies。

### 4.4 外部服务

| 服务 | 用途 | 触发方式 |
| --- | --- | --- |
| OpenAI 兼容 LLM endpoint | 真实推理 | `--provider real` + `INCIDENT_LENS_*` |
| 本机 `codex` CLI | Codex 订阅 | `CodexSubscriptionProvider` |
| （无数据库/Redis 依赖） | — | 全部只读都是本地文件 |

## 5. 文件与数据依赖

### 5.1 输入

- `data/splits/{seed,dev,test,database}_ids.json` → 评估浮标（6 / 10 / 20 / 4，共 40 个案例）；
- `data/incidents/incident_XXX/public/*`（6 个文件）→ 运行只读事实；
- `data/topology/services.yaml` → 服务目录（`EvidenceProvider` 唯一允许的 yaml 路径）；由数据生成脚本产出；
- `data/monitoring/{normal,anomaly}.json` → 监控 profile 的快照样本；
- `data/dataset_manifest.json` → 生成器版本、计数与已知局限；
- `data/incidentbench_v1/{public_case_index.json, rca/**, splits/**, manifest.json, coverage.json}` → IncidentBench 公开包；
- `data/incidentbench_v16_dev/` → v1.6 开发用公开包；
- `<oracle_root>/oracle/incident_XXX.json` → 评测私有标签（运行时不可见）。

### 5.2 输出

- 单次运行：`results/<run_id>/{trace.json, result.json, report.md}`；
- 评测：`<out>/{raw-runs.jsonl, case-level.csv, aggregate.csv, error-analysis.md, ...}`；
- 契约：`docs/contracts/*.json`（`export-schemas`）；
- IncidentBench：`out/{raw-state.jsonl, runs.csv, aggregated.csv, ...}` + `.execution.lock`。

### 5.3 缓存

- CLI：`results/cache.sqlite`（`--cache-db`）；
- Web/Streamlit：`results/ui-cache.sqlite`；
- 内容：`cache_entries` 表的命名空间/响应/哈希。

### 5.4 测试数据

- `tests/reliability/` 用 `git show` 冻结 provider fixture（CI 需要 `fetch-depth: 0`）；
- `tests/web/fixtures/*.json` 由 `tests/web/generate_fixtures.py` 生成。

## 6. 关键调用链（运行时）

```text
run_investigation(incident_id, provider, data_root, budget, variant, cache, workflow)
  → InvestigationRun(...).compile()
  → langgraph.StateGraph.invoke(await) 
      每个节点 → agents.<role>.*(provider, payload, model, schema)
                  → provider.structured_call → (provider recovery/repair)
                  → registry.execute(context, tool, args)
                       → EvidenceProvider(只读 data/)
                  → merge_results → guards.<gate>
                  → observability.emit_event
  → 返回到 STOP → report → state
  → save_run(state, out) → 三产物
```

## 7. 依赖目录汇总（原文速查）

| 目标 | 由谁 import |
| --- | --- |
| `langgraph` | 仅 `orchestration/graph.py` |
| `incident_lens.schemas` | 几乎全部模块（唯一跨层共享叶子） |
| `incident_lens.orchestration.graph` | `evaluation/runner.py`, `incidentbench/experiment.py`, `artifacts?`(间接), `web`, `cli`, `ui` |
| `incident_lens.tools.provider.EvidenceProvider` | `evaluation/runner.py`, `incidentbench/builder.py`, `web`, `cli`, `ui` |
| `incident_lens.artifacts.{save_run,load_replay}` | `cli`, `web`, `ui`, `evaluation` 测试 |
| `incident_lens.evaluation.runner` | 仅 `incidentbench/experiment.py` 与评估脚本 |
| `incident_lens.web.server` | 仅 `web/__main__.py` 与浏览器测试 |