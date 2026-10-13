# IncidentLens V1.4 IncidentBench — 离线工程验收报告

**结论：离线开发、回归与可重算实验里程碑已验收；研究级 V1.4 尚未完成。**

本报告对应源码冻结提交 `072cea5`。本地基线为 `5f2cb2a2bbe1a07469c12e667a3f25ea6a2d1cc1`；Benchmark 契约为 `incidentbench-v1.0`。运行包版本保留 `0.1.3`，未宣称正式 V1.4 研究发布。所有代码为本地提交，未 push、tag 或发布 PR。

用户确认暂无人工 Reviewer，先完成待审数据与离线工程。因此未编造人工签收、严格盲测、真实模型性能或完整 P0–P7 研究验收。没有实现 V1.5 算法。

## 1. 阶段验收

| 阶段 | 实际交付与状态 |
|---|---|
| P0 | 通过：完整本地审计；V1.3 已合入；旧 pytest **637 passed, 2 skipped**；Ruff、旧数据验证通过；Legacy Seed 四变体 **24 runs**；V1.2 DB response `RESOLVED`。|
| P1 | 通过：独立 Schema、数据/Oracle 路径、评分、工具等价性与文件所有权冻结；独立 QA 检查接口及安全边界。|
| P2 | 工程候选已集成：因果世界→跨来源观测 Builder、完成后 Oracle、Runner；有 4 个声明分组。**独立家族 Exit Gate 未通过：共享编码器，独立审核家族数为 0。**|
| P3 | 已生成并公开/特权校验 **20 个待审 Seed 候选**，反事实与来源分组检查通过；**人工审核与独立 Dev/Test 未完成**。|
| P4 | 离线技术验收通过：实际四架构 Graph、正常弃权/失败分母、请求计数/null、匿名审查包、统计与显式离线 resume；**80 runs 实际完成并重算**。|
| P5 | **未通过**：没有人工双审/Label Owner、Frozen Core 或正式模型预算签收；仅生成 `sealed=false` 开发锁与候选 Seed 标签完整性承诺。|
| P6 | **REAL_EVAL_PENDING**：本次真实 Provider 请求为 **0**。正式 Runner fail-closed；真实实验与真实恢复未实施。|
| P7 | 离线重算、技术 QA、数据/评测/模型卡和研究文档已完成；**人工语义审核、独立样本统计推断与正式研究发布未完成**。|

P2/P3 的科学性条件不足时，继续实现可独立验证的离线工程，不将后续工程检查冒充已通过这些研究 Gate。

## 2. 数据集与覆盖

根目录：`C:\Develop\python_projects\COMP5584_Agents\IncidentLens\data\incidentbench_v1`。

| 项目 | 实际数量 |
|---|---:|
| Core 候选 Seed / Dev / Test | **20 / 0 / 0** |
| 可辨识 / 缺证据候选 | **16 / 4** |
| 普通 / 误导 / 反事实变体 | **4 / 4 / 8**（4 对） |
| Monitoring / OOD 新生产样本 | **0 / 0** |
| 声明分组 / 有效来源聚类 / 独立审核家族 | **4 / 1 / 0** |
| 人工 Reviewer / 已接受标签 | **0 / 0** |
| 报告审查 claims / 已审 claims | **75 / 0** |
| 盲态 | `development_visible` |

所有 Oracle 状态为 `pending`，存于忽略的 evaluator-only 目录。公开包与运行 Graph 不含候选答案文件。生成器、公开数据校验、安全校验不等于人工因果正确性确认。没有复制模板冒充 100 个独立研究样本；100 例目标未达成。

候选机制覆盖：Backend pool 4、Postgres connection exhaustion 1、lock contention 4、slow query 1、Redis unavailable 4、Payment timeout 2、Backend saturation 4。

含该来源记录的案例数：Logs 20、Metrics 20、Changes 6、Configs 4、Database 8、Topology 20。Monitoring/OOD 的通用生成支持有单测，未把单测样本计入新生产数据。

公开 bundle SHA256：
`5a76e499e8172f9c4e754f789f1b377f9d7a78a59ff262ec271becaab3b80f07`

候选 Seed 标签 salted commitment：
`6a21cdd3a32223496b6d3ff7a4908bc463c85bb458630c7db2c7eceaa6fbeec0`

该承诺仅保护待审 Seed 标签完整性；**不是 Frozen Test 封存，也不是盲测证明**。原始标签和 salt 不随交付包导出。

## 3. 实际四组离线实验

路径：`C:\Develop\python_projects\COMP5584_Agents\IncidentLens\results\incidentbench\v1\20261013-offline-final`。

