# IncidentBench 2026-10-14 修复与复测交接

> 迭代主线与当前验收边界见[统一迭代说明](acceptance/rca-retest-iteration-20261015.md)。本文保留该阶段证据；历史测试计数不代表后续版本的在线验收。

## 原始结果定位

输入目录：`results/incidentbench/v1/20261014-comp-deepseek-v4-flash-pilot-budget32-retest-900s`。

- `incident_2001.dynamic_no_verifier.repeat-0`：19 次调用后在 merge 阶段发生 `MERGE_FINDING_ID_COLLISION`，随后以 `UNRECOVERABLE_ERROR` 终止。不是预算或超时。
- 四个变体均未发布配置 diff `incident_2001-E-004`。已有 changes 查询把 `end_ts` 设为 12:00:00，而部署 E-003 发生在 12:00:10。日志没有 severity 元数据，ERROR 过滤也会得到空结果。
- Full 的中间修复试跑已经获取 E-003、E-004、backend pool_waiters 和 gateway 5xx；Verifier 判 sufficient，但仍携带称为可选 corroboration 的 requested_checks。候选保留早期 open_questions，竞争假设也没有得到共同证据下的重新评估。协调器选择正确根因，不代表运行时允许接受。

## 已完成修改

1. `agents/service.py`：验证身份与引用后，由运行时根据 Finding 的身份和内容生成 ID，避免模型复用 F1 等局部标签引发跨任务冲突；merge 的身份、引用和碰撞检查保留。
2. IncidentBench 首次 changes 发现移除模型猜测的时间及 change_type 过滤，保留 service，覆盖当前公开 incident 包。后续已发现 changes 的查询保留过滤。首次 logs 发现移除 severity/contains，保留 service、时间范围和 limit。旧工作流不启用这些发现规则。
3. `graph.py`：IncidentBench 的 query_changes 若只占一个工具槽位，可使用同次查询返回的真实 change_id，在原有两次工具调用额度内获取 diff。所有调用仍走 registry/ACL/预算/事件记录。
4. 协调器收到实际 query_history 摘要，包含执行参数、返回 ID 和错误码，不含原始记录 excerpt。
5. `CoordinatorDecision.hypothesis_updates`：允许 IncidentBench 协调器重新评估现有假设。生成 schema 限制假设 ID 和公开引用 ID；运行时验证原因身份和引用权限。无引用的 SUPPORTED/REJECTED 状态降为 OPEN，与 merge 的规则一致。
6. 假设发生变化后，Full 必须重新审查，不能使用旧快照的接受结果。仅由旧 FINALIZE_REJECTED 产生的过期错误可在重新评估后清除；其他共享问题仍保留。
7. `Review.optional_checks`：区分非阻塞补充验证与 requested_checks。新的生成 schema 拒绝 sufficient 同时存在阻塞检查或矛盾，真实 provider 可走原有结构化修复。历史 Review 合约仍可读取旧记录。
8. Fixed IncidentBench 保留一次固定专家调度，完成后增加共同证据下的终局协调调用。若仍需调查则正常弃权，不追加专家任务。
9. 说明部署前的健康基线不能机械地作为部署后故障的 against_ids；是否移除仍由证据下的模型评估决定。根因接受守卫未放宽。
10. 复测脚本支持 `--variant full|dynamic_no_verifier|single|fixed`，并支持带 UTF-8 BOM 的原 protocol。

## 验证边界

- 最后一次相关测试：`37 passed`（agents、graph、review boundary、真实 adapter 的 HTTP fixture）。包括跨任务 Finding ID、同任务有界 diff 获取、更新引用/身份约束、重新审查快照、可选检查和公开查询范围等。
- Ruff 与 git diff --check 通过。
- 中间版本曾全量 `876 passed, 3 skipped`；这发生在最终状态协调扩展前，不能当作最终版本全量通过。
- 用户要求停止时，全量测试已输出 `878 passed, 3 skipped, 1 failed`。失败是 `test_graph_exception_keeps_known_failure_denominators` 的 `benchmark lock drift`；该轮运行期间源码仍在变更。尚未在静止的最终源码上重新执行确认，不能标记最终全量通过。进行中的真实 dynamic_no_verifier 复测已停止，用户自行复测。
- 中间真实试跑未再出现 Finding ID 碰撞，但仍有正常弃权；Fixed 的一次试跑仍把部署前 HTTP 200 放入候选 against_ids，守卫拒绝了定案。最终版本四个变体的根因恢复率尚未验证。
- 中间试跑：`results/incidentbench/v1/20261014-evidence-discovery-fix` 和 `results/incidentbench/v1/20261014-evidence-reconciliation-v3`。中断的 dynamic_no_verifier 目录只有范围记录和中断标记，不是完整结果。
- 新增终局协调调用和提示/合约改变，复测必须保存新的 source hashes，不能与原始冻结运行混作同一实现。

## 复测命令

先运行最终代码的全量回归：

```powershell
.venv\Scripts\python.exe -m pytest -q
```

以下为一个真实 Full 定向复测。替换 variant 和输出目录即可分别检查其他变体；请使用全新的输出目录：

```powershell
.venv\Scripts\python.exe scripts\retest_live_provider_fix.py --dataset results\incidentbench\v1\20261013-deepseek-development-pilot\dataset --protocol results\incidentbench\v1\20261014-comp-deepseek-v4-flash-pilot-budget32-retest-900s\pilot-protocol.json --incident incident_2001 --variant full --out results\incidentbench\v1\user-retest-reconciliation\full
```

负例使用 `--incident incident_2002` 和另一输出目录，检查是否仍能正确弃权。此脚本使用公开 evidence pack，不加载私有 oracle；结果中保存 source hashes、trace、report 和 usage/termination verification。

优先检查：无 MERGE_FINDING_ID_COLLISION；查询获取 E-003/E-004；有无 HYPOTHESIS_RECONCILED；Full 更新后有新 REVIEW；optional_checks 不成为阻塞；部署前健康基线是否仍被错误保留为反证；负例有没有因新提示产生错误定案。
