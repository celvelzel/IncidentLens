# IncidentLens V1.4 审核路径与子 Agent 桥接改进计划

日期：2026-10-13（Asia/Shanghai）。状态：仅制定计划，尚未实施或复测。

本计划依据用户要求：下一轮总预算设为 **600 秒**，单次响应上限保持 **180 秒**；先完成三个改进的计划，不修改代码或运行配置。

## 1. 当前证据与问题范围

- DeepSeek 开发试跑：2 个 Seed × 4 架构，技术完成 0/8；3 次 PROVIDER_TIMEOUT、5 次 STRUCTURED_OUTPUT_INVALID。调查 HTTP 请求 28 次，另有 1 次探针。不能把这些失败当作正常弃答。
- gpt-6-luna/high 子 Agent 通过文件桥运行真实 Graph 的 single 条件：2 例均在约 300 秒触发总预算。13 份实际消费响应通过 Schema 校验，2 份迟到响应没有计入成功。
- 其中 request-0006 和 request-0014 的 Review 在没有假设时填入 `target_hypothesis_id="none"`，Schema 接受。不存在的目标没有立即被运行时拒绝。
- `orchestration/graph.py` 的 merge 对 full/single 无条件路由到 verify；verify 在查找目标之前 append review，且在 sufficient 时可能先清空共享 open_questions。查找失败只产生空 fingerprint，未立即拒绝。
- FinalizeGate 已检查真实候选、因果支持与审核快照；目前证据没有证明不存在目标能绕过最终 Gate。改进目标是提前拒绝无效审核及消除不必要调用，不声称已出现伪造成功。
- 文件桥父端轮询间隔为 0.5 秒。没有分解子 Agent 发现、模型生成、读写与父端消费时间；不能把数分钟超时直接归因于轮询，或承诺减少读写一定能大幅提速。

原始证据位于 `results/incidentbench/v1/20261013-deepseek-development-pilot/` 与 `results/incidentbench/v1/20261013-luna-high-subagent-pilot/`，实施及复测使用新目录。

## 2. 下一轮预算约定

| 项目 | 下一轮设定 |
|---|---|
| 每次完整调查总时限 | 600 秒 |
| 每次物理 API 请求 / 子 Agent 响应等待上限 | 180 秒 |
| 模型请求额度 | 16 次，保持现有试跑设置 |
| 工具调用额度 | 12 次，保持现有试跑设置 |
| 调查轮数 | 4 轮，保持现有试跑设置 |
| 案例 | incident_2001、incident_2002，公开数据保持原字节 |
| 初次复测架构 | single equivalent tools / benchmark RCA |
| 缓存与跨调查并发 | cache off / jobs=1 |
| 来源与指标 | 子 Agent 平台 tokens、费用、实际温度、内部 HTTP 请求未知 |

有效等待不得超过剩余总预算：`min(180, remaining_wall_seconds)`。修正调用也计入总时限和请求额度；不是为每次修正重新获得 600 秒。600 秒包含工具、审核和桥接往返。系统配置原本就有 600 秒默认值，此处是提高本次 pilot 的局部 300 秒设置，不需要提高全局默认值。

本轮仅记录以上参数；后续实施时才写入新 pilot protocol、桥配置和预算快照，不修改或覆盖旧实验 protocol。

## 3. 改进一：无假设审核路径

### 实施方案

优先保留冻结的 `Review` 契约，不把目标字段全面改成 nullable，不引入虚构占位 ID。

1. 定义可审候选为当前运行中状态 OPEN 或 SUPPORTED 的实际 Hypothesis。REJECTED 保留为历史，但不作为可接受根因审核目标。
2. merge 后若没有可审候选，full/single 返回 coordinate，并记录明确的审核跳过事件及原因 `NO_REVIEWABLE_HYPOTHESIS`。
3. verify 入口再次检查，防止直接调用节点或状态变化绕过 merge 的分流；没有可审目标时不执行 verifier fetch 或模型审核。
4. coordinator 依据已有事实、未解决问题、完成任务和剩余预算选择补充有实际鉴别价值的检查或 ABSTAIN。无假设本身不证明不可辨识，不立即自动发出成功弃答。
5. 没有新事实且可执行鉴别任务已耗尽时，正常证据不足结束；不得通过循环重复同一已完成任务消耗预算。
6. 有候选时继续既有 verifier/self-reflection 与 FinalizeGate；不能为了节省调用绕过有候选的必要审核，也不清空既有有效阻断条件。

