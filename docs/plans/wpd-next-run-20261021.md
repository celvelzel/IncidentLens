# WP-D 下一轮运行准备与稳健性改进 — 2026-10-21

状态：实现与静态检查阶段；未执行单元测试、集成测试、故障注入、桥接实验或真实 API 请求。
不做阶段收尾、演示、发布或严格 G1a/G4 验收。改动未经过运行验证，不能保证下一轮无故障。

## 1. 已有结果的检查结论

详见 `analysis/wp_d/reports/retained-trace-review-20261021/findings.md`、
`per-run.csv`、`inspection.json`。这些是读取旧 trace 的分析，不是新测试。

保留结果为 8 次根因匹配、4 次正常弃权。Full/Single/Fixed/NoVerifier 的请求数为
67/52/26/48，工具数为 51/44/23/34。Full 未观察到额外质量收益，不能假设下一轮必须获胜。
8 次根因匹配均有已观察的变化及配置差异支持；6 次报告对至少一个竞争假设的排除理由偏弱。
拓扑中的“无下游依赖”不能证明该服务健康；支持一个机制的配置变化也不等于反驳所有其他机制。
这次审查属于工程语义核查，不是独立双人标注，也不把原始报告改成经过完整人审的 Grounded RCA。

## 2. 下轮案例与评估规则

两套方案均使用完整既有 Dev10（incident_3001–incident_3010），四组，一次重复，40 槽位。
只根据原有挑战标签选择，不根据下一轮结果挑选样本或修改参考标签。

- 3001/3006：普通病例；3002/3007：误导变更；3003/3008：关键证据缺失。
- 3004/3005：相似表象下池配置与数据库容量的反事实配对。
- 3009/3010：数据库锁等待与 CPU 型慢查询的反事实配对。
- 元数据与 owner acceptance sidecar 的 10 个 public_sha256 一致，见 dev-case-selection.json。
- 仍然只有两个名义家族和一个 near-duplicate cluster，来源同一生成器；不是独立 Test。
  数据中没有新增的真实跨来源冲突病例，不能把 Dev10 宣称为全面困难集。

事先固定三个对比 Full–Single、Full–Fixed、Full–NoVerifier。报告根因匹配、正确弃权、
引用存在/授权及语义支持、竞争假设排除理由、工具/请求/轮次/审查动作。语义审核允许
SUPPORTED/MIXED/UNSUPPORTED/UNKNOWN，不能以 ID 存在替代支持。不要求 Full 获胜。
本项目接受的完成运行质量分析不计算历史网络失败率；技术终止状态仍作为日志事实保留。
不能据此声称端到端可靠率或无偏整体成功率。Token/费用未知时为 null。

## 3. 两个运行版本（都未开始）

| 项目 | 桥接版 | 真实 API 版 |
|---|---|---|
| plan | configs/wp_d/bridge-plan.json | configs/wp_d/api-plan.json |
| protocol | bridge-protocol.json | api-protocol.json |
| runtime config | bridge-runtime.yaml | api-runtime.yaml |
| 模型 | trae-subagent-bridge-v1，外部身份未验证 | deepseek-v4.1-flash-1017，执行前匹配配置及该模型的真实 readiness |
| 请求等待 | 全组 1200 秒 | 全组 1200 秒 |
| 结构修复 | 每逻辑调用最多 1 次 | 每逻辑调用最多 1 次 |
| 传输重试 | 无网络，不自动重发等待中的请求 | 可重试超时/网络/408/429/5xx，最多 2 次，逻辑调用最多 4 个物理尝试 |
| 退避 | 不适用 | 2–20 秒，尊重 Retry-After，受剩余 wall/request 预算约束 |

