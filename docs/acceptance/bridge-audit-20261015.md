# 桥接完整性审计与 API 失败归因

> 迭代主线与当前验收边界见[统一迭代说明](rca-retest-iteration-20261015.md)。本文保留该阶段证据；历史测试计数不代表后续版本的在线验收。

日期：2026-10-15。审计对象为 `user-retest-reconciliation/full-subagent-bridge-blind` 及同目录 API 复测。旧实验文件未修改。本报告区分原始产物能证明的事实、无法核实的外部行为及本次新实验。

## 结论

现存产物未出现直接的答案注入或未观测证据引用；但没有足够审计材料证明外部 Agent 无上下文污染、无仓库越权读取或无人工编辑，不能认证为干净盲测，也不能据此指控作弊。目录名含 `blind`，但其协议本身为 `formal=false`、`blindness_level=development_visible`。

桥接成功与 API 失败并非只涉及模型身份。历史比较同时改变了总预算、单次超时执行方式、提示/Schema 包装和运行时版本；API 还出现了可直接观察的运输超时和阶段恢复缺口。桥接外部 Agent 的实际模型、温度及工具权限均未被验证。

## 原桥接的产物检查

- 15 个请求、15 个响应、15 份 dispatch，60 条队列日志。
- 每份 dispatch 嵌入的 JSON 均与对应请求完全一致；去掉请求 ID、role、schema 名后，dispatch 前缀只有一个模板，没有逐条额外提示。
- 15 份响应均通过原 JSON Schema，也通过将全部声明字段设为 required 的 Schema。故本次没有证据支持“原桥接靠缺失字段或宽松 Schema 才成功”。此检查使用本地已有的 jsonschema 库完成，不代表语义正确性审核。
- 响应中出现的证据 ID 都存在于对应输入中；最初 coordinator 的 evidence_catalog 为空。未发现显式新增的未见证据 ID。ID 检查不能判断自然语言事实是否偷偷来自其他文件。
- 输入提供了公开 failure-mode taxonomy，包含正确机制及多个其他机制；不能把选择了正确候选本身当作 oracle 泄漏。
- 没有保存子 Agent 完整会话、继承上下文、工具访问、真实模型/采样参数、响应修改历史。日志也没有时间戳、请求/响应哈希或不可变接收副本，原脚本不在当次 source hashes 中。

原脚本仅靠文字禁止外部读文件：它不是 OS 隔离，也无法阻止外部 Agent 继承历史、访问 sibling requests 或自行读 oracle。文件中的限制文字只能证明要求过，不能证明遵守了。哈希也只能支持一致性检查，不能证明响应作者身份或对抗拥有同一目录写权限的操作者。

机器检查结果：`results/acceptance/bridge-audit-20261015/historical-artifact-audit.json`。这是事后检查，不能补造旧运行时缺失的访问记录。

## 影响公平比较的差异

| 因素 | 桥接 | API |
|---|---|---|
| 实际回答者 | 未认证的外部 Agent，标签 trae-subagent-bridge-v1 | deepseek-v4-flash-0731，经配置端点 |
| 总时限 | 7200 秒 | 早期 900 秒，后期 1800 秒 |
| 单次限制 | 协议写 180；原脚本默认 1800，实际 CLI 值未保存；轮询还先接收再判断超时 | HTTPX 原为分阶段超时，不是整个请求的硬截止时间 |
| 初始提示 | 原始 system_prompt/payload 加 dispatch 外层说明 | system_prompt 后追加 Schema 指令，payload 放入 user message |
| Schema | 原 Pydantic schema | 修复后强制列出全部字段 |
| 采样设置 | temperature=0 只是元数据，无法约束外部 Agent | 请求体明确 temperature=0 |
| 外部上下文/工具 | 只能由操作者遵守限制，无访问证明 | API 请求仅携带消息及参数；网关内部实现不在本仓库可见范围 |
| 请求用量 | 文件请求误记为 HTTP；token 未知 | 实际 API 请求；超时请求总 token 未知 |

