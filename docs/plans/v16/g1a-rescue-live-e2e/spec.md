# G1a 救援逻辑 + 真实 E2E 验收 规格（spec）

日期：2026-10-15
依据：docs/plans/v16/IncidentLens\_V1.6\_Codex\_MultiAgent\_Implementation\_Plan.md、CODEX\_START\_HERE.md
状态：待批准

## 1. 背景与问题

上一次真实 API 复测（results/incidentbench/v1/user-retest-reconciliation/real-v4-wall3600-req300/full/）中，incident\_2001 的根因诊断已正确（backend\_pool\_config\_regression）且 Verifier 判定 sufficient，但在 coordinate 阶段遭遇端点 302 秒挂起 ×2 → 任务尝试耗尽 → RUNTIME\_ERROR。graph.py `stop()`（L1131-1134）只要存在 RUNTIME\_ERROR 即判 UNRECOVERABLE\_ERROR，`report()`（L1221-1235）在无报告时只产出 INCONCLUSIVE 兜底，导致**已验证的诊断被丢弃**，整场被标记 INCONCLUSIVE。

G1a 目标（用户授权，小规模正负例，不做全量 Benchmark）：

* incident\_2001 正例：真实模型（deepseek-v4-flash-0731）找到正确根因 → 通过 Verifier → 完成 RCA 报告。

* incident\_2002 负例：公开证据不足（changes/configs/database 均为空），正确弃权（INCONCLUSIVE 正常弃答，非技术失败、非臆造根因）。

* Token/费用/时间上限尽量宽松，先确保端到端实验能完成。

## 2. 不可协商约束（继承）

1. 不覆盖历史 results/，所有产物写入新目录 `results/v16/live-e2e/g1a-20261015-01/`。
2. 不放宽验收规则、不伪造实验、不挑成功结果宣称通过。
3. .env/密钥不进日志；provider.py 对 genai.comp.polyu.edu.hk 已实现 trust\_env=False，不动。
4. temperature=0、cache\_mode=off；configs/system.yaml 的 provider\_recovery 保持关闭，不改全局配置。
5. 真实复测前必须：冻结源码版本（retest 脚本自带 retest\_snapshot）→ 全量回归测试通过 → v16\_e2e\_preflight.py 预检通过。
6. 救援产出的 RESOLVED 报告必须显著标注 `rescued=true`，termination 保留 runtime\_failure=True / reason=UNRECOVERABLE\_ERROR 的诚实记账。
7. 顺序执行两场真实运行（避免压垮端点），每任务最多 2 次尝试（configs/system.yaml 不动）。

## 3. 变更设计（决策完备）

### 3.1 变更一：RUNTIME\_ERROR 事件补全错误分类（src/incident\_lens/orchestration/graph.py）

新增辅助方法（放在 `stage_retryable_error` 附近）：

```python
@classmethod
def error_details(cls, exc):
    from incident_lens.llm.provider import ProviderError

    code = getattr(exc, "code", "") or (
        "PROVIDER_TIMEOUT" if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) else ""
    )
    transport = isinstance(exc, (TimeoutError, asyncio.TimeoutError)) or (
        isinstance(exc, ProviderError)
        and getattr(exc, "code", "") in {"PROVIDER_TIMEOUT", "PROVIDER_TRANSPORT_ERROR"}
    )
    return {"error_code": code, "transport_error": transport}
```

在全部 6 处 RUNTIME\_ERROR 发射点并入该 details（保留原有 message/stage/error\_type 字段）：

* L284 monitor（stage="monitoring"）

* L528 coordinate（stage="coordinate"）

* L720 dispatch（stage="dispatch"）

* L864 merge（stage="merge"）

* L983 verify（stage="verify"）

* L1115 remediate（stage="remediation"）

### 3.2 变更二：救援逻辑（同文件）

新增方法 `rescue_report(state)`，在 `report()` 的 INCONCLUSIVE 兜底之前调用。全部条件满足才救援，否则返回 None：

