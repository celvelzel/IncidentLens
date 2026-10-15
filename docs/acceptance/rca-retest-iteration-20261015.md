# 从真实调查失败到可靠收尾：RCA 复测迭代说明

日期：2026-10-15。范围：当前相对 HEAD 的全部已跟踪未提交修改，以及新增的脚本、回归测试、验收文档和 `results/acceptance` 产物。整理时暂存区为空。既有提交中的功能仅作为背景，不算本轮新增成果。

## 1. 目标与目前结论

目标是让 IncidentLens 能从公开证据完成调查，在证据充分时可靠交付 RCA 报告，在证据不足、预算耗尽或协议违规时保持明确的失败或弃权结果。

本轮走过的路径是：**真实复测暴露证据发现与状态协调缺陷 → 修复并加入回归 → 审计桥接成功是否可信 → 用受控对照分离模型、适配器和运输因素 → 扩大真实 API 预算定位剩余障碍 → 消除已通过审查后的冗余模型调用。**

目前已证明：新增行为通过离线回归；真实 API 曾找到正确机制并完成更新后的充分性审查；保存的真实状态可在不追加模型调用的情况下完成修复后的收尾。**尚未证明：最终修复版本从初始 incident 开始，重新完成一次完整真实 API 调查。** 原 v4 运行仍为失败，不能用离线延续改写它。

## 2. 迭代一：先解决“证据存在，却没有被正确发现和合并”

### 做了什么测试、发现什么问题

2026-10-14 的真实 API 复测覆盖 full、dynamic_no_verifier、single、fixed。它暴露了三个相互关联的问题：

- dynamic_no_verifier 在第 19 次调用后发生 `MERGE_FINDING_ID_COLLISION`。不同专家使用相同局部标签，例如 F1，被当作跨任务的全局身份。
- 四个变体均漏掉关键配置 diff E-004。changes 查询截止于 12:00:00，实际部署 E-003 在 12:00:10；日志的 ERROR 过滤也可能排除没有 severity 元数据的公开记录。空查询被误用为继续索取旁证的依据。
- 中间修复版本已找到部署、配置 diff 和症状，仍可能因过期 open_questions、未重新评估的竞争假设，以及“sufficient 同时提出阻塞检查”而无法接受根因。找到正确标签不等于满足运行时的定案要求。

### 做了什么修改

1. 验证身份和引用后，以 Finding 的身份、任务和内容生成稳定 ID，保留 merge 的碰撞与权限检查。
2. IncidentBench 首次 changes 发现去掉猜测的时间/type 过滤，保留服务范围；首次 logs 发现去掉 severity/contains，保留时间和数量限制。后续已发现来源的查询保留模型过滤，旧工作流保留原规则。
3. changes 任务有空余工具槽位时，用真实返回的 change_id 获取 diff，仍受两次调用上限、ACL、预算与事件记录约束。
4. 给协调器提供实际 query_history 摘要，区分“查过但过滤为空”和“尚未查过”。摘要不附原始 excerpt。
5. 新增 `hypothesis_updates`：协调器可用已观察证据修正既有候选和竞争解释。禁止改变原因身份或引用未观察 ID；无证据的 SUPPORTED/REJECTED 不能直接成立。
6. 区分阻塞性的 `requested_checks` 和非阻塞的 `optional_checks`；新的生成合约禁止 sufficient 与矛盾/阻塞检查并存。Full 的候选变化后必须重新独立审查。
7. Fixed 在固定专家调度完成后增加一次终局协调评估；若仍需调查则弃权，不额外分派专家。这改变了该变体的调用组成，需要新的源码版本与预算记录。

### 得到了什么改善

定向回归覆盖身份冲突、查询范围、同任务有界 diff 获取、引用/原因身份约束和重新审查。后续真实 v4 已实际观察 E-003/004/005/008/009，并将 `backend_pool_config_regression` 设为 SUPPORTED、排除竞争原因。证据发现与共同状态协调取得实际进展，但不能据此宣称四变体最终恢复率已通过。

详细历史：[10 月 14 日修复与交接](../IncidentBench_20261014_RCA_Fix_Notes.md)。其中 37 passed 是当时定向测试；878 passed、3 skipped、1 failed 是当时源码变动期间的历史全量结果，不能当作当前验证状态。

## 3. 迭代二：补齐阶段恢复，分清请求超时与总预算

### 做了什么测试、发现什么问题

真实 API 调查继续暴露出阶段不一致：专家调用能够重试，verify 的一次运输超时却直接终止；修复 verify 后，wall=1800 的试跑又在第一次 coordinate 调用超时时结束，仍剩大量预算。另一次 wall=900 的运行虽然恢复了三次超时，累计延迟仍耗尽总预算。