共同提案：8 轮、40 工具、64 请求许可、7200 秒 wall、cache off、桥接/API jobs=8、temperature=0、
run_order_seed=14100。同一版本内所有架构使用相同参数及服务规则，不临时增加提示。
这些值是针对 1200 秒等待及既有最大 26 请求/20 工具观察的保守容量提案，尚未校准。
64 个许可包含 adapter 的请求重试和修复；40 槽位的许可上界为 2560，wall 上界和为 80 小时，
不是预期耗时或费用。中断后新尝试会额外消耗资源，不能据此承诺整个批次的绝对总费用上限。
批次遇失败默认暂停，避免 Provider 不可用时连续消耗。API 保持鉴权及 readiness 检查。
桥接和真实 API 是两个不同模型条件，不合并计算总体准确率或直接比较速度。

## 4. 已实现的运行改进（待运行验证）

- 调查员工具计划的输出 Schema 约束为真实有效工具集合；普通专家使用 context 与 task 的交集。
  Coordinator 的任务 ACL 在结构化响应验证内部检查，使既有一次修复机会能处理非法提议。
  保留生成后的权限检查，不扩大权限、不静默裁剪模型输出。
- 共用提示词强调正向支持、实际矛盾、缺失证据及拓扑事实的区别，所有组一致应用；版本已更新。
- 桥接加入与 API 同类的 RunJournal：增量事件、线程心跳、诊断双槽快照、活跃请求和最终健康。
  请求等待每 30 秒记录剩余时间及字节数，超时独立标识；日志不记录 API 密钥。
- 桥接响应以原始 UTF-8 内容装配，不 strip、不转换 CRLF。原子发布、fsync、唯一临时文件及
  有界 Windows PermissionError 重试；已经服务过的不同响应拒绝覆盖。请求摘要校验、防路径穿越。
- watch 可自动把 >60 KiB 请求准备成 40 KiB 分块，带顺序/字节数/SHA256 清单；修复请求同样处理。
  分块内容是消息数组的一部分，不是每块各自独立 JSON；必须拼接全部块后理解。
- 两类 runner 保存实际 elapsed_ms、measured-usage 和最终 journal 健康，source lock 增加依赖锁及准备配置。
- Graph recursion_limit 随调查轮数增加并保留 STOP/report 余量；业务预算和 FinalizeGate 不放宽。
- 新批次 supervisor 保存启动意图、PID、退出码、stdout/stderr、每槽位状态、输入清单、产物摘要及心跳。
  状态查询脚本支持批次和待服务桥接请求。API 子进程本身仍使用已清理的 provider 错误分类，
  原始错误消息不可被误认为精确网络归因；文件写失败与业务异常分开定位。

## 5. 中断恢复的明确边界

实现的是 R1 批次恢复，不是 R2 单次调查续跑。RunJournal 快照仍标为 diagnostic_only。

1. 准备时冻结代码/配置/Prompt/requirements、实际安装依赖版本、公共数据、模型/协议、随机顺序。
   API 另绑定 readiness 和端点摘要；不保存密钥。不在旧实验目录继续写。
2. --resume 在恢复前比对输入清单，校验已完成产物 SHA256 与身份；已完成槽位跳过，只继续未开始项。
3. 若旧父进程消失但子进程仍存活，拒绝恢复。每槽位 OS worker lease 防止旧/新 worker 同时运行。
   Windows PID 检查失败时保守拒绝，不能因 PID 复用误杀进程。
4. 中断中的调查不加载旧快照；只有 --retry-interrupted 才创建新 attempt，并记录父尝试。
   已完成的技术失败不因 resume 自动重跑；只有 --retry-failed 才建立新的失败项尝试。所有已写状态及旧目录保留。
5. Ctrl-C 或 STOP_REQUESTED 使 supervisor 尝试停止子进程，15 秒后终止，必要时强制结束。
   硬终止没有 finally 保证；恢复时根据已有产物对账。无法确定的远端请求结果保持未知，
   不承诺 exactly-once、不保证零重复成本。
6. batch-events 若尾部损坏不代表完整记录；它是诊断日志，batch-state 原子快照用于 R1 恢复。
   损坏的 state/manifest 或产物摘要不匹配必须停止，不能猜测补齐或覆盖原件。