### 拟修改位置

- `src/incident_lens/orchestration/graph.py`：merge 路由与 verify 入口。
- `src/incident_lens/agents/service.py`：明确无候选时继续调查/弃答的协调提示；避免生成占位审核。
- `src/incident_lens/orchestration/guards.py`：仅在需要共享候选选择规则时增加小型纯函数；既有最终校验保持严格。

### 验收

- 空候选、全为 REJECTED、直接 verify 入口：不调用审核模型，不生成 `none` Review，保留审计事件。
- 缺证据 fixture 能经正常 STOP/FINISHED 得到 INCONCLUSIVE；超时失败仍不计为正确弃答。
- 可辨识 fixture 的必要审核与根因输出不回退；full 与 single 的独立审核/自省含义仍有区别。
- 同一完成任务不被重新调度；超出预算可靠结束，不能出现无限 coordinate 循环。

## 4. 改进二：目标 ID 存在性校验

### 实施方案

1. 生成时约束：类似现有 `analysis_schema(records)`，构造审核输出模型，把目标 ID 限定为当前可审候选集合。空集合走改进一，不向 Provider 发送一个无法满足的 Review Schema。
2. 运行时再次校验：即便自定义 Provider 绕过输出 Schema，也必须在任何状态更新之前验证目标存在、属于当前运行、仍可审。
3. 不存在目标时产生安全错误码 `REVIEW_TARGET_NOT_FOUND`；已拒绝目标采用单独可审性错误。禁止自动替换为第一个候选，禁止把字面量 `none` 当作空值。
4. 目标校验与原有可见证据引用校验均通过后，才 append review、更新 requested_checks、处理 open_questions 并记录非空候选 fingerprint。
5. 动态 Schema 失败沿用既有修正次数上限和请求计数，不增加无限修正或静默宽松回退。运行时语义失败按现有失败流程记录并 STOP。
6. FinalizeGate 继续要求当前候选和证据快照一致；旧审核不能接受后来变化的候选或证据。

### 拟修改位置

- `src/incident_lens/agents/service.py`：动态审核 Schema、审核提示。
- `src/incident_lens/orchestration/graph.py`：验证先于写入，安全拒绝。
- 共享 `schemas/contracts.py` 的 Review 原始字段和有效历史序列化格式原则上不变。

### 验收

- 已存在可审 ID 通过；不存在的 ID、其他运行的 ID、`none`、REJECTED ID 被拒绝。
- 特别验证 `sufficient + unknown target` 无法清空 open_questions、写入审核或改变后续请求状态。
- Schema 约束与运行时校验分别测试，不能只用同一生成模型证明运行时安全。
- 审核过后改变候选/证据，既有快照校验仍阻止错误 FINALIZE；合法历史 Review 仍可反序列化。

## 5. 改进三：减少桥接往返开销

### 先计时，再优化

每份请求增加可比较的父端时间戳：生成完成、请求发布、响应检测、格式校验结束、运行时消费。子端记录发现请求、读完输入、响应提交。统一在同一主机使用单调时钟；记录时钟来源，避免把 UTC 字符串和 monotonic 混算。

能直接测得排队/发现/传输/消费耗时；子端的发现到响应提交仍包含模型推理与工具调度，平台未提供的数据不伪装为纯模型生成耗时。

### 实施方案

