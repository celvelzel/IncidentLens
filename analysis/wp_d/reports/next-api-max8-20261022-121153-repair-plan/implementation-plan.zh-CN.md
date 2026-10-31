# Dev40 三项问题的解冻后修复实施方案

日期：2026-10-22（上海时间）。状态：**方案已编写，代码未修改，测试未执行，真实调用未执行**。

执行前提：用户负责的其他Agent完成旧版本失败项补跑、保存选择口径和产物，并由用户明确通知代码解冻/开始实施。补跑结束本身不自动触发本方案；本任务不启动Agent、不发送其他聊天消息、不创建定时任务或自动修改代码。

## 0. 范围、基线与交接

本方案中的“三项”对应原因核查最后确认的三个具体问题：

| 编号 | 问题 | 直接证据 |
|---|---|---|
| R1 | 无足够正向原因证据的竞争假设可以永久阻塞完成 | 19次可诊断弃权均有竞争假设阻塞，其中8次只剩该项；guards.finalize_errors依赖其他候选的support_ids或open_questions |
| R2 | 审查提出的检查没有形成执行/解释闭环，审查目标也可能停留在弱候选 | slot-017 Full/3007的event-39已请求query_metrics(postgres)，后续未执行；5次审查都围绕backend_pool_config_regression，虽后来取得postgres锁等待 |
| R3 | 模型误读metric_names=[]及已返回证据，重复查询后仍称证据未观察到 | slot-038 NoVerifier/3001六次backend指标查询都返回pool_waiters=153，最终理由仍把空指标列表当成漏查；工具实现本身正确 |

依据：上一轮`next-api-max8-20261022-121153-cause-audit/findings.zh-CN.md`、逐槽原因表及原始trace。基线源码commit为`50467d2c0e9376c7a7d401714c68f49edc7184a1`，以批次manifest的实际文件SHA256为最终依据，不能只核对HEAD。

预算分类缺陷、传输错误分类和DynamicDecision验证诊断属于**另列问题**，本方案不暗中将它们打包实现。若后续需要一并修复，先在解冻后的实施范围中明确增补。

本轮唯一写入位置为当前`analysis/wp_d/reports/...-repair-plan/`目录，不写docs/plans、源码、测试、配置或原始批次。保存`protected-before.json`与`validation.json`，证明当前方案编写没有改变冻结条件。

### 解冻后的首个动作

1. 确认补跑进程和子进程已退出，旧批次已封存；不依赖进程心跳单独判断。
2. 读取最新补跑attempt、最终选择清单和用户指定的结果口径。失败尝试全部保留，不择优挑结果；若有多attempt，明确最终采用规则及所有消耗。
3. 对照本方案引用的旧attempt逐条核实结论是否仍成立，新增补跑证据作为附录，不覆盖旧核查。
4. 保留未关联的dirty文件（当前有未跟踪`0`以及已有分析目录）。实施前检查适用AGENTS与实际工作树，必要时在用户授权范围内隔离开发。
5. 保存旧运行完整输入与源码快照、协议、模型和依赖版本，确认能重建旧条件，再实施修复。

## 1. 总体实现原则

三个问题都按“确定性事实→模型决策→门禁验证→可解释事件”处理。代码只根据公开数据与本次真实工具观测推导事实；不导入Oracle、参考支持集合或病例编号。

- R1改变的是“哪些竞争解释有资格构成硬阻塞”，属于明确的实验条件变更，不能声称只是日志优化。
- R2改变Full的检查执行闭环和审查目标选择；Single自审使用相同事实和检查记录，但不增加独立Verifier。NoVerifier不新增审查。Fixed保持原本一次专家调度，不能通过后台自动补查询变成动态基线。
- R3统一所有架构的查询事实表示、参数语义和报告约束；不改变空列表的正确含义。
- 维持现有来源授权、已观察引用、正向支持、不同来源、真实矛盾、预算、STOP、审查快照与取消守卫。未完成检查、工具失败和部分分页不能伪装成正常完成。
- 不增加模型/工具/轮数预算，不更换模型、不修改数据或参考标签，不修改旧结果。未来真实执行采用新冻结版本和新目录。

建议新增三个小模块：`orchestration/query_facts.py`、`orchestration/review_checks.py`、`orchestration/competition.py`。事实与规则放在独立纯函数中；graph只接入，避免继续扩大graph内的耦合逻辑。

## 2. R3：先建立可信查询事实，防止空列表误读

### 2.1 修改位置

