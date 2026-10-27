# IncidentLens Code Wiki

本 Wiki 面向希望快速理解、运行和扩展 IncidentLens 的开发者。内容基于仓库源码（`src/incident_lens`，约 1.5 万行 Python）与测试、配置、脚本整理而成。

## 项目一句话

IncidentLens 是一个**证据驱动的多智能体软件故障根因分析（RCA）系统**：多个受限角色在只读工具 ACL 与预算约束下调查日志、指标、数据库和变更记录，由确定性 Gate 强制"有引用才可下结论，否则显式弃权（`INCONCLUSIVE`）"。

- 包名：`incident-lens`，版本 `1.6.1`
- 语言 / 运行时：Python `>=3.11`
- 编排框架：LangGraph `StateGraph`
- 数据契约：Pydantic v2 StrictModel
- 入口：CLI `incident-lens` / `python -m incident_lens.cli`，Web（Starlette + 原生 JS SPA），可选 Streamlit

## 文档地图

| 文档 | 内容 | 适合谁 |
| --- | --- | --- |
| [01-architecture.md](01-architecture.md) | 系统分层、核心数据流、设计原则、线程/并发模型 | 所有人，先读这篇 |
| [02-module-map.md](02-module-map.md) | 目录树与每个包的职责、模块清单 | 需要定位代码的人 |
| [03-orchestration.md](03-orchestration.md) | LangGraph 九节点工作流、路由、预算、STOP、Merge、Gate、CAES | 修改运行时行为的人 |
| [04-agents-and-prompts.md](04-agents-and-prompts.md) | 各 Agent 角色、Prompt 组织、结构化输出绑定、Mock 策略 | 调整调查策略/提示词的人 |
| [05-data-contracts.md](05-data-contracts.md) | 核心 Pydantic 模型、状态机、枚举、跨模型不变量 | 改 schema / 写测试的人 |
| [06-tools-and-security.md](06-tools-and-security.md) | 工具清单、权限矩阵、只读证据加载、查询账本、路径安全 | 安全与工具开发者 |
| [07-llm-and-cache.md](07-llm-and-cache.md) | Provider 抽象、结构化输出修复、错误分类、重试预算、语义缓存 | 接入模型/调优可靠性的人 |
| [08-evaluation-and-benchmark.md](08-evaluation-and-benchmark.md) | 消融评估、指标、终止协议校验、IncidentBench 数据集与实验 | 做实验与论文复现的人 |
| [09-interfaces.md](09-interfaces.md) | CLI 子命令、Web API/SPA、Streamlit、产物与 Replay | 使用/集成系统的人 |
| [10-running-and-testing.md](10-running-and-testing.md) | 安装、配置项、常用命令、测试分层、CI、故障排查 | 首次运行与维护者 |
| [11-dependency-map.md](11-dependency-map.md) | 模块依赖方向、外部依赖、文件与数据依赖 | 架构评审/重构者 |
| [12-symbol-reference.md](12-symbol-reference.md) | 关键类与函数速查表（按模块分组） | 查 API 的人 |

## 30 秒理解系统

```text
公开事故摘要 + 只读证据包
        │
        ▼
Coordinator ──► 1~2 个调查任务（logs / metrics / database / changes）
        │                 │
        │                 ▼
        │          ToolRegistry（角色 ACL + 实际查询账本）
        │                 │
        │                 ▼
        │          本地 Finding / Hypothesis（仅本任务可见）
        │                 │
        ▼                 ▼
      Merge（身份/引用/ID 校验后发布到共享证据板）
        │
        ▼
   Verifier（只能 fetch 已共享证据，指纹绑定候选与证据版本）
        │
        ▼
   FinalizeGate（确定性检查：≥2 个不同来源、因果判别器、无未决问题…）
        │
   ┌────┴────┐
   ▼         ▼
 RESOLVED  INCONCLUSIVE
   │
   ▼
 Remediation（仅 PLAN_ONLY，不执行）
   │
   ▼
 统一 STOP 协议 → 确定性报告 + trace
```

## 关键事实速览

