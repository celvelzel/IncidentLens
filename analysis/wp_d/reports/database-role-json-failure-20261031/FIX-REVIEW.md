# 修复复核：commit `1e22200`（只读审查）

复核时间：2026-10-31 18:10（Asia/Shanghai）。只读：未修改 `src/`、`tests/`、`configs/`、`docs/`；只跑了离线测试与两次真实网关重放。

## 结论

**根因已修复，可以认为修复完成。** 分析阶段的提示词不再命令模型调用工具，执行权限也不再出现在分析请求里；同一失败调用的离线重放已从"两次都输出 DSML"变为"一次返回合法 `AnalysisOutput`"。线上 `full40` 批次（commit 之后启动，`prompt_version=roles-v16-analysis-phase-20261031`）中 database 角色 66 次分析调用只有 1 次 `INVALID_JSON`，且该次修复后成功。

仍有 3 个**未覆盖的边角**（不影响主结论，见文末）。

## 一、改动内容（commit `1e22200`，已推送 origin/main）

`src/incident_lens/agents/service.py`
- 新增 `ANALYSIS_PHASE_PROMPT`（第 69 行）：明确"工具已由 runtime 执行完毕、本次请求没有可调用工具、只返回一个 `AnalysisOutput`、后续检查写进 `requested_checks`"。
- 新增 `ANALYSIS_ROLE_PROMPTS`（第 79 行）：按角色给**纯分析判据**，database 版保留"连接数 vs 上限、池容量 vs 数据库容量、锁/慢查询需实测、超时单独不足、健康容量不排除上游池故障"，**不含任何 `get_db_*` 或"Inspect … with"祈使句**。
- `analyze()`（第 494 行起）改为 `SYSTEM_PROMPT + ANALYSIS_PHASE_PROMPT + 角色分析判据`；`context` 只保留 `workspace_id/incident_id/run_id/role`（第 498 行），**移除 `allowed_tools`、`allowed_evidence_scope`、`remaining_tool_calls`**；payload 增加 `phase="analysis"`。
- `PROMPT_VERSION` 升到 `roles-v16-analysis-phase-20261031`，语义缓存键随之隔离。

`src/incident_lens/llm/structured_output.py`
- 第 147 行：非 JSON 内容**开头**匹配 `<｜|DSML｜|` 时打 `tool_call_markup` 标记（只加形状描述，不回显工具名/参数/模型原文）。
- 第 169 行起：`repair_message()` 对该标记追加定向说明（"上一次返回了工具调用标记而非 JSON，本次没有可调用工具，请用 `requested_checks` 表达后续工作"）。

未改：`provider.py` 的修复循环、`database.py` 的 `DATABASE_PROMPT`（规划阶段仍需要它）、`configs/wp_d/api-runtime.yaml`。

## 二、验证（我独立复核，非引用对方结论）

| 检查 | 结果 |
|---|---|
| 新增测试 `tests/unit/test_structured_output_v13.py` + `tests/integration/test_analysis_phase_boundary.py` | 66 passed |
| 全量离线回归（`tests/`，排除 live 文件） | **1122 passed, 3 skipped**（7:51） |
| `docs/acceptance/*.json` 里登记的源码 sha256 | 与当前工作区文件**完全一致** |
| `docs/acceptance/*.json` 的 6 行回执 | 6/6 success、每次 1 次 HTTP、0 次修复 |
| 分支状态 | `HEAD == origin/main == 1e22200`，`src/tests/configs/docs` 干净 |

**我自己的真实网关重放**（`%TEMP%\dbrole-repro\`）：

- `live_check.py`（slot-018 原始 payload 走修改后的生产 `analyze()`）：1 次 HTTP、0 次修复，返回合法 `AnalysisOutput`（`evidence_ids=['incident_3010-E-003']`，2 个 hypothesis、2 个 requested_check）。修复前同 payload 是 2/2 DSML。
- `live_logs_check.py`（新批次里唯一的 logs 角色失败，slot-008/attempt-004 `fixed-logs`）：1 次 HTTP、0 次修复，成功。说明该修复对非 database 角色的同类问题也有效。

**修复后真实批次统计**（`results/v16/wp-d/full40-local-gateway-c4-20261031`，40 槽、4 变体，09:04Z 起跑，`prompt_version` 确认是 v16）：

- 已完成分析调用 578 次，`STRUCTURED_REPAIR` 仅 10 次（database 1、logs 1、coordinator 6、single 2），远低于修复前的 17/53。
- `MODEL_FAILURE` 只有 1 次，且不是 database 的 DSML：slot-025 的 coordinator 第 4 轮返回"响应信封无字符串内容"（`UNKNOWN_PROVIDER_ERROR`），属网关侧问题，与本次修复无关；该槽已由 supervisor 自动重试（现为 attempt-003）。
- 对比修复前批次：database 53 次逻辑调用中 9 次终态 `INVALID_JSON`；修复后 database 66 次调用中仅 1 次 `INVALID_JSON`（slot-033），**且这一次修复后成功**。

## 三、未覆盖的边角（建议，不阻塞）

1. **DSML 识别只认"开头"。** 正则用了 `content.lstrip()` 锚定行首。修复前我抓到的**修复轮**输出是 `"I'll query PostgreSQL internals…\n\n<｜DSML｜> calls>"`——前面有一句散文，这种形状不会被标记，修复提示退化为通用文案。实测：`leading DSML` → 标记命中；`prose then DSML` → 未命中。主路径（首轮即 DSML）已覆盖，这属于"坏上加坏"的二阶情况。
2. **只认 DSML 一种标记。** `<|tool▁calls|>`、`<function_call>` 等其他原生工具标记同样判 `INVALID_JSON` 但不触发定向修复。当前网关（`magpie` → `deepseek-v4.1-flash`）只见过 DSML，够用；换提供商时需要补。
3. **`thinking: disabled` 仍被网关忽略。** 重放时 `reasoning_content` 照常返回、`reasoning_tokens` 计入 `completion_tokens`（slot-018 本次 completion 3304，其中 2500+ 是推理）。不影响 JSON 合法性，但会让 token 口径偏高、延迟偏长。

另注：`analysis_schema()` 的 `evidence_ids` 是 `Literal[tuple(sorted(ids))]`，即把允许的 ID 硬编码进 schema 的 `const`。这是有意的强约束（模型在 `reasoning_content` 里明确抱怨过"schema literally constrains evidence_ids to only that ID"），但它也是模型想"再查一次"的诱因之一；修复靠阶段声明压住了，若要进一步降风险可考虑把"没有可引用 ID 时怎么办"写进 `citation_rule`。

## 四、复现与证据位置

- 我的重放脚本：`%TEMP%\dbrole-repro\live_check.py`、`live_logs_check.py`（走生产 `analyze()`，密钥读 `.env` 不打印）
- 修复前原始响应：同目录 `raw-attempt1.txt`、`raw-repair1.txt`
- 对方验收：`docs/acceptance/analysis-phase-json-fix-20261031.{md,json}`、`results/acceptance/analysis-phase-fix-20261031/`
- 修复后真实批次：`results/v16/wp-d/full40-local-gateway-c4-20261031/`（39/40 完成，slot-025 重试中）
- 另一份并行审计（同一根因，结论一致）：`analysis/wp_d/reports/local-gateway-json-audit-20261031/report.zh-CN.md`
