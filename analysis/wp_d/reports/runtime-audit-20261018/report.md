# WP-D 运行错误日志核查

## 核查结果

本批最终选定的 12 个运行共记录 215 次 HTTP 请求；MODEL_FAILURE 事件为 27 次 PROVIDER_TIMEOUT、2 次 PROVIDER_HTTP_ERROR、2 次 BudgetExceeded。运行级失败是 4 次，不是 31 次；单次调用失败可以被恢复或在其他调查分支仍得到足够证据后完成。保存的 recovered_model_failure_count 合计为 18；不要把剩余事件直接等同为失败案例。

核查使用 trace、observability 原始事件、scope 和 Windows System 电源日志；被检查的 budget / observability / graph / provider / runtime 五个源码文件与全部 12 次运行保存的哈希一致。本次没有修改运行源码、配置、数据，没有调用 Provider。

## Slot 4：电脑待机导致等待停顿，唤醒后触发本地总预算

- 请求意图：2026-10-17 19:24:07（北京时间）。
- Windows Kernel-Power 506：19:25:51 进入新型待机，原因 Screen Off Request。
- Windows Kernel-Power 507：22:38:22 退出新型待机，原因 Input Mouse。
- 模型调用取消及 BudgetExceeded：22:38:22，与唤醒时间吻合；请求记录耗时约 194 分钟。
- 原配置为单次请求 420 秒、总运行 5400 秒。预算/超时依赖本进程执行；设备待机时无法按常态及时调度取消，唤醒后才完成失败处理。

结论：电源日志与超长日志空窗及失败时刻高度吻合，支持待机是超长等待及预算耗尽的重要直接因素。此前两次 Provider 超时也是真实记录，但不能把最终失败仅归咎于提供方。输出 INCONCLUSIVE 与案例方向一致，正常弃答流程仍未通过。

## Slot 8：同样与新型待机精确吻合

- 最后一个正常进展事件：2026-10-18 15:14:08（北京时间）。
- 15:15:22 系统进入新型待机，原因 Screen Off Request。
- 16:49:34 系统因鼠标输入退出待机。
- 同一秒模型请求记录 BudgetExceeded / wall_budget_exhausted；没有正常完成普通案例诊断。

结论：该运行不能用于论证 Verifier 降低或提高诊断质量，受到设备待机这一外部运行条件影响。

## Slot 11：协调阶段连续两次请求超时，重试耗尽

coordinate-4 的第 1 次和第 2 次尝试分别约 422.48 秒、422.87 秒后报 PROVIDER_TIMEOUT，随后终止。这与配置的 420 秒请求上限吻合，说明重试确实执行过，不能说完全没有重试。

PROVIDER_TIMEOUT 由本地 HTTP 客户端异常转换产生，证明客户端在截止时间内未取得完成响应，不证明供应商内部故障、具体网络根因或限流。保存的日志不足以区分网络链路、服务端排队、生成过慢。没有 HTTP 429 证据可直接归因为限流。

## Slot 12：超时后本地 PermissionError 打断重试，日志落盘是高置信候选路径

末尾顺序：MODEL_FAILURE(PROVIDER_TIMEOUT) → MODEL_WAIT_ENDED → TASK_FAILED → RUNTIME_ERROR(PermissionError)。任务记录仍为 coordinate-4 第 1 次失败，没有第 2 次 TASK_ASSIGNED。

TaskManager.fail 同步发出 TASK_FAILED；RunJournal.event 先 append/fsync 事件，再原子替换 status.json。替换失败会从 fail() 内直接抛出异常，跳过 retry_transient 后续的重试判断，覆盖原先的超时异常。

离线复现：使用 Windows CreateFileW 打开临时复现目录中的 status.json、不给 FILE_SHARE_DELETE，再执行真实 TaskManager.fail → RunJournal.event。成功重现 PermissionError(WinError 5)，TASK_FAILED 已落盘、任务仍可重试，但 fail() 已抛异常。这与 slot12 的边界顺序一致。

限制：历史错误被 safe_error 脱敏为异常类型，没有堆栈、文件路径或 WinError；不能证明历史现场一定是 status.json，也无法确认占用者。不要将其解释为模型越权调用工具，亦不能把 slot12 全部归为网络故障。

## 为什么容易出现多次运行错误

1. 两个运行受到设备新型待机影响，进程内超时无法在设备暂停期间正常执行。
2. 请求超时确实较多：27 次，通常约 420 秒。Provider recovery 的传输恢复模式本轮全部关闭；但 workflow 层仍有任务重试，两者不能混淆。slot11 重试两次仍超时，因此关闭传输恢复并不是它必然失败的充分原因。
3. 日志落盘与业务运行同步绑定；本地文件替换异常可以中断业务重试。slot12 的候选机制已离线复现。
4. 未知异常日志只保留类型，缺少安全堆栈和 winerror，导致历史归因不完整。

建议下轮真实实验先防止系统自动睡眠/新型待机；修复日志原子替换对短暂文件占用的处理，并在本地受控诊断记录中保存脱敏堆栈、errno/winerror。随后统一重跑受环境影响的单元。不要仅增加预算，也不要在不同架构间采用不同重试配置。本次仅核查，未实施这些运行代码/系统设置变更。

## Slot 5 最终结果及清理状态

第三次运行 run-05-incident_1001-dynamic_no_verifier-retry-02 是唯一最终结果，运行 ID 为 run-dc205fd008f64dfeb4e597a53a422e5b；正常完成但错误弃答。final-selection.json 由 summarize.py 读取，汇总保持 12 个单元、slot5 一行。

用户再次明确授权删除前两次目录及其失败记录和日志。本轮执行了带绝对路径边界校验的 PowerShell 删除命令，但自动审批仍返回 blocked by policy。命令未执行，两个目录及其日志未删除。本次没有换用其他删除机制绕过拒绝。旧日志保留只因该阻止；最终统计已不读取这两个运行。

证据：audit.json、windows-power-events.json、permission-reproduction.json、reproduce_journal_permission.py。
