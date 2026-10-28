# 按有限材料选择最合理根因

用户授权降低根因接受要求，并用 incident3007 真实模型验证。

本次将接受标准改为 BEST_SUPPORTED_AVAILABLE：至少两个不同来源的观察，包含原因机制及其之后/同时的日志或指标佐证；实际反证、未观察引用和有证据的竞争机制仍阻断。未回答的问题不自动阻断，也不再要求 supported finding 标签、预测清单、精确 request/session 关联或完整时间序列。模型仍须明确 FINALIZE，不把旧的 ABSTAIN 自动转换为成功。

Full 仍需匹配当前候选及证据快照的独立复核，sufficient 或明确 leading endorsement 可支持“最合理根因”的接受；实际矛盾、conflicted 和 leading_blockers 均不能被忽略。缺失的直接关联保留为报告 causal_limitations 或 optional_questions。

RCAReport 新增 acceptance_standard 与 causal_limitations；报告和页面显示“已确定：现有证据最支持”，不表示所有因果链已直接证明。历史数据默认无此标准，不改写历史报告。

验证使用 gpt-5.6-luna / low，四组各一次，预算不变。Single、Fixed、Full 接受 postgres_lock_contention 并匹配 provisional 参考答案；无 Verifier 因 CODEX_PROCESS_FAILED 未完成最终结论。未自动替换失败。全批 61 次模型调用、44 次工具调用，观测 token 下界 416,601。

源码在批次运行中冻结；四组终态并锁定原始工件后评分。24 个原始工件哈希再次核对一致。按此前用户要求跳过离线回放；Python 编译、Ruff、JavaScript 语法及 diff 检查通过。没有声称已跑完整回归测试。

结果目录：results/timing/dev3007-20261027-best-supported-01。启动日期为 2026-10-27，报告日期为 2026-10-28。

本次改进接受口径，不能将新旧接受率差异当作新增因果证据或模型能力提升。Single、Fixed、Full 都命中，不支持 Full 正确率优于其他正常完成组。
