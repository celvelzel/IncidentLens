# IncidentLens — Presentation Script

**Deck:** `presentation/IncidentLens_Deck.pptx` (21 slides: 15 main + 6 backup)
**PDF:** `presentation/IncidentLens_Deck.pdf`
**Target length:** 9 min 57 s of speaking (8–10 min window) + Q&A
**Language:** spoken English; 中文提示 is for rehearsal only and is not read aloud.

---

## 0. How to use this script

1. **Read the English block, not the slide.** The slides carry the evidence; the script
   carries the argument. Do not read bullet points aloud.
2. **The Chinese block under each slide is a presenter note**, not a translation: it says
   what to point at, what to avoid saying, and where the hand-off happens.
3. **Six speaker blocks, no invented contributions.** The blocks below are a *speaking
   allocation by slide*, chosen for narrative continuity. They are not claims about who
   built what. The group decides who takes which block; the Individual Contribution
   Statement stays blank until each member fills it in.
4. **Rehearse with a timer.** If a block runs long, cut the sentence marked *(cut if
   tight)* rather than rushing the evidence numbers.
5. **Never improvise a number.** Every figure in this script is in
   `docs/submission/source_of_truth.md`. If a number is not there, say "we did not measure
   that" — that answer is stronger than an estimate.

### Timing map

| # | Slide | Section | Speaker | Time |
| ---: | --- | --- | --- | ---: |
| 1 | Title | — | S1 | 0:20 |
| 2 | Incident review is an evidence problem | 01 Problem | S1 | 0:42 |
| 3 | The question we set out to test | 01 Problem | S1 | 0:38 |
| 4 | One auditable investigation pipeline | 02 Design | S2 | 0:45 |
| 5 | Roles are real; permissions are code | 02 Design | S2 | 0:38 |
| 6 | Coordination follows the evidence gap | 02 Design | S2 | 0:42 |
| 7 | Grounding is a deterministic gate | 02 Design | S3 | 0:33 |
| 8 | Implementation is reproducible | 03 System | S3 | 0:33 |
| 9 | Demo: live run, then replay | 03 System | S3 | 1:10 |
| 10 | Does coordination earn its cost? | 04 Evaluation | S4 | 0:38 |
| 11 | Dynamic leads on quality | 04 Evaluation | S4 | 0:42 |
| 12 | Coordination pays for itself | 04 Evaluation | S4 | 0:42 |
| 13 | The failure mode is conservative | 04 Evaluation | S5 | 0:38 |
| 14 | What this evaluation does not establish | 05 Discussion | S5 | 0:36 |
| 15 | What we learned | 05 Discussion | S6 | 0:40 |
| 16–21 | Backup | Q&A only | whoever owns the topic | on demand |

**Speaker totals:** S1 1:40 · S2 2:05 · S3 2:16 · S4 2:02 · S5 1:14 · S6 0:40.
Sum = **9:57**. That is the whole 8–10 minute window; if a block runs long, cut a
*(cut if tight)* sentence rather than borrowing time from the next speaker.

### Before you start

- Deck open in presentation mode, PDF as fallback on a second window.
- Console running locally: `.venv/Scripts/python.exe -m incident_lens.web` (default
  `127.0.0.1:8022`; pass `--port` to change). Sidebar pages are Chinese-labelled:
  总览 `#/` · 新建调查 `#/investigate` · 痕迹档案库 `#/library` · 运行详情 `#/run` ·
  系统设计 `#/system` · 评测结果 `#/evaluation`. Warm up `#/library` first.
- One recorded trace already loaded in a second browser tab:
  `#/run?path=results/acceptance/demo-live-20261102/trace.json&step=last&demo=1`
  (the `step=last` parameter opens the completed state; `demo=1` opens the demo chapters).
  This is the same command the live run uses — Mock, `dynamic`, `incident_001`, stock budget —
  captured from the running app, so the screenshot on slide 9 and the replay show one trace.
- If the network or provider fails: switch to the PDF and the recorded trace. Never run a
  live provider call on stage without a fallback.

---