## 6. 后续获准后使用的命令（本轮未执行）

从项目根目录运行，先完成离线回归及故障注入再执行任何模型批次。

```powershell
$env:PYTHONPATH = Join-Path $PWD 'src'
$P = '.venv/Scripts/python.exe'
# 待批准后才运行以下离线检查；当前未跑
& $P -B -m pytest tests/integration/test_wpd_run_preparation.py tests/integration/test_bridge_retest.py tests/integration/test_observability_retry_isolation.py tests/integration/test_wpd_repair_accounting.py

# 桥接：prepare 只生成冻结清单，不发模型请求
& $P -B scripts/run_wpd_batch.py --plan configs/wp_d/bridge-plan.json --out results/v16/wp-d/next-bridge-UNIQUE --prepare
# execute 才真正启动；当前禁止启动
& $P -B scripts/run_wpd_batch.py --plan configs/wp_d/bridge-plan.json --out results/v16/wp-d/next-bridge-UNIQUE --execute

# 真实 API：先取得本轮实际兼容性记录；example 不能当作 readiness
& $P -B scripts/run_wpd_batch.py --plan configs/wp_d/api-plan.json --out results/v16/wp-d/next-api-UNIQUE --readiness local_oracles/wp-d/current-readiness.json --prepare
& $P -B scripts/run_wpd_batch.py --plan configs/wp_d/api-plan.json --out results/v16/wp-d/next-api-UNIQUE --readiness local_oracles/wp-d/current-readiness.json --execute
```

API 执行顺序：先用同配置完成 full 正例及负例严格 G1a，再启动 Dev40。若需要更换 model_id、
response_format、thinking 或预算，应在 prepare 前修改对应协议/配置并重新做匹配 readiness。
不要把桥接成功改记为 API readiness。此处不调用模型获取 readiness。

恢复命令在对应 execute 后添加 --resume；中断项获准重启再加 --retry-interrupted。
若已有 STOP_REQUESTED，先查明停止原因并显式移走停止文件后恢复。查询只读：

```powershell
& $P -B scripts/run_status.py results/v16/wp-d/next-bridge-UNIQUE
# 用 supervisor-status.json 中当前 attempt 路径替换 <ATTEMPT>
& $P -B analysis/wp_d/serve_bridge_response.py --bridge-dir '<ATTEMPT>/_bridge' --watch 45 --prep-dir '<ATTEMPT>/_prepare' --chunk-kb 40
```

每请求使用同一服务模板，仅允许读取本请求（或所有分块）并写一个 raw JSON；不得读取其他请求、
结果或 Oracle。--serve-dir 必须按 attempt 分开。服务修复请求不能遗忘；无手工修正、无附加 ACL 提醒。
服务助手会保留 NOT_JSON 内容，由 harness 发起一次修复，不能覆盖旧响应来追求成功。

## 7. 仍须验证的风险（本轮明确不测试）

- 新 Coordinator ACL 校验、任务工具 enum、结构化修复与实际供应商 JSON Schema 兼容性。
- OS worker lease、Ctrl-C、父进程硬终止后子进程存活、PID 复用、Windows 文件共享锁及硬链接支持。
- 子进程在最终产物写入与状态提交之间退出时的恢复；摘要篡改、source drift、JSON 损坏、磁盘满。
- 大 Unicode 请求分块、repair 漏服务、重复/不匹配响应、有界等待与 STOP 竞争。
- API 429/5xx/超时退避、请求/Token/wall 边界、未知远端结果及取消的实际记账。
- 新语义提示是否减少错误排除、是否造成过度弃权，必须由后续实验判断。

已新增离线回归文件 tests/integration/test_wpd_run_preparation.py，但未运行。
真实 API 无法被代码改动保证永不超时；此交付提供可诊断/可停止/批次级可恢复的实现，
不是“下次测试无故障”的承诺。最终安装、全量回归、阶段收尾与演示按用户要求推迟。