这些是不同问题：增加总时限可以缓解累计等待，但不能修复“单次失败直接终止”的控制流；增加单次超时也会延长每次失败占用的时间。

### 做了什么修改

- verify 使用任务级有界尝试，设置当前 state，使任务转换事件与 trace 快照一致；每次审查使用新任务 ID。
- coordinate 和 monitoring 使用共享的 `retry_transient`，仅对允许恢复的运输错误重新发起，记录失败尝试及 `MODEL_RECOVERED`。
- STOP、取消、协议违规和预算耗尽继续停止；没有通过无限重试掩盖错误。
- bridge 和 HTTP 共用初始 messages 与 strict Schema。递归将声明字段列入 required，要求显式输出 null/空列表，减少默认字段被遗漏造成的结构化错误。
- HTTP 的 legacy/reliable 两条发送路径增加整体单次发送截止控制，补足 HTTPX 分阶段超时的边界。取消清理可能让异常返回略晚于配置截止；远端是否继续生成及计费无法从客户端判断。

### 得到了什么改善

故障注入测试证明单次 verifier/coordinator 运输失败可以按限次恢复，并维持停止协议和失败统计。真实 v4 的 verify-2 超时后重试成功，提供了实际恢复证据。结构化修复为 0 是该次运行的观察结果，不代表所有输入从此不会发生结构化错误。

历史问题逐条保留在 [live-provider issues](live-provider-issues.md)。其中旧源码行号和旧全量计数仅对应当时版本。

## 4. 迭代三：审计桥接，用对照实验收窄失败归因

### 为什么保留这些测试

桥接成功、真实 API 失败，并不能直接推出模型能力差异。需要分别回答“旧桥接有无可见注入”“同输入真实模型能否处理”“固定回答能否走通适配器”三个问题。

| 测试 | 观察结果 | 可以支持的结论与限制 |
|---|---|---|
| 旧桥接产物审计：15 组 request/response/dispatch | 嵌入请求一致，响应通过两种 Schema 检查，未发现输入外证据 ID | 未发现直接注入迹象；缺少外部会话/工具日志，不能认证无污染或正式盲测 |
| 三个保存输入的真实 API 探针 | coordinator 与 diff 分析成功，Verifier 超时；分析找对机制，但重复索要已有 diff | API 能处理这两项输入；不能由 Verifier 无返回判断其推理能力 |
| 单次截止补修后的 Verifier 追加探针 | 再次超时，约 182 秒返回异常 | 截止与取消路径有观测；不是端到端成功 |
| 固定旧桥接回答，经 HTTP MockTransport 运行全图 | 15 次适配器尝试，成功，真实网络请求为 0 | 这套回答可被适配器/工作流接受；不能证明真实模型会产生它们 |
| 同样回答经修复后文件桥接运行全图 | 15 次 bridge、0 次 HTTP，成功 | envelope、许可结算和桥接计数可工作；未执行新的外部 Agent |

四次真实探针中两次有返回、两次超时；已知 token 下界为 10,825，总 token 和成本未知。两条离线全图路径改变的是适配器，不是重复的真实模型评测，因此保留两者有对照意义。

### 修复了哪些可信度缺口

桥接要求全新队列，响应绑定 session/request/SHA-256，错误绑定立即失败，保存接收副本与带时间哈希日志，最多一次结构修复；超时/取消/STOP 均结算未知用量。桥接消耗 LLM 请求预算，但不再误记真实 HTTP。入口拒绝 formal 或非 development_visible 桥接协议。

真实与桥接入口保存有效参数以及 src/scripts/configs/pyproject 摘要、结束时源码漂移。摘要能检查前后一致，不能证明外部隔离或识别“中途修改后恢复”。桥接依然没有 OS 沙箱、模型身份认证或外部工具访问证明。

另一个报告缺陷在审计中被发现：预测被直接用作 causal_chain。现在按实际支持记录的时间和证据 ID 展示观察序列，预测单列为未确认。其改善是报告事实更可追溯，不代表新增了因果证据。

详细证据：[桥接审计与 API 归因](bridge-audit-20261015.md)，产物在 `results/acceptance/bridge-audit-20261015/`。

## 5. 迭代四：扩大真实 API 预算后，定位“诊断已通过，交付仍失败”

v4 使用 wall=3600 秒、request=300 秒，保留有界任务重试。其 full 调查使用 25/32 次请求，耗时约 2955 秒，发生五次约 302 秒的客户端超时；最终以 `UNRECOVERABLE_ERROR` 结束，协议有效、源码无前后漂移。

关键事件链：