同一公开输入，`deterministic-public-policy-v1`、temperature 0、cache off、jobs 1、32 模型调用 / 24 工具调用 / 6 round / 600 秒预算上限。每次独立 Provider、Budget 和实验 UUID 下的唯一 run_id；顺序 seed 14100。全部使用现有 `run_investigation`，没有预填正确报告或 Real→Mock fallback。

| 变体 | 技术完成 | 候选根因命中 | 正确弃权 | 模拟 structured calls | Tool calls |
|---|---:|---:|---:|---:|---:|
| strong_single_equivalent_tools | 20/20 | **7/16** | 4/4 | 244 | 142 |
| fixed_four_equivalent_tools | 20/20 | **4/16** | 4/4 | 160 | 120 |
| dynamic_no_verifier | 20/20 | **7/16** | 4/4 | 198 | 96 |
| full | 20/20 | **7/16** | 4/4 | 244 | 142 |

这些是 **Mock + pending Oracle 的 provisional 诊断分数**，不是大模型准确率，也不是多 Agent 优越性证据。可辨识案例上的正常 INCONCLUSIVE 保留在 16 的分母中，不获正确弃权信用。

实际模型 HTTP 请求 **0**。Token、cost、human support、unsupported claim、human grounded success、remediation effectiveness 均为 **null**。Citation existence 为 1.0；它不代表语义支持，75 条审查主张全部待审。

配对差异 Full−Single = 0，Full−Fixed-four = 0.1875，Full−no-Verifier = 0；这是流程诊断。按 family/blueprint/near-duplicate/counterfactual 联合来源聚类后只有 **1 cluster**，所以 **CI 和 exact p-value 为 null**，禁止统计显著性或生产泛化主张。

重算路径：`C:\Develop\python_projects\COMP5584_Agents\IncidentLens\results\incidentbench\v1\20261013-offline-final-analysis`。

80 个 raw / scores / STARTED / DURABLE 记录及 run_id 均唯一。Case CSV 的全部逐行字段值一致，列顺序不同；其余 aggregate、paired/family CSV 和统计 JSON 字节一致。完成后的显式 resume 未改变 raw ledger，不重跑已完成/失败项。

Raw SHA256：`ca4bfe7d75606e57f567cc010825221e42fe400e4f7e67eca93a76c5806239ba`。

## 4. 实际验证与失败记录

最终串行全量：**723 passed, 0 failed, 0 errors, 3 skipped，156.56 秒**。其中 IncidentBench **86 passed, 1 skipped**。Ruff lint 通过；format check **145 files already formatted**；`git diff --check` 通过。

三项 skip 均是主机 symlink 创建权限不足；新的 Windows junction 数据根/锁文件拒绝测试实际通过。未删旧断言或将失败改为 skip。

- 首轮并发全量为 **722 passed, 1 failed, 3 skipped**：旧 Streamlit Recorded Replay 30 秒超时。
- 不改 UI 源码的独立复测 **1 passed，10.07 秒**；随后串行全量全部通过。只能称存在负载相关可能性，未证明唯一超时原因。
- 中途 Benchmark suite 的错误文案断言失败已保留；实际篡改被正确拒绝，文案统一后 targeted replay **3 passed**。
- 首次 fresh clone 暴露 Git EOL 转换导致 manifest hash mismatch；通过 `.gitattributes` 和 Git 字节重入库修正。没有改主树数据字节或覆盖旧实验，新的 clone bundle SHA 与主树完全相同。

Fresh Wheel：**7 条命令通过**，涵盖 build/install、pip check、Legacy environment/data/Mock/Replay。**这不是 wheel-only IncidentBench 验证。** 新 Benchmark 目前要求 editable source checkout；独立 wheel 缺少仓库布局资源，`create_lock` 不支持该运行方式。

Fresh editable checkout：依赖安装、pip check、公开数据校验通过；CLI E2E **1 passed，15.51 秒**，实际执行 **8 次 Mock Graph** 并重算。该环境与 clone 留存在 `.worktrees/v14-reproduce-env` 和 `.worktrees/v14-clean-checkout`。

重新核对 **253 个原有 data 文件，0 字节变化**。原 `llm/`、`evaluation/`、EvidenceProvider、FinalizeGate 和 `scripts/run_eval.py` 无 diff。历史结果没有重写；源计划文件仍按原样保留未跟踪状态。

## 5. 修改文件与工作流

所有代码位于 `C:\Develop\python_projects\COMP5584_Agents\IncidentLens`；完整逐文件列表见交付的 `changed-files.txt`。