1. 建立 READY 握手：子 Agent 就绪后才启动该案例的 Graph 计时；计时内仍包含实际调查往返，不从结果中任意减去等待。
2. 子端一次读取完整请求，不重复显示相同大段 Schema；单次响应用原子写入提交。响应内容仍由子 Agent 生成，不用规则程序代答。
3. 在实际传输中每次仍提供必需角色提示、完整 Schema、身份与公开上下文。只有验证过相同任务内的资源引用解析时，才考虑传输去重；不得删掉约束来降低耗时。
4. 索引只跟踪未处理请求，避免反复全目录扫描；父端已有 0.5 秒轮询，先依据测量判断是否值得替换为通知机制。
5. 生命周期明确为 pending/claimed/responded/consumed/cancelled/expired。取消在同一任务边界可观察，子端跳过已取消项；迟到响应隔离保存，永不喂入下一请求。
6. ID 包含 experiment/run/call/attempt；新 provider 的计数不得把前一案例的累计请求数当作本案例用量。消费结果按实际 admitted、responded、validated、consumed 分别计数。
7. 减少无意义重复工具查询，但保留新证据后的必要复查。保持 cache off；不要把跨运行响应缓存作为提速或模型效果。
8. 平台 tokens/费用/HTTP 次数/温度继续为未知。沿用一个持久子 Agent 时显式保留上下文持续的限制，不能宣传为无历史 API 调用的公平替代。

### 拟修改位置

- 新版本本地桥适配器，以 `local_oracles/luna_graph_bridge_20261013.py` 为参考，保留原脚本及其哈希可复核性；不要原地改变旧实验解释。
- 对应子 Agent 请求处理指令、计时/生命周期日志和统计脚本。
- 不修改生产 HTTP Provider 或缩减 Graph 安全检查以适应桥。

### 验收

- 正常请求唯一消费；重复提交幂等，半写不可消费，过期/取消/前一运行响应均被拒绝。
- 单次等待不超 180 秒和剩余总预算；总 600 秒触发取消后不得消费任何迟到结果。
- 各案例计数与事件逐项对账，不累计串号；耗时缺项用 null。
- 确认桥请求不含 Oracle 或私有真值；只在状态落盘后读取候选标签。
- 本地传输测试证明轮询/扫描行为改善后，真实试跑另报端到端耗时；不承诺未测出的具体提速比例。

## 6. 实施顺序、测试与复测

1. **基线保全**：保存当前代码/桥版本及旧产物哈希；记录工作区。原有 V1.5 计划是已有未跟踪文件，本任务不改动或实施。
2. **预算与观测**：在新协议中设 600/180，增加时间与生命周期日志。可先进行预算单独调整的同两例观察，以区分增加时间和代码改进的作用；它与旧 300 秒结果不是等预算比较。
3. **路由与语义修复**：先实现改进一，再实现改进二，运行定向测试。
4. **桥优化**：依据计时证据实施改进三，保证有效响应和取消语义不退化。
5. **工程验收**：定向测试后运行既有全量 pytest、Ruff lint/format、公开与评测侧数据校验；记录实际命令与结果，不删除失败断言。
6. **真实复测**：先同两例、single、600/180，保存原始状态、计时、请求/响应/消费计数，完成后重算候选评分。通过后再决定是否扩展四架构。

拟覆盖/新增测试：`tests/unit/test_agents.py`、`tests/integration/test_graph.py`、`tests/integration/test_review_boundary.py`、`tests/integration/test_termination_scoring.py`、`tests/incidentbench/test_scoring.py`，以及桥适配器的生命周期/计时测试。具体新增文件按最终实现落点确定。

无需真实模型调用的确定性测试必须先通过。真实模型的格式有效、技术完成、根因正确、正常弃答分开报告；不为达到某个通过率改 Oracle 或删除失败案例。即使工程测试通过，也不预先保证模型结果一定成功。

## 7. 交付与完成标准

- 三个改进分别可审查、可回退的功能提交；预算/协议另行记录。
- 修改文件、实际测试日志、600/180 协议与版本指纹、完整新试跑产物、分阶段耗时和保存状态重算结果。
- 不覆盖历史产物，不将子 Agent 当作真实 HTTP 用量计费，不使用 Frozen Test 调参，不实现 V1.5 算法。
- 本计划不解决 DeepSeek 输出字段错误的具体根因：现有原始记录粒度不足，后续需单独增加安全字段级诊断并验证。仅提高总时限不保证解决其单次超时或结构化失败。

## 8. 本轮实际变更

仅新增本计划文档。生产代码、测试、运行配置、旧桥脚本和旧实验均未修改；没有发起模型调用、测试或复测。600/180 是已确定的下一轮参数，尚未写入可执行配置。
