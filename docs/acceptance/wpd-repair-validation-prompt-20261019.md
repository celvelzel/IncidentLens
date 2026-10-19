# 离线验证提示词（修复交接留档）

请验证 IncidentLens 在 2026-10-19 对 P0、P1、Verifier 衡量和 Token 计数的修复。
工作目录必须是 `C:\Develop\python_projects\COMP5584_Agents\IncidentLens`。
先阅读 `docs/acceptance/wpd-repair-20261019.md`。修复实施于独立工作树；合入后使用上述主项目路径。单 Agent 执行，保留现有脏改动。

这份提示词只授权离线测试与只读分析，不授权真实模型调用、矩阵重跑、删除旧目录或修改原始结果。
不要读取/输出 .env、API key 或完整失败响应。不要为了通过测试放宽证据/引用/权限约束。

1. 检查当前代码是否仍对应修复说明，记录 git HEAD、修改文件及指纹。不要沿用旧 source_unchanged 代替当前核对。
2. 使用可用的 Python 环境。若复用原仓库 `.venv`，务必把当前 worktree 的 src 放在 PYTHONPATH 最前，并先打印 incident_lens.__file__ 确认加载的是 worktree 代码，避免误测原仓库的 editable install。
3. 先运行新增 `tests/integration/test_wpd_repair_accounting.py`，再运行以下相关回归；保存完整日志与退出码。任何失败先分析归因，再做范围明确的修复，不删除断言掩盖错误。

```powershell
Set-Location 'C:\Develop\python_projects\COMP5584_Agents\IncidentLens'
$repairPython = 'C:\Develop\python_projects\COMP5584_Agents\IncidentLens\.venv\Scripts\python.exe'
$env:PYTHONPATH = Join-Path (Get-Location).Path 'src'
& $repairPython -c "import incident_lens; print(incident_lens.__file__)"
& $repairPython -m pytest -q tests/integration/test_wpd_repair_accounting.py
& $repairPython -m pytest -q tests/unit/test_provider.py tests/unit/test_provider_errors_v13.py tests/unit/test_provider_http_retry_v13.py tests/unit/test_agents.py tests/integration/test_failure_accounting.py tests/integration/test_live_provider_recovery.py tests/integration/test_provider_runtime_v13.py tests/integration/test_finalize_resume_guards.py tests/integration/test_rescue_finalization.py tests/integration/test_changes_scope_completion.py tests/integration/test_observability_retry_isolation.py tests/evaluation tests/incidentbench/test_experiment_fairness.py
```

4. 额外重点核验以下行为，已有测试覆盖不足时补充离线回归：
   - legacy 503/429 短暂故障后恢复，coordinate/diagnosis/verify 都有有限重试；401/403、显式 quota、普通 4xx 不重试。
   - Retry-After 超过剩余时间、STOP、取消、已耗尽预算都不会再发请求；可靠传输层已经耗尽时，不叠加业务层重试。
   - 日志写入异常仍不打断重试；新增诊断不泄露错误正文/凭据。
   - failure_mode 长句变体被 generation schema 拒绝；不修改历史 Hypothesis 读取兼容性。
   - FINALIZE_REJECTED 不污染真实 open_questions；真实问题/未解决竞争者/缺少复核仍阻断最终化。
   - 只有评估变化、证据不变时可重新尝试最终化；同一快照同一错误重复时仍能停止。
   - 预算预留只调节动态任务，固定基线保持固定排期；被推迟的任务可从事件查到。
   - 复核只有完全相同的证据/评估/目标才复用；变更目标、假设、证据或真实问题后重新复核；single 不被报告为独立 Verifier。
   - REVIEW_EFFECT / FOLLOWUP 的计数、归属与 Token 成本匹配；成功工具调用没有新证据时不得计为新增证据收益。
   - 成功后超时、失败后恢复、输出修复、取消、usage 缺失、仅 prompt+completion、合法零值、bool/负值都正确计数；未知保持 null，已知下界不丢失，无重复计数。
5. 复核 `analysis/wp_d/reports/token-recovery-20261019/` 中的 input_sha256，确认与原文件一致；旧目录不写入。必要时用新输出目录重汇总，不能覆盖已有报告。
6. 提交测试汇报：通过/失败/未执行、实际测试代码路径、失败原因、Token 完整性、Verifier 观测字段和剩余风险。离线通过不代表提供方恢复，也不代表 slot 5/9 已经改判。

真实测试须另行获得用户授权，再进行少量连通性验证和新冻结版本的运行；不能直接运行旧四项补跑脚本。
