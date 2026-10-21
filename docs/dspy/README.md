# IncidentLens × DSPy：实施、复现与验收

日期：2026-10-21。基线：`fb0c848d5f25`，Python 3.12，DSPy 3.0.4。

当前结论：**离线优化及可回滚工程链路已验证；质量改善尚未确立。正式优化版本上线 NO-GO。**
LangGraph、Provider、动态 Pydantic Schema、ACL、预算、Oracle 隔离继续执行原有职责。
默认运行不导入 DSPy，不加载候选 Bundle，不改变原始任务指令。

## 已完成与待完成

| 阶段 | 已交付 | 尚需的证据 |
| --- | --- | --- |
| P0 可行性 | 依赖安装、pip check、自定义 Adapter、风险分析、兼容测试 | 真实模型端点及预算 |
| P1 基线与数据 | 完整 Prompt 冻结、历史 Trace 清单审计、调用前采集器、标注 Schema 与协议 | 双人审核、裁决、独立 Test |
| P2–P3 优化 | Manual/LabeledFewShot/BootstrapFewShot/MIPROv2；逐模块对照与成本记录程序 | 经审核的真实数据训练与 Dev 选择；真实质量结果 |
| P4 集成 | 显式 Bundle、版本与内容哈希、缓存隔离、CLI、追踪、回滚及 CI | 胜出 Bundle 的人工审阅和等价性审查 |
| P5 验证 | 160 次 Mock 系统对照、模块/边界回归、验收记录 | 真实多架构对照及人工语义终审 |

未把 Mock 的高分或可导出性作为 H1–H4 的实验证据。没有创建“已审核”的生产 Bundle。

## 代码入口

- `src/incident_lens/prompts/resolver.py`：严格 Bundle 格式、基线兼容检查、确定性渲染。
- `src/incident_lens/prompts/calls.py`：在原始 structured_call 外附加版本元数据与可选采集。
- `src/incident_lens/prompts/snapshots.py`：显式启用的 JSONL 采集器，按调用关联请求与结果/失败。
- `agents/service.py`：仅 Analysis/Verifier 接收附加任务指令；所有原始安全与角色指令保留。
- `cache/semantic.py`：原 Prompt 版本和 Bundle 内容哈希共同参与命名空间。
- `evaluation/runner.py`：测量包装器保留 Resolver/采集器，记录 optimizer/hash/format。
- `experiments/dspy/`：独立离线数据、重放、Adapter、优化器、单模块与系统评估。
- `tests/dspy/`：候选拒绝、版本不兼容、引用边界、缓存隔离、预算与四种优化器测试。

安全规则继续保留在不可由 Bundle 替换的基线中；可优化任务指导和示例只作为附加部分。
“不可替换”指 Resolver 不提供覆盖接口，不代表 Prompt 本身能够保证模型绝不受注入影响。
真正的权限、证据 ID、身份、Schema 与预算约束仍由原运行时代码执行。

## 安装和纯离线验证

在仓库根目录执行，避免把目录名 `experiments/dspy` 作为 Python 的运行目录。

```bash
python -m venv .venv
.venv/bin/python -m pip install -r experiments/dspy/requirements.lock
.venv/bin/python -m pip install -e '.[dev,dspy]'
.venv/bin/python -m pip check
INCIDENT_LENS_OFFLINE_TESTS=1 .venv/bin/python -m pytest -q tests/dspy
.venv/bin/python -m ruff check src tests scripts experiments
```

Windows 将 `.venv/bin/python` 替换为 `.venv/Scripts/python.exe`。
锁文件记录本次 Python 3.12 环境，包括传递依赖；不替换项目原有 requirements.lock。
DSPy 为可选 extra。新增 CI 独立安装它；普通运行时不需要安装。
实验包禁用 LiteLLM 导入时的在线价格表下载，既不使用它的传输，也不使用推测价格。
费用未知保留空值，不根据价格表估算。

完整 Python/JavaScript 回归使用项目 CI 中的 Node 22。本环境默认 Node 24.19.0
已移除旧测试使用的 `--experimental-default-type`，曾导致一个 UI 测试失败；验证时
安装独立 Node 22 并仅调整验证命令 PATH，没有改动产品或测试以隐藏该问题。

## 历史 Trace 可行性审计

```bash
.venv/bin/python -m experiments.dspy audit --root . --out results/dspy-audit-new
```

审计以原 `inspection.json` 的 12 条路径及 SHA-256 为清单，不另行挑选运行。
当前有 11 个原 Trace 文件可用且哈希匹配，1 个缺失。生成的 worksheet 包含最终
hypothesis、against_ids 和对应公开记录，全部待审核。**可用于训练的精确历史快照数为 0。**
最终共享状态不能冒充 Analysis 所见的局部工具结果，或 Verifier 当时获取的证据。
Coordinator 还会做 hypothesis_updates；最终错误归属必须保留 unknown，直到有调用前后证据。

原 6/8 弱反驳发现保留为探索性问题线索。它来自已选取的完成运行，未经独立双人裁决，
不能推广为总体错误率，也不能证明 Analysis/Verifier 是错误源。没有修改原 Trace 或报告。