1. event-92：第一次 sufficient。
2. event-97：Coordinator 决策 FINALIZE，同时更新候选和竞争假设。
3. event-98：合并更新。旧审查快照随之过期，因此重新审查是正确要求。
4. event-104：更新后的审查再次 sufficient，既有 `finalize_errors` 全部通过。
5. 工作流却再次进入 coordinate-5，两次各约 302 秒的超时耗尽任务尝试，未交付成功 RCA。

这说明扩大总预算确实让调查走得更远，但没有消除多余调用暴露的运输失败机会。原运行有 INCONCLUSIVE 报告，准确表述是“成功诊断报告未交付”，不是“完全没有文件”。客户端日志不能确定超时来自端点、网络或网关的哪一层。

## 6. 迭代五：在保持审查守卫的前提下完成确定性收尾

### 修改

Full 重新审查后，若已有最近的 FINALIZE、审查目标一致、仍为 RUNNING 且原定案守卫全部通过，直接进入 finalize，发布 `FINALIZE_RESUMED_AFTER_REVIEW`。不再让模型重复批准同一结论。finalize 仍检查请求、token 与墙钟预算；停止后的新事件也被协议判为非法。

### 验证

- 完整故障回归构造“第二次 FINALIZE 模型调用必然超时”的场景：修复后只有一次 FINALIZE 模型决策，更新后有新 REVIEW，随后直接 DIAGNOSIS_ACCEPTED，不再发出模型调用。
- 16 类拒绝条件及其他变体、过期预算、停止后发布检查，验证捷径不会跳过证据、快照、竞争原因或停止约束。
- 从真实 v4 event-104 做取证式离线延续，保留之前事件、23 次请求和历史失败，推算剩余时限，禁止任何新增模型调用。原 finalize/stop/report 得到 RESOLVED / DIAGNOSIS_READY / SUCCESS，protocol_valid=true、new_http_requests=0。

这里的提升是消除一次本不需要的协调决策及其失败机会。离线延续仅验证已完成调查状态的交付能力；其驱动重建任务状态、使用内部结构，不是生产级断点恢复接口，也没有重新验证前面的在线调查。

详细证据：[收尾修复验收](finalize-resume-20261015.md)，产物在 `results/acceptance/finalize-resume-20261015/`。

## 7. 当前未提交改动如何组成一个整体

以下路径相对仓库根目录；本表覆盖整理开始时全部修改和新增文件类别。

| 文件或目录 | 作用 | 对应验证 |
|---|---|---|
| `src/incident_lens/agents/service.py` | 公开证据发现、Finding ID、合约与假设重评 | unit/test_agents、integration/test_graph、test_review_boundary |
| `src/incident_lens/schemas/contracts.py` | optional_checks、hypothesis_updates | 合约生成与引用拒绝测试 |
| `src/incident_lens/orchestration/graph.py` | 查询摘要、有界 diff、阶段恢复、更新后审查、直接收尾 | graph、fault_matrix、review_boundary |
| `src/incident_lens/orchestration/guards.py` | 重新审查后的收尾资格 | test_finalize_resume_guards |
| `src/incident_lens/evaluation/termination.py` | STOP 后禁止新增收尾事件 | test_finalize_resume_guards |
| `src/incident_lens/llm/provider.py`、`structured_output.py` | strict Schema、共享消息、单次截止 | test_provider_runtime_v13、test_bridge_retest |
| `src/incident_lens/evaluation/runner.py` | 区分文件桥接与 HTTP 计数 | test_bridge_retest |
| `src/incident_lens/evaluation/retest_provenance.py` | 复测源码摘要和前后漂移 | 已保存探针/复测 scope 与 verification |
| `src/incident_lens/orchestration/report.py` | 已观察支持记录与预测分开呈现 | unit/test_report_grounding |
| `scripts/retest_live_provider_fix.py` | 四变体入口、BOM 协议兼容、参数与版本留痕 | 历史真实定向复测及 scope |
| `scripts/retest_subagent_bridge.py` | 开发桥接绑定、超时、结算及审计 | test_bridge_retest、桥接离线全图对照 |
| `scripts/probe_saved_bridge_requests.py` | 同输入真实 API 探针，不执行完整工作流 | 四次探针的输入与结果 |
| `tests/unit/test_agents.py`、`tests/integration/test_graph.py` | 修复身份冲突、发现/引用约束的回归 | 迭代一 |
| `tests/integration/test_review_boundary.py` | 角色视图、候选更新后审查、收尾故障回归 | 迭代一、五 |
| `tests/reliability/test_fault_matrix.py` | verify/coordinate 瞬时故障恢复 | 迭代二 |
| `tests/active_investigation/test_graph_integration.py` | 审查成为 runtime task 后，区分所选调查任务与全部运行任务 | 保留 caes 任务精确匹配和预算断言 |
| `tests/integration/test_provider_runtime_v13.py` | 两种 adapter 的整体截止和未知用量 | 迭代二 |
| 新增 `test_bridge_retest.py`、`test_finalize_resume_guards.py`、`test_report_grounding.py` | 各自固定本轮发现的协议、收尾、报告缺陷 | 迭代三、五 |
| 三份专项文档、`live-provider-issues.md`、两组新增 acceptance 产物 | 保留发现过程、复现条件、原始成功/失败证据 | 本文作为主入口，专项材料提供细节 |

