收件方：TokenPlan 支持 tokenplan@pjlab.org.cn（仅草稿，未发送）

主题：deepseek-v4.1-flash-1017 低请求频率仍出现模型通道 429，请核查具体规则

您好，控制台余额及 5 小时/7 天用量限额均充足，但模型 deepseek-v4.1-flash-1017 持续出现 429。此前执行批次包含重试的任意滚动 60 秒请求峰值仅 18 次，外部并发 1 也曾失败。

2026-10-23 10:39:12（北京时间；02:39:12 UTC）进行一次独立极小请求，仅要求返回 {"ok":true}，相同模型、OpenAI Chat Completions 接口、temperature=0、thinking disabled、json_schema，无重试。约 2.32 秒收到 HTTP 429，error.message 为 Channel rate limit reached for model。

x-request-id: req_230f4357-4108-47d7-939f-9785468ccb13

trace_id: b8d41907a49d6a541e3ab70d83298545

请协助核查：

1. 此次请求具体命中的通道限制是什么？计数维度、限制值、当前计数、重置时间分别是什么？
2. 是否存在该模型独立的短窗口、并发、上游容量或通道路由限制？通道是否跨账户共享？
3. 该通道是否有容量或配置异常，能否恢复或分配可用通道？
4. 建议的调用频率、全局在途上限、退避等待时间是什么？能否返回 Retry-After 及限流范围响应头？

谢谢。
