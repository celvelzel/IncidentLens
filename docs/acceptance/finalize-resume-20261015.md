# FINALIZE 更新后审查的收尾修复

> 迭代主线与当前验收边界见[统一迭代说明](rca-retest-iteration-20261015.md)。本文保留该阶段证据；历史测试计数不代表后续版本的在线验收。

## v4 判断核验

来源：`results/incidentbench/v1/user-retest-reconciliation/real-v4-wall3600-req300/full/trace.json`。原始运行和失败产物保持不变。

- event-92：Verifier 首次 sufficient。
- event-97：Coordinator 决策 FINALIZE，同时更新根因及竞争假设。
- event-98：运行时合并这些更新。因此旧审查快照失效，重新审查是必要步骤。
- event-104：Verifier 再次 sufficient；引用、候选与证据快照、竞争假设和共享问题均满足现有 finalize_errors。
- 随后却回到 coordinate-5，model-call-24 和 25 分别约 302 秒超时，最终 UNRECOVERABLE_ERROR。

因此最后交付中断确实由运输超时触发，同时暴露了多余模型决策的工作流缺陷。不能据此归结为整个模型没有能力；也不能推断端点具体为什么挂起，客户端日志只有超时证据。原运行产生了 INCONCLUSIVE 报告，准确说法是“没有交付成功的 RCA 报告”，而非完全没有产物。

## 修改行为

在 full 模式重新审查返回后，仅当已有最近的 FINALIZE 决策、审查对象与该决策一致、运行仍处于 RUNNING 且所有既有定案守卫通过，直接路由到确定性的 finalize 节点。记录 FINALIZE_RESUMED_AFTER_REVIEW，关联原决策索引和新审查事件。

不生成新决策，不跳过重新审查，不把运输错误转成成功，也不更改正常调查的协调路径。finalize 仍执行请求、token 与剩余墙钟预算审计；single/fixed/dynamic_no_verifier 路径保持原行为。新事件纳入停止协议的冻结后禁止发布集合。

责任实现：`orchestration/guards.py`、`orchestration/graph.py`、`evaluation/termination.py`。

## 验证与边界

定向回归 38 passed；覆盖“第二次 FINALIZE 模型调用一定超时”的完整故障场景，以及无 FINALIZE、审查不足、不同目标、阻塞检查、矛盾、无引用、快照漂移、竞争假设未解决、STOP、过期预算和其他变体。Ruff 通过。

真实 v4 状态的离线实验从 event-104 延续：保留该点以前的事件、证据、任务状态及23次调用，按历史调用推算剩余总时限；使用禁止任何模型调用的 Provider，经过原 finalize、stop、report 后得到 RESOLVED / DIAGNOSIS_READY / SUCCESS，protocol_valid=true。历史两次专家失败和一次 Verifier 恢复仍保留，不删除失败分母。

这是取证用的离线状态延续，不是生产断点续跑接口、不是新模型输出、不是一次新的完整真实 API 成功。未执行新的真实 API 请求。原始运行仍为失败，未被重新标记或覆盖。

产物：`results/acceptance/finalize-resume-20261015/checkpoint-continuation/`。其中 verification.json 保存原 trace 的 SHA-256、源码摘要、原事件前缀完整性和零新增 HTTP 请求标识；continue_checkpoint.py 可重现该取证过程（输出目录必须不存在）。

全量回归命令：

```powershell
.venv\Scripts\python.exe -m pytest -q -rs
.venv\Scripts\python.exe -m ruff check src scripts tests
git diff --check
```

全量日志：`results/acceptance/finalize-resume-20261015/pytest-final.log`。未提交或推送，保留其他 Agent 的未提交修改。

最终全量结果：**914 passed、3 skipped，372.85 秒**。三个跳过均为 Windows 符号链接权限不足。Ruff 与 git diff --check 通过。
