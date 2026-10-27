# 08 · 评估体系与 IncidentBench

评估相关代码：[`evaluation/`](../../src/incident_lens/evaluation)、[`incidentbench/`](../../src/incident_lens/incidentbench)；脚本在 [`scripts/`](../../scripts)。

## 1. 评估设计原则

1. **先执行，后读 oracle**：原始状态先落盘，评分阶段才加载 `private/` oracle，避免运行时泄漏。
2. **失败计入分母，不可判定则单列**：在可识别且非 `NO_ALERT` 的案例上，技术失败会被打成 `False`（而非 `None`），因此进入 `root_cause_accuracy` 的分母；反之，不可识别、`NO_ALERT`、或缺少 oracle 的指标为 `None`，在 `aggregate()` 中被排除出分母，并以 `*_unknown` 计数单列——绝不把"未知"变成 0。
3. **引用存在 ≠ 语义支持**：`citation_existence_validity` 只验证引用是否真实观测；语义支持需要人工复核（`semantic_review_status`）。
4. **可复算**：每行含 `scoring_version`；混合版本禁止聚合。
5. **同配置对比**：所有变体必须共享同一 provider、budget、dataset revision、prompt/schema 版本；任何一个漂移都会报错。

## 2. 运行时变体 vs 基准条件

| 运行时 `variant` | IncidentBench 条件名 | 说明 |
| --- | --- | --- |
| `single` | `strong_single_equivalent_tools` | 单智能体自规划、自反思，等价数据库工具 |
| `fixed` + `benchmark_fixed_four` | `fixed_four_equivalent_tools` | 固定 logs+metrics+database+changes 四专家 |
| `dynamic_no_verifier` | `dynamic_no_verifier` | 动态协调但无独立审查 |
| `full` | `full` | 完整系统（含 Verifier） |

`legacy fixed`（三专家）与 `fixed_four` 是不同条件，不能混用。

## 3. 消融评估流水线（`evaluation/runner.py`）

`evaluate_split(data_root, split, variants, provider_factory, out, budget, provider_name, jobs)`（L217）：

```text
1. 校验 jobs ∈ 1..4、provider ∈ {mock, real}、variants 合法且不重复
2. load_split(data_root, split) → incident_ids（只读 splits，不读 oracle）
3. EvidenceProvider 计算 dataset_revision
4. 计算 src/incident_lens 全部 .py 的 source_sha256
5. 每个 (incident, variant) 独立创建 provider（禁止复用实例）
6. MeasuredProvider 包装：统计物理请求、usage、失败
7. 校验所有变体的 config 完全一致（provider/model/temperature/budget/prompt/schema/dataset revision）
8. 运行 run_investigation(..., cache=None)
9. 异常 → 构造 ERROR 状态（report.status=ERROR），保留失败
10. 写 raw-runs.jsonl（先落盘）
11. 读 oracle → score_completed / score_without_oracle
12. 写 case-level.csv / aggregate.csv / error-analysis.md
```

### 3.1 `MeasuredProvider`（L85）

包装任意 Provider，记录：

- `llm_requests`（物理尝试数）；
- `failed_calls`；
- `total_tokens` / `measured_total_tokens` / `tokens_complete`；
- `latency_ms`；
- 每次调用的 `call_id` 与失败分类。

`usage_metrics(provider, state)` 把 Provider 计数与 state 计数对账，防止漏记。

### 3.2 输出文件

| 文件 | 内容 |
| --- | --- |
| `raw-runs.jsonl` | 每个 (case, variant) 的完整 state、`metrics` 行、`fairness` 配置快照、`measured_calls`、以及**仅评测侧**的 oracle 字段 |
| `case-level.csv` | 每个运行一行指标（含 `config_sha256`、`initial_public_sha256`、`dataset_revision`） |
| `aggregate.csv` | 按 variant 聚合 |
| `error-analysis.md` | 失败分类、需人工复核的案例、Mock 免责声明 |

流程中 `raw-runs.jsonl` 每完成一个 case 就追加一次，全部结束后排序重写；`case-level.csv` 也是增量刷新。中途中断的付费运行仍可审计。

## 4. 指标（`evaluation/metrics.py`）

