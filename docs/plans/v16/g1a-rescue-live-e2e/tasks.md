# G1a 实施任务清单（tasks）

对应 spec.md。批准后按序执行，每任务完成即更新状态。

## T1 救援逻辑实现（写者：ma_implementer，共享 checkout 单写者）
- [x] 1.1 graph.py 新增 `error_details(exc)` 类方法（spec §3.1），6 处 RUNTIME_ERROR 发射点并入 `error_code`/`transport_error`（L284/L528/L720/L864/L983/L1115）。
- [x] 1.2 graph.py 新增 `rescue_report(state)`（spec §3.2），report() 中 INCONCLUSIVE 兜底前调用；构造与 finalize() L1017-1027 一致，DIAGNOSIS_ACCEPTED 带 `rescued=True`、`rescue_review_event_id`。
- [x] 1.3 termination.py `normalize_termination()` diagnosis_failure 判定支持 rescued checkpoint（spec §3.3）；`accepted_diagnosis()` 增加 rescued checkpoint 校验。
- 验证：新增测试通过 + 全量回归无回归。（6 passed；956 passed 3 skipped；ruff clean。spec 之外的两处必要补丁见里程碑报告：报告补挂 workflow_status/termination、冻结期检查对已校验 rescued 事件豁免）

## T2 测试（tests/integration/ 新增 4 组，spec §3.5）
- [x] 2.1 救援成功场景（verify sufficient + 运输类 RUNTIME_ERROR ×2 → RESOLVED + rescued 标注）。
- [x] 2.2 证据不足不救援（finalize_errors 非空 → INCONCLUSIVE 兜底）。
- [x] 2.3 非运输错误不救援（STRUCTURED_OUTPUT_INVALID）。
- [x] 2.4 normalize_termination 记账（diagnosis_failure=False、runtime_failure=True、reason=UNRECOVERABLE_ERROR；ABSTAIN/预算耗尽不救援且判定不变）。
- 验证：`.venv\Scripts\python.exe -m pytest tests/integration -q` 新增用例全绿。（tests/integration/test_rescue_finalization.py 6 passed）

## T3 离线预飞行
- [x] 3.1 全量回归：`.venv\Scripts\python.exe -m pytest -q` 全绿。（首轮 955 passed + test_ui 超时 1 失败，经复跑 test_ui 4 passed 确认为负载抖动非回归）
- [x] 3.2 `ruff check src scripts tests` 无告警。
- [x] 3.3 `.venv\Scripts\python.exe scripts/v16_e2e_preflight.py` 预检通过（exit_code=0，results/v16/live-e2e/g1a-20261015-01/preflight-01/preflight.json）。
- 任何失败先修，不进入真实调用。

## T4 协议 v5 + 版本冻结
- [x] 4.1 创建 `results/v16/live-e2e/g1a-20261015-01/protocol-retest-v5-generous.json`（spec §3.4：max_rounds=8、max_tool_calls=32、max_llm_calls=48、max_wall_seconds=5400、request_timeout=420，其余同 v4）。
- [ ] 4.2 冻结源码版本（retest 脚本自带 retest_snapshot，运行时自动落盘）。

## T5 真实 E2E 正例 incident_2001
- [x] 5.1 `scripts/retest_live_provider_fix.py --dataset results/incidentbench/v1/20261013-deepseek-development-pilot/dataset --protocol results/v16/live-e2e/g1a-20261015-01/protocol-retest-v5-generous.json --incident incident_2001 --variant full --out results/v16/live-e2e/g1a-20261015-01/incident-2001-full`（顺序执行，后台运行并监控）。
- [x] 5.2 核验：根因正确（backend_pool_config_regression）、verification.json sufficient、report.md 完整、protocol_valid；rescued 情况显著标注并如实说明。

T5 验收说明（2026-10-16）：用户明确接受已有正例并授权勾选。report.md 为 RESOLVED，根因为 backend_pool_config_regression，protocol_valid=true、STOP 完成；verification.json 同时记录 graph.py 源码漂移（source_unchanged=false），故本勾选为用户接受的开发正例结果，不代表冻结实验通过。

## T6 真实 E2E 负例 incident_2002
- [ ] 6.1 同参数 `--incident incident_2002 --out results/v16/live-e2e/g1a-20261015-01/incident-2002-full`。
- [ ] 6.2 核验：INCONCLUSIVE 正常弃权（reason=INCONCLUSIVE）、无臆造 root_cause、无 RUNTIME_ERROR。

T6 状态（2026-10-16）：按用户指示暂时跳过，不再调用模型。既有尝试保留：v5 预算耗尽；v6 首次运输失败、后续预算耗尽。尚无正常正确弃权验收，不能标为 PASS；G1a 整体验收仍未闭环。

## T7 独立复核 + 里程碑报告
- [ ] 7.1 ma_reviewer 独立复核两场证据链（result/report/verification/trace/failed-calls、救援标注、历史产物零覆盖）。
- [ ] 7.2 按计划 §12 格式输出 G1a 里程碑报告：实际修改、测试结果、证据路径、剩余问题、下一步。

## 风险登记
- 端点挂起复发 → v5 宽松预算 + 救援兜底；连续挂起耗尽尝试时如实记录为运输失败。
- 救援被质疑为放宽验收 → 严格 finalize_errors 门禁 + 诚实记账（runtime_failure=True）+ rescued 标注。
- 多变量同时改动（源码+预算）→ 报告中声明偏离单变量原则，依据用户"先确保完成"指令。
