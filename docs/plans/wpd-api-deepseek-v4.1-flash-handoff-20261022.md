# WPD API 模型切换交接：DeepSeek V4.1 Flash 1017

日期：2026-10-22  
状态：仅完成工作树与模型配置准备。未安装依赖、未创建 `.env`、未获取 readiness、未 prepare、未 execute、未发出任何模型请求。本文不宣称模型兼容性或正式测试已通过。

## 1. 工作树与基准

- 原目录（未改动）：`C:\Develop\python_projects\COMP5584_Agents\IncidentLens`，分支 `main`，HEAD `abb1b887581c5c0e542db0a2d24da66c5ee3d795`。
- 新工作树：`C:\Users\RickyMa\.trae-cn\worktrees\IncidentLens\feat-switch-deepseek-NMdFdU`。
- 新工作树分支：`feat-switch-deepseek-NMdFdU`，基准提交同为 `abb1b887581c5c0e542db0a2d24da66c5ee3d795`（`feat(wp-d): integrate concurrent ChatGPT subscription batches`，2026-10-22 09:17:39 +0800）。
- 工作树已在 Git 中独立注册；`git worktree list` 仅包含原 `main` 工作树和本工作树。
- 本任务未提交、未推送、未切换原目录分支，也未操作正在运行的桥接批次。

## 2. 从原目录迁入与核对

- 任务开始时原目录 `git status --porcelain` 为空：没有已跟踪修改、删除，也没有非忽略的未跟踪源码、测试或配置。因此无需复制补丁；新工作树直接从同一 HEAD 检出即可。
- 八并发实现已在 HEAD 提交中，不是未提交改动：
  - `scripts/run_wpd_batch.py` 的 `CONCURRENCY_LIMITS` 为 `{"bridge": 4, "api": 8, "subscription": 8}`；
  - `src/incident_lens/incidentbench/schemas.py` 注明桥接上限 4、API/订阅上限 8。
- 迁移前对以下关键文件比较了原目录、工作树与 `HEAD` 的 Git blob SHA256，内容一致：
  `scripts/run_wpd_batch.py`、`src/incident_lens/incidentbench/schemas.py`、`configs/wp_d/api-protocol.json`、`configs/wp_d/api-runtime.yaml`、`configs/wp_d/api-plan.json`、`configs/wp_d/bridge-protocol.json`、`configs/wp_d/bridge-plan.json`、`configs/wp_d/bridge-runtime.yaml`、`tests/integration/test_wpd_parallel_batch.py`。
- 未复制 `.env`、`.venv`、旧 `results`、缓存、`local_oracles`、密钥或私有数据。新工作树当前没有 `.env` 和 `.venv`，需要按第 4 节单独准备。
- 保留未改：桥接模型 `trae-subagent-bridge-v1`、桥接/API 的 `jobs=1`、预算、提示、评估规则、桥接与 API 的 runtime 恢复参数。

## 3. API 模型配置修改与来源确认

实际参与 WPD API 执行的模型来源有两处，必须同时匹配：

| 来源 | 是否参与 | 说明 |
|---|---|---|
| `configs/wp_d/api-protocol.json` | 是 | `model_id` 进入冻结协议；预算、`response_format`、`jobs` 也来自此处。 |
| `configs/wp_d/api-runtime.yaml` | 是（无模型字段） | 提供 `thinking: disabled`、结构修复和重试恢复参数；本次未改。 |
| 工作树 `.env` / 进程环境 | 是 | `INCIDENT_LENS_MODEL` 必须等于协议 `model_id`，否则 prepare/execute 直接拒绝；`BASE_URL`、`API_KEY` 为必需凭据。 |
| `config.json` | 否 | 仓库中没有该文件，当前 WPD API 路径也不读取它；仅 `tests/integration/test_codex_subscription_feasibility.py` 把它当作临时订阅配置文件。 |
| `configs/wp_d/api-plan.json` | 间接 | 只引用协议、runtime 和数据路径，不含模型字段。 |
| `configs/wp_d/api-readiness.example.json` | 否（模板） | 不是 readiness 记录，只作字段示例。 |

本次在新工作树中的修改：

- `configs/wp_d/api-protocol.json`
  - `model_id`：`deepseek-v4-flash-0731` → `deepseek-v4.1-flash-1017`
  - `protocol_id`：`incidentbench-wpd-api-prepared-20261021` → `incidentbench-wpd-api-deepseek-v4.1-flash-1017-20261022`
  - 其余字段均未变：`jobs=1`、8 轮、40 工具、64 请求、7200 秒 wall、1200 秒请求等待、temperature 0、cache off、`json_schema`、四个变体、种子与评估计划。
- `configs/wp_d/api-readiness.example.json`
  - `model_id` 同步为 `deepseek-v4.1-flash-1017`。
  - 仍保留 `provider_compatible: false` 与 `TEMPLATE_ONLY_NOT_READINESS`；它不是本轮 readiness，也不得当作 readiness 使用。

尚待确认（本轮未验证）：