## 新快照与标注协议

```bash
.venv/bin/incident-lens run --case incident_001 --provider mock \
  --out results/dspy-capture-run \
  --record-decisions results/dspy-decision-events.jsonl
.venv/bin/python -m experiments.dspy extract \
  --events results/dspy-decision-events.jsonl --out results/dspy-pending.jsonl
```

采集发生在实际 Provider 调用前，保存传入的公开 payload、当次 Schema、system prompt、
版本/哈希；另行记录 Provider 的结构化结果或异常类别和 usage。Provider 结果还不等于
通过后续身份/领域检查的结果；必须经 replay 再验证。采集默认关闭，保存位置应控制访问。
不记录环境变量、API key、Authorization header 或私有 Oracle。公开日志也可能含敏感内容，
发布数据前仍须清理并重新冻结数据哈希。

提取器去重 stage/payload/schema，相同真实调用输入只保留一个样本。失败请求也可成为
待审样本；任何模型输出都不会自动晋升为 gold。详见 `Sample.schema.json`。

每条样本必须完成以下审核：

1. 保留原 payload、Schema、Prompt 和来源哈希，填写 incident/family/near-duplicate cluster 的出处。
2. 独立两人审核并记录不同 reviewer 标识；分歧记录 adjudication，不默认采纳模型结论。
3. 为候选原因与证据标记 supports/directly_refutes/insufficient/irrelevant/unknown，附机制和时间依据。
4. 区分“支持 A”“直接反驳 B”“尚无证据”，正常拓扑、空查询和故障前健康不能单独反驳故障后原因。
5. 填写完整 expected 输出；Analysis 每个支持/反对引用都须有匹配的语义关系标注。
6. 标注正确/错误弃权、error_owner、prompt_fixable；系统错误先修逻辑，不能交给 Prompt 掩盖。
7. 设置 train/dev；同一事故不能跨集合。保守的默认 family/cluster 表示共享合成源，不伪造独立性。
8. 冻结样本文件及哈希。Test 必须与 train/dev 的事故、来源家族和近重复 cluster 分离。

CLI 拒绝 pending、单 reviewer、缺少裁决/理由、gold Schema 不合法和无语义标注的引用。
标签、原始 gold、family、split、rationale 和 Oracle 不进入当前待预测样本的模型输入。
Few-shot 只能来自训练集合；其输入与期望输出当然是示例内容，不得将评估样本放入示例。

## A0–A3 单模块实验

配置先登记在 `protocol.json`，主目标 H1，H2–H4 次要。
A0 原始；A1 固定人工选例；A2 LabeledFewShot 或 BootstrapFewShot；A3 MIPROv2。
A1/A2 使用同一初始附加指令、相同 shot 上限；记录实际示例数及完整消息大小。
LabeledFewShot 仅作随机示例选择对照，不是性能驱动的选择器。DSPy 3.0.4 内部 seed 为 0。
MIPROv2 使用显式 seed，并记录实际提案、验证和搜索调用；trial 数不等于请求数。

```bash
.venv/bin/python -m experiments.dspy optimize \
  --data reviewed-samples.jsonl --stage analysis --optimizer manual \
  --shots 2 --provider real --max-requests 100 --out results/dspy-A1-analysis
.venv/bin/python -m experiments.dspy optimize \
  --data reviewed-samples.jsonl --stage analysis --optimizer BootstrapFewShot \
  --shots 2 --provider real --max-requests 200 --out results/dspy-A2-analysis
.venv/bin/python -m experiments.dspy optimize \
  --data reviewed-samples.jsonl --stage analysis --optimizer MIPROv2 \
  --shots 2 --seed 21 --trials 8 --provider real --max-requests 500 \
  --out results/dspy-A3-analysis
.venv/bin/python -m experiments.dspy evaluate \
  --data reviewed-samples.jsonl --split dev --provider real --max-requests 200 \
  --bundle A1=results/dspy-A1-analysis/candidate.json \
  --bundle A2=results/dspy-A2-analysis/candidate.json \
  --bundle A3=results/dspy-A3-analysis/candidate.json --out results/dspy-module-dev
```

Verifier 用 `--stage verify` 分别执行；不能把 Analysis 的局部指标视为 Verifier 改善。
真实 Provider 读取 `INCIDENT_LENS_DSPY_ENDPOINT`、`INCIDENT_LENS_DSPY_API_KEY`、
`INCIDENT_LENS_DSPY_MODEL`；endpoint 沿用 RealChatProvider 的 base URL 约定。
此环境未配置这些凭据，因此未发起真实模型请求。

训练及选优 Dev 会被优化器使用，不能再充当未见 Test。单模块 Test 路径要求独立来源拆分。
系统工具仅允许 seed/dev；正式 Test 需另冻结协议，避免误用现有共享合成 Test 名称。
输出目录必须不存在；失败不隐式覆盖或续跑付费任务。保留失败输出目录和终端日志再诊断。