桥接首个调用约 60.8 秒，结合首尾事件时间推算全程约 931.5 秒，长于旧 API 的 900 秒预算；其中一项 coordinator 调用约 181.1 秒。由于旧队列日志无时间戳、scope 未保存实际 call_timeout，不能确认它当次采用了默认 1800 秒；但协议中的 180 秒并未得到严格保证。

源码摘要对比显示：桥接与 `full-pre-wall-raise`、`full-pre-coordinate-retry` 的 src hashes 相同；与更早的 schema/verify 修复前运行存在差异。所以不能把所有旧 API 失败都解释为同一版本上的模型能力差异。

## 本次修复

1. FileQueueBridgeProvider 仅允许全新队列；每次运行有随机 session_id，响应必须绑定 request_id 和请求内容 SHA-256。错误绑定/格式立即失败，不再等待操作者反复编辑同一个最终文件。
2. 保存带时间、请求/响应哈希的日志，以及实际接收的请求和响应副本。外部回写须通过原子 rename；无日志时失败可见，不再静默丢弃日志。
3. 所有已经取得许可的超时、取消、STOP 和错误路径都结算未知 usage；token 完整性明确为 false。
4. bridge 请求保留 LLM 预算计数，HTTP 请求计为 0，另记 bridge_requests。
5. bridge 与 HTTP adapter 共用初始 messages 和 strict_schema；bridge 的一次结构修复与 legacy HTTP 的修复消息一致。外层 dispatch 仍是桥接执行说明，不能声称两种外部运行环境完全一致。
6. bridge 单次有效超时必须等于协议 request_timeout；原脚本的 1800 秒默认已移除。HTTP legacy/reliable 两路径增加整个单次发送的 asyncio 截止控制，避免只依赖 HTTPX 的分阶段超时。触发后会等待取消清理，返回异常的总耗时可能略长于配置值；不能保证远端停止生成或免于计费。
7. 拒绝正式实验及非 development_visible 的桥接协议；模型身份、温度、外部隔离均显式标为未验证。不能将元数据当成隔离证明。
8. 两个复测入口保存 src、scripts、configs、pyproject 的摘要及有效 provider 参数，结束时报告 source_drift。检测运行前后漂移，不能代替只读文件系统或侦测“中途改动后恢复”。
9. 修复报告将 predicted_observations 直接当 causal_chain 的缺陷：已观察序列改为带时间、证据 ID 的真实支持记录；预测单独显示为未确认观察。原桥接报告里后端延迟/错误率上升、连接池 timeout 等预测不能按已测事实引用。根因接受规则未放宽。
10. 修正旧问题文档以首次事件时间冒充运行起点的时限计算；900 秒那轮并没有提前约 22 秒耗尽预算。

这些修复处理了协议和证据报告漏洞，没有为桥接外部进程提供 OS 沙箱。使用拥有 oracle 访问权限的外部 Agent 仍不能获得正式盲测资格。

## 对照实验

### 相同输入的真实 API 探针

使用原桥接保存的三个请求：初始 coordinator `req-0001`、diff 分析 `req-0011`、Verifier `req-0012`。保留对应 system_prompt、user_payload 和动态 schema；走当前 HTTP 初始提示和 strict Schema，temperature=0，单次 180 秒，关闭探针内结构修复，每个输入一次。它没有运行整个工作流，也没有给 API 提供桥接答案。

第一组实测：

- req-0001：有效结构输出，INVESTIGATE，6,106 token。
- req-0011：有效结构输出，识别 backend_pool_config_regression，4,719 token；但仍要求再次取得已经包含在输入里的 diff，并追问更多旁证，存在重复调查倾向。
- req-0012：PROVIDER_TIMEOUT，未取得可分析的 Verifier 回答，用量未知。

共三次真实 HTTP 请求，已知 token 下界 10,825；总 token 和成本未知，不能将超时调用计为零消耗。两项成功证明 API 模型能够处理这些相同输入并识别机制；第三项失败发生在取得回答之前，不能据此评判 Verifier 推理能力。

