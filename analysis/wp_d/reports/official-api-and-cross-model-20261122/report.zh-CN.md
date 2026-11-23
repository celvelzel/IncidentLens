# 官方 API 修复验证与跨模型对照实验报告（2026-11-22）

本报告记录在项目主线基础上完成的三项后续工程与实验工作：

1. **修复结构化输出自定义校验诊断盲区**：定位并修复 `ReviewOutput.leading_review_consistency`、`task_tool_acl` 与 `tool_arguments` 在 `_SAFE_TYPES` 中被静默折叠为 `$: validation_error` 的问题，并在验证提示词中显式声明互斥契约（commit `39621e5`）。
2. **官方 DeepSeek API 全量硬化集实验（144 槽位）**：在修复后代码上，直连官方 `https://api.deepseek.com/v1` 运行 `deepseek-flash`（`json_object`、`thinking: disabled`、`cache: off`）完整 36 案例 × 4 架构 = 144 槽位。
3. **跨模型接入与思维链消融（OhMyGPT / `tencent/hy4-flash`）**：通过官方 `openai` Python SDK 集成 OhMyGPT（`--provider ohmygpt`），在硬化集 6 类难度杠杆代表案例（6 × 4 = 24 槽位）上完成 **开启思维链 vs 关闭思维链** 消融及跨模型架构对照。

---

## 1. 结构化输出修复前后消融（官方 DeepSeek API）

在直连官方 DeepSeek API（`json_object` 模式、`thinking: disabled`）进行硬化集 6 代表案例 × 4 架构（24 槽位）首轮测试时，发现 `single` 与 `full` 在 `verify` 阶段大面积报错：

- **根因**：`ReviewOutput.leading_review_consistency` 抛出 `PydanticCustomError("leading_review_consistency", ...)`，但 `src/incident_lens/llm/structured_output.py` 的 `_SAFE_TYPES` 未收录该自定义错误码，导致修复提示词只返回模糊的 `$: validation_error`，模型在唯一一次修复重试中重复违反同一互斥约束。
- **修复**：将 `leading_review_consistency`、`tool_arguments`、`task_tool_acl` 加入 `_SAFE_TYPES`，增加零泄漏静态修复提示 `_SAFE_REPAIR_HINTS`，并在 `service.verify()` 与 `prompts/verifier.md` 中写明字段互斥不变式。

| 阶段 | 范围 | `verify` 阶段格式崩溃 | 技术完成 | 质量成功 |
| --- | --- | ---: | ---: | ---: |
| 修复前（`deepseek-chat`） | 6 案例 × 4 架构（24 槽位） | **8 / 12**（`single` 4/6、`full` 4/6） | 15 / 24 | 10 / 24 |
| 修复后定向重测（`deepseek-chat`） | 之前失败的 9 个槽位（含全部 8 个 `verify` 崩溃） | **0 / 8**（7 次一次过、1 次首轮修复恢复） | **9 / 9** | **9 / 9** |
| 修复后全量（`deepseek-flash`） | 完整硬化集 36 案例 × 4 架构（144 槽位） | **0 / 144**（`STRUCTURED_OUTPUT_INVALID = 0`） | **137 / 144 (95.1%)** | — |

---

## 2. 官方 DeepSeek API（`deepseek-flash`）硬化集 Dev36 全量（144 槽位）

- **数据**：`causal-world-v2-hardened`（Dev 36 案例：29 可识别 / 7 应弃权，`incident_4001`–`incident_4036`）
- **模型与配置**：官方直连 `https://api.deepseek.com/v1` · `deepseek-flash` · `json_object` · `thinking: disabled` · `temperature: 0.0` · `cache: off` · `max_rounds: 8` · `max_tool_calls: 40` · `max_llm_calls: 64` · `max_wall_seconds: 900`
- **总消耗**：144 槽位合计约 **1,881 万 Token**；技术完成 **137 / 144（95.1%）**。

### 2.1 主表（与前期本地网关 144 槽位批次并列参考）

分母口径与既有 `hardened144-20261101` 一致：`技术完成` 分母为 36；`根因正确` 分母为已完成的可识别案例；`正确弃权` 分母为已完成的不可识别案例；`质量成功` 为失败包含口径（分母 36）。