### 4.1 `score_completed(state, oracle)`

| 指标 | 定义 |
| --- | --- |
| `diagnosis_match` | `RESOLVED` 且 culprit + failure_mode 均匹配 oracle |
| `root_cause_correct` | 协议有效、非诊断失败、且 diagnosis_match |
| `correct_abstention` | 不可识别案例中，非 runtime failure、协议有效、`INCONCLUSIVE` 且无根因 |
| `monitoring_accuracy` | `IncidentAlert.status` 与 oracle 的 `monitoring_expected_alert` 一致 |
| `remediation_success` | `PLAN_READY` 且协议有效；`PLAN_FAILED` 则 False |
| `workflow_success` | SUCCESS→正确；ABSTAINED→正确弃权且不可识别；NO_ACTION→监控准确；FAILED→False |
| `misleading_correct` | 误导证据案例中仍给出正确根因 |
| `misleading_decoy_observed` | 误导证据是否被实际观测到 |
| `citation_existence_validity` | 报告引用中"存在于索引且被 TOOL_CALL 实际观测"的比例 |
| `unsupported_claim_rate` | 需人工复核；未复核恒为 `None` |
| `semantic_review_status` | `unreviewed` / `reviewed` |

`score_without_oracle(state)`：保留执行事实与引用指标，所有答案质量字段为 `None`，绝不虚构真值。

### 4.2 `aggregate(rows)`

- 按 `VARIANTS = (single, fixed, dynamic_no_verifier, full)` 分组；
- 混合 `scoring_version` 直接报错；
- 每个指标输出 `_successes` / `_failures` / `_denominator` / `_unknown` / `_rate`；
- 成本类（tool_calls、llm_requests、tokens、cost、latency）只有在全部非空时才求和；
- `token_usage_basis = "provider_reported; measured_total_tokens is a lower bound when incomplete"`。

### 4.3 其他评估模块

| 文件 | 职责 |
| --- | --- |
| `verifier.py` | `verifier_metrics(state)`：审查次数、复用、请求检查、拒绝原因 |
| `reliability_metrics.py` | `aggregate_reliability(rows)`、`technical_completion(state)`：技术完成率、恢复率 |
| `v16.py` | v1.6 质量评分、`summarize`、`write_companion` |
| `retest_provenance.py` | 重测前后代码/数据快照对比 |
| `run_io.py` | `atomic_bytes` / `atomic_json` / `append_json`：原子写与独占创建 |

## 5. 终止协议校验（`evaluation/termination.py`）

`normalize_termination(state)` 把三种历史形态统一成可评分结果：

| 来源 | 判定 |
| --- | --- |
| `v2` | 存在 `state.termination`、report 内 termination、或 `REQUEST`/terminal 事件 / `protocol_version=2` |
| `legacy` | 旧版 trace，无协议字段 |
| 混合/损坏 | 记录 `protocol_valid=False` 与语义错误 |

v2 校验：

1. `TerminationResult` 可反序列化；
2. state 与 report 的 termination 完全一致；
3. 恰好一个 `REQUEST` 与一个 terminal 事件，且不能有 legacy `STOP`；
4. REQUEST 在 terminal 之前；
5. terminal 的 details 与 termination 一致；
6. terminal 类型（`NORMAL_TERMINATION` / `RUNTIME_FAILURE`）与 `runtime_failure` 一致；
7. REQUEST 的 `stop_reason` 与最终 reason 兼容（`STOP_TIMEOUT` 允许请求时的任一正常原因）；
8. `required_roles` 合法；
9. ACK 覆盖所有必需角色；否则 `STOP_TIMEOUT`；
10. `stop_completed` 与实际 STOP/ACK 状态一致。

`recovered_call_ids(events)` 识别"失败后又被成功重试"的 call_id，用于区分**已恢复失败**与**未恢复失败**。这直接决定 `INCONCLUSIVE` 是否应升级为 `UNRECOVERABLE_ERROR`。

`SCORING_VERSION` 随协议演进；聚合时强校验。

## 6. 主动证据评估（`evaluation/active_evidence/`）

