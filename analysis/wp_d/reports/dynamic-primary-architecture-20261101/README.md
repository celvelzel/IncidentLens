# `dynamic` 作为主架构：证据、论点与边界

日期：2026-11-01（Asia/Shanghai）。本文只做只读分析，不修改任何冻结产物。数据源是
`results/v16/wp-d/full40-local-gateway-c4-20261031/final-success-comparison.json`（每个槽位
最后一个成功 attempt），用同目录 `recompute.py` 可逐项复算。

## 1. 决策

- **主架构 = `dynamic`**（运行时默认）。动态选择专家、多轮补查，Merge 校验 + FinalizeGate
  确定性接地，**没有独立 LLM Verifier**。
- **`full` = 消融对照**，文档中显示为 *dynamic (with verifier)*：同一调度路径上增加 Verifier
  的 `sufficient` 审查与指纹匹配。
- `single`、`fixed` 保留为基线，用于回答“多 Agent 是否值得”和“一次性固定批次是否足够”。

重命名只发生在**运行时别名**层面。IncidentBench 的条件名（`strong_single_equivalent_tools`、
`fixed_four_equivalent_tools`、`dynamic_no_verifier`、`full`）是冻结契约：已保存的
`protocol.json` 必须继续通过 `ExperimentProtocol.conditions` 校验，历史 trace 与结果行也必须继续
被 `validate_metadata` 接受。因此 `dynamic_no_verifier` / `no_verifier` 作为 `dynamic` 的别名被
`variants.normalize_variant`（运行时入口，未知名报错）与 `variants.canonical_name`（聚合分组，
未知名保持原样）分别处理；新运行不再写出旧拼写。

## 2. 总体对比（每个槽位最后一个成功 attempt）

| 架构 | 技术完成 | 根因正确 | 正确弃答 | 质量成功 | 平均耗时 | 平均请求 | 平均工具 | 平均 Token | Attempts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Single | 10/10 | 8/8 | 2/2 | 10/10 | 391.2s | 17.6 | 15.0 | 257,146 | 10 |
| Fixed-4 | 10/10 | 5/8 | 2/2 | 7/10 | 96.9s | 7.9 | 7.6 | 56,586 | 10 |
| **Dynamic（主架构）** | 10/10 | 8/8 | 2/2 | 10/10 | 233.5s | 14.0 | 11.8 | 145,035 | 10 |
| Full（*dynamic with verifier*） | 10/10 | 8/8 | 2/2 | 10/10 | 438.9s | 18.8 | 15.9 | 269,832 | 12 |

四项资源都以 Dynamic 为基准换算（正值表示对方更高）：

| 对照 | 耗时 | 请求 | 工具 | Token |
| --- | ---: | ---: | ---: | ---: |
| Single | +67.5% | +25.7% | +27.1% | +77.3% |
| Full | +88.0% | +34.3% | +34.7% | +86.0% |
| Fixed-4 | −58.5% | −43.6% | −35.6% | −61.0% |

## 3. 证据 + 论点

**对 Single：质量相同（10/10），平均耗时降低 40.3%、请求降低 20.5%、工具查询降低 21.3%、
Token 降低 43.6%，支持“动态分工减少无效查询与上下文”这一设计论点。**

Single 是强单 Agent 基线：同一身份自规划、自反思，持有全部公开只读工具，串行执行。它在质量上
与 Dynamic 打平，说明“把四类证据域拆给四个角色”并不自动提高正确率；它多消耗的 1.6 倍 Token
与 67.5% 的额外墙钟，来自把所有证据域塞进同一条串行上下文。Dynamic 的收益不是“模型更多”，而是
**每轮只派最需要的一两个专家，把无关上下文挡在共享证据板之外**。

**对 Full（dynamic with verifier）：质量相同（10/10），耗时高 88.0%、请求高 34.3%、工具高
34.7%、Token 高 86.0%，说明独立 Verifier 在本批没有产出可测的质量增益。**

我们只表述为“未观测到增益”，不据此断言 Verifier 永远无用。本批的 8 个可识别案例里，Dynamic 的
候选根因与 Full 完全一致（3001/3002/3004/3005/3006/3007/3009/3010 全部 RESOLVED 且匹配），
Verifier 没有改变任何一个最终结论，却让每次运行多出一次审查调用与相应的补查。它可能对更难的
竞争假设、错误候选或跨源矛盾有价值——这正需要**按需触发**的后续实验，而不是全量常开。

**对 Fixed-4：Fixed 更便宜（96.9s、7.9 请求、56,586 Token），但错弃 3 个可识别案例
（3004/3005/3010），证明“一次性固定批次无法补证”——这恰恰是 Dynamic 多轮补查的价值所在。**

Fixed-4 一次性固定派出 Logs、Metrics、Database、Changes，拿到什么就判什么。它没有“发现缺口后
再派人”的能力，所以在需要二次定位的三个案例上把可识别事故判成 `INCONCLUSIVE`。它的低成本是真
的，但代价是 7/10 的质量；在本批里它是**最低成本的对照，不是最优架构**。

