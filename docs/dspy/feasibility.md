# Prompt Optimization Feasibility Study — 2026-10-21

工程原型 GO；优化版本正式部署和质量改善声明 NO-GO。

源码核对基于 `fb0c848d5f25481ded1552932307efe0fc5a34cd`。
DSPy 3.0.4 与项目 Python 3.12、Pydantic 2.14.0、LangGraph 1.2.14 能共同安装，
依赖检查通过。现有 LangGraph 与 structured_call 边界可以保留；DSPy 不必进入运行时。

## 实际证据

- 完整 Python 回归：1,070 passed、2 skipped；独立 DSPy 合约检查：14 passed。
- JavaScript：21 passed。Ruff 和 pip check 通过。
- 四种优化器路径已执行，包括真实 DSPy MIPROv2 搜索流程；提案与任务模型均为 Mock。
- Analysis/Verifier × Manual/Bootstrap/MIPRO 共 6 次实际 Predict/导出消息等价校验。
- 冻结 Dev10 × 四种架构 × A0/A1/A2/A3 = 160 次 Mock 调查。
- 每个条件均为 40 次调查、346 个模型调用许可对应请求、193 次工具调用，31 个根因匹配、
  4 个正确弃权。其余结果保留在原始输出，不删除失败或不确定运行。
- 120 个与 A0 的案例/架构配对中，请求及工具调用差异均为零。
- Mock 不读取 Prompt 的语义，以上相同结果是工程兼容证据，**不是优化无效或有效的真实模型结论**。
- 12 条单模块 Mock 对照记录与逐样本配对已执行，均无改善或退化；这些标签为机械测试输出。
- 10 个精确 Mock 调用前样本已采集并保持 pending。没有把模型响应标为人工审核 gold。
- 原 12 个保留 Trace 清单中，11 个文件存在且 SHA-256 一致；缺失 1 个。精确历史输入为 0。

汇总、源文件指纹、6 个 wire hash、测试数量和真实模型请求数见
`results/acceptance/dspy/validation.json`。历史审计及待审 worksheet 同目录保留。
完整生成输出仍在本地 `results/acceptance/dspy/verified-mock-smoke/`，可用 smoke 命令重建。

第一次完整回归在默认 Node 24 上有 1 个既有 UI 测试因废弃命令行选项失败；
改用 CI 对应的独立 Node 22 后全量通过。未修改 UI 实现或删除失败断言。

## 错误归属与可优化性

现有 SYSTEM_PROMPT 已包含“支持 A 不等于反驳 B”“无遥测不等于健康”等指令。
因此不能将本次加入的版本化入口当作新增因果能力。
原八个成功诊断里的六个薄弱反驳是最终报告核查，不能从最终共享状态直接定位到 Analysis。
Coordinator 也有 hypothesis_updates；Verifier 的 verdict/contradictions 是另一类输出。

本次 worksheet 保留最终候选和实际 against records，让审核者判断：
这是直接相反的观察、只支持竞争机制、时间不匹配、纯拓扑，还是证据不足。
error_owner 与 prompt_fixable 默认 unknown。需要实际调用前输入及输出，再判断最早出现
错误的组件；若属于 merge、gate 或调度逻辑，先修程序。

## 主要限制

当前没有模型凭据或可信双人语义标签，没有独立 held-out Test，没有成本改善结论。
单模块自动指标只能比较已裁决的引用关系和候选状态，不能完整判断自然语言反驳质量。
25% 相对错误下降保留为建议目标，不是实验结果或已经满足的门槛。

A4 GEPA 为可选扩展，本次未实现；现阶段的数据及预算缺口不会因多加入优化器而解决。
正式模型实验需额外固定总 wall/Token 预算、盲审安排、可接受质量退化界限与交错运行设计。
不能只修改候选的 status 字段就将本工程结果解释为通过语义验收。

自动生成的 run ID、snapshot ID 和时延会随运行变化；报告哈希用于标识本次证据，不承诺不同运行字节一致。
