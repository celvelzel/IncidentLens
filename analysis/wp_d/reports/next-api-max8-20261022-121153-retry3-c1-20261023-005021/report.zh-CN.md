# 并发 1 单槽补跑结果

2026-10-23（Asia/Shanghai），仅 slot-001 / incident_3010 / dynamic_no_verifier 新增 attempt-004，外部槽位并发 1；未启动其他 slot，未追加第二次调查。

冻结模型 deepseek-v4.1-flash-1017、提示词、预算、内部重试、任务派发行为保持原配置。仅新增分析侧编排脚本及产物，保留历史 attempt。

运行约 119.47 秒，共 7 次 HTTP 请求、3 个逻辑结构化调用、4 次传输重试，已上报 tokens 5,077（下界）。第一次 coordinate 成功；dispatch 中两个逻辑调用均收到三次 HTTP 429 / rate_limit_exceeded，按 2 秒、4 秒退避后以 transport_retry_limit 终止。最终 UNRECOVERABLE_ERROR / FAILED / runtime_failure=true，工具调用 0。

外部槽位并发 1 不等于整个流程只允许 1 个 HTTP 在途请求；本次日志显示 dispatch 两个逻辑调用交错进行。按用户要求保留冻结内部行为，没有修改此并行策略。现有证据仅能确认 API 通道限流，不能确定 RPM/TPM、额度、账号共享或上游容量原因。

224 项冻结输入一致、原始 batch-manifest 不变；补跑前全部 61 个历史 attempt 目录树一致，selection_valid=true。该失败尝试不替换原结果，最终仍为 30 个正常完成、10 个技术失败。

后续应先核查服务商限流类型和账户额度；继续将外部槽位并发从 1 下调已无空间。若要限制 slot 内部请求并发或改变退避策略，需要另行授权并明确与冻结协议的差异，本轮未执行。

审计详情见 retry-manifest.json、retry-state.json、final-selection.json，以及结果目录 runs/slot-001/attempt-004/verification.json。
