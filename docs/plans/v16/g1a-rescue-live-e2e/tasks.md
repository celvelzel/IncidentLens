# G1a 实施任务清单（tasks）

对应 spec.md。批准后按序执行，每任务完成即更新状态。

## T1 救援逻辑实现（写者：ma\_implementer，共享 checkout 单写者）

* [x] 1.1 graph.py 新增 `error_details(exc)` 类方法（spec §3.1），6 处 RUNTIME\_ERROR 发射点并入 `error_code`/`transport_error`（L284/L528/L720/L864/L983/L1115）。

* [ ] 1.2 graph.py 新增 `rescue_report(state)`（spec §3.2），report() 中 INCONCLUSIVE 兜底前调用；构造与 finalize() L1017-1027 一致，DIAGNOSIS\_ACCEPTED 带 `rescued=True`、`rescue_review_event_id`。

* [x] 1.3 termination.py `normalize_termination()` diagnosis\_failure 判定支持 rescued checkpoint（spec §3.3）；`accepted_diagnosis()` 增加 rescued checkpoint 校验。

* 验证：新增测试通过 + 全量回归无回归。（6 passed；956 passed 3 skipped；ruff clean。spec 之外的两处必要补丁见里程碑报告：报告补挂 workflow\_status/termination、冻结期检查对已校验 rescued 事件豁免）

## T2 测试（tests/integration/ 新增 4 组，spec §3.5）

* [x] 2.1 救援成功场景（verify sufficient + 运输类 RUNTIME\_ERROR ×2 → RESOLVED + rescued 标注）。

* [x] 2.2 证据不足不救援（finalize\_errors 非空 → INCONCLUSIVE 兜底）。

* [x] 2.3 非运输错误不救援（STRUCTURED\_OUTPUT\_INVALID）。

* [x] 2.4 normalize\_termination 记账（diagnosis\_failure=False、runtime\_failure=True、reason=UNRECOVERABLE\_ERROR；ABSTAIN/预算耗尽不救援且判定不变）。

* 验证：`.venv\Scripts\python.exe -m pytest tests/integration -q` 新增用例全绿。（tests/integration/test\_rescue\_finalization.py 6 passed）

## T3 离线预飞行

* [x] 3.1 全量回归：`.venv\Scripts\python.exe -m pytest -q` 全绿。（首轮 955 passed + test\_ui 超时 1 失败，经复跑 test\_ui 4 passed 确认为负载抖动非回归）

* [x] 3.2 `ruff check src scripts tests` 无告警。

* [x] 3.3 `.venv\Scripts\python.exe scripts/v16_e2e_preflight.py` 预检通过（exit\_code=0，results/v16/live-e2e/g1a-20261015-01/preflight-01/preflight.json）。

* 任何失败先修，不进入真实调用。

## T4 协议 v5 + 版本冻结

* [x] 4.1 创建 `results/v16/live-e2e/g1a-20261015-01/protocol-retest-v5-generous.json`（spec §3.4：max\_rounds=8、max\_tool\_calls=32、max\_llm\_calls=48、max\_wall\_seconds=5400、request\_timeout=420，其余同 v4）。

* [ ] 4.2 冻结源码版本（retest 脚本自带 retest\_snapshot，运行时自动落盘）。

## T5 真实 E2E 正例 incident\_2001

* [x] 5.1 `scripts/retest_live_provider_fix.py --dataset results/incidentbench/v1/20261013-deepseek-development-pilot/dataset --protocol results/v16/live-e2e/g1a-20261015-01/protocol-retest-v5-generous.json --incident incident_2001 --variant full --out results/v16/live-e2e/g1a-20261015-01/incident-2001-full`（顺序执行，后台运行并监控）。

* [x] 5.2 核验：根因正确（backend\_pool\_config\_regression）、verification.json sufficient、report.md 完整、protocol\_valid；rescued 情况显著标注并如实说明。

T5 验收说明（2026-10-16）：用户明确接受已有正例并授权勾选。report.md 为 RESOLVED，根因为 backend\_pool\_config\_regression，protocol\_valid=true、STOP 完成；verification.json 同时记录 graph.py 源码漂移（source\_unchanged=false），故本勾选为用户接受的开发正例结果，不代表冻结实验通过。

## T6 真实 E2E 负例 incident\_2002

* [x] 6.1 同参数 `--incident incident_2002 --out results/v16/live-e2e/g1a-20261015-01/incident-2002-full`。

* [x] 6.2 核验：INCONCLUSIVE 正常弃权（reason=INCONCLUSIVE）、无臆造 root\_cause、无 RUNTIME\_ERROR。

T6 验收说明（2026-10-17）：用户授权勾选。经历 v5 死循环、v6-1/v6-2 运输失败、t6-real 预算耗尽、t6-real-2 ISSUE-7 崩溃（Verifier 引用越界）后，用户修复 ISSUE-7 并复测 t6-real-3。t6-real-3 证明代码修复全部生效：3 轮 review 全判 insufficient、全程零引用违规、无臆造 root\_cause、调查持续挖掘新判别因果源无死循环。该场最终因 coordinate-4 连续两次 PROVIDER\_TIMEOUT 耗尽尝试预算而以 UNRECOVERABLE\_ERROR 收尾（failure\_stage=coordinate，纯运输层 ISSUE-4 类），正式 ABSTAIN 决定未走出。本勾选为用户接受的行为正确性验收（负例方向正确、无臆造、无代码缺陷），不代表无 RUNTIME\_ERROR 的严格 PASS；运输层复测补录见 results/v16/t6-closure/20261016-static-01/t6-real-3/ 与 docs/acceptance/live-provider-issues.md ISSUE-7。

## T7 独立复核 + 里程碑报告

* [ ] 7.1 ma\_reviewer 独立复核两场证据链（result/report/verification/trace/failed-calls、救援标注、历史产物零覆盖）。

* [ ] 7.2 按计划 §12 格式输出 G1a 里程碑报告：实际修改、测试结果、证据路径、剩余问题、下一步。

## 风险登记

* 端点挂起复发 → v5 宽松预算 + 救援兜底；连续挂起耗尽尝试时如实记录为运输失败。

* 救援被质疑为放宽验收 → 严格 finalize\_errors 门禁 + 诚实记账（runtime\_failure=True）+ rescued 标注。

* 多变量同时改动（源码+预算）→ 报告中声明偏离单变量原则，依据用户"先确保完成"指令。

