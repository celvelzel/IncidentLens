# 探针结果：模型通道已恢复

2026-10-26 12:31（Asia/Shanghai）。参照 `next-api-max8-20261022-121153-console-investigation` 的失败文档，向同一 endpoint、同一模型发送一条独立探针，仅一次、无重试、不含项目数据。

## 结论

返回 **200**，不是 429。模型通道限流已解除，单请求形状下可用。

| 项目 | 本次（2026-10-26 12:31） | 上次探针（2026-10-23 10:39） |
|---|---|---|
| 状态 | 200 | 429 |
| 耗时 | 约 2.55 秒 | 约 2.32 秒 |
| 错误 | 无 | `Channel rate limit reached for model` |
| 内容 | `{"ok": true}`，finish_reason=stop | 无 |
| x-request-id | `req_79d51c40-affe-4f31-b049-a5dd9b63018e` | `req_230f4357-4108-47d7-939f-9785468ccb13` |

请求字段与冻结批次一致：model `deepseek-v4.1-flash-1017`、temperature 0、messages、response_format=json_schema、thinking disabled。endpoint `https://discovery-api.intern-ai.org.cn/v1/chat/completions`，经本机代理 127.0.0.1:7892（与冻结 provider 的 trust_env 路由一致）。usage：61 输入 + 6 输出 = 67 token。

## 本地环境差异（已记录，不影响结论）

本机 `NO_PROXY` 含带方括号的 `[::1]`，httpx 会将其转成无法解析的 `all://*[::1]` 并直接报 `Invalid port`，导致任何 trust_env=True 的 httpx 客户端构建失败。探针脚本仅把该条目去方括号（`::1` 仍正确映射为 `all://[::1]`），未改变对 API 主机的代理路由。原批次及 2026-10-23 探针未遇到此项，说明该环境变量是后来才出现的；正式补跑前需确认 worker 进程的 `NO_PROXY` 是否同样含 `[::1]`，否则 provider 侧 trust_env=True 的请求会整体失败。

## 边界

- 单次 200 只证明此刻单请求可用，不能证明限流规则已调整、阈值多大，也不能保证并发 8 的正式批次不会再次触发；历史 429 出现在远低于页面所示 RPM 的频率下。
- 未替换密钥、切换模型、改变服务商设置或修改冻结 provider；未重跑 slot，未联系服务商。
- 若要正式补跑，仍按原 console-investigation 报告的路径：先用独立诊断确认可用（本次已确认），再由用户规划正式补跑，并单独记录新实验条件。