## 1. Opening — slide 1 (S1, 0:20)

**English**

> Good morning. We are presenting IncidentLens, a multi-agent system that investigates
> software incidents. Its contract is simple: every accepted root cause must cite the
> records that support it, and when the evidence is insufficient, the system must say so.
> We report a matched four-architecture evaluation on a 36-case development corpus.

**中文提示**
开场只做两件事：说清"引用或弃权"的契约，说明有 36 案例×4 架构的对照实验。不要在此处
介绍成员或分工。语速放慢，把 "cite the records" 和 "must say so" 两个短语咬清楚。

**Transition:** "Let me start with why this is an evidence problem, not a writing problem."

---

## 2. Problem — slide 2 (S1, 0:42)

**English**

> Incident review is not a summarisation task. Logs show chronology; metrics show scope
> and saturation; database state shows sessions and locks; change records show what
> happened just before onset. Each shows only part of the mechanism.
>
> A general-purpose agent fails in three predictable ways. It can write a fluent cause
> with no record-level support. It reads whatever is in its context, including
> evaluator-only labels it should never see. And when evidence is thin, its default is
> still to answer.
>
> IncidentLens is built around the opposite contract: cite exact records, or abstain.

**中文提示**
左图四张卡片依次点一下即可，不要逐个念说明。右侧三条失败模式是本节重点：无引用、
越权读取、证据不足仍作答。最后一句"cite exact records, or abstain"要落在红色横幅上。

**Transition:** "That contract gives us a research question with two halves."

---

## 3. Research question — slide 3 (S1, 0:38)

**English**

> Our question has two halves: can a coordinated multi-agent system produce an answer a
> reviewer can audit, and can it refuse when the visible evidence is insufficient — without
> paying an unreasonable cost?
>
> Multi-agent is justified by evidence specialisation, not by agent count. The four sources
> need different tools and different questions; roles create scoped access, and a
> coordinator decides which gap matters next. That is coordination, not four independent
> LLM calls.
>
> Non-goals: production changes, real telemetry, a model leaderboard.

**中文提示**
两个半句是重点：可审计的答案 + 证据不足时敢弃权 + 成本可接受。强调"not four
independent LLM calls"，这是评委最容易追问的一点。右下三张卡片是三个贡献点，各一句。

**Transition:** "Here is the pipeline that implements it." *(hand to S2)*

---

## 4. Pipeline — slide 4 (S2, 0:45)

**English**

> This is the whole system. Public evidence enters; an optional monitor can raise an alert.
> The coordinator owns the budget and assigns at most two specialist tasks per round.
> Specialists can call only the tools their role allows. Merge validates identity, task,
> role and every citation, then updates a shared hypothesis board. FinalizeGate makes the
> accept-or-abstain decision deterministically.
>
> Two boundaries matter. The shaded steps are model-driven; the outlined steps are
> deterministic code. And remediation runs only after acceptance, and is plan-only — it
> proposes, it never executes.

**中文提示**
用手沿箭头走一遍：Public Input → Coordinator → 专家池 → Merge → 假设板 → FinalizeGate
→ 报告/弃权。重点区分实线（确定性代码）与模型步骤。Verifier 是消融，不是主流程，务必
说明，否则第 12 页的结论会显得矛盾。

**Transition:** "Roles are the next question: are they real, or just prompt wording?"

---

## 5. Roles and ACL — slide 5 (S2, 0:38)

**English**

> Roles here are not personas in a prompt. The coordinator has no evidence tools at all;
> each specialist has only the tools for its source. The verifier can fetch only records
> already observed, by ID.
>
> Three mechanisms enforce it: an immutable agent context, an actual-query ledger that
> records what was really read, and a public-file allowlist. A finding that does not match
> the run, task and role that produced it is rejected — that is the identity check behind
> two of our technical failures.

**中文提示**
表格只点两行：Coordinator 是 "none"，Database Investigator 是 5 个工具。底部三个机制
是加分点。这里可以顺带说"单智能体基线拿到的是全部工具的并集"，为第 11 页的对照埋伏笔。

