# 09 · 接口层：CLI、Web、Streamlit 与产物

## 1. 命令行（`incident-lens`）

入口：[`cli.py`](../../src/incident_lens/cli.py)，`pyproject.toml` 注册 `incident-lens = "incident_lens.cli:main"`。

### 1.1 子命令总览

| 子命令 | 作用 | 退出码 |
| --- | --- | --- |
| `check-environment` | 打印 `incident-lens` / `langgraph` / `pydantic` / `streamlit` 版本 | 0 |
| `list-cases` | 列出 `data/` 下公开案例（id、标题、开始时间） | 0 |
| `validate-data` | 校验公开数据：JSON 可解析、必填字段、无私有字段 | 0 通过 / 1 失败 |
| `run` | 运行一次调查并保存产物 | 0 / 2（配置或 Provider 错误） |
| `replay` | 离线重放已保存 trace，不调用模型/工具 | 0 |
| `web` | 启动 Starlette + SPA 仪表盘 | 0 |
| `export-schemas` | 导出 21 个契约 JSON Schema 到 `docs/contracts/` | 0 |

### 1.2 `run` 参数

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--case` | 必填 | 事故 ID（`incident_xxx`） |
| `--provider` | `mock` | `mock` / `real` |
| `--variant` | `full` | `full` / `single` / `fixed` / `dynamic_no_verifier` |
| `--out` | 必填 | 必须是**全新或空**目录 |
| `--data-root` | `data` | 公开数据根 |
| `--config` | `configs/system.yaml` | 系统配置 |
| `--cache-mode` | 配置/`CACHE_MODE`/`off` | `off` / `exact` / `semantic` |
| `--cache-db` | `results/cache.sqlite` | SQLite 路径 |
| `--max-rounds` | 4 | 覆盖配置 |
| `--max-tool-calls` | 12 | 覆盖配置 |
| `--max-llm-calls` | 16 | 覆盖配置 |
| `--max-seconds` | 600 | 覆盖配置 |
| `--max-tokens` | 配置/无 | 覆盖配置 |
| `--response-format` | `json_schema` | `json_schema` / `json_object` |
| `--thinking` | 环境变量/无 | `enabled` / `disabled` |
| `--request-timeout` | 180 | 秒 |
| `--profile` | 配置/`legacy_rca` | `legacy_rca` / `incident_response` |
| `--selection-policy` | 配置 | `current_dynamic` / `active_evidence` / `active_no_cost` / `active_no_discrimination` / `first_eligible` |
| `--shadow-caes` | False | 只记录不生效 |
| `--monitor-mode` | `legacy` | `legacy` / `manual_snapshot` / `offline_replay` |
| `--snapshot` | 无 | JSON 文件，公开 `EvidenceRecord` 列表 |

`run` 的行为：

1. `load_dotenv()` 读取 `.env`；
2. 拒绝符号链接或非空输出目录；
3. 读 YAML 配置，CLI 参数优先；
4. 构造 `Budget`；
5. `mock` → `MockProvider`；`real` → `RealChatProvider`（读 `INCIDENT_LENS_BASE_URL` / `_API_KEY` / `_MODEL`）；
6. `cache_mode != off` → `SemanticCacheAdapter`；
7. `workflow_options(...)` 合并 profile / monitor mode / snapshot / CAES；
8. `asyncio.run(run_investigation(...))`；
9. `save_run(...)` 写三个产物；
10. 打印状态、run_id、工具/LLM 调用数、产物路径。

### 1.3 退出码与错误

- `ProviderError` → 打印 `exc.code` 到 stderr，返回 2；
- `ValueError` / `OSError`（配置、数据、trace）→ 打印类型名与固定文案，返回 2（不回显敏感细节）。

## 2. 产物（[`artifacts.py`](../../src/incident_lens/artifacts.py)）

### 2.1 `save_run`

写出三个文件（`open("x")` 独占创建，已存在即失败）：

| 文件 | 内容 |
| --- | --- |
| `trace.json` | 信封：`schema_version=v1`、provider、variant、cache_mode、elapsed_ms、model_id、prompt_version、完整 state |
| `result.json` | `RCAReport` 的 JSON |
| `report.md` | `render_report(report)` 生成的 Markdown |

保存前执行：

1. `InvestigationState.model_validate_json(state.model_dump_json())` 全量重校验；
2. `report is not None`；
3. `validate_metadata` 校验信封字段白名单、provider/variant/cache_mode 枚举。

### 2.2 `load_replay`

```text
1. 读取 JSON（utf-8-sig）
2. validate_metadata：schema_version=v1，字段只允许白名单
3. reject_private_fields：递归拒绝 ground_truth / is_identifiable / true_primary_root 等评测字段
4. InvestigationState.model_validate_json：触发 consistent_provenance
5. report 必须存在
6. validate_replay_observations：
   - 每个 TOOL_CALL 事件必须通过角色 ACL
   - ToolResult 必须可解析
   - 记录的 incident_id / service / source_type 与工具匹配
   - 同一 evidence_id 的内容不得变化
   - evidence_index ⊆ observed