- 新增 `src/incident_lens/incidentbench/`：schemas、builder/scenarios、family_split、oracle_store、validator、manifest、normalizer、scorer、citation_review、statistics、experiment。
- 新增六个 CLI：build、validate、run、analyze、prepare_citation_review、seal IncidentBench。
- 新增 `tests/incidentbench/`，包含实际 Graph/CLI/恢复/安全/统计/重算测试。
- 新增公开候选数据、protocol config、数据/标注/盲测/公平/统计/验收文档。
- 共享改动：`orchestration/graph.py` 和 `schemas/workflow.py` 仅显式 benchmark opt-in、DB 等价工具和 fixed-four；legacy fixed 仍为三专家。更新双语 README、忽略私人 Oracle、冻结数据字节的 Git attributes。

隔离 WP 提交（已由 Lead 逐项 cherry-pick）：A `c5e2cd7`；B `1a25696` + `9ce8940`；C 初版 `203f66f`、中断恢复增量 `1923e7e`；D `146e002`。E 为只读独立技术 QA，没有冒充人工标注。Lead 集成及安全/重算/字节修复另有本地提交。

中断续接时核对了 main、五个 worktree、暂存/未暂存 C 增量和后台进程；无残留测试进程。C 增量保留后重新指派实现/QA，未将未执行的 80-run、最终 suite、安装验收标为完成。续接清单保留在 `results/acceptance/v14/continuation-audit.json`。

## 6. 实际运行命令

以下从仓库根目录执行，已有输出不能覆盖：

```powershell
.venv\Scripts\python.exe -m pytest -q --junitxml=results/acceptance/v14/final/full-pytest-serial.xml
.venv\Scripts\python.exe -m ruff check src tests scripts
.venv\Scripts\python.exe -m ruff format --check src tests scripts
.venv\Scripts\python.exe scripts/validate_incidentbench.py --dataset data/incidentbench_v1 --mode public
.venv\Scripts\python.exe scripts/validate_incidentbench.py --dataset data/incidentbench_v1 --mode privileged --oracle-root local_oracles/incidentbench_v1
.venv\Scripts\python.exe scripts/run_incidentbench.py --dataset data/incidentbench_v1 --split seed --variant all --provider mock --protocol configs/incidentbench-protocol.yaml --oracle-root local_oracles/incidentbench_v1 --cache-mode off --jobs 1 --out results/incidentbench/v1/20261013-offline-final
.venv\Scripts\python.exe scripts/analyze_incidentbench.py --input results/incidentbench/v1/20261013-offline-final/raw-runs.jsonl --oracle-root local_oracles/incidentbench_v1 --out results/incidentbench/v1/20261013-offline-final-analysis
.venv\Scripts\python.exe scripts/run_incidentbench.py --dataset data/incidentbench_v1 --split seed --variant all --provider mock --protocol configs/incidentbench-protocol.yaml --oracle-root local_oracles/incidentbench_v1 --cache-mode off --jobs 1 --out results/incidentbench/v1/20261013-offline-final --resume
.venv\Scripts\python.exe scripts/verify_install.py --out results/acceptance/v14/final/fresh-install
```

完整重新生成应使用新 demo 根与新的 evaluator 根；不要重新写入已交付的数据或结果。输入生成方法见 IncidentBench README。正式 Test 不执行调参或评分，本次 Test 为空。

源码 SHA：`21aa09c11cf29ee8edc512f05740ca98183af411249692c775b2b16c652caedd`。
Prompt SHA：`79ee059c2b50b7b77af1b942cbb3e99daea547588badd9fcbe1ef5a48256bdb2`。
Protocol SHA：`f041cd492fda139bc286459c1e43a75d98f48fefb50f2553b3833e193cf3ff4b`。
Python **3.13.5**；Pydantic 2.14.0、LangGraph 1.2.14、httpx 0.28.1、PyYAML 6.0.3、NumPy 2.2.6。

## 7. 未完成事项与可信度边界

1. 独立因果蓝图与独立 Dev/Frozen Test、目标 100 个经审查案例尚未建设完成；现有 20 例是开发候选。
2. 两位实际人工 Reviewer、独立 Label Owner、真值签收、冲突裁定与 75 条引用语义审核尚未发生。
3. P5 正式封存和正式 Runner 验收、P6 真实模型公平比较、真实实验恢复尚未完成；当前正式执行 fail-closed，real resume 不支持。
4. 没有足够独立聚类进行研究统计推断，没有真实模型、生产泛化或多 Agent 优越性证据。
5. 新 Monitoring/OOD production cohort 数量为 0；旧功能回归通过不等于完成新专项研究。PLAN_ONLY 不表示修复成功。
6. 仅支持 editable checkout 的 Benchmark；原始完成文件含本地路径，搬迁后的独立重算尚无重定位协议。软件能核查审查来源字段，但不能认证其确为人类填写；安全路径检查仍有通常的 TOCTOU 边界。

以上事项不能由 Coding Agent 伪造补齐。本次交付可用于继续真实场景设计、人工标注与后续授权实验，不是完整研究级 V1.4 发布。
