# Dev40 失败与弃权原因核查

批次：`next-api-max8-20261022-121153`。范围：11个原始技术失败、25个正常弃权；另检查4个已诊断结果作对照。

**结论：问题并非单一API不稳定。除调用失败和两条终止分类缺陷外，存在漏查已提供指标、拿到证据后仍被竞争假设阻塞、审查建议未执行及模型错误解释查询语义等问题。直接重跑不能保证解决。**

本轮没有重跑、没有API请求、没有构造运行时Provider、没有执行项目测试或修复。仅在本报告新目录写分析脚本及输出。冻结源码、配置、Prompt、数据、原始批次、上一轮分析与已存在的评估文件均保持不变。

## 1. 口径与证据边界

核查原始scope、trace、result、verification、supervisor stderr以及当前冻结源码；参考对照复用上一轮已通过completion receipt检查的私有评分文件，没有新建运行或改写标签。

“参考支持集合已取回”只表示保存的工具观测覆盖项目已接受参考集合，不等于独立证明完整因果链，也不意味着可跳过竞争假设和引用语义检查。本报告没有将参考答案注入运行时，没有生成human review记录。

| 结果分组 | 数量 | 核查结论 |
|---|---:|---|
| 技术失败 | 11 | 6个未定类型传输失败、1个明确429、2个结构化输出验证失败、2个预算分类异常 |
| 正常弃权：参考证据缺失病例 | 6 | 与项目参考一致，属于正常且适当的弃权 |
| 正常弃权：可诊断、未取齐参考支持集合 | 8 | 全部没有查询postgres指标；已有公共指标未被获取 |
| 正常弃权：可诊断、已取齐参考支持集合 | 11 | 仍受竞争假设、额外日志/时间序列要求或模型解释问题阻塞 |
| 已诊断对照 | 4 | 用于检查为何同一机制在其他条件下能结束；不把这些结果当作消融因果证明 |

19个可诊断弃权的最后一份目标候选评估都含 `Competing hypothesis remains unresolved`；其中8个目标候选仅剩这一项gate错误。10个可诊断弃权曾尝试FINALIZE但被拒绝。门禁是在执行现有规则，不宜把拒绝一概叫作门禁实现错误；需要复核假设生成、竞争候选可信度和参考证据要求之间的设计适配。

## 2. 11个失败：逐槽定位

| 槽位 | 病例/架构 | 直接终止原因 | 证据与确定性 |
|---|---|---|---|
| 001 | 3010/NoVerifier | 保存为BUDGET_EXHAUSTED，实为分类异常 | 最后ABSTAIN；0个RUNTIME_ERROR；6/8轮、21/40工具、29/64请求、877/7200秒。停止理由含“within budget” |
| 004 | 3010/Single | coordinate-2的DynamicDecision验证失败 | 原响应和一次repair均为`$: value_error`，event-40/43分类、event-44 MODEL_FAILURE、event-46 RUNTIME_ERROR |
| 010 | 3004/Full | coordinate-11收到HTTP429，重试上限后失败 | event-275/278/281三次429，退避2秒、4秒；event-282明确transport_retry_limit；event-285终止 |
| 012 | 3005/Fixed | 保存为BUDGET_EXHAUSTED，实为分类异常 | 最后ABSTAIN；0个RUNTIME_ERROR；1/8轮、7/40工具、8/64请求、243/7200秒；实际是固定一次调度结束、未满足诊断条件 |
| 020 | 3008/NoVerifier | dispatch阶段未定类型传输错误 | event-25 UNKNOWN_PROVIDER_ERROR，event-26 non_retryable_failure，event-29终止；该逻辑调用只尝试1次 |
| 022 | 3003/NoVerifier | coordinate阶段未定类型传输错误 | 较早NETWORK_UNAVAILABLE曾重试恢复，最终event-92 UNKNOWN_PROVIDER_ERROR、event-93拒绝重试、event-96终止 |
| 026 | 3009/Full | dispatch阶段未定类型传输错误 | event-60 UNKNOWN_PROVIDER_ERROR、event-61拒绝重试、event-67终止 |
| 028 | 3006/Full | coordinate阶段未定类型传输错误 | event-81 UNKNOWN_PROVIDER_ERROR、event-82拒绝重试、event-85终止 |
| 032 | 3007/Single | coordinate-2的DynamicDecision验证失败 | event-44/47均`$: value_error`，已用一次repair，event-50终止 |
| 035 | 3002/Full | verify阶段未定类型传输错误 | event-230 UNKNOWN_PROVIDER_ERROR、event-231拒绝重试、event-234终止 |
| 039 | 3001/Full | coordinate阶段未定类型传输错误 | 较早429曾恢复，最终event-269 UNKNOWN_PROVIDER_ERROR、event-270拒绝重试、event-273终止 |