| 架构 | 技术完成 | 根因正确 | 正确弃权 | **质量成功** | 根因误判 | 误弃权 | 平均耗时 | 平均请求 | 平均工具 | 平均 Token | 修复次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Single | 33/36 | 21/26 | 7/7 | 28/36 (77.8%) | 0 | 5 | 76.5 s | 17.5 | 13.6 | 197,986 | 7 |
| Fixed-4 | **36/36** | 6/29 | 7/7 | 13/36 (36.1%) | 0 | 23 | 17.3 s | 7.4 | 7.2 | 36,478 | 1 |
| **Dynamic（主架构）** | **35/36** | **24/28** | **7/7** | **31/36 (86.1%)** | **0** | **4** | **56.4 s** | **14.8** | **11.1** | **113,645** | **5** |
| Full（dynamic + verifier） | 33/36 | 21/27 | 6/6 | 27/36 (75.0%) | 0 | 6 | 67.0 s | 18.5 | 14.6 | 187,781 | 6 |

- **配对比较（同案例内 `quality_success`）**：
  - `dynamic` vs `single`：**+6 胜 / −3 负 / 27 平**；平均 Token 低 **42.6%**，平均耗时低 **26.3%**。
  - `dynamic` vs `full`：**+6 胜 / −2 负 / 28 平**；平均 Token 低 **39.5%**，平均耗时低 **15.8%**。
  - `dynamic` vs `fixed`：**+18 胜 / −0 负 / 18 平**。
- **0 根因误判**：全部 137 个技术完成槽位中 `false_resolution = 0`，所有非技术失分均为保守弃权（`INCONCLUSIVE`）。
- **7 次技术失败构成**：4 次 `FINDING_IDENTITY_MISMATCH`、2 次 `PROVIDER_TRANSPORT_ERROR`、1 次 `Evidence sufficient@UNRECOVERABLE_ERROR`；**0 次 `STRUCTURED_OUTPUT_INVALID`**。

### 2.2 分难度杠杆明细（质量成功 / 案例数）

| 杠杆 | Single | Fixed-4 | **Dynamic** | Full |
| --- | ---: | ---: | ---: | ---: |
| `standard` | 6/7 | 2/7 | **6/7** | 4/7 |
| `boundary` | 5/7 | 2/7 | **6/7** | **6/7** |
| `competing` | 5/7 | 1/7 | **6/7** | 4/7 |
| `missing`（应弃权） | **7/7** | **7/7** | **7/7** | 6/7 |
| `misleading` | **2/2** | 1/2 | **2/2** | **2/2** |
| `counterfactual_pair` | 3/6 | 0/6 | 4/6 | **5/6** |

值得关注的是：尽管 `full` 整体性价比低于 `dynamic`，但在 `counterfactual_pair` 杠杆上取得了 **5/6**，高于 `dynamic`（4/6）与 `single`（3/6）。

---

## 3. 跨模型实验与思维链消融（OhMyGPT / `tencent/hy4-flash`）

为验证架构结论不局限于单一模型家族，通过官方 `openai` Python SDK 接入 OhMyGPT（`https://api.ohmygpt.com/v1`，模型 `tencent/hy4-flash`，`json_schema` 模式），选取覆盖全部 6 类难度杠杆的 6 个硬化集代表案例（`incident_4001` `standard`、`4007` `boundary`、`4012` `competing`、`4014` `misleading`、`4018` `missing`、`4035` `counterfactual_pair`）× 4 架构 = **24 槽位**，分别测试默认开启思维链与显式关闭思维链（`thinking: {"type": "disabled"}`）。

### 3.1 思维链开关消融（24 槽位汇总）

| 配置 | 批墙钟耗时 | 技术完成 | 900s 超时次数 | 质量成功 | 根因误判 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `hy4-flash` 开启思维链（默认） | 48.0 min（2,880 s） | 11 / 24 (45.8%) | 6（`single` 3、`full` 3） | 7 / 24 (29.2%) | 0 |
| **`hy4-flash` 关闭思维链** | **12.6 min（758 s，快 3.8×）** | **23 / 24 (95.8%)** | **0** | **13 / 24 (54.2%)** | **0** |