- 新增`src/incident_lens/orchestration/query_facts.py`：从TOOL_CALL及其有效结果构建有类型的查询摘要，不调用工具。
- `orchestration/graph.py:payload`：在现有query_history旁增加query_facts及其版本/指纹，保持既有字段兼容。
- `agents/service.py:plan_tools/analyze/decide/verify`：传递统一事实；加强决策与最终报告的结构化约束。
- `schemas/contracts.py`或新局部输出模型：为新版本决策增加结构化证据缺口说明，默认空列表以兼容历史产物。
- `prompts/coordinator.md`、`single.md`、`metrics.md`、`verifier.md`：按实际存在文件调整，说明scope边界及已观察/未观察/查询失败三者差异。
- `tools/metrics.py`：保留现有筛选语义，只补测试，预期不需要改执行逻辑。

### 2.2 事实结构与边界

每次query_metrics保存：`event_id/call_id/task_id/service/start/end/metric_filter_mode/metric_names/ok/record_ids/observed_metric_names/next_cursor/new_evidence_ids`。

- `metric_names=[]`精确标记`metric_filter_mode=ALL_IN_SCOPE`，不能标成EMPTY或MISSING。
- 非空列表标记`NAMED_ONLY`；失败标记FAILED；有next_cursor标记PARTIAL。只有成功且分页穷尽才可称该查询scope已检查。
- 全量是**当前服务、时间窗和公开数据快照内**的全量，不是该服务永远没有其他指标，不是生产健康证明。首次查backend全部指标并不覆盖postgres。
- 同时提供`observed_metric_names`和证据ID，使模型直接看到`pool_waiters`已经返回；不根据想象构造pool_limit/CPU/内存等不存在的指标。
- `get_db_health_metrics`的事实明确是database类别切片，不把它视为query_metrics(postgres)已完成。

### 2.3 停止与报告的约束

在新版本决策局部Schema中增加`evidence_gaps`，每项包含：gap类型（未查scope/已查为空/工具失败/部分结果/已有观察仍缺少机制佐证）、相关事件ID、scope、关联候选ID与简短解释。运行时验证事件确实存在且scope匹配。

确定性校验只拒绝**可证明的结构冲突**：例如引用返回pool_waiters的调用，却将其记录为零条指标；或把postgres DB类别查询当作postgres metrics查询。保留“已经看到pool_waiters，但不足以区分机制”的合法表达。

不要通过搜索自由文本中的“empty”“never observed”等词判违规；不自动替模型编造诊断。能在现有一次结构修复中纠正的反馈应返回具体稳定错误码（例如QUERY_SCOPE_MISMATCH、OBSERVED_METRIC_MARKED_MISSING），复用原预算与记账。无法修复则保留输出失败/未决状态，不能静默成功。

报告区分“取到了什么”“还缺什么”“该缺口为什么影响结论”，并列出仍未观测的资源量。纯文本仍可能出现语义误述，须保留静态/人工语义审核，不承诺结构化字段即可消灭所有幻觉。

### 2.4 必须通过的离线用例

| 用例 | 期望 |
|---|---|
| 空列表query_metrics返回latency+pool_waiters | 标记ALL_IN_SCOPE，两个指标都出现在事实与模型payload |
| 指定metric_names仅返回latency | 不能宣称已覆盖pool_waiters |
| backend全量/窗口A，问题为postgres或窗口B | 不能复用为已覆盖 |
| 失败、空结果、有分页分别输入 | 输出FAILED/EXHAUSTED_EMPTY/PARTIAL，互不混淆 |
| 已见pool_waiters但缺CPU/memory | 可保留机制不确定；不能说pool_waiters未观察到 |
| 自由文本出现“empty metric_names” | 不靠关键词强制判错或强制诊断 |
| slot-038保存事件离线提取 | 应显示6次backend全量查询都返回E-005；这只是事实提取回归，不宣称修复模型已成功 |

## 3. R2：审查检查形成持久闭环，落实到实际查询

### 3.1 修改位置

- 新增`orchestration/review_checks.py`：检查台账、scope匹配、生命周期和事件投影。
- `graph.py:coordinate/merge/verify/payload/board_fingerprint`：接入台账，替代仅覆盖state.requested_checks及仅看最近一次review的跟踪方式。
- `agents/service.py:decide/verify`：要求对未处理检查作执行或解释，并约束审查目标候选集合。
- 新增局部台账Schema；历史requested_checks仍可读。台账进入新产物与journal诊断快照，但不扩展成单次调查可执行恢复功能。

### 3.2 检查状态机

`PENDING → ASSIGNED → EXECUTED_PENDING_REVIEW → SATISFIED`。