## 8. 测试与材料的整理决定

本次没有删除回归测试或原始测试结果。逐项检查后，新增测试分别保护可复现的缺陷或信任边界；两条离线全图对照也有不同的适配器验证目的。删除它们会削弱归因或回归保护。

失败日志同样保留：桥接审计阶段曾出现 UI 回放一致性失败，单项和静止全量复跑未复现；具体原因未证实。10 月 14 日的 benchmark lock drift 也保留为运行期间改源码的教训。不能通过删掉失败只呈现成功来制造迭代效果。

整理方式是增加本文主线入口，给历史交接材料标明版本边界，修复重复 ISSUE 编号、时间顺序和过度归因。旧计数保留为历史，不与最终全量相加、不解释为准确率提升。桥接队列中的 request/response/receipt 看似重复，但分别服务于输入、外部交付和实际接收一致性核对，因此保留。

## 9. 已验证的完善与仍需补齐的验收

| 维度 | 起初问题 | 目前得到的完善 | 证据范围 |
|---|---|---|---|
| 证据发现 | 过滤遮蔽部署与 diff | 首次发现、真实 ID 有界拉取、历史查询可见 | 回归 + v4 实际获取证据 |
| 状态协调 | 旧问题/竞争原因/旧审查阻塞 | 有引用的重评，变化后重新审查 | 回归 + v4 两次 sufficient |
| 运输恢复 | 部分阶段一次超时即终止 | 阶段有界重试、完整截止与未知用量 | 故障注入 + v4 verify 恢复 |
| 比较可信度 | 桥接被误当真实 HTTP/盲测 | 开发范围、绑定审计、参数和版本留痕 | 桥接/HTTP 对照；隔离仍未认证 |
| 报告可信度 | 预测当已确认因果链 | 真实支持记录可追溯、预测单列 | 报告回归 |
| 最终交付 | 审查通过后重复请求模型并超时 | 守卫通过后确定性收尾 | 故障回归 + 零新增 API 的真实状态延续 |

收尾修复版本保存的全量结果为 **914 passed、3 skipped**，日志 `results/acceptance/finalize-resume-20261015/pytest-final.log`。三个跳过均与 Windows 符号链接权限有关。这是软件回归结果，不是 914 次真实调查。

下一次完整验收应冻结最终源码/协议，在全新输出目录从 `incident_2001` 初始状态执行真实 API full 调查，保留所有失败尝试、真实请求用量与报告；随后增加 `incident_2002` 负例与重复运行，检查正确弃权和稳定性。当前仍缺最终版本完整真实正例成功、负例防误报及四变体重测结果。单次成功也不能推出总体准确率或模型排名。

本文仅整理已发生的测试与修复，没有发起新的付费 API 运行。当前整理的离线检查结果另见 `results/acceptance/rca-retest-review-20261015.log`。

### 本次整理的复核结果

- 对本轮涉及的九个测试文件重新执行回归：**220 passed，15.86 秒**。没有调整代码或断言来消除失败。
- 当前生产源码、脚本与配置和收尾修复验收所存摘要比较，差异为 `[]`；因此上述 914 passed 的历史全量对应相同实现。本次没有再跑一遍全量，也没有把 220 与 914 相加。
- Ruff、`git diff --check`、本文和三份专项材料的本地文档链接检查通过。
- 暂存区为空；未提交、未推送。本次新增主文档、复核日志及文件审阅清单，更新四份旧文档的入口或错误表述，没有删除原始失败结果。

复核命令（仓库根目录）：

```powershell
.venv\Scripts\python.exe -m pytest -q tests/unit/test_agents.py tests/unit/test_report_grounding.py tests/integration/test_graph.py tests/integration/test_review_boundary.py tests/integration/test_provider_runtime_v13.py tests/integration/test_bridge_retest.py tests/integration/test_finalize_resume_guards.py tests/reliability/test_fault_matrix.py tests/active_investigation/test_graph_integration.py
.venv\Scripts\python.exe -m ruff check src scripts tests
git diff --check
```

逐文件状态、内容摘要和保留用途记录在 `results/acceptance/rca-retest-review-inventory-20261015.json`。清单是本次审阅时的快照，不取代各次运行原有的冻结摘要，也不涵盖忽略规则排除的历史结果。
