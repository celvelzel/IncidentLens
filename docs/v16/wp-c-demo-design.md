# WP-C：真实调查回放设计

本次扩展沿用现有 Starlette + 原生 JavaScript Dashboard。目标是解释一条真实录制的调查路径，不重新运行 LLM，不修改推理、Provider、Oracle、FinalizeGate 或评分。此前 `status.md` / G3 / QA 文档保留为历史记录；本次已有 T5 产物不追溯改变此前的验收结论。

## 界面与事实边界

页面分为播放器、共享状态工作流、当前事件、假设演化、Verifier / FinalizeGate、可靠性时间线及原有详情标签页。演示模式只放大文字并展开章节、假设和审查面板；普通回放仍可折叠使用。档案库每行提供“演示回放”。支持首步、上一/下一步、播放/暂停、1×/2×/4×、范围 seek、数字 Jump、分类导航及语义书签。

所有调查面板都由 `replayPrefix(trace, N)` 重建。初始只使用公开事故摘要、身份、预算和最终证据索引作为授权参照；最终索引不会自动成为已观察证据。工具成功、角色/工具/来源、事故、服务及完整记录一致后，证据才在前缀中可见。历史 Finding 按 ID 合并；假设只在 `MERGE` / `HYPOTHESIS_RECONCILED` 提交，`DECISION.hypothesis_updates` 明确标为提议。相同输入与位置产生相同投影。

报告及完整 Trace / Markdown 下载只在对应 `REPORT` 事件之后显示。任何 seek 或播放推进都会关闭并清空 Evidence Inspector，防止前一步打开的未来证据停留在更早的位置。网络中的完整录制是回放输入；这不是对拥有该录制文件的用户实施加密访问控制。

## 真实协作展示

工作流展示真实 Coordinator assignments、专家 task/attempt 状态、Shared Findings、Hypotheses 和 Verifier 建议。角色选择显示实际任务、结果及证据。记录存在但未执行的审查建议另标“仅审查建议 · 未调度”；尚未开始的真实 dispatch 标“已调度 · 尚无执行记录”。不生成 Agent 聊天气泡或隐含推理。

T5 的实际执行角色是 Coordinator、Metrics / Dependencies、Changes、Database、Verifier。Logs 仅出现在 Verifier 的建议中，没有 Logs 任务执行或 `query_logs` 调用，不能称其发现了超时日志。Provider recovery 按 `MODEL_RECOVERED.call_ids` 关联既有失败，不按相邻事件配对。模型请求包含成功 `LLM_CALL` 和失败 `MODEL_FAILURE`；调查轮次只计 `INVESTIGATE`，与 FINALIZE 决策数区分。

Evidence Inspector 保留原始 Evidence ID、公开源路径、事故观测时间、首次来源 Agent、查询执行时间、工具/任务/调用、后续检索记录，以及当前前缀中的 Finding / Hypothesis 关系和报告引用。事故时间为 10 月 1 日、调查执行时间为 10 月 16 日，两者不混淆。不额外读取来源文件或 Oracle，不对缺失原文做补写。所有不可信文本均安全转义。

## 只读 API 合约扩展

当前用户授权覆盖必要的只读 API 适配，因此扩展历史 WP-C“无后端变更”范围：`POST /api/replay` 保留原有字段，新增 `replay_metadata`。只读取同目录固定名称 `scope.json`、`result.json`、`verification.json`；不跟随产物内的路径或任意 protocol/private 文件。读取沿用 results 目录与所有祖先链接/reparse 检查，大小上限 2 MB。

只返回白名单字段；scope 必须匹配 incident / variant，protocol 必须匹配 provider / model；展示 verification 还要求同目录 result 与 Trace report（含 run / incident）完全一致。不直接返回 source hash 字典、私有路径或验证对象。缺失/损坏/不一致的 companion 给出 unavailable 警告，不影响有效 Trace。Trace 形状或 JSON 损坏返回受控错误。

这些 companion 是内部一致性元数据，不具备签名真实性保证。页面明确将其标为“独立最终产物元数据快照”，不充当历史调查状态。T5 的 `source_unchanged=false` 与 `graph.py` 漂移有常显提示，不能称为冻结正式实验；token / cost / elapsed 未记录时维持 unknown。未记录或未知 provider 不推定为 REAL。

## 视觉与交互

保留现有语义颜色、字体、卡片、focus 样式、浅/深色主题和原生按钮/披露控件。通过 ui-ux-pro-max 的 keyboard focus / disclosure 指引核查可见焦点与遮挡；窄屏按钮换行、控制条可换行、长 ID 可折行，演示模式无需动画。实际浏览器验证包括 reduced motion、1440×1000、390×844、844×390；未宣称完成屏幕阅读器或所有设备审计。
