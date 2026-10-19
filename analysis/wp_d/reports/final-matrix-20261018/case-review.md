# 最终案例结果核查

12 项均有终态产物；8 项正常完成，4 项运行失败。6 项案例通过（4 项根因正确、2 项正确弃答）；2 项错误弃答。参考标签仍为 candidate，未进行逐句事实审查。

| Slot | 案例 | 架构 | 案例判断 | 终止原因 |
|---|---|---|---|---|
| 1 | incident_1002 | full | 根因正确，通过 | DIAGNOSIS_READY |
| 2 | incident_1002 | dynamic_no_verifier | 根因正确，通过 | DIAGNOSIS_READY |
| 3 | incident_1001 | fixed | 根因正确，通过 | DIAGNOSIS_READY |
| 4 | incident_1003 | full | 运行失败，未通过 | BUDGET_EXHAUSTED |
| 5 | incident_1001 | dynamic_no_verifier | 错误弃答，未通过 | INCONCLUSIVE |
| 6 | incident_1002 | single | 根因正确，通过 | DIAGNOSIS_READY |
| 7 | incident_1003 | fixed | 正确弃答，通过 | INCONCLUSIVE |
| 8 | incident_1001 | full | 运行失败，未通过 | BUDGET_EXHAUSTED |
| 9 | incident_1002 | fixed | 错误弃答，未通过 | INCONCLUSIVE |
| 10 | incident_1003 | dynamic_no_verifier | 正确弃答，通过 | INCONCLUSIVE |
| 11 | incident_1001 | single | 运行失败，未通过 | UNRECOVERABLE_ERROR |
| 12 | incident_1003 | single | 运行失败，未通过 | UNRECOVERABLE_ERROR |

研究假设：尚无证据证明 full 整体优于 dynamic_no_verifier。误导案例两者均成功；普通案例 full 预算失败、无 Verifier 错误弃答；证据不足案例 full 预算失败、无 Verifier 正确弃答。
slot 11 的末次运行错误为 PROVIDER_TIMEOUT；slot 12 虽有 Provider 超时，但末次运行错误为 PermissionError，不能全部归为网络问题。
slot 5 由 final-selection.json 显式指向 retry-02，保留真实 run_id 和原冻结排期。前两次网络中断由用户确认，已排除最终统计；原始目录删除遭自动审批策略阻止，仍保留。
全部 12 项保存的 source_unchanged 和 protocol_valid 均为 true；这些是运行时记录。另对本次处理前后 659 个受保护源码、配置、数据及保留产物文件进行了哈希核对，均未改变。
未知 token / 金额仍为未知；未重新调用模型。

后续日志核查更新：Windows 电源事件与 slot4/8 待机及唤醒失败时间吻合；slot12 的日志文件替换 PermissionError 候选路径已离线复现。详见 ../runtime-audit-20261018/report.md。用户重新授权后删除 slot5 前两次目录仍被审批策略阻止，目录和原日志未删除。
