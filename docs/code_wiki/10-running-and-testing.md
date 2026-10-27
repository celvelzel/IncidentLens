# 10 · 运行、配置与测试

## 1. 环境要求

| 项 | 要求 |
| --- | --- |
| Python | `>=3.11`（CI 使用 3.13） |
| Node.js | 仅前端/浏览器测试需要（CI 使用 22） |
| 模型访问 | 可选；Mock 模式完全离线 |
| 操作系统 | macOS / Linux / Windows（CI 覆盖 ubuntu 与 windows） |

## 2. 安装

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

python -m pip install -r requirements.lock
python -m pip install -e '.[dev]'
```

- `requirements.lock`：完整冻结依赖（CI 使用）；
- `.[dev]`：`pytest`、`pytest-asyncio`、`ruff`；
- 运行时依赖全部固定版本：`langgraph==1.2.14`、`pydantic==2.14.0`、`httpx==0.28.1`、`streamlit==1.65.0`、`starlette==1.7.0`、`uvicorn==0.54.0`、`numpy==2.2.6`、`PyYAML==6.0.3`、`python-dotenv==1.2.4`。

验证安装：

```bash
incident-lens check-environment
# 或
python scripts/verify_install.py
```

## 3. 首次运行（Mock，无需密钥）

```bash
incident-lens validate-data
incident-lens list-cases
incident-lens run --case incident_001 --provider mock --cache-mode off --out results/demo001
incident-lens replay --trace results/demo001/trace.json
incident-lens web            # http://127.0.0.1:8022
```

产物：

```
results/demo001/
├── trace.json
├── result.json
└── report.md
```

## 4. 接入真实模型

创建 `.env`（参考 `.env.example`）：

```bash
INCIDENT_LENS_BASE_URL=https://your-endpoint/v1
INCIDENT_LENS_API_KEY=sk-...
INCIDENT_LENS_MODEL=your-model
INCIDENT_LENS_RESPONSE_FORMAT=json_schema
INCIDENT_LENS_REQUEST_TIMEOUT=180
# INCIDENT_LENS_THINKING=enabled
```

运行：

```bash
incident-lens run --case incident_001 --provider real \
  --variant full --profile legacy_rca \
  --max-rounds 4 --max-tool-calls 12 --max-llm-calls 16 --max-seconds 600 \
  --out results/real001
```

注意：

- **不会自动回退 Mock**。缺少配置会直接返回 `PROVIDER_CONFIGURATION_REQUIRED`（退出码 2）。
- 若模型不支持 `json_schema`，改用 `--response-format json_object`，并把 `provider_recovery.format_capability` 设为 `json_object`。
- Codex 订阅可通过 `scripts/probe_codex_subscription.py` 与本机 `codex` CLI 验证，见 `llm/codex_subscription.py`。

## 5. 配置项（`configs/`）

### 5.1 `system.yaml`（默认）

```yaml
max_rounds: 4
tool_calls_limit: 12
llm_calls_limit: 16
time_limit_seconds: 600
structured_repair_retries: 1
cache_mode: "off"

provider_recovery:            # 显式 opt-in，默认关闭
  enabled: false
  max_transport_retries: 2
  max_structured_repairs: 1
  max_physical_attempts_per_call: 4
  initial_backoff_seconds: 0.5
  max_backoff_seconds: 4.0
  jitter_mode: none
  reserve_verifier_requests: 0
  min_request_time_seconds: 5.0
  format_capability: json_object
```

CLI 优先级：**命令行参数 > 环境变量 > YAML > 代码默认值**。

### 5.2 `incident-response.yaml`

```yaml
max_rounds: 6
tool_calls_limit: 24
llm_calls_limit: 24
time_limit_seconds: 600
structured_repair_retries: 1
cache_mode: "off"

workflow:
  profile: incident_response
communication:
  mode: centralized
monitor:
  enabled: false          # 需要手动快照/回放时再开启
  mode: legacy
  max_calls: 8
database_agent:
  enabled: true
remediation:
  enabled: true
  execution_mode: plan_only
  max_calls: 2
task_runtime:
  max_attempts: 2
  continue_on_partial_failure: true
stop:
  enabled: true
  ack_timeout_seconds: 5.0

provider_recovery:
  enabled: false
```

### 5.3 `agents.yaml`

**角色 → 工具白名单** 的配置镜像（与 `security/context.py` 的 `ROLE_TOOL_ACL` 对应），不是模型参数：

```yaml
coordinator: []
logs: [query_logs]
metrics: [query_metrics, get_dependencies]
changes: [query_changes, get_config_diff]
database: [get_db_connections, get_db_active_sessions, get_db_lock_waits,
           get_db_slow_queries, get_db_health_metrics]