### 2.1 “预算耗尽”不是配置上限不足

`graph.py:1448` 在没有RUNTIME_ERROR、也没有RESOLVED报告时，直接检查自由文本stop_reason中是否包含`budget`。slot-001说“within budget”也会命中；slot-012是模型把固定调度结束称作budget exhausted。两条最后决策均为ABSTAIN，客观使用量未触及8轮/40工具/64请求/7200秒上限。

这是终止结果分类依赖自由文本的实现缺陷。应在后续版本改成依据结构化运行事实分类；本轮不修复、不改写结果，也不把这两条自动改记正确。两例参考均为可诊断，改分类不会凭空增加根因匹配。

### 2.2 6个传输失败：可确定“为何未重试”，不能确定底层病因

这6个最终失败都被分类为UNKNOWN_PROVIDER_ERROR、retryable=false；日志明确记录non_retryable_failure，所以**不是自动重试已经耗尽**，而是最终失败调用的第1次物理尝试就被策略拒绝重试。最终调用耗时约20.3–123.5秒，不能将其等同于1200秒请求等待上限超时。

原始底层异常类型/连接阶段没有保存，相关stderr均为空，trace与journal保留的是清理后的分类。不能确认具体是代理、连接断开、HTTP协议、TLS、供应商服务、客户端行为或其他原因；也不能断言降低并发一定有效。因此先前建议中把这7条（含429）统称“外部故障”过于宽泛，应区分**明确限流1条**与**根因未定传输失败6条**。

静态代码另有值得后续验证的分类覆盖边界：provider捕获内置TimeoutError后会交给classify_transport，但后者仅显式识别httpx.TimeoutException和httpx.NetworkError，其他异常落入UNKNOWN。当前保存证据不足以证明这6条实际命中了哪个异常分支，不能据此宣布根因已找到。

### 2.3 2个结构化失败：语义/模型级验证失败，具体约束不可恢复

两条都成功收到可解析内容及Token用量，失败点为DynamicDecision的根级`value_error`，不是没连上API，也不是JSON语法错误。已进行一次结构修复，修复后仍失败。

当前模型存在action语义和任务ACL等after-validator；但清理后的摘要只保留根路径和类型，没有原响应及具体验证器标识。repair提示也只得到类似`Response JSON does not match the required schema. $: value_error`的反馈，纠错指向不足。**无法凭现有产物判断究竟是action字段组合、ACL还是其他根级约束**；不能把其中一种猜测写成确定原因。

### 2.4 调用失败之外，失败调查本身也可能已经卡住

Full/3004和Full/3001分别已有8次、7次sufficient审查，最后决策为FINALIZE，但最终仍以调用错误结束。Full/3004在event-213曾因redis/payment等竞争假设未解决而拒绝完成。恢复API连接不等于这些调查必然成功，也不应把它们描述成“只差一次请求即可正确诊断”。

## 3. 25个正常弃权：逐槽定位

### 3.1 六个适当弃权

| 槽位 | 病例/架构 | 核查 |
|---|---|---|
| 003 | 3008/Fixed | 公共数据只保留症状，缺少原因特异证据；正常ABSTAIN |
| 005 | 3008/Full | 对缺失源作查询后仍无原因特异支持；正常ABSTAIN，5次审查 |
| 009 | 3003/Single | 无可确认配置变化和池机制的证据；正常ABSTAIN |
| 014 | 3003/Full | 无关键配置/池证据，未强行从症状归因；正常ABSTAIN，5次审查 |
| 024 | 3003/Fixed | 有限调度下只获得症状，正常ABSTAIN |
| 031 | 3008/Single | 调查后仍缺少能区分原因的证据；正常ABSTAIN |

NoVerifier对应的3003/3008为技术失败，未混入这6个正确弃权。Full的重复检查存在效率问题，但不能因为其耗时较长而否定最终适当弃权。

### 3.2 八个未取齐支持集合：共同遗漏postgres指标