产物：`results/acceptance/bridge-audit-20261015/same-input-api/`。该组有冻结摘要且运行中无源码漂移；它发生在本次 HTTP 硬截止时间补修之前，不能用来证明补修后端到端成功。

另对 Verifier 相同输入进行一次单独的补修后请求，仍为 PROVIDER_TIMEOUT，elapsed_ms 约 182,143，运行中 source_drift=[]。180 秒截止触发后 HTTP 取消清理还会耗时，不能将配置值解释为整个协程一定在 180 秒内返回。结果见 `same-input-api-verifier-final/summary.json`。这是有限追加的一次，不是反复运行后只挑成功结果。两组总计四次真实 HTTP 请求，只有两次取得回答，总 token 仍未知。

### 固定回答，替换适配器的离线对照

将原桥接 15 份响应按 role/schema 顺序送入 RealChatProvider 的 HTTP MockTransport，不调用网络。采用同一公开数据、原 run_id 和 900 秒预算，走当前图运行时、Schema 校验与接受守卫，结果为 15 次适配器请求、零修复、DIAGNOSIS_READY / SUCCESS。所有保存回答均用尽，未补造新的模型回答。

该实验只说明 HTTP 适配器与当前工作流能够接受这些回答并完成诊断；它不证明真实模型会独立生成相同序列，也不是逐字重现旧运行的全部中间 state。产物里的 actual_http_requests 是 MockTransport 的适配器尝试数；scope 和 live_http_requests=0 明确标示没有真实网络调用。

产物：`results/acceptance/bridge-audit-20261015/recorded-output-http-fixture/`。

修复后的 FileQueueBridgeProvider 也用同一套已保存回答完成全图离线重放：15 次 bridge 请求、0 次 HTTP、零修复，DIAGNOSIS_READY / SUCCESS。它验证了新响应 envelope、许可结算及统计路径，但没有执行新的外部 Agent。产物为 `fixed-bridge-recorded-output-fixture/`。

## 归因边界

可确认的非模型因素包括：原比较时限不等、桥接人工服务开销、新端点运输超时、阶段重试缺口，以及旧源码/适配协议差异。桥接历史时长本身就不满足旧 900 秒限制。

模型或解码设置可能改变任务选择、所需旁证和重复查询；本次真实 API 分析输出已经显示了重复索取已有 diff 的行为。但只有一组输入、少量样本，外部 Agent 身份/温度未知，Verifier 首次又超时，所以不能给出“换某模型即可成功”、模型能力排序或各因素贡献百分比。

要分离模型因素，应在开发集固定源码、公开数据、提示、动态 Schema、工具权限、采样设置及有效预算，用可认证的同一 API 执行通道比较模型，保留所有失败与重复运行。桥接仍可作为带明确限制的工作流诊断工具。

## 验证

新增 bridge 协议、用量、取消/STOP、并发请求 ID、错误响应绑定和一次修复测试；增加 HTTP 硬截止时间两路径测试，以及预测不再进入已确认报告的测试。

命令：

```powershell
.venv\Scripts\python.exe -m pytest -q -rs
.venv\Scripts\python.exe -m ruff check src scripts tests
git diff --check
```

验证过程保留：补修单次截止前曾全量 890 passed、3 skipped；补修后相关定向测试 39 passed。随后全量为 891 passed、3 skipped、1 failed，失败项是 UI 回放状态一致性；该项单独重跑 1 passed。那轮期间有并发的新结果文件写入，尚不能确认其因果关系。失败日志为 `pytest-final.log`；停止其他产物写入后的完整复跑日志为 `pytest-final-stable.log`，以该轮最终结果为准。Ruff 和 git diff --check 已通过。未提交、未推送；原有工作区修改保留。

最终静止复跑：**892 passed、3 skipped，229.75 秒**。三个跳过均因 Windows 符号链接权限不足。此前 UI 回放失败未在单独重跑和停止其他产物写入的全量复跑中复现；没有为此修改 UI 逻辑，也不能把其具体成因标为已证实。