**原因分析**：多智能体 RCA 是 10–25 步的串行工具探索循环。开启思维链将单次调用拖慢至 40–70 秒，导致 `single` 与 `full` 在中途耗尽 900 秒墙钟预算（`BUDGET_EXHAUSTED`）；关闭思维链后单步降至 5–8 秒，把预算转化为更多轮实地取证，并由外部确定性 `FinalizeGate` 兜底校验，端到端成功率接近翻倍。

### 3.2 `tencent/hy4-flash`（关闭思维链）四架构明细

| 架构 | 技术完成 | 根因正确 | 正确弃权 | **质量成功** | 根因误判 | 误弃权 | 平均耗时 | 平均请求 | 平均工具 | 平均 Token | 修复次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Single | 6/6 | **0/5** | 1/1 | 1/6 (16.7%) | 0 | 5 | 173.8 s | 23.2 | 18.2 | 254,026 | 1 |
| Fixed-4 | 6/6 | 2/5 | 1/1 | 3/6 (50.0%) | 0 | 3 | 28.4 s | 7.5 | 7.0 | 39,809 | 1 |
| **Dynamic（主架构）** | **6/6** | **4/5** | **1/1** | **5/6 (83.3%)** | **0** | **1** | **85.6 s** | **15.2** | **9.3** | **123,861** | **0** |
| Full（dynamic + verifier） | 5/6 | 3/4 | 1/1 | 4/6 (66.7%) | 0 | 1 | 146.0 s | 21.0 | 15.2 | 264,436 | 1 |

### 3.3 跨模型关键发现

1. **轻量非思考模型上的能力放大效应**：在关闭思维链的 `hy4-flash` 上，单智能体 `single` 在 5 个可识别案例上 **0/5 全部误弃权**（均耗 254k Token / 173.8s）；而 `dynamic` 将质量成功从 **16.7% 提升至 83.3%（5/6）**，同时平均 Token 降低 **51.2%**、平均耗时降低 **50.7%**。这说明多智能体角色分工不仅在较强模型上降本，在轻量/无思考模型上还能显著放大诊断能力。
2. **反事实配对上的跨模型一致信号**：在 `deepseek-flash` 与 `hy4-flash`（关思考）两个不同模型家族上，`dynamic` 失手的 `incident_4035`（`counterfactual_pair`）均由 `full`（带 `Verifier`）成功定位，支持后续探索 **按需 Verifier（`dynamic_review`）** 路线。

---

## 4. 证据边界（Evidence Boundary）

- **开发可见与临时标签**：本报告全部批次均运行于开发可见硬化集 `causal-world-v2-hardened`，`formal: false`、`blindness_level: development_visible`，oracle 标签状态均为 `pending`（尚无独立人工验收与盲测）。
- **单次重复与描述性结论**：全部实验均为单次重复（`repeats = 1`），差异为描述性实测结果，不构成统计显著性主张或生产环境准确率保证。
- **官方 DeepSeek 144 槽位断点续跑说明**：该批次前 42 个有效槽位（41 完成 + 1 例真实 `FINDING_IDENTITY_MISMATCH`）运行后遭遇账号余额不足（HTTP 402），充值后保留上述 42 个有效槽位并按相同修复后代码与协议续跑其余 102 个槽位完成全量 144 槽位；所有原始运行产物均保存在本地 `results/repro-deepseek-flash-hardened144/`（按 `.gitignore` 不入库）。
- **跨模型抽测范围**：OhMyGPT `tencent/hy4-flash` 覆盖 6 个代表案例（24 槽位 × 开/关思考两轮 = 48 槽位），覆盖全部 6 类难度杠杆但并非完整 36 案例全量；且聚合网关由服务方按请求路由上游供应商。
- **0 根因误判的前提边界**：所有技术完成运行中的“0 误判”依赖 `FinalizeGate` 中针对 7 种预定义故障模式的确定性判别契约，不代表在开放、弱结构化 OOD 生产故障上天然具备零误判保障。
