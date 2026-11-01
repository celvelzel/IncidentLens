# 硬化集 36 案例 × 四架构 × 144 槽位：正式规模对比（2026-11-01）

**批次名**：`full144-hardened-c4-20261101`
**数据**：`causal-world-v2-hardened`（Dev 36 案例：可识别 29、应弃权 7）
**模型**：`auto/deepseek-v4.1-flash`（本地网关，`json_schema`，thinking 关闭，cache off）
**并发**：4；**重复**：1；**槽位**：36 × 4 = 144；**实际耗时**：4 小时 39 分

> 一句话结论：`dynamic`（主架构）在 36 个硬化案例上质量最高（33/36，技术上完成的 33 次全部判对），
> 且比 `single` 和 `full` 便宜三分之一以上；`fixed` 最便宜但在可识别案例上大量误弃权（12/27）；
> 所有架构都**没有出现一次根因误判**——失分全部是"该答而弃权"，不是"答错"。

---

## 1. 主表

分母说明：`技术完成` 为 36 个槽位中成功跑完的数量；`根因正确` 只在技术上完成且案例可识别时计分；
`正确弃权` 只在案例不可识别时计分；`质量成功` 以 36 为分母，技术失败计为未成功。

| 架构 | 技术完成 | 根因正确 | 正确弃权 | 质量成功 | 平均耗时 | 平均请求 | 平均工具 | 平均 tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Single | 35/36 | 25/28 | 7/7 | 32/36 (88.9%) | 680.9 s | 17.3 | 14.5 | 245,971 |
| Fixed-4 | 34/36 | 15/27 | 7/7 | 22/36 (61.1%) | 196.3 s | 7.8 | 7.4 | 58,042 |
| **Dynamic（主架构）** | 33/36 | **27/27** | 6/6 | **33/36 (91.7%)** | 412.9 s | 14.6 | 12.0 | 149,216 |
| Full（dynamic + verifier） | 34/36 | 23/27 | 7/7 | 30/36 (83.3%) | 503.8 s | 17.6 | 15.5 | 233,772 |

在**技术上完成的运行里**的质量成功率：Dynamic 33/33 (100%)、Single 32/35 (91.4%)、
Full 30/34 (88.2%)、Fixed 22/34 (64.7%)。

总消耗 2,437 万 tokens，其中技术失败消耗 92.2 万（3.8%）。

## 2. 关键发现

**（1）零误判：失分全部是过度弃权。**
19 个"可识别但未得分"的案例，全部以 `INCONCLUSIVE` 结束，没有一个给出错误的 `culprit_service`/`failure_mode`。
7 个不可识别案例在所有完成的运行里全部正确弃权。对"引用或弃权"契约来说，这是比总分更强的证据：
系统在答的时候是准的，代价是召回——尤其 `fixed` 会漏掉将近一半可识别案例。

**（2）Dynamic 是质量最高且动态家族里最便宜的一档。**
相对 `single`：质量 33 vs 32，耗时 −39.4%、请求 −15.6%、工具 −17.2%、tokens −39.3%。
相对 `full`：质量 33 vs 30，耗时 −18.0%、请求 −17.0%、工具 −22.6%、tokens −36.2%。
即 Verifier 回路在这批硬化案例上**没有带来质量增益**，只带来约 57% 的额外 tokens。

**（3）Fixed-4 最便宜，但硬化集正好打在它的弱点上。**
196 s、7.8 次请求、58k tokens，但可识别案例只对 15/27，误弃权 12 次。
相对 `dynamic`，它省 61% tokens / 52% 耗时，代价是少 11 个成功案例。

**（4）配对比较（同一案例内，动态 vs 其他）。**

| 对照 | dynamic 更好 | dynamic 更差 | 持平 |
| --- | ---: | ---: | ---: |
| vs Single | 3 | 2 | 31 |
| vs Fixed-4 | 12 | 1 | 23 |
| vs Full | 5 | 2 | 29 |