| 文件 | 职责 |
| --- | --- |
| `variants.py` | 6 个 CAES 变体 B0–B4 |
| `runner.py` | 实验执行、锁、断点续跑 |
| `metrics.py` | 选择事件、选择指标（覆盖率、信息增益、成本） |
| `recovery.py` | 中断恢复：从 raw + oracle 重新评分 |
| `replay.py` | 从选择事件重放决策 |
| `statistics.py` | bootstrap 置信区间、配对检验 |

CAES 变体映射：

| 变体 | `selection_policy` | 消融点 |
| --- | --- | --- |
| B0 | `current_dynamic` | 基准（+`benchmark_fixed_four`） |
| B1 | `current_dynamic` | 动态基线 |
| B1c | `first_eligible` | 首个合格候选，无打分 |
| B2 | `active_no_cost` | 去掉成本项 |
| B3 | `active_no_discrimination` | 去掉判别力项 |
| B4 | `active_evidence` | 完整 CAES |

`workflow_values(variant, config)` 固定：`legacy_rca`、数据库等价工具、`benchmark_rca=True`、`remediation_enabled=False`、`shadow_caes=False`。

## 7. IncidentBench 数据集

### 7.1 目录

```text
data/incidentbench_v1/
├── public_case_index.json          # 案例元数据（不含答案）
├── rca/                            # 公开证据包
│   └── incidents/incident_xxx/public/{incident.json,logs.jsonl,metrics.csv,...}
├── splits/{seed,dev,test}_ids.json
└── manifest.json                   # 哈希清单

<oracle_root>/                     # 物理分离的私有标签
└── oracle/incident_xxx.json
```

### 7.2 案例元数据（`BenchmarkCaseMetadata`）

`incident_id`、`split`、`scenario_family_id`、`scenario_variant_id`、`challenge_tags`、`public_sha256`、`source_blueprint_id`、`near_duplicate_cluster_id`、`counterfactual_pair_id`、`cohort`（`core` / `ood` / `monitoring`）。

### 7.3 Oracle（`BenchmarkOracle`）

含 `true_primary_root`（culprit + failure_mode + `root_cause_code`）、`acceptable_support_sets`、`contradicting_evidence_ids`、`misleading_evidence_ids`、`required_discriminator_types`、`causal_sequence`、`identifiability_rationale`、`is_identifiable`、`annotator_status`、`review_version`、`cohort`、`reviewer_ids`。

标签约束：

- `is_identifiable == bool(acceptable_support_sets)`；
- `annotator_status != "pending"` 时必须至少有 2 个独立 reviewer；
- `cohort == "core"` 时 failure_mode 必须是允许的 7 类（ood/monitoring 可超出）。

### 7.4 构建与校验

| 模块 | 职责 |
| --- | --- |
| `builder.py` | `build_dataset(config, out, oracle_root)`：生成 public 包与 oracle，写 public index、splits、manifest |
| `scenarios/world.py` | `World`、`simulate(spec, variant)`、`encode(world, incident_id)`：从故障世界模型生成一致的日志/指标/变更/数据库证据 |
| `validator.py` | `validate_dataset`: 文件完整性、public/oracle 分离、哈希、可解性、无泄漏 |
| `manifest.py` | `digest_tree`、`create_lock` / `verify_lock`、`label_commitment`、`seal_dataset` |
| `family_split.py` | 按故障族分层切分，避免同族跨 split 泄漏 |
| `normalizer.py` | `normalize(state)` → 统一评分行 |
| `oracle_store.py` | `OracleStore`：路径白名单 + 只能读 oracle 目录 |

## 8. IncidentBench 实验（`incidentbench/experiment.py`）

`run_experiment(dataset, split, provider_factory, out, protocol, oracle_root)`（L424）：

```text
1. 校验 protocol / dataset / readiness
2. 正式模式要求 provider=real 且 model 已冻结
3. load_cases：public index + split ids 双向一致
4. dataset lock / execution lock（独占文件锁）
5. run_order：case × repeat × variant 随机打乱（固定 seed）
6. 每个运行：独立 provider / budget / run_id，cache=off
7. 原始 state 先持久化（durable_write）
8. 运行结束才加载 oracle → score_benchmark_run
9. 支持 resume：校验锁与协议一致后从已完成集合继续
10. finalize_experiment：汇总、配对分析、导出
```