## 4. 逐案例

| 案例 | 四方均正确 | 关键差异 |
| --- | --- | --- |
| incident_3001 | 是 | 四方正确；Fixed-4 最省（77.5s / 50,912 Token） |
| incident_3002 | 是 | 四方正确；Dynamic 168.2s，Single 442.1s |
| incident_3003 | 是 | 四方正确弃答；Dynamic 343.9s 低于 Single 630.6s |
| incident_3004 | 否 | **Fixed-4 错误弃答**；其余三方正确根因 |
| incident_3005 | 否 | **Fixed-4 错误弃答**；其余三方正确根因 |
| incident_3006 | 是 | 四方正确；Dynamic 的 Token（95,281）约为 Single（140,289）的 68% |
| incident_3007 | 是 | 四方正确；Dynamic 162.0s 对 Single 407.0s |
| incident_3008 | 是 | 四方正确弃答；**Dynamic 386.3s 高于 Single 280.1s**，Full 724.9s |
| incident_3009 | 是 | 四方正确；Dynamic 240.9s 对 Single 391.3s |
| incident_3010 | 否 | **Fixed-4 错误弃答**；Full 的最终成功 attempt 是第 3 次 |

`incident_3008` 是唯一一个 Dynamic 比 Single 更贵的案例，也是唯一一个证据本身不足、四方都必须
弃答的案例（另一个不可识别案例 3003 里 Dynamic 反而更快）。它和 `incident_3010` 的 Full 三次
attempt 一起，指向下一节的第一优先级问题。

## 5. 全尝试成本

| 架构 | Attempts | 结构化失败 | 中断 | 额外重试 Token | 额外重试耗时 | 全部已知 Token | 全部已知耗时 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Single | 10 | 0 | 0 | 0 | 0.0s | 2,571,460 | 3,911.5s |
| Fixed-4 | 10 | 0 | 0 | 0 | 0.0s | 565,863 | 969.1s |
| **Dynamic** | 10 | 0 | 0 | 0 | 0.0s | 1,450,353 | 2,334.7s |
| Full | 12 | 1 | 1 | 179,050 | 223.1s | 2,877,375（下界） | 4,612.5s（下界） |

Dynamic 在本批 10 个槽位全部一次成功，没有结构化失败、没有中断，因此“最终成功均值”与“全尝试
成本”在 Dynamic 上完全一致——这一点比 Full 更容易解释，也更经得起追问。Full 的额外成本来自
3010 的两次失败 attempt，不能把 Provider 失败解释成“模型已经给出正确诊断”，也不能把断连归因为
网关故障。

## 6. 可以说 / 不能说

可以说：

- “在 10 个开发可见案例上，Dynamic 与 Single/Full 质量相同（10/10），资源显著更低。”
- “Dynamic 相对 Full 高 34–88% 的资源换来了 0 个额外正确案例；因此本批未观测到独立 Verifier 的
  质量增益。”
- “Fixed-4 最便宜，但在 3004/3005/3010 上错误弃答，说明一次性固定批次无法补证。”
- “把 Dynamic 设为默认不改变产品风险画像：接地门控、引用校验和弃答逻辑与实验时完全相同。”

不能说：

- “Dynamic 在统计上优于 Single/Full”或“已达到显著性”。
- “Verifier 无用”或“Full 永远不会更好”——只能说本批未观测到增益。
- “40/40 技术完成等于 40/40 诊断正确”（质量是 10/10、7/10、10/10、10/10）。
- “Fixed-4 最便宜所以整体最优”。
- “这些结论可外推到盲测或生产”。

边界：10 个 `development_visible` 案例、每案例 1 次重复、oracle 为 `pending/candidate-v1`、
单一本地网关与单一模型（`auto/deepseek-v4.1-flash`）、temperature 0、cache off。这是描述性开发
证据。

## 7. 冻结产物说明

`final-success-comparison.json` 中的 `correctness` 字段存在历史编码问题（读作乱码
`��ȷ����`）。该文件是冻结的历史实验产物，**不重写、不“修正”**；本文与 `recompute.py` 都从
`root_cause_correct` / `correct_abstention` / `quality_success` 重新推导正确性，不依赖该字段。
需要干净标签时，请在**新目录**下生成新分析，而不是就地改历史文件。

## 8. 复算

```bash
.venv/Scripts/python.exe analysis/wp_d/reports/dynamic-primary-architecture-20261101/recompute.py
```

脚本只读，输出与本文第 2 节的表一致。它把 `dynamic_no_verifier` 折叠为 `dynamic`，因此即使
历史行仍用旧拼写，四个架构也只会被报告一次。

## 9. 后续

主架构的下一步不是再加一个 Agent，而是补上**证据不足时的成本护栏**，并把 Verifier 从“常开”
改为“按需触发”。优先级与验收方式见 [优化路线](../../../../docs/guides/optimization-roadmap.zh-CN.md)。