`dynamic` 对 `full` 是 +5/−2，但注意 `dynamic` 本批有 3 次技术失败、`full` 只有 2 次；
在失败更多的前提下仍赢下配对比较。

## 3. 分难度杠杆（质量成功 / 该杠杆案例数）

| 杠杆 | 含义 | Single | Fixed-4 | Dynamic | Full |
| --- | --- | ---: | ---: | ---: | ---: |
| standard | 标准可识别 | 6/7 | 3/7 | 6/7 | 6/7 |
| boundary | 边界证据 | 6/7 | 4/7 | 6/7 | 5/7 |
| competing | 竞争性成因 | 6/7 | 4/7 | **7/7** | 6/7 |
| missing | 缺失判别证据（应弃权） | 7/7 | 7/7 | 6/7 | 7/7 |
| misleading | 误导性证据 | 2/2 | 1/2 | 2/2 | 2/2 |
| counterfactual_pair | 反事实配对 | 5/6 | 3/6 | **6/6** | 4/6 |

`dynamic` 的强项正好落在硬化集新增的两类难点上：竞争性成因 7/7、反事实配对 6/6
（其他架构在这两类上各丢 1–3 个）。`missing` 一格里 dynamic 的 6/7 是那 1 次技术失败，
不是误判。

## 4. 技术失败（8/144，5.6%）

| 槽位 | 案例 | 架构 | 阶段 | 原因 | tokens |
| --- | --- | --- | --- | --- | ---: |
| slot-001 | incident_4021 | fixed | dispatch | STRUCTURED_OUTPUT_INVALID | 40,828 |
| slot-015 | incident_4004 | dynamic | dispatch | STRUCTURED_OUTPUT_INVALID | 169,654 |
| slot-017 | incident_4020 | dynamic | coordinate | STRUCTURED_OUTPUT_INVALID | 221,962 |
| slot-024 | incident_4006 | dynamic | dispatch | STRUCTURED_OUTPUT_INVALID | 90,171 |
| slot-046 | incident_4032 | fixed | dispatch | STRUCTURED_OUTPUT_INVALID | 52,074 |
| slot-051 | incident_4011 | full | coordinate | STRUCTURED_OUTPUT_INVALID | 138,938 |
| slot-060 | incident_4032 | full | dispatch | FINDING_IDENTITY_MISMATCH | 51,999 |
| slot-132 | incident_4019 | single | dispatch | FINDING_IDENTITY_MISMATCH | 155,973 |

分布：single 1、fixed 2、dynamic 3、full 2——四个架构都有，说明这是**provider / 结构化输出层**的
偶发问题，不是某一架构的缺陷。6 次是输出被截断导致 schema 校验失败，2 次是工具返回的
finding 与本轮身份不匹配被确定性门禁拦下。按预案未重试，失败槽位保留在分母中。

## 5. 证据边界（必须随数字一起引用）

- **不是盲测**：协议 `formal: false`、`blindness_level: development_visible`；本机可见公开案例与开发切分。
- **标签是临时的**：所有 oracle 的 `annotator_status` 为 `pending`，对错判定可能在人工复核后变动。
- **单次重复、单模型、36 案例**：没有置信区间主张；表中的差异是描述性的，不做显著性推断。
- **输入未漂移**：144/144 槽位记录 `source_unchanged: true`，批次期间源码/配置哈希与冻结快照一致
  （这项校验覆盖仓库输入，不覆盖网关侧的路由或版本变化）。
- 技术失败按协议留在分母里，因此"质量成功/36"是**失败包含**口径；"技术上完成内的成功率"另列。

## 6. 复现

```bash
.venv/Scripts/python.exe analysis/wp_d/reports/hardened144-20261101/score_batch.py
```

脚本只读批次目录，输出 `results/v16/wp-d/full144-hardened-c4-20261101/final-success-comparison.json`
（144 条记录，含预测、真值、失败原因、杠杆与逐槽资源用量）。