| 槽位 | 病例/架构 | 已观察与遗漏 | 主要定位 |
|---|---|---|---|
| 007 | 3010/Fixed | 未取慢查询样本，也未取postgres查询延迟 | 固定一次工具计划只查backend/gateway指标及连接类证据，原因证据覆盖不足 |
| 016 | 3005/NoVerifier | 已取155/100连接容量记录，未取postgres连接数指标 | 一直没有query_metrics(postgres)，虽有其他源症状却未形成其要求的跨源支持 |
| 017 | 3007/Full | 已取7700ms锁等待，遗漏已存在postgres查询延迟指标 | 审查曾明确要求postgres指标，后续调度未执行；get_db_health_metrics返回空不等于query_metrics(postgres)也为空 |
| 021 | 3007/Fixed | 没取锁等待，也没取postgres查询延迟 | 固定工具计划覆盖不足，误导变更的空diff无法替代数据库原因调查 |
| 023 | 3009/NoVerifier | 已取锁等待，未取postgres查询延迟指标 | 把单一数据库样本视为无法佐证，却未查询已提供的另一个指标源 |
| 029 | 3007/NoVerifier | 已取锁等待，未取postgres查询延迟指标 | 同类跨工具证据覆盖遗漏；查询redis/payment和backend，未查postgres指标 |
| 037 | 3006/Fixed | 未取锁等待、未取postgres查询延迟 | 一次固定计划未覆盖实际致因服务 |
| 040 | 3009/Fixed | 未取锁等待、未取postgres查询延迟 | 一次固定计划未覆盖实际致因服务 |

这8条的公共metrics.csv中都存在对应postgres指标，trace中query_metrics(postgres)次数均为0。这是**实际数据源存在但没有执行相应查询**，不能解释为数据集没有提供该指标。即便补齐指标，也不保证其他门禁全部通过。

Full/3007尤其明确：event-39的review请求`t2-postgres-metrics`，filters.service=postgres、allowed_tools包含query_metrics；实际后续工具调用没有执行该查询。event-183执行的是get_db_health_metrics，读取database.jsonl中的health_metrics类别，和metrics.csv中的query_metrics不是同一个入口。其5次review都以backend_pool_config_regression为目标；即使event-141已获得postgres锁等待，后续review仍未转向该更有直接观察支持的候选。这是调度、检查闭环和审查目标选择的联合问题，不能单独归咎于Verifier“没有提出检查”。

### 3.3 十一个已取回参考支持集合但仍弃权

| 槽位 | 病例/架构 | 最终阻塞 | 原因定位 |
|---|---|---|---|
| 008 | 3009/Single | 仅竞争假设未解决 | 锁等待和postgres延迟均已观察，目标SUPPORTED；backend/redis/payment等候选及不匹配的service×mode组合仍OPEN |
| 011 | 3002/NoVerifier | 目标开放问题+竞争假设 | 配置差异和pool_waiters均已观察，仍要求公共数据未提供的pool错误日志，把额外佐证作为必需条件 |
| 013 | 3001/Single | 仅竞争假设未解决 | 配置、池等待已观察，目标SUPPORTED；其他资源/redis/payment候选未关闭 |
| 015 | 3002/Single | 仅竞争假设未解决 | 主机制已支持，backend_resource_saturation仍OPEN，导致FINALIZE拒绝 |
| 018 | 3006/Single | 仅竞争假设未解决 | 锁等待和查询延迟已观察，目标SUPPORTED；其他饱和/慢查询候选仍OPEN |
| 019 | 3001/Fixed | 仅竞争假设未解决 | 主机制支持已获得，但一次固定调度后没有进一步更新/关闭其他候选 |
| 027 | 3004/Fixed | 仅竞争假设未解决 | 配置差异已观察、目标SUPPORTED；同时漏backend pool_waiters指标，竞争候选仍未关闭 |
| 030 | 3002/Fixed | 仅竞争假设未解决 | 配置变化与池等待已观察，仍有多个无直接原因证据的候选阻塞 |
| 033 | 3006/NoVerifier | 目标开放问题+竞争假设 | 锁等待与延迟已观察，继续要求不存在的持续会话/健康时间序列；缺失gateway后续指标也限制传播链检查 |
| 034 | 3005/Full | 目标开放问题+竞争假设+独立审查 | 连接数指标、容量拒绝记录与后续症状均已取回，仍要求持续postgres/后端时间序列来排序因果；最终弃权 |
| 038 | 3001/NoVerifier | 目标开放问题+竞争假设 | pool_waiters已反复返回，仍把metric_names=[]理解成漏查资源指标；末次理由说pool-saturation机制从未观察到，与工具记录不符 |

其中8条只剩竞争假设错误：008、013、015、016、018、019、027、030。016属于上一节“未取齐参考集合”，但其实际候选已有数据库记录、日志/拓扑引用，机器gate最后仅报竞争假设；这也说明“参考集合覆盖”和“当前gate是否通过”是两个不同问题，不应互相替代。

