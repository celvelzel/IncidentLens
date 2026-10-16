# Codex 启动指令 — IncidentLens V1.6

请打开并严格执行同目录的 `IncidentLens_V1.6_Codex_MultiAgent_Implementation_Plan.md`。项目仓库是 `celvelzel/IncidentLens`，任务是 V1.6 End-to-End Validation, Benchmark & Investigation Replay。

**不要只复述/重写计划；现在开始实际操作。** 首先只读审计 HEAD、工作区更改、README、RCA 验收、IncidentBench/实验公平性协议、前端 Replay，执行 M0 的现有测试，落地 `docs/v16/status.md`、`ownership.md`、`contract-freeze.md`。然后按计划通过可用的多 Agent/子 Agent 功能并行开展：

- **WP-A**：真实 Provider E2E 正/负例（在用户批准真实 API 预算后运行；之前先完成全部离线验证和复测准备）
- **WP-B**：审计 20 Seed、设计并校验可信 Dev/Test 候选集和公开/私有标签隔离（不可伪造人工 reviewer 或独立家族）
- **WP-C**：复用当前 Web `/api/replay`，升级 Agent 协作交流、假设变化、证据追踪及播放界面（不得编造 Trace 事件）
- **WP-D**：公平 Single/Fixed/Dynamic/Full 协议与分析，先跑 Mock 回归；真实组间对照待 G1/G2 和费用批准
- **WP-E**：只读独立 QA

Lead 管理共享接口、各子 Agent 文件所有权/独立 worktree、集成 Gate 和最终结果。不得覆盖未提交内容、删除旧测试、绕过 FinalizeGate、向 Agent 泄漏 Oracle、静默替换 Mock/Real、将离线续接视为完整真实成功。每个工作包必须交付实际文件、更改、测试退出码、产物路径及证据级别。

开始时先给我 M0 实际审计及并行工作包启动状态；遇到付费 API、缺失独立人工审核或无法获取 private Oracle 的阻塞，只暂停依赖它的步骤，继续其他可完成任务，并明确列出需要我做的批准或人工操作。
