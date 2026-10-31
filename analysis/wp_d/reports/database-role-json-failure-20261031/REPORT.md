# database 角色 `INVALID_JSON` 根因分析（local-gateway-dev5-20261031）

分析时间：2026-10-31 15:4x（Asia/Shanghai）。对象：`results/v16/wp-d/local-gateway-dev5-20261031` 中全部 6 个失败槽位（slot-003/004/008/009/015/018）。本次分析只用**离线重放**：从失败 attempt 的 `trace.json` + `events-0001.jsonl` 还原该次 analyze 调用的完整请求体，直接对本地网关 `http://127.0.0.1:3425/v1` 重发。重放请求的 `prompt_tokens` 与原始记录**逐 token 一致**（2826 / 修复 2848），因此重放内容确认为原始请求本身。

## 结论

database 角色的分析调用不是"模型输出了坏 JSON"，而是**模型根本没有输出 JSON**：它把 system prompt 里的工具指令当成了一次真实工具调用，用 DeepSeek 原生工具调用标记 `<｜DSML｜>calls>`（`｜` = U+FF5C）写进了 `message.content`。请求里没有 `tools` 数组，网关也没有把这段标记翻译成 `tool_calls` 或按 `response_format: json_schema` 强制成 JSON，于是这段纯文本直接落到 `json.loads`，被判为 `INVALID_JSON`（phase=syntax）。

"一次修复后仍非法"不是修复逻辑出错，而是**修复本质上只是把几乎相同的 prompt 再发一次**：无效输出没有回传给模型，追加的只是一句通用提示，且 system prompt 里的工具指令原封不动。模型的主导行为不变，于是重复同一段 DSML。

## 一、直接证据（slot-018 精确重放）

失败调用：`task-3010-db-1`，logical id `logical-a37af05c40ff4c4c8f6f473f0c8cf9ea`，输入 1 条记录 `incident_3010-E-003`（postgres slow query，7700 ms，wait_event=CPU，无阻塞）。

重放得到的 `content`（`finish_reason=stop`，HTTP 200，未截断）：

```
<｜DSML｜> calls>
<｜DSML｜> invoke name="get_db_connections">
<｜DSML｜> parameter name="service" string="true">postgres</｜DSML｜> parameter>
<｜DSML｜> parameter name="start_ts" string="true">2026-10-12T08:45:00Z</｜DSML｜> parameter>
<｜DSML｜> parameter name="end_ts" string="true">2026-10-12T10:15:00Z</｜DSML｜> parameter>
<｜DSML｜> parameter name="limit" string="false">50</｜DSML｜> parameter>
</｜DSML｜> invoke>
... get_db_active_sessions / get_db_lock_waits / get_db_slow_queries / get_db_health_metrics 各一次
```

即模型把 system prompt 中列举的**五个工具全部调用了一遍**，参数 `service=postgres / start_ts=08:45 / end_ts=10:15 / limit=50` 也与 prompt 与该任务 filters 完全对应。这不是幻觉，是对 prompt 的忠实执行。

同一请求连续重放 3 次，3/3 都是 DSML；原始批次中该调用的第一次与修复各一次，也是 2/2 DSML。

模型返回的 `reasoning_content`（网关无视了请求中的 `thinking: {"type":"disabled"}`）直接写出了这次决策：

> "I have 38 tool calls remaining. Let me query the DB tools to gather more evidence. ... Should I call tools? The remaining tool calls exist."

## 二、机理

1. **analyze 的 system prompt 仍在命令模型调用工具。** `src/incident_lens/agents/database.py:3` 的 `DATABASE_PROMPT` 以祈使句开头："Inspect database internal observations with get_db_connections, get_db_active_sessions, get_db_lock_waits, get_db_slow_queries, get_db_health_metrics. All tools require service, start_ts and end_ts"。这段文本在 `plan_tools()` 里作为"怎么选工具"的说明是合理的，但在 `analyze()`（`src/incident_lens/agents/service.py:476`）里被原样复用——而 analyze 阶段**不允许**再调工具，只要求输出 `AnalysisOutput`。
2. **user payload 里还带着"还能调 38 次工具"的上下文。** `context` 是同一个 `AgentContext`，含 `allowed_tools` 五项与 `remaining_tool_calls`。模型据此判断工具有效。
3. **请求里没有任何 tools 声明。** `body` 只有 `model/temperature/messages/response_format/thinking`（`src/incident_lens/llm/provider.py` 中 `_reliable_call`）。网关（magpie，后端 `deepseek-v4.1-flash`）没有把 DSML 标记转成 `tool_calls`，也没有执行 `json_schema strict`；`finish_reason` 仍是 `stop`，所以截断探测也不会命中。
4. **校验只接受纯 JSON。** `validate_response()`（`src/incident_lens/llm/structured_output.py:121`）对 `content` 直接 `json.loads`，首字符 `<` 立刻抛 `JSONDecodeError`，`pos=0 < len` 且不是 "Unterminated string"，于是分类为 `INVALID_JSON`，phase=syntax。

对照实验（同一 payload、同一网关，各 1 次）：

| 变体 | 结果 |
|---|---|
| 原样 database prompt | `INVALID_JSON`，content 为 DSML，2086 字符 |
| database prompt + "Do not call tools. The records below are the only available observations; answer with the JSON object only." | **合法 JSON**，5357 字符 |
| 去掉 database 工具段落，仅保留通用 SYSTEM_PROMPT | **合法 JSON**，5338 字符 |

这说明触发点是**提示词里的工具指令**，不是 schema、不是记录内容、不是 token 上限（该模型 max output 384k，本次 completion 仅 700 左右）。