**Transition:** "Scoped tools alone do not decide what to investigate next — coordination does."

---

## 6. Coordination — slide 6 (S2, 0:42)

**English**

> Each round starts from the current evidence gap, not from a fixed checklist. The
> coordinator emits exactly one of three contracts: investigate with one or two assignments,
> finalize with one selected hypothesis, or abstain with an explicit stop reason.
>
> Every assignment must name a discriminator — a check that could actually change the
> answer. An assignment without a discriminator cannot move the hypothesis, so it is not
> worth a tool call.
>
> Budgets are physical: four rounds, twelve tool calls, sixteen model requests, six hundred
> seconds. The loop cannot run forever.

**中文提示**
"evidence gap" 是本项目最核心的设计词，要说清是"当前缺什么证据"而不是"下一步做什么"。
四个硬上限要念数字，这是防"无限循环"质疑的证据。

**Transition:** "But coordination only helps if the acceptance step is trustworthy." *(hand to S3)*

---

## 7. FinalizeGate — slide 7 (S3, 0:33)

**English**

> This is the trust mechanism. A candidate must cite records that were actually observed
> in this run. The finding must match the run, task and role that produced it. A resolved
> answer needs a supported hypothesis and a causal chain, not just a top score. Any
> unresolved blocker, open contradiction or missing discriminator forces abstention.
>
> The gate never reads model confidence, chain-of-thought or evaluator labels. And the
> strongest thing it can accept is BEST_SUPPORTED_AVAILABLE — deliberately weaker than
> proof.

**中文提示**
四项检查逐条说，最后强调"never uses model confidence"。如果评委追问"那和让模型自己说
不确定有什么区别"，答案是：模型只能提议，接受与否由代码判定（见第 16 页 backup）。

**Transition:** "That gate is code, so let me show what the code actually is."

---

## 8. Implementation — slide 8 (S3, 0:33)

**English**

> The runtime is a LangGraph state machine with typed Pydantic contracts. The same runtime
> powers the CLI and the web console, and a saved trace can be replayed without touching
> the graph, tools or provider.
>
> Failure handling is explicit: bounded recovery, request permits, one structured-output
> repair per stage, task budgets and a unified stop protocol. The current suite is
> 1,179 tests passed, 3 skipped, no failures. Separately, the evaluation counts technical
> failures instead of hiding them.

**中文提示**
技术栈胶囊不要逐个念。重点两句话：同一运行时 + 可离线重放；失败处理是设计的一部分。
测试数字只说一次，不要重复。

**Transition:** "Let me show it running, then replay the same trace." *(demo)*

---

## 9. Demo — slide 9 (S3, 1:10, includes live demo)

**English (say while switching windows)**

> We will run incident_001 with the Mock provider, so this is offline and deterministic.
> Watch three things: the coordinator chooses two tasks, then a second round; the budget
> counters move; and FinalizeGate accepts only after citations are present.
>
> *(run finishes)* Now the same trace as a recorded replay. The badge changes to Recorded
> Replay, and the graph, tools and provider are not called — this is state rebuilt from
> the saved event log.
>
> One more click: a citation. It opens the source file, the query that produced it, the
> agent and the timestamp.

**Demo cues (click order)**
1. `#/investigate` (新建调查) → provider **Mock · 离线确定性** → case `incident_001` →
   **发起调查**.
2. While it runs: point at the budget strip (调查轮次 / 工具调用 / 模型请求) and the
   coordinator decisions appearing one by one.
3. Result: status badge, cited root cause, 假设看板 tab.
4. New tab: recorded trace URL above → badge **Recorded Replay** + **MOCK**.
5. Click a citation chip → 证据 drawer → 来源文件, 来源工具/事件, 查询执行时间, 原始摘录.

**中文提示**
演示最怕卡住。三件事按顺序：先说"Mock，离线可复现"，再指预算计数，最后点引用。
如果现场运行超过 20 秒没有新事件，直接切到已保存的 replay 标签页，并说"这是同一条
痕迹的重放，不重新调用模型"。不要现场切 Real provider。

