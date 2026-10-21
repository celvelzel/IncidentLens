# ChatGPT 账号额度路径：Codex 订阅接入及可行性 — 2026-10-21

## 当前结论

指定模型严格固定为 `gpt-6-luna-light`。当前状态为
`BLOCKED_EXACT_MODEL_NOT_AVAILABLE_FOR_CHATGPT_LOGIN`。

官方支持使用 ChatGPT 登录的 Codex CLI/SDK 进行程序化调用，此时走 ChatGPT/Codex
订阅用量，而不是把订阅余额变成普通 API Platform 余额。普通 OpenAI API 的鉴权及计费
仍独立；不能拿 ChatGPT OAuth token 当作 Platform API key。本实现不提取 auth.json
或浏览器 Cookie，不调用私有逆向端点，也不提供订阅到通用 API 的转发代理。

官方来源（本轮已实际读取）：
- https://learn.chatgpt.com/docs/auth （ChatGPT 订阅认证与 API key 按量认证；一般 API 使用 Platform key）
- https://learn.chatgpt.com/docs/non-interactive-mode （codex exec、缓存登录、JSON Schema、JSONL 事件）
- https://learn.chatgpt.com/docs/pricing （订阅使用量与 API token 价格分离）
- https://learn.chatgpt.com/docs/config-file/config-reference （forced_login_method、model_instructions_file、工具开关）

## 指定模型探测结果

本机 `codex-cli 0.154.0`，`codex login status` 显示 Logged in using ChatGPT。
未读取账户身份、密钥或认证缓存内容；此记录不证明 API Platform 有余额，也未读取具体订阅扣减。

收到指定模型指令后只进行了 1 次极小合成探测，精确传入 `--model gpt-6-luna-light`。
服务端 HTTP 400 返回：

> The 'gpt-6-luna-light' model is not supported when using Codex with a ChatGPT account.

因此当前不能宣称此指定模型可通过本账号 Codex 订阅运行，也不推断其普通 Platform API
是否可用。没有将模型改成近似别名、没有回退、没有换认证方式、没有再发其他模型请求。
CLI 的 unknown-model fallback metadata 警告只是本地元数据回退，不能据此认定实际模型回退；
后端拒绝了该精确模型名。本实现自身禁止任何模型替换。

证据：`results/acceptance/codex-subscription-luna-light-feasibility-20261021/` 下的
feasibility.json、acceptance-summary.json 以及 calls/*/startup-diagnostic.json。
正式事故调查 0 次，正式四架构矩阵 0 次。

## 历史探测与适用边界

指定模型指令之前曾做 7 轮小型接入排障，共 8 个 CLI 调用尝试（HTTP 物理请求数未知）：
前三轮所用文档示例模型被服务端拒绝；中间三轮得到正确输出，但因主动禁用 code-mode host
产生的诊断 item 被严格事件校验拒绝；修正配置冲突后，第七轮两项合成探测通过。
该轮使用的是先前模型，只证明订阅接入机制在当时条件下可工作，不是新模型 readiness。
保留全部历史，不把旧成功结果改写为 `gpt-6-luna-light` 成功结果。

第七轮两项分别为 schema JSON 算术回复、项目实际任务权限约束工具计划；所提工具未执行。
CLI 报告的两次 token 总和为 11806，仅是这两次已记录 turn 的用量，不是全部排障消耗、
订阅 credits 或 API 账单。当前所有成功放行检查要求 receipt 中模型与指定模型精确一致。

## 实现文件与调用边界

- `src/incident_lens/llm/codex_subscription.py`：实现项目 LLMProvider 接口。
  只接受 gpt-6-luna-light；官方 CLI 复用自身 ChatGPT 登录，强制 chatgpt auth；
  子进程移除 Platform API key、CODEX_API_KEY 和项目 API 凭据，不加载用户 config。
  每请求新建 ephemeral 会话及独立空工作目录；禁用 shell、MCP/apps/plugins、浏览器、
  子 Agent 等工具来源；替换基础 instructions，避免载入项目 AGENTS.md；输出 Schema
  强约束及本地 Pydantic 校验，事件中非消息项拒绝接收。
- `scripts/probe_codex_subscription.py`：默认只检查登录，显式 --run-feasibility
  才最多进行两个合成请求；失败即停止，不调用事故工具或 Oracle。
- `scripts/run_codex_subscription_case.py`：未来单案例开发入口，需要
  --execute-development-case、匹配协议以及同模型成功可行性 receipt。该入口本轮未执行。
- `configs/wp_d/codex-subscription.json` 与 codex-subscription-protocol.json：
  当前及后续账号订阅路径均固定为指定模型；不影响另外两套既有 bridge/DeepSeek 配置。
- `tests/integration/test_codex_subscription_feasibility.py`：离线传输与模型锁定检查，
  不启动 CLI、不调用模型、不运行事故调查。

输出字段区分真实远程 Codex 服务、普通 API、文件队列桥接。CLI 不暴露的温度、实际模型
快照、底层 HTTP 重试、credits 扣减和费用保持未验证/unknown。actual_http_requests=0
仅指 Python 适配器没有直接发送 HTTP，不意味着 Codex 没有联网；underlying_http_requests
为 null。CLI 报告 token 放在独立字段并保留已知下界，不能冒充完整 API 请求账单。
独立空目录与事件检查不是完整 OS 数据隔离证明；不能以此宣布严格 G1a/G4 或盲测通过。

## 后续命令（不启动正式测试）

```powershell
$env:PYTHONPATH = Join-Path $PWD 'src'
# 零模型请求，仅登录方式检查；使用新输出目录
.venv/Scripts/python.exe -B scripts/probe_codex_subscription.py --out results/acceptance/codex-auth-UNIQUE
# 只有获得该精确模型的访问后，才重新做小型探测；不自动换模型
.venv/Scripts/python.exe -B scripts/probe_codex_subscription.py --out results/acceptance/codex-luna-probe-UNIQUE --run-feasibility
```

后续完整实验必须先拿到 gpt-6-luna-light 自身的成功 receipt，再冻结对应源码、CLI 版本、
配置、数据和运行顺序；另行批准和启动。保持当前模型锁定，不用历史其他模型结果解锁。
本轮没有修改 ChatGPT 登录、没有购买额度、没有启动完整实验、没有提交或推送。