工具失败记FAILED，权限不足记UNAVAILABLE；因预算未执行记DEFERRED_BUDGET；reviewer有明确理由撤销阻塞要求记WITHDRAWN_WITH_RATIONALE。后者是“该检查不再必要”，不是声称其内容被验证。预算不足不解除尚存的实质性因果缺口。

每条检查具有稳定check_id，保留提出它的review_event_id、候选/证据快照、scope及所有变更理由。同一检查再次提出只追加来源，不清空未完成项。`state.requested_checks`可保留为未决台账投影；不能让新review用一个新列表悄悄覆盖旧检查。

“执行过”与“回答了问题”必须分开：

- 以实际TOOL_CALL有效参数及返回结果对账，不只依赖task_id、assigned或模型自报completed。
- 同service、规范化时间范围、工具类型及指标过滤范围才可匹配。空filters/自然语言scope只靠task_id不能自动认定满足。
- 完全相同scope可确定性匹配；同scope下ALL_IN_SCOPE覆盖某NAMED_ONLY请求，但需检查成功、分页穷尽。跨窗口覆盖只有明确实现并测试包含关系后才允许，初版不猜测语义等价。
- get_db_health_metrics不满足query_metrics(postgres)；`ok=false`不满足；成功为空只证明该scope查过，不证明健康或假设被反驳。
- SATISFIED需复核结论与本次实际证据关联，引用已授权/已取回ID；空结果也要写“缺失如何影响判断”。不能自动据此把候选REJECTED。

### 3.3 调度策略

对Full/Single的每个新决策，payload提供未决检查和上一轮执行结果；模型返回检查处置映射：执行、与已完成scope对应、延期、建议撤销（最终由review确认）。

优先安排尚未执行、可在当前预算内完成、用于区分现有有根据候选的检查。仍维持每轮最多两个任务及决策/审查请求预留。遗漏台账处置应在现有结构修复预算内返回明确反馈，不能静默注入额外工具或扩大ACL。

如果某检查被延期，应给出预算/权限/证据适用性理由并保留在未决记录；若最后仍影响结论，则正常弃权或保留对应失败，不能为了结束清空台账。没有新增证据不等于无进展：假设评估变化、scope首次穷尽和真正矛盾的解决仍可算进展。

审查目标选择：最新FINALIZE明确选择的候选仍必须被审查；没有选择时，根据公开已观察支持、cause discriminator、跨源支持和未决问题生成候选事实摘要，要求review解释目标选择。存在有直接原因观测的候选时，目标Schema优先约束到这些候选；若有直接矛盾，不通过简单计数掩盖它。相同证据分数不使用Oracle破平局。候选支持显著变化时允许重新选目标，不能一直沿用初始弱候选；新目标/快照必须重新审查，旧sufficient不复用。

### 3.4 必须通过的离线用例

1. 请求query_metrics(postgres)，调度backend指标或get_db_health_metrics：检查保持未决。
2. 用不同task_id执行同一规范scope：能对账；相同task_id却执行不同scope：不能满足。
3. 后续review删除旧检查：旧项仍有状态与处置历史；明确撤销有理由和来源，不会悄悄消失。
4. 成功空结果、失败、部分分页：分别有不同状态，均不能自动推出“服务健康”。
5. 任务因预算不可支付：不调用、不加预算，保留DEFERRED_BUDGET及结论影响。
6. 指标/候选证据变化：原sufficient审查不可跨快照生效；STOP或取消后不得追加调度。
7. Full/3007形状的合成公开fixture：审查请求postgres指标后，必须执行对应入口或有明确未执行处置；不能只调DB health后标完成。
8. 新强候选出现：review允许转目标；有FINALIZE目标时只审查被选候选。
9. Fixed仍只执行一次固定专家组；NoVerifier没有新增review；Single没有变成独立审查。

## 4. R1：区分有根据竞争解释与未观测可能性

### 4.1 修改位置

- 新增`orchestration/competition.py`：纯函数生成竞争解释评估，不改写Hypothesis原始状态。
- `guards.py:finalize_errors/reviewed_finalization_ready`和`graph.py:candidate_assessments`共用同一policy，不能只改payload展示而让实际门禁仍采用旧逻辑。
- `graph.py:payload/report`增加阻塞原因、未观测可能性、公开证据依据和残余不确定性。
- 新版本policy_id绑定scope/协议/源码冻结；旧版本产物和旧policy保持可解释。

### 4.2 竞争解释分层