**Transition:** "So the system runs. The real question is whether coordination earns its cost." *(hand to S4)*

---

## 10. Evaluation design — slide 10 (S4, 0:38)

**English**

> The evaluation is a matched comparison, not a leaderboard. All four architectures see the
> same public evidence, the same tools, budgets, model and decoding settings.
>
> Thirty-six hardened cases: twenty-nine have an identifiable cause, seven must be
> abstained. Four architectures × thirty-six cases × one repeat = 144 attempted slots;
> 136 completed. Technical failures stay in the denominator, root accuracy uses only
> identifiable completed runs, and abstention only unidentifiable completed runs.
>
> The labels are evaluator-only and provisional, and the corpus is development-visible.

**中文提示**
"matched" 是关键词：同模型、同数据、同预算、同解码。分母规则要讲清，否则 33/36 与
27/27 看起来像自相矛盾。最后一句主动交代"非盲测、标签临时"，先于评委提问。

**Transition:** "Here is what that measurement produced."

---

## 11. Quality — slide 11 (S4, 0:42)

**English**

> On quality, Dynamic completes 33 of 36 and is the only architecture to get every
> identifiable completed case right: 27 of 27. The more important number is the zero:
> across 144 attempts, no run named a wrong root cause. All 19 identifiable misses ended
> INCONCLUSIVE.
>
> Fixed-4 is much cheaper, but it wrongly abstains on 12 of 27 identifiable cases — one
> fixed batch cannot recover a source it never queried.
>
> Dynamic is also the only variant at 7/7 on competing causes and 6/6 on counterfactual
> pairs.

**中文提示**
先说 33/36，再说 27/27，最后说 0。顺序很重要：质量 → 根因正确 → 零错判。Fixed-4 的
12/27 过度弃权是"便宜但有代价"的证据，别说成"Fixed-4 很差"。

**Transition:** "Quality alone is not the claim — cost is the other half."

---

## 12. Cost — slide 12 (S4, 0:42)

**English**

> Cost changes the conclusion. Against Single, Dynamic gains one quality success while
> using about 39 percent less latency and 39 percent fewer tokens. Against the verifier
> variant it gains three quality successes, with 18 percent less latency and 36 percent
> fewer tokens.
>
> The verifier itself cost 57 percent more tokens and produced no measured quality gain in
> this batch. That is a negative result, and we report it as one.
>
> These are descriptive differences from one model and one repeat. We do not claim
> statistical significance.

**中文提示**
三组对比各一句，不要背小数。最后一句"negative result"要说得坦然——评委通常因此加分。
"no measured gain" 不等于"verifier 无用"，只是在本批次没有测到收益。

**Transition:** "The failure analysis is where the honest part of the story is." *(hand to S5)*

---

## 13. Failure mode — slide 13 (S5, 0:38)

**English**

> This is the honest failure analysis. The dominant error is over-abstention: 19
> identifiable cases ended INCONCLUSIVE — 12 under Fixed-4, and none under Dynamic.
>
> There were eight technical failures out of 144: six invalid structured outputs — five
> response envelopes the provider returned without string content, and one truncated output
> that stayed invalid after its one repair — plus two identity mismatches. We did not retry
> them; they stay in the denominator.
>
> The pattern is consistent across the lever table: Dynamic is strongest where causes
> compete or where a counterfactual pair must be separated. The risk profile is
> conservative — missed conclusions, not fabricated ones.

**中文提示**
热力图只点两格：Competing 的 7/7 和 Counterfactual 的 6/6。然后指右侧 19 / 8 / 12。
如果评委问"零错误是不是因为标签太容易"，答：29 个可识别案例里有 7 个竞争原因、6 个
反事实对、7 个边界案例，且这是开发可见语料（见第 14 页）。

**Transition:** "Which brings us to what this evaluation cannot establish." *(hand to S5 again — same speaker, one breath)*

---

## 14. Boundaries — slide 14 (S5, 0:36)

**English**