## 三、为什么"一次修复"救不回来

`provider.py:596` 的修复路径：

```python
messages.append({
    "role": "user",
    "content": repair_message(exc) if self.targeted_structured_repair
               else "Return valid JSON matching the supplied schema. One repair only.",
})
continue
```

问题有三层：

1. **无效输出从未回传。** `messages` 里只有 system + user + 新的 user 指令，没有那条 assistant 消息。token 证据：原始 2826 → 修复 2848，只多 22 token，正好是一句 `repair_message`，而不是 2000 字符的坏输出。
2. **system prompt 原样保留。** 模型仍然看到"用五个工具去查"，于是继续按工具调用作答。
3. **temperature=0 在这个网关上不保证可复现。** MoE/批处理导致同一 prompt 会重采样；`cached_tokens` 命中说明前缀相同。因此"修复"实际是一次重新掷骰子，而不是纠错。

全批次统计（`runs/*/attempt-*/observability/events-*.jsonl`）：

- `MODEL_FAILURE` 共 9 次，**9/9 都是 database 角色、都是 `INVALID_JSON`**；其他角色 0 次终态失败。
- database 角色发生 `STRUCTURED_REPAIR` 的调用 17 次：其中 **8 次修复后成功、9 次两次都失败**。约一半概率，符合"重采样"而非"修正"的判断。

## 四、为什么只有 database 角色

- **只有 database 的 prompt 是"祈使句 + 工具名 + 参数要求"的三连。** metrics 的写法是 "Allowed query_metrics(...)"，logs 是 "Allowed query_logs(...)"，changes 是 "Allowed query_changes(...)"；database 则直接命令 "Inspect ... with ..."，且把五个工具名与必填参数逐一列出。
- **database 任务经常在"缺口"上收尾。** slot-018 里 `get_db_lock_waits` 返回 NO_DATA，records 只覆盖 slow query 一项，而任务问题同时问了连接数、活跃会话、锁等待、慢查询、健康度。模型自然想"再查一次"，正好落进 prompt 的工具诱导。
- **planner 调用不受影响**：planner 的产出模型 `InvestigatorPlan` 本身就是"要调哪些工具"的 JSON，模型按 schema 输出即可，不会转成 DSML。所以同一角色 planner 大量成功、analyze 偶尔暴死。

## 五、建议修复（按性价比排序）

1. **analyze 阶段去掉工具指令（首选，已验证有效）。** 在 `analyze()` 里对 database 使用"分析版"提示词：保留判据（连接数 vs 上限、须有阻塞会话/时长、健康容量不能反证上游池配置故障、空证据=未知、可弃答），删掉"Inspect ... with <tool>"与工具参数要求，并明确 "No tools are available in this step; answer only from the records."。对照实验表明这一句即可让输出变为合法 JSON。
2. **修复要真正"修"。** 把无效的 assistant 内容追加进 `messages`（或至少附其前 2000 字符），并把诊断具体化：检测到 `<｜DSML｜>` 时直接说 "You attempted a tool call; tools are unavailable here; return the JSON object"。同时把 `remaining_tool_calls` 从 analyze 的 context 中去掉或显式置 0，避免"还能调 38 次"的误导。
3. **给 DSML 单独分类。** 在 `validate_response()` 里识别 `<｜DSML｜>`, `<｜tool▁call`, 或"content 以 `<` 开头且含 invoke" → 新类别 `TOOL_CALL_MARKUP_IN_CONTENT`（phase=syntax，repairable），日志里能一眼区分"格式错"与"模型想调工具"，也为后续把这类输出解析成 `requested_checks` 留口子。
4. **网关能力登记。** magpie 目前既不执行 `response_format: json_schema strict`，也忽略 `thinking: disabled`。若换成支持 `tools` 的通道，可把五个 `get_db_*` 作为真正的 tools 声明，让模型走 `tool_calls`，再由 runtime 决定是否执行；否则应在 `format_capability` 上标为"仅 json_object"或"无强制"，避免上层误以为有结构化保证。
5. **给 database analyze 增加一次"改写后重试"**（换 system prompt 而非原样重发），这比把 `structured_repair_retries` 从 1 提到 2 更有效；单纯加次数只是多掷一次骰子，期望失败率从 ~50% 降到 ~25%，而换 prompt 是直接消除触发条件。

## 六、复现方法

脚本与原始响应保存在 `%TEMP%\dbrole-repro\`（`payload.json`、`repro.py`、`probe.py`、`raw-attempt1.txt`、`probe-*.txt`）：

```
cd %TEMP%\dbrole-repro
python -I repro.py     # 原样重放 + 修复重放
python -I probe.py     # 三组 prompt 对照
```

脚本从仓库 `.env` 读取端点与密钥，不打印密钥；payload 取自 `runs/slot-018/attempt-001` 的 `trace.json` 与 `observability/events-0001.jsonl`。

## 附：涉及代码位置

- `src/incident_lens/agents/database.py:3` — `DATABASE_PROMPT`（工具祈使句）
- `src/incident_lens/agents/service.py:62` — database 角色提示词组装
- `src/incident_lens/agents/service.py:476` — `analyze()`：复用同一 prompt 与 context
- `src/incident_lens/llm/provider.py:596` — 修复消息追加（不含无效输出）
- `src/incident_lens/llm/structured_output.py:121` — `validate_response()` 语法判定
- `src/incident_lens/llm/structured_output.py:161` — `repair_message()`
- `configs/wp_d/api-runtime.yaml` — `structured_repair_retries: 1`