| 维度 | 事实 |
| --- | --- |
| 工作流节点 | `monitor → coordinate → dispatch → merge → verify → finalize → remediate → stop → report` |
| 工作流 profile | `legacy_rca`（默认，直接从 coordinate 开始）、`incident_response`（从 monitor 开始，可 NO_ALERT 提前结束） |
| 消融变体 | `full`、`single`、`fixed`、`dynamic_no_verifier`（另有 IncidentBench 的 `fixed_four_equivalent_tools` 等 4 条件） |
| 默认预算 | 4 轮 / 12 次工具 / 16 次 LLM 调用 / 600 秒（`configs/system.yaml`） |
| 响应型预算 | 6 轮 / 24 次工具 / 24 次 LLM / 600 秒（`configs/incident-response.yaml`） |
| 失败模式 | pool 配置回归、Postgres 连接耗尽、Redis 不可用、外部支付超时、资源饱和、锁竞争、慢查询 |
| 数据集 | 40 个合成案例：seed 6 / dev 10 / test 20 / database 4；公开 `public/` 与评测私有 `private/` 分离 |
| 工具 | 11 个只读工具（5 个数据库 + logs/metrics/deps/changes/config diff + 共享证据） |
| 产物 | 每次运行写 `result.json`、`report.md`、`trace.json`（输出目录必须全新） |

## 代码入口

| 用途 | 位置 |
| --- | --- |
| 安装脚本入口 | [`pyproject.toml`](../../pyproject.toml) → `incident_lens.cli:main` |
| CLI 实现 | [`cli.py`](../../src/incident_lens/cli.py) |
| 运行时核心 | [`orchestration/graph.py`](../../src/incident_lens/orchestration/graph.py) |
| 顶层运行函数 | `run_investigation(...)`，同文件 L1677 |
| Web 服务 | [`web/server.py`](../../src/incident_lens/web/server.py) |
| 数据契约 | [`schemas/contracts.py`](../../src/incident_lens/schemas/contracts.py) |
| 工具注册与 ACL | [`tools/registry.py`](../../src/incident_lens/tools/registry.py)、[`security/context.py`](../../src/incident_lens/security/context.py) |

## 阅读建议

1. **只想跑起来**：读 [10-running-and-testing.md](10-running-and-testing.md)，执行 `pip install -e '.[dev]'` 后用 `--provider mock` 离线运行。
2. **想理解调查逻辑**：按 [01](01-architecture.md) → [03](03-orchestration.md) → [04](04-agents-and-prompts.md) 顺序阅读。
3. **想改安全边界**：读 [06-tools-and-security.md](06-tools-and-security.md) 与 [05-data-contracts.md](05-data-contracts.md) 中的不变量。
4. **想做实验**：读 [08-evaluation-and-benchmark.md](08-evaluation-and-benchmark.md)。

## 术语表

| 术语 | 含义 |
| --- | --- |
| Evidence / EvidenceRecord | 一条公开、只读、可引用的证据记录（日志/指标/变更/配置/拓扑/数据库） |
| Finding | 单个调查任务对证据的局部解释，带 `evidence_ids` 引用 |
| Hypothesis | 候选根因，包含 `culprit_service`、`failure_mode`、支持/反对证据 |
| Review | Verifier 对候选的审查结论（`sufficient` / `insufficient` / `conflicted`） |
| FinalizeGate | 确定性验收逻辑，见 `orchestration/guards.py` |
| CAES | Cost-Aware Evidence Selection，可选的启发式任务选择模块 |
| STOP 协议 | 统一终止：冻结工具/任务、取消在途工作、等待 ACK、记录 `TerminationResult` |
| Shared board | Merge 校验后发布的共享证据与假设集合 |
| Plan-only | 修复建议只生成计划，绝不执行生产变更 |

## 已知边界

- 这是**应用层隔离**，不是 OS 级 Python 沙箱；不提供进程级安全保证。
- Mock Provider 是确定性策略，不是真实模型能力，Mock 结果不能证明模型准确率或架构优越性。
- 数据是合成模板，不是独立采集的生产基准。
- 报告与引用只证明"有证据支持"，不保证根因绝对正确。