> We are explicit about the boundary. There is no blind test: the corpus is
> development-visible and the labels are provisional. There is one model and one repeat, so
> we report descriptive differences with no confidence intervals.
>
> The dominant error is over-abstention. The cost-guard savings are replay estimates, not
> live savings — but its measured firing favours our primary architecture: all six Dynamic
> stops were correct abstentions, and every identifiable loss sat on an ablation control.
> Cache and recovery were validated on Mock traces rather than production traffic.
>
> It is a research and teaching prototype. We do not claim production readiness,
> state-of-the-art performance, or that hallucination is eliminated.

**中文提示**
六张卡片不用全念，念前两张（非盲测、单模型单次），再念"over-abstention"。守卫卡片
可以主动反打一句：省 token 是估算，但触发是实测——Dynamic 的 6 次终止全部正确弃权，
误伤全部在消融对照组。最后一句 "Not claimed" 是防御性最强的一句，放慢说。不要在此处
补充未经测量的数字。

**Transition:** "So what should someone take away from this?" *(hand to S6)*

---

## 15. Conclusion — slide 15 (S6, 0:40)

**English**

> Three lessons. Coordination should follow evidence gaps, because a fixed expert batch
> wastes queries. Grounding must be deterministic, because model confidence is not an
> acceptance signal. And abstention must be measured as a first-class outcome, because the
> main failure mode was over-abstention, not fabrication.
>
> Next steps: a blind holdout with independent human labels and a significance-tested
> replication; a live test of the cost guard; and a verifier triggered only on conflict.
>
> IncidentLens turns agent investigation into an auditable evidence process, and it reports
> what it cannot conclude. Thank you — we welcome questions.

**中文提示**
收尾不要重复结果数字。三个教训各一句，三个 next step 各一句，最后落在"reports what
it cannot conclude"。说完停两秒再进入 Q&A，不要立刻补话。

---

## 16. Backup slides — how to use them in Q&A

Jump to the slide, say one sentence, then answer. Do not read the table aloud.

| Slide | Use when asked | One-sentence opener |
| ---: | --- | --- |
| 16 · Decision semantics | "How does the loop terminate? What if it just keeps going?" | "Every terminal path is typed: investigate, finalize, abstain, or a runtime failure that stays in the denominator." |
| 17 · Metrics and denominators | "Why 33/36 and not 33/33?" | "Quality counts technical failures; root correctness and abstention each use their own eligible denominator." |
| 18 · Paired outcomes and levers | "Is the difference real, or noise?" / "Which cases did Dynamic win?" | "Case by case: 12 wins, 1 loss, 23 ties against Fixed-4; ties dominate because most cases are solvable by every architecture." |
| 19 · Failures and evidence | "What failed? Were failures retried?" / "Where do labels come from?" | "Eight technical failures, six invalid structured outputs and two identity mismatches, all retained; labels are evaluator-only and provisional." |
| 20 · Security and replay | "Can an agent read the answer key? Can replay escape the results directory?" | "Role ACLs, immutable context, an actual-query ledger, a public allowlist, and replay paths confined to `results/` with a fixed filename." |
| 21 · Reproduce | "Can we run it now?" | "Yes — install, validate, run with Mock, replay, then open the web console. No API key is needed for the Mock path." |

---

## 17. Rehearsal checklist

- [ ] Full run-through with a timer; total between 9:00 and 9:59.
- [ ] Every hand-off spoken aloud once: the transition line is the cue, not a nod.
- [ ] Demo rehearsed twice: once with the live Mock run, once falling back to the recorded
      replay as if the run had stalled.
- [ ] Numbers spot-checked against `docs/submission/source_of_truth.md`.
- [ ] No sentence claims PolyU endorsement, production readiness or state-of-the-art.
- [ ] Backup slide numbers memorised (16–21) so nobody hunts for them on stage.
- [ ] Contribution statement still blank; the group completes it separately.

### If you are running long

Cut, in this order: slide 5's third mechanism sentence, slide 8's test-count aside,
slide 12's second comparison, slide 14's cache/recovery clause. Never cut slide 13 or 14 —
the failure analysis and the boundary are what distinguish this talk from a product pitch.