| 层级 | 依据 | 对完成的影响 |
|---|---|---|
| EVIDENCED_ALTERNATIVE | 同一incident内已实际观察、授权、与该候选service/mode相关的正向原因特异证据，或经可核验语义评估支持的具体竞争机制 | 未解决时仍硬阻塞 |
| MATERIAL_COUNTEREVIDENCE | 与主候选机制/时序直接矛盾的已观察记录 | 维持阻塞，不能因竞争候选弱而忽略 |
| UNOBSERVED_POSSIBILITY | 只有问题、通用症状或拓扑，没有可指向该机制的正向原因证据 | 不等同于被反驳；可不单独形成竞争硬阻塞，但必须公开残余不确定性 |
| ASSESSMENT_UNCERTAIN | 记录看起来可能相关，但确定性规则/有效语义评估无法判断其是否支持具体原因 | 保守保留阻塞或安排有限核查，不静默归入无证据可能性 |

判据首先复用已存在cause_discriminator作**正向识别**，但“未匹配该规则”不能直接证明没有原因支持。对非规则覆盖的记录，要显式标为ASSESSMENT_UNCERTAIN；若引入模型语义判断，必须引用真实ID、给出具体观察关系并允许复核，不能只信一个confidence分数。

拓扑只能证明依赖关系，通用deadline/5xx主要是症状；不能仅凭这些记录就宣称redis、payment或任意service×mode组合有正向原因证据。也不能自动把这些候选改为REJECTED。Hypothesis的OPEN/SUPPORTED/REJECTED保持原语义，竞争资格作为派生评估单独保存。

### 4.3 新门禁的通过条件

主候选仍须满足当前grounding要求：真实已观察引用、跨来源支持、cause discriminator、已支持的判别性调查、无未解决的主候选实质问题或矛盾；Full仍须相同候选/证据快照的独立充分审查。

仅将“其他任意候选有support_ids/open_questions即阻塞”替换为“仍存在EVIDENCED_ALTERNATIVE/MATERIAL_COUNTEREVIDENCE/ASSESSMENT_UNCERTAIN即阻塞”。未观测可能性不自动成为硬门禁，但报告必须带出它们；检查台账中的真实必要项不因重新分层自动清空。

对主候选自身open_questions/shared questions的清理不做关键词自动删除。可选遥测与实质缺口的区分需有R2台账处置和理由；当前证据确不足以支持主机制时仍弃权。R1不是保证任何单条原因记录均可诊断的捷径。

### 4.4 必须通过的离线用例

| 场景 | 期望 |
|---|---|
| 主候选满足现有条件，其他仅有“是否redis故障”问题、无原因证据 | 新policy允许不因这一个可能性硬阻塞；报告保留未知，原Hypothesis不自动REJECTED |
| 两个候选均有直接原因观测 | 继续阻塞；禁止挑支持条数较多的一个直接成功 |
| 主候选有真实反证/时间矛盾 | 继续阻塞，不因竞争候选缺证据放过 |
| 竞争候选提供规则未覆盖但可能相关记录 | ASSESSMENT_UNCERTAIN，保守处理 |
| 竞争候选只有拓扑或同一条generic deadline | 不把症状当原因；若存在无法判定的具体机制联系则进入uncertain |
| 主候选仅一源、无discriminator或引用越权 | 保持原失败条件 |
| 证据缺失病例/多个原因不分明 | 仍弃权；不以消除竞争问题换取过度诊断 |
| review不足、过期、目标不符、未处置必要检查、STOP | 不可完成 |
| 三组对照架构 | 同样使用竞争证据policy；架构区别仅保留其既有调度/审查设计 |

### 4.5 旧测试的兼容与修改纪律

现有`test_finalize_resume_guards.py`和`test_review_boundary.py`包含“重新打开竞争候选并添加问题就必须阻塞”的断言。R1会有意改变其中**仅靠问题阻塞**的新policy行为；实施时必须记录测试迁移：

- 旧policy回归保留原断言，历史结果可解释。
- 新policy分别测试无原因支持的可能性可以披露后完成，以及有真实竞争原因/不确定证据仍阻塞。
- 不得直接删掉competitor用例或把断言统一改成允许通过；审查快照、矛盾与授权相关用例保持。

## 5. 文件清单与实施顺序

以下是解冻后预计涉及的路径；**本轮未创建或修改这些运行文件**。