1. 存在 ≥1 个 RUNTIME\_ERROR 事件，且**全部** `details.transport_error == True`（任何非运输错误 → 不救援）。
2. `state.decisions` 非空且最后决策 `action != "ABSTAIN"`（正常弃答不救援）。
3. 终止原因不是 BUDGET\_EXHAUSTED（预算耗尽不救援）。
4. 存在**唯一** hypothesis `h` 使 `finalize_errors(state, h, self.variant) == []`（复用 guards.py FinalizeGate，含 Verifier verdict=sufficient + 快照指纹匹配，不绕过门禁）。

满足时：

1. `supported = h.model_copy(update={"status": "SUPPORTED"})`。
2. 按 finalize() L1017-1027 **完全相同**的构造生成 `RCAReport(status="RESOLVED", root_cause=supported, causal_chain=observed_chain(state, supported), supporting_evidence_ids=supported.support_ids, rejected_hypotheses=[...], stop_reason=state.decisions[-1].stop_reason or "Evidence sufficient")`。
3. 查找对应 REVIEW 事件（`details.review.target_hypothesis_id == h.hypothesis_id` 且 verdict=sufficient 的最后一个），发射 DIAGNOSIS\_ACCEPTED 事件，details 包含：

   * `root_cause=supported.model_dump(mode="json")`

   * `supporting_evidence_ids=supported.support_ids`

   * `rescued=True`

   * `rescue_review_event_id=<该 REVIEW 事件 event_id>`

   * `degraded_call_ids`（同 finalize 逻辑）

`report()` 修改：`if state.report is None:` 处先尝试 `self.rescue_report(state)` 赋值，成功则跳过 INCONCLUSIVE 兜底。

不改变 `stop()` 的终止判定与 termination 记账（reason 仍为 UNRECOVERABLE\_ERROR、outcome=FAILED、runtime\_failure=True）——救援只恢复报告，不粉饰运输失败。

### 3.3 变更三：termination 记账支持 rescued acceptance（src/incident\_lens/evaluation/termination.py）

`accepted_diagnosis()`（L38-49）无需修改：rescued DIAGNOSIS\_ACCEPTED 的 root\_cause/supporting\_evidence\_ids 与报告一致，天然匹配。

修改 `normalize_termination()` 中 diagnosis\_failure 判定块（约 L353-365，现逻辑：failure\_stage 不在 {remediation, stop} 或 ACCEPTED 前有非 remediation/stop 的 RUNTIME\_ERROR → diagnosis\_failure=True）：

* 若接受事件 `details.rescued == True`：checkpoint 改为 `rescue_review_event_id` 指向的 REVIEW 事件位置；checkpoint **之后**的 RUNTIME\_ERROR 若全部 `details.transport_error == True`，则 `diagnosis_failure=False`（保留 runtime\_failure=True、reason=UNRECOVERABLE\_ERROR）。

* 非 rescued 路径行为完全不变（只读归一化，绝不改写历史事件）。

`accepted_diagnosis` 对 rescued 情况需额外校验：checkpoint REVIEW 事件存在且其 target\_hypothesis\_id 对应报告根因（防止伪造 checkpoint）。

### 3.4 变更四：协议 v5（新文件，不覆盖 v4）

路径：`results/v16/live-e2e/g1a-20261015-01/protocol-retest-v5-generous.json`

以 `results/incidentbench/v1/user-retest-reconciliation/pilot-protocol-retest-v4.json` 为基底克隆，仅改预算类字段与 id：

| 字段                 | v4           | v5                                                                               |
| ------------------ | ------------ | -------------------------------------------------------------------------------- |
| protocol\_id       | ...retest-v4 | incidentbench-v1-comp-deepseek-v4-flash-two-case-g1a-live-e2e-generous-retest-v5 |
| max\_rounds        | 6            | 8                                                                                |
| max\_tool\_calls   | 24           | 32                                                                               |
| max\_llm\_calls    | 32           | 48                                                                               |
| max\_wall\_seconds | 3600         | 5400                                                                             |
| request\_timeout   | 300          | 420（超过已知 302 秒挂起）                                                                |

其余字段（provider\_id=real, model\_id=deepseek-v4-flash-0731, temperature=0.0, cache\_mode=off, response\_format=json\_schema, formal=false, jobs=1, repeats=1, blindness\_level=development\_visible 等）不变。