monitoring: []
remediation: []
verifier: [fetch_evidence_by_ids]
reporter: [fetch_evidence_by_ids]
```

### 5.4 `model.yaml`

项目级模型默认值（不含密钥）：

```yaml
provider: mock
model: null
temperature: 0
prompt_version: roles-v6
output_schema_version: schema-v1
```

### 5.5 `active-investigation.example.yaml`

CAES 配置示例：策略名、候选池大小、权重、阈值、影子模式。复制为实际配置后通过 `--selection-policy` / `--shadow-caes` 启用。

### 5.6 `incidentbench-protocol.yaml`

IncidentBench 实验协议：4 个等价工具条件、budget、repeats、jobs、blindness、analysis plan、formal 门禁。

## 6. 测试

### 6.1 全量

```bash
python -m pytest -ra
```

`pyproject.toml`：`testpaths=["tests"]`、`asyncio_mode="auto"`。

### 6.2 离线保证

```bash
INCIDENT_LENS_OFFLINE_TESTS=1 PYTHON_DOTENV_DISABLED=1 python -m pytest -ra
```

`tests/conftest.py` 的 `offline_network_guard` 会把任何非 `127.0.0.1` / `::1` / `localhost` 的 `socket.connect` 直接抛错。CI 默认开启。

### 6.3 分层

| 层 | 目录 | 关注点 |
| --- | --- | --- |
| 单元 | `tests/unit/` | 模型校验、工具参数、预算、缓存、Guard |
| 集成 | `tests/integration/` | 端到端图、CLI、Web、并发、STOP、恢复、产物边界 |
| 评估 | `tests/evaluation/` | 指标、终止协议、可靠性、聚合 |
| 基准 | `tests/incidentbench/` | 构建、校验、打分、统计、实验锁 |
| CAES | `tests/active_investigation/` | 候选、特征、策略、影子模式 |
| 隔离 | `tests/isolation/` | 路径逃逸、私有数据泄漏 |
| 可靠性 | `tests/reliability/` | 真实 Provider fixture 与账本 |
| 前端 | `tests/web/` | JS 单测 + Playwright 浏览器验收 |

### 6.4 前端测试

```bash
npm ci
npx playwright install --with-deps chromium
npm test                 # node --test tests/web/*.test.mjs
npm run test:browser     # Playwright 浏览器验收
```

`scripts/run_mock_browser.py` 会自动启动本地 Web、运行浏览器验收、再关闭服务，并清理所有 `INCIDENT_LENS_*` 环境变量，确保不会意外访问真实模型。

### 6.5 Lint

```bash
python -m ruff check src tests scripts
```

规则：`E4, E7, E9, F, I`，行长 100，目标 Python 3.11。

## 7. CI（`.github/workflows/ci.yml`）

| Job | 内容 |
| --- | --- |
| `ruff` | Ubuntu + Python 3.13，`pip install ruff==0.17.0`，`ruff check src tests scripts` |
| `python` | Ubuntu + Windows 矩阵，`fetch-depth: 0`（可靠性 fixture 用 `git show`），安装 `requirements.lock` + `.[dev]`，`pytest -ra --junitxml=results/ci/pytest.xml`，上传 JUnit artifact |
| `javascript-browser` | Ubuntu + Node 22 + Playwright Chromium，`npm ci`、`npm test`、`scripts/run_mock_browser.py`，上传 `results/ci/browser/` |

CI 全局环境：

```yaml
PYTHONUTF8: '1'
PYTHON_DOTENV_DISABLED: '1'
INCIDENT_LENS_OFFLINE_TESTS: '1'
```

## 8. 常用脚本

| 脚本 | 用途 |
| --- | --- |
| `scripts/verify_install.py` | 安装自检 |
| `scripts/validate_dataset.py` | 校验 `data/` 公开案例 |
| `scripts/verify_stop_protocol.py` | 校验 STOP/终止协议 |
| `scripts/run_eval.py` / `analyze_eval.py` | 消融评估与聚合 |
| `scripts/run_incidentbench.py` / `analyze_incidentbench.py` | IncidentBench |
| `scripts/build_incidentbench.py` / `validate_incidentbench.py` / `seal_incidentbench.py` | 数据集生成/校验/冻结 |
| `scripts/run_reliability_eval.py` | 可靠性评估 |
| `scripts/run_cache_eval.py` | 缓存收益评估 |
| `scripts/run_v15_active_eval.py` / `analyze_v15_active.py` | CAES 实验 |
| `scripts/run_status.py` | 运行状态汇总 |
| `scripts/run_mock_browser.py` | 浏览器验收 |

## 9. 故障排查

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `PROVIDER_CONFIGURATION_REQUIRED` | 缺少 `INCIDENT_LENS_BASE_URL/API_KEY/MODEL` | 配置 `.env`；不要期望自动 Mock |
| `Use a fresh output directory` | 输出目录非空或为符号链接 | 换新目录 |
| `Run artifacts already exist` | 目标目录已有产物 | 换新目录，不要覆盖 |
| `Trace has no completed report` | trace 来自未完成运行 | 重新运行 |
| `Replay observation has foreign evidence` | trace 被篡改或数据版本不一致 | 用原始数据重跑 |
| `Evaluator-only fields cannot enter replay` | trace 混入 oracle 字段 | 从公开数据重新生成 |
| `policy violation` / `FORBIDDEN` | 角色越权或未共享证据 | 检查 `ROLE_TOOL_ACL` 与 Merge |
| `Stop acknowledgement timeout` | ACK 超时 | 提高 `ack_timeout_seconds`；检查取消逻辑 |
| `Budget exhausted` | 轮次/工具/LLM/wall/token 超限 | 提高对应上限或减少任务 |
| 缓存始终 miss | 命名空间变化（模型/提示词/证据/ACL） | 查看 `cache_namespace_digest` |
| Windows 下输出乱码 | 控制台编码 | 设置 `PYTHONUTF8=1` |

## 10. 数据校验与扩展示例

新增一个公开案例：

1. 在 `data/incidents/incident_XXX/public/` 放 `incident.json`、`logs.jsonl`、`metrics.csv`、`changes.jsonl`、`configs.jsonl`、`database.jsonl`；
2. 需要 oracle 时放 `data/incidents/incident_XXX/private/oracle.json`（仅评测使用，绝不进入运行）；
3. 运行 `incident-lens validate-data`；
4. 把 ID 加入 `data/splits/*.json`（如需参与评估）；
5. 运行 Mock 验证全链路。

新增 IncidentBench 案例请用 `incidentbench/scenarios/world.py` 的世界模型生成，避免手写证据导致不一致。