## 4. 跨案例机制定位

### 4.1 当前竞争假设规则会让只有问题、没有原因证据的候选阻塞

`guards.py:112–119` 对任何非REJECTED的其他候选，只要有support_ids或open_questions，就加入“竞争假设未解决”。不要求它先具备原因特异证据，也不区分已有症状支持、仅引用拓扑、未测量问题和可信竞争解释。

多个trace有redis/payment源为空、无cause discriminator、甚至support_ids为空但open_questions非空的候选。这些候选会阻塞主机制；而提示词又正确要求不能把“缺失”当“健康”、不能无证据反驳。于是可能进入：提出任意可能性→没有数据排除→不能REJECT→主机制永远无法结束的闭环。

这是**设计规则与稀疏证据包之间的不协调证据**，不是证明所有这类假设都应无条件忽略。后续应明确“有根据的竞争解释”和“未观测、没有正向支持的可能性”的处置，保留真正矛盾证据的安全门禁。本轮不修改规则。

### 4.2 metrics空列表并不会导致漏取

`tools/metrics.py:11` 的条件是`not args.metric_names or ...`，空列表表示该服务/时间窗内全部指标；`agents/service.py:42`的提示也明确说明。该行为不是本轮缺陷。

slot-038六次backend query_metrics都使用空列表；每次均返回E-001正常基线和E-005的pool_waiters=153。最后模型却说“all backend metric queries used empty metric_names”，并把“没有pool_limit/pool_in_use/CPU/memory”与“pool-saturation机制从未观察到”混在一起。确实没有提供完整资源时间序列，但已有pool_waiters不可被忽略。这里主要是证据解释和对未提供指标的额外要求，不能修成禁止空列表或据此认定工具返回丢失。

### 4.3 重复检查较多，但不能把所有无新增调用都认作浪费

572个TOOL_CALL中，487个保存了显式args，其中65个是相同tool+args的第二次及以后调用；另85个没有显式args，不据此判定重复。352个调用没有新增evidence_id，包括Verifier依法fetch已见证据、对不同范围的空查询、合理负证据检查和普通重复，不能直接称“61.5%的调用无效”。

但具体trace确有可改善情况：Full/3003、3008分别出现20、11个重复requested-check计数；Full/3007重复问检查，却没有执行已请求的postgres指标；NoVerifier/3001重复6次相同backend指标查询，最终仍误述结果。这些比单纯提高轮数更值得后续处理。

## 5. 给后续规划的结论（均未实施）

1. **先分清日志分类和真实失败。** 两条BUDGET记录是分类问题；六条UNKNOWN传输记录还没有底层根因，不应全部当临时网络故障。
2. **补足安全可诊断信息。** 未来需要稳定的validator标识及清理后的异常类型/连接阶段，才能区分结构约束和传输失败；不需要把密钥或完整错误正文记入日志。
3. **优先考虑证据查询覆盖与requested-check闭环。** 八条未取齐支持集合均漏postgres指标，3007/Full有明确请求未执行的证据；不能只增加Verifier次数。
4. **明确有根据竞争假设的完成语义。** 保留矛盾检查，避免没有正向原因证据的任意可能性永久占用硬门禁；同时检查稀疏参考标签要求与运行时门槛是否一致。
5. **检查模型证据解释与额外佐证要求。** 3001/NoVerifier和3005/Full等已经取得关键观测，仍误读或要求不存在的额外时间序列。单纯重跑/加预算未必有效。
6. **后续如果要改变这些行为，属于新版本冻结后的实验。** 本批不可事后改标签、覆盖失败或混合新旧版本结果。重跑范围与条件由用户后续规划。

## 6. 产物与保护检查

- `evidence-audit.json`：40个槽位逐条工具查询、实际返回ID、新增ID、假设状态、目标gate历史、调用失败事件、review/followup记录。
- `per-slot-causes.csv`：40行可筛选原因表，25个正常弃权和11个失败均保留。
- `audit-summary.json`：原因计数与保护核验摘要。
- `protected-inputs-before.json`：1337个受保护文件SHA256，覆盖原始批次、上一轮报告、src/scripts/configs/prompts/data及已存在评分文件。
- `audit_saved.py`：仅使用Python标准库的提取脚本，不导入项目运行时。

提取前后1337个受保护文件集合及SHA256完全一致；224个冻结输入仍匹配batch-manifest。运行产物未改写、没有新增attempt，没有执行项目测试、Provider调用或修复。本报告中“确定”限于日志/源码直接支持的事实；底层传输病因和具体DynamicDecision根级验证器仍为未知。