| 阶段 | 预计文件 | 交付/退出条件 |
|---|---|---|
| S0 | 新版本计划/冻结记录，独立开发目录（如实际需要） | 确认旧批次封存、用户解冻指令、最新源码差异和补跑口径 |
| S1：R3事实层 | query_facts.py、graph.py、service.py、局部Schema、相关prompts；新增test_query_facts.py | 空列表语义、scope、分页/失败均正确；不新增工具调用 |
| S2：R2检查闭环 | review_checks.py、graph.py、service.py；新增test_review_check_lifecycle.py | 未执行不伪装满足、预算/ACL/STOP守卫不变、架构边界测试通过 |
| S3：R1竞争规则 | competition.py、guards.py、graph.py；新增test_competition_policy.py，迁移相关旧断言 | 有根据竞争仍阻塞、未知披露不冒充反驳、旧policy兼容 |
| S4：联调 | tests/integration/test_wpd_diagnostic_repairs.py、相关既有回归、变更说明 | 完成四架构离线联调与失败分类边界核查；再决定是否冻结真实实验 |

每阶段交付：实际修改文件、行为差异、运行命令、测试结果、仍未验证项。若用户之后要求提交，按功能阶段组织；本轮不提交、不推送。

新增policy字段须被当前runner保留到scope与锁中；如果ExperimentProtocol为extra=forbid，先显式扩展版本化字段或定义独立冻结policy manifest，不能把自造字段直接塞进JSON后忽略解析失败。已有协议读取、源码与prompt指纹检查一并测试。

## 6. 解冻后验证命令与标准

以下是未来命令，**本轮没有执行**。新增测试文件需先按上述阶段实现。

```powershell
$env:PYTHONPATH = Join-Path $PWD 'src'
$P = '.venv/Scripts/python.exe'
& $P -B -m pytest tests/integration/test_query_facts.py tests/integration/test_review_check_lifecycle.py tests/integration/test_competition_policy.py tests/integration/test_wpd_diagnostic_repairs.py
& $P -B -m pytest tests/integration/test_finalize_resume_guards.py tests/integration/test_review_boundary.py tests/integration/test_wpd_run_preparation.py tests/incidentbench/test_experiment_fairness.py tests/incidentbench/test_review_workflow.py
& $P -B -m pytest
& $P -B -m ruff check src tests
git diff --check
```

新增离线测试使用合成公开数据、Stub/MockProvider和保存trace的纯提取；不得把私有Oracle或旧参考答案嵌入运行策略。旧trace只能检验事实和离线规则差异，不能把重算结果覆盖原始运行或声称模型真的重做了调查。

接受标准：所有新增行为表及安全负例通过；四架构权限、预算及调用记账一致；历史产物可读取；空数据/真实竞争/证据矛盾没有被放宽为成功。全量回归失败需逐条归因，不能仅因原测试断言不适应新policy就忽略。

离线通过只证明工程约束，不能证明真实模型查询覆盖、诊断率或Full净收益提高。未来真实验证由用户另行规划，不在此附带启动命令。

## 7. 后续实验怎样证明修复有效

保留当前补跑完成的旧条件B0；新条件分别记录B0+R3、B0+R3+R2、B0+R3+R2+R1的源码、Prompt、policy版本。是否实际执行所有消融由用户按资源决定；若只跑最终版本，只能评价三项组合，不能单独归因Verifier或某个模块。

同一条件内继续完整Dev10×四架构、同一模型/预算/重试规则。调度并发若改变需明确记录，不能把它造成的外部调用差异当架构净收益。不同版本不拼成一个40槽矩阵，旧失败与新消耗全部保留。

除已有根因匹配、正确弃权及资源指标，新增：

- 已请求、可执行检查的实际scope覆盖率；未执行项的原因覆盖率。
- 指标已返回却被结构化标为缺失的冲突数；postgres等实际致因服务的指标覆盖（评估时对照，运行时不读答案）。
- 竞争资格各层数量、因真实竞争/未知可能性分别阻塞的次数。
- 相同scope重复数及有新增证据/候选评估/有效负scope进展的审查比例。
- 过度诊断、错误根因与缺失证据病例正确弃权，防止用降低安全性换匹配数。

所有指标同时保留技术终止账本与正常完成质量口径；共同完成配对集合明确列出。Dev10仅有两个名义家族和一个近重复簇，不做确认性显著性、独立盲测或生产泛化宣称。

## 8. 可交接执行指令

用户解冻后可直接使用：

> 旧版本补跑已结束并封存，现授权代码解冻。请先核对补跑新产物及当前源码，再按本文件S0→S4实施R3、R2、R1。保持四架构边界、原始结果和无关修改；每阶段汇报修改文件、验证命令与结果、剩余问题。先完成离线验证，不自行启动真实API实验；预算分类及调用诊断若要增补，先明确列入实际范围。

这段是未来交接模板，不构成当前执行授权。本轮最终交付是方案与保护验证记录。