```

注意：这是**内部一致性**校验，不是加密签名；被手工篡改且内部自洽的 trace 无法被检测出"真实性"，但伪造跨角色/跨数据源证据会被拒绝。

## 3. Web 服务（`incident-lens web`）

实现：[`web/server.py`](../../src/incident_lens/web/server.py)，启动：[`web/__main__.py`](../../src/incident_lens/web/__main__.py)，默认 `127.0.0.1:8022`（uvicorn）。

### 3.1 路由

| 方法 | 路径 | 请求 | 响应 |
| --- | --- | --- | --- |
| GET | `/api/health` | — | `{ok: true}` |
| GET | `/api/meta` | — | 预算默认值、ACL、Provider 默认设置 |
| GET | `/api/cases` | — | 公开案例列表 |
| POST | `/api/run` | `RunRequest` | `{trace, report_md, path, recorded: false}` |
| GET | `/api/traces` | — | 已保存 trace 摘要（按修改时间倒序） |
| POST | `/api/replay` | `{path}` | `{trace, report_md, path, recorded: true, replay_metadata}` |
| GET | `/api/download` | `?path&kind=trace\|report` | 文件下载 |
| GET | `/` | — | `web/static/` 静态 SPA |

### 3.2 `RunRequest`

```python
incident_id: ^incident_[0-9]{3,}$
provider: "mock" | "real" = "mock"
cache_mode: "off" | "exact" | "semantic" = "off"
response_format: "json_schema" | "json_object" | None
thinking: "enabled" | "disabled" | None
timeout: float >= 1.0 | None
workflow: WorkflowOptions = default
```

行为：

- `incident_response` profile 自动使用 `Budget(max_llm_calls=24, max_tool_calls=24, max_rounds=6)`；
- 运行后保存到 `results/ui/<run_id>/`；
- `ProviderError` → HTTP 502 + `{error:{code,message}}`；配置/数据错误 → 500；
- 错误消息不包含文件路径、密钥或原始 provider 响应。

### 3.3 路径安全

- `_resolve_trace_path`：必须 `resolve()` 后在 `results/` 内，且 basename 必须是 `trace.json`；
- `_resolve_download_file`：逐级 `lstat` 拒绝 symlink / Windows reparse point，最终必须仍在 `results/`；
- `_replay_metadata`：只读取固定名 `scope.json` / `result.json` / `verification.json`，每个限制 2MB 且必须是 dict；`result.json` 必须与当前报告逐字节等价才展示 verification；不跟随 trace 内的任意路径；
- 下载内容**从内存重新生成**，不直接发送磁盘上的 `report.md`（防止旁路篡改）。

### 3.4 SPA 结构

| 文件 | 职责 |
| --- | --- |
| `static/index.html` | 侧边导航、主区、drawer、toast 骨架 |
| `static/js/app.js` | hash 路由（`#/`、`#/investigate`、`#/run`、`#/library`）、主题、侧栏、meta 刷新 |
| `static/js/api.js` | `api()` fetch 封装、`ApiError`、时间/时长格式化、状态与角色标签 |
| `static/js/views.js` | 四个页面：总览、新建调查、运行详情、痕迹档案库 |
| `static/js/components.js` | badge、空状态、骨架屏、toast、drawer、证据 chip、报告渲染 |
| `static/js/replay.js` | 纯函数 replay reducer：按事件前缀重演状态、书签、可靠性视图 |
| `static/js/replay-panels.js` | replay 面板 HTML：元数据、工作流、历史、审查时间线、可靠性 |

关键点：

- 前端 replay 是**纯函数**，只消费 trace 中的事件，不请求后端重新计算；
- `replayReducer` 校验事件的工具/证据来源一致性，前端也能发现伪造事件；
- Mock 与 Recorded Replay 在 UI 中显式标注，避免误读为真实模型结果。

## 4. Streamlit（可选）

[`ui/app.py`](../../src/incident_lens/ui/app.py)：

- 左侧选择案例、Provider、variant、profile、预算、cache；
- 运行后 `render_state(trace, state)`：
  - 5 个 KPI（outcome、轮次、工具调用/上限、模型请求/上限、缓存命中数）；
  - 时间线（按角色过滤，`DECISION` / `REVIEW` 默认展开，`LLM_CALL` 隐藏）；
  - 假设板（状态、服务、失败模式、支持/反对证据）；
  - 角色与工具权限表；
  - 观测证据注册表；
  - 根因报告、监控告警、任务尝试、终止结果；
- 也支持加载已保存 trace 并标记 `recorded=True`；
- 运行产物写入 `results/ui/<run_id>/`。

启动：

```bash
python -m streamlit run src/incident_lens/ui/app.py
```

Streamlit 是旧界面，功能与 Web SPA 重叠但更简洁，适合本地调试。

## 5. 产物目录约定

```text
results/
├── cache.sqlite                 # CLI 语义缓存
├── ui-cache.sqlite              # Web/Streamlit 语义缓存
├── ui/<run_id>/{trace.json,result.json,report.md}
└── <自定义输出>/{trace.json,result.json,report.md}
```

`/api/traces` 递归扫描 `results/**/trace.json`，因此任何 CLI 输出只要放在 `results/` 下都会出现在档案库中。

## 6. 环境变量

| 变量 | 作用 |
| --- | --- |
| `INCIDENT_LENS_BASE_URL` | OpenAI 兼容 endpoint |
| `INCIDENT_LENS_API_KEY` | API key |
| `INCIDENT_LENS_MODEL` | 模型名 |
| `INCIDENT_LENS_RESPONSE_FORMAT` | `json_schema` / `json_object` |
| `INCIDENT_LENS_THINKING` | `enabled` / `disabled` |
| `INCIDENT_LENS_REQUEST_TIMEOUT` | 请求超时秒数（默认 180） |
| `CACHE_MODE` | `off` / `exact` / `semantic` |
| `CACHE_DB_PATH` | 缓存 SQLite 路径 |
| `CACHE_SIMILARITY_THRESHOLD` | 默认 0.95 |
| `CACHE_TTL_HOURS` | 默认 24 |
| `CACHE_EMBEDDING_MODEL` | `fake` 或 SentenceTransformer 模型名 |

`.env` 由 `python-dotenv` 在 CLI 与 Web 启动时加载，不会写入 trace。