- 服务商当前是否接受 `deepseek-v4.1-flash-1017` 这个精确标识。
- 该模型在 `json_schema`、`temperature=0`、`thinking=disabled` 下的真实行为。
- 真实 readiness 的 `model_id`、`response_format`、`thinking` 必须分别匹配新协议、`json_schema`、`disabled`。
- `jobs` 上限虽为 8，但当前协议仍为 `jobs=1`；若后续要提高并发，需要另改协议并重新准备新批次，不能沿用旧 manifest。

## 4. 独立环境与凭据配置

以下命令仅记录，本轮未执行。必须在新工作树根目录运行：

```powershell
Set-Location -LiteralPath 'C:\Users\RickyMa\.trae-cn\worktrees\IncidentLens\feat-switch-deepseek-NMdFdU'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

凭据只写到新工作树自己的 `.env`，不要复制或提交原目录 `.env`：

- 路径：`C:\Users\RickyMa\.trae-cn\worktrees\IncidentLens\feat-switch-deepseek-NMdFdU\.env`（已被 `.gitignore` 忽略）。
- 必需变量：
  - `INCIDENT_LENS_BASE_URL=<服务商端点>`；
  - `INCIDENT_LENS_API_KEY=<密钥，仅在本地填写>`；
  - `INCIDENT_LENS_MODEL=deepseek-v4.1-flash-1017`。
- 可选/记录用变量：
  - `INCIDENT_LENS_THINKING=disabled`（批次子进程实际使用 `api-runtime.yaml` 的 `thinking`；该变量会被写入批次外部元数据）；
  - `INCIDENT_LENS_RESPONSE_FORMAT=json_schema`（批次子进程实际使用协议中的 `response_format`）。

注意：`run_wpd_batch.py` 和 `retest_live_provider_fix.py` 都以 `override=False` 加载 `.env`，已有 shell 环境变量优先。启动前确认当前终端没有残留旧的 `INCIDENT_LENS_MODEL` 值。任何输出、日志或交接内容都不得包含密钥。

## 5. Readiness 要求

本轮没有创建 readiness 探测，也没有可用的新模型记录。执行前必须由真实探测生成新记录，字段至少满足：

```json
{
  "model_id": "deepseek-v4.1-flash-1017",
  "response_format": "json_schema",
  "thinking": "disabled",
  "provider_compatible": true
}
```

- `provider_compatible: true` 只能来自实际观察，不得沿用旧模型记录、不得用示例文件冒充、不得手写为 true。
- 建议的新记录位置：`results\acceptance\wpd-api-readiness-deepseek-v4.1-flash-1017-20261022\readiness.json`。
- prepare 会校验该记录与协议及 `api-runtime.yaml` 一致，并把其 SHA256 写入批次 manifest；执行期间该文件必须保持不变。

## 6. 新批次目录与 prepare/execute 模板

以下命令均在新工作树执行，本轮不运行。输出目录必须唯一且此前不存在（`--prepare` 要求新建目录）。

```powershell
Set-Location -LiteralPath 'C:\Users\RickyMa\.trae-cn\worktrees\IncidentLens\feat-switch-deepseek-NMdFdU'
$env:PYTHONPATH = Join-Path $PWD 'src'
$P = Join-Path $PWD '.venv\Scripts\python.exe'
$R = Join-Path $PWD 'results\acceptance\wpd-api-readiness-deepseek-v4.1-flash-1017-20261022\readiness.json'
$Out = Join-Path $PWD 'results\v16\wp-d\api-deepseek-v4.1-flash-1017-dev10-20261022-01'

# 仅冻结输入，不构造 provider、不发模型请求
& $P -B scripts/run_wpd_batch.py --plan configs/wp_d/api-plan.json --out $Out --readiness $R --prepare

# 真实调用，必须在 readiness、环境和离线检查确认后单独授权执行
& $P -B scripts/run_wpd_batch.py --plan configs/wp_d/api-plan.json --out $Out --readiness $R --execute
```

执行前按既有计划先完成离线回归及 full 正例/负例严格 G1a 检查；本轮未运行这些检查。批次启动后可用以下命令只读查看状态，恢复时在 `--execute` 后追加 `--resume`，中断/失败重试分别追加 `--retry-interrupted` / `--retry-failed`：

```powershell
& $P -B scripts/run_status.py $Out
```

## 7. 运行期间冻结要求

- 批次运行期间不得修改源码、`configs/wp_d/*`、提示词、公共数据、`requirements.lock`、readiness 记录或 `.env` 中的模型/端点配置。`run_wpd_batch.py` 会在每次派发前重新冻结输入；检测到漂移会拒绝启动后续槽位。
- 更换模型、response format、thinking 或预算，必须新建协议/配置、重新获取匹配 readiness，并使用新的输出目录；不要对旧批次使用 `--resume`。
- 所有操作显式 `Set-Location` 到新工作树；不要在原目录运行本交接中的命令，以免影响正在运行的桥接批次。

## 8. 剩余事项

1. 在新工作树创建并安装独立 `.venv`。
2. 由负责人本地创建 `.env`，填入端点、密钥和 `INCIDENT_LENS_MODEL=deepseek-v4.1-flash-1017`。
3. 对 `deepseek-v4.1-flash-1017` 执行真实兼容性探测，生成匹配的新 readiness。
4. 运行离线回归及必要的严格 G1a 检查。
5. 经单独授权后执行第 6 节的 `--prepare`，确认 manifest 后再 `--execute`。