`ExperimentProtocol` 默认值：

`max_rounds=6`、`max_tool_calls=24`、`max_llm_calls=32`、`max_wall_seconds=600`、`jobs=1..8`、`run_order_seed=14100`、`repeats=1`、`response_format=json_schema`、`request_timeout=180`、`cache_mode=off`、`blindness_level=development_visible`、`analysis_seed=14101`、`bootstrap_samples=10000`、`analysis_plan=family_clustered_paired_bootstrap_plus_exact_discordance`。

强约束：`variants` 必须恰好是 4 个等价工具条件；`formal=True` 必须 `provider=real` 且 `model_id` 已冻结。

## 9. 评分与统计

### 9.1 `score_benchmark_run(state, oracle=None, annotations=None)`

- 无 oracle：只给执行事实，标签字段为 `None`；
- 有 oracle：`technical_completion` 且 `RESOLVED` 且 culprit+mode 匹配 → 正确；
- 不可识别案例：正确弃权；
- 误导案例：单独统计；
- 有人工复核：`human_support_rate`、`unsupported_claim_rate`、`human_grounded_success`。

### 9.2 统计（`incidentbench/statistics.py`）

| 函数 | 作用 |
| --- | --- |
| `effective_clusters(rows)` | 按 scenario family 聚类，处理同族相关性 |
| `paired_comparison(rows, baseline, metric)` | 配对 bootstrap，输出差值 CI 与 exact discordance |
| `analyze(rows)` | 全指标汇总 |

随机种子默认 `14101`，bootstrap 10000 次。

### 9.3 人工引用复核（`citation_review.py`）

- `prepare_review_bundle(states)`：抽取每个 run 的关键 claim + 观测证据；
- `merge_reviews(bundle, records, adjudications)`：合并双人标注与裁决；
- `review_coverage`：覆盖率、支持率、不支持率；
- `validate_truth_reviews`：校验复核文档与 oracle 版本一致。

### 9.4 门禁（`readiness.py`）

`evaluate_run` / `summarize` / `validate_completed` / `validate_acceptance` / `evaluate_completed`：正式发布前检查数据完整性、盲测、标签一致性、预算与协议冻结。

## 10. 常用脚本

| 脚本 | 用途 |
| --- | --- |
| `scripts/run_eval.py` | 运行 `evaluate_split` |
| `scripts/analyze_eval.py` | 聚合、bootstrap、故障分析 |
| `scripts/rescore_eval.py` | 用新评分版本重算历史 raw |
| `scripts/run_reliability_eval.py` | 可靠性/技术完成率 |
| `scripts/run_cache_eval.py` | 缓存命中与节省 |
| `scripts/run_incidentbench.py` | IncidentBench 实验 |
| `scripts/analyze_incidentbench.py` | 统计与配对分析 |
| `scripts/build_incidentbench.py` | 生成数据集 |
| `scripts/validate_incidentbench.py` | 数据校验 |
| `scripts/seal_incidentbench.py` | 冻结数据集 |
| `scripts/prepare_citation_review.py` | 生成引用复核包 |
| `scripts/run_v15_active_eval.py` | CAES 主动证据实验 |
| `scripts/analyze_v15_active.py` | CAES 统计 |

## 11. 复现实验的最小步骤

```bash
# 1. 离线消融
python scripts/run_eval.py --split dev --variants single fixed dynamic_no_verifier full \
  --provider mock --out runs/ablation-dev

# 2. 聚合
python scripts/analyze_eval.py --runs runs/ablation-dev

# 3. IncidentBench（开发协议）
python scripts/validate_incidentbench.py --dataset data/incidentbench_v1
python scripts/run_incidentbench.py --dataset data/incidentbench_v1 --split dev \
  --protocol configs/incidentbench-protocol.yaml --out runs/incidentbench-dev

# 4. 统计
python scripts/analyze_incidentbench.py --runs runs/incidentbench-dev
```

正式实验必须使用 `formal=true` 的冻结协议、真实模型与私有 oracle；开发协议的数字不能当作最终结论。