声明：同时修改源码 + 多项预算与"单变量"原则冲突，按用户"先确保端到端完成"的优先级执行，并在里程碑报告中如实声明。

### 3.5 变更五：测试（tests/integration/ 新增，参考 test\_review\_boundary.py、test\_termination\_scoring.py 的状态构造）

1. **救援成功**：构造 verify 已 sufficient + coordinate 阶段运输类 RUNTIME\_ERROR ×2 的状态 → report() 产出 RESOLVED 报告，DIAGNOSIS\_ACCEPTED 带 rescued=True 与 rescue\_review\_event\_id。
2. **证据不足不救援**：finalize\_errors 非空（缺 Verifier sufficient）→ 仍产出 INCONCLUSIVE 兜底。
3. **非运输错误不救援**：RUNTIME\_ERROR 含 error\_code=STRUCTURED\_OUTPUT\_INVALID（transport\_error=False）→ 不救援。
4. **记账正确**：normalize\_termination 对 rescued 状态判定 diagnosis\_failure=False、runtime\_failure=True、reason=UNRECOVERABLE\_ERROR、accepted\_diagnosis()=True；对 ABSTAIN/预算耗尽状态不救援且判定不变。

## 4. 验证步骤（按序）

1. 全量回归：`.venv\Scripts\python.exe -m pytest -q` 全绿 + `ruff check src scripts tests` 无告警。任何回归先修，不进入真实调用。
2. 预检：`.venv\Scripts\python.exe scripts/v16_e2e_preflight.py` 通过（Verifier 预检；如含两次尝试语义按脚本执行）。
3. 真实运行（顺序，后台 PowerShell，`.env` 已配 deepseek-v4-flash-0731）：

   * `scripts/retest_live_provider_fix.py --dataset results/incidentbench/v1/20261013-deepseek-development-pilot/dataset --protocol results/v16/live-e2e/g1a-20261015-01/protocol-retest-v5-generous.json --incident incident_2001 --variant full --out results/v16/live-e2e/g1a-20261015-01/incident-2001-full`

   * 同参数 `--incident incident_2002 --out .../incident-2002-full`
4. 核验：

   * incident\_2001：result.json 根因=backend\_pool\_config\_regression（或等价正确判定）、verification.json verdict=sufficient、report.md 完整 RCA、protocol\_valid；若经救援产出，必须可见 rescued=true 标注且运输故障如实记录。

   * incident\_2002：INCONCLUSIVE 正常弃权（ABSTAIN/Insufficient evidence），无臆造根因，无 RUNTIME\_ERROR/UNRECOVERABLE\_ERROR。
5. ma\_reviewer 独立复核证据链，最后按计划 §12 格式输出 G1a 里程碑报告（实际修改、测试结果、证据路径、剩余问题、下一步）。

## 5. 验收标准（G1a）

* 正例：真实模型定位正确根因 + Verifier sufficient + RCA 报告落盘。干净 RESOLVED 为最佳；若依赖救援，报告显著标注 rescued=true 并如实说明运输故障（不得算作干净通过，须在报告中区分）。

* 负例：正常弃权，INCONCLUSIVE，reason=INCONCLUSIVE（非 UNRECOVERABLE\_ERROR），无 root\_cause。

* 两场产物完整（result.json / report.md / verification.json / trace / failed-calls），全部位于新目录，历史产物零覆盖。

* 回归 + 预检证据齐全。

## 6. 风险与缓解

* 端点 302 秒挂起复发：request\_timeout=420 + max\_attempts=2 + 救援逻辑兜底（已验证诊断不再丢失）。

* 救援被误用为"作弊"通道：严格复用 finalize\_errors 门禁 + 全部 RUNTIME\_ERROR 必须运输类 + ABSTAIN/预算耗尽排除 + rescued 标注 + 诚实记账（runtime\_failure 保持 True）。

* 多变量同时改动（源码 + 预算）：按用户优先级执行并在报告中声明偏离单变量原则。

* 成本：仅 2 个案例 × 1 次 × full 变体，顺序执行。