指标为：gold 引用关系与候选状态完全一致率；每个候选是否有多余反对引用或错误拒绝；
Schema/领域成功、实际请求、原 usage 和时延；逐样本改善/退化配对。
引用关系指标只是可自动计算的代理，**不判断自由文本反驳理由是否成立**。
不得只优化该分数就宣称 H1 成立；人工需要盲审模型输出里的因果解释与弃权质量。
输出失败计为错误，未测得的反驳次数保留 null，不当作零错误。

## Adapter 与导出格式

采用 `incidentlens-task-json-v1`：保留原始安全/角色 Prompt，再附加 Signature.instructions
和 canonical JSON 示例。`dspy.Predict` 通过自定义 IncidentAdapter 调用原 service 函数，
而不是绕过 Provider。MIPRO 指令提案也通过现有 structured_call，受全局实验请求许可上限约束。
请求上限包含修复和优化提案；它是请求数约束，不是美元或 Token 费用上限。
每个真实 HTTP 请求仍受原超时约束；离线整批若需严格 wall/Token 预算需由外部调度进一步限定。

导出校验实际调用原生 Predict+Adapter 和 Bundle replay，比较完整消息、输入及动态 Schema。
仅证明该自定义 Adapter 的等价性，不能推广到 DSPy ChatAdapter/JSONAdapter 或任意保存程序。
只导出 JSON，无 pickle/任意代码反序列化。没有宣称可直接部署原生 DSPy 保存文件。

## 系统实验与回滚

```bash
.venv/bin/python -m experiments.dspy system --data-root data --split dev \
  --provider real --max-requests 2000 --max-calls 32 \
  --bundle A3=results/dspy-A3-analysis/candidate.json --out results/dspy-system-dev
```

每个条件完整执行 Full/Single/Fixed/NoVerifier，cache 强制 off，模型、temperature、
预算及数据版本保持相同；使用已有 oracle-after-run runner。报告逐事故与架构配对成本，
根因和弃权分开计分。整个 arm 的运行顺序按 seed 打乱；当前没有按每个事故交错，
因此真实时延比较仍可能受时间漂移影响，正式研究应补交错和多次独立重复。

正式 CLI 只加载标记 reviewed、具 reviewer 和 review_evidence、且匹配冻结基线的 Bundle。
这些字段是审核记录，不是电子签名；通过代码评审与受控文件发布建立审核可信性。
原始候选保持 candidate，在实验路径内可用，正常 CLI 会拒绝。

```bash
.venv/bin/incident-lens run --case incident_001 --provider mock \
  --prompt-bundle reviewed-bundle.json --out results/reviewed-run
# 回滚：省略 --prompt-bundle；原始 Prompt 与独立缓存命名空间自动恢复。
```

合并两个 stage Bundle 时保留每个 stage 的训练及选优来源、编译日志和等价性结果，
重新计算 Bundle 哈希后再审核。不要手动删掉示例而继续使用旧实验身份。

## 验收和风险

- 安全：不得新增 ACL 越权、跨 incident 引用、绕过 Schema、Oracle 泄漏或预算超限。
- H1：预注册每候选错误反驳计数，目标相对下降 ≥25%；零基线不计算相对下降。
- 根因/弃权：逐事故报告退化，质量负责人审查是否可接受，不能只平均掉弃权退化。
- 小样本：列出原始次数与配对改善/退化，不用单一百分比宣称显著性。
- 成本：测请求、Token 完整性、工具、时延与编译额外开销；未知费用 null。
- 只要缺可信人审、独立来源或真实实验，结论继续是“质量改善尚未确立”。

| 风险 | 当前处理 | 退出条件 |
| --- | --- | --- |
| 错误来自 Coordinator/merge/gate | worksheet owner 默认 unknown，先定位 | 非 Prompt 问题转逻辑修复 |
| 共享合成源过拟合 | cluster/family gate；Test 需独立 | 无独立来源不作泛化结论 |
| 指标投机/空输出 | 完整 gold judgment 比较，额外/缺失候选扣分 | 保留人工盲审 |
| few-shot 引入别的事故 ID | 原动态引用和身份校验继续执行 | 任一越权回退 |
| 原生/导出格式不同 | 自定义 Adapter 与消息级比较 | 不等价不得当同条件 |
| 预算或模型不可用 | 显式请求上限、每请求超时、失败留痕 | 无凭据不发真实请求 |
| Prompt 失效/版本漂移 | baseline hash 校验和缓存隔离 | 不兼容拒绝加载 |
| 微小样本多次择优 | 固定 Dev 搜索，单独 Test | 不在 Test 上继续调参 |

## 后续排期与责任交接

10/22–24：架构负责人复核本可行性结果，确认模型与经费。
10/25–29：数据负责人采集真实调用前输入；两名审核者及评价负责人裁决并冻结 train/dev。
10/30–11/08：DSPy 负责人运行单模块实验；评价负责人做配对和成本分析。
11/09–15：架构与 QA 审核胜出 Bundle、检查消息等价及安全回归；未过门槛不推广。
11/16–20：评价/QA 完成真实系统对照、人工盲审、异常与回滚；协调负责人冻结演示材料。
具体人员沿用六人现有职责，本实现未擅自给成员指派工作或发送消息。
