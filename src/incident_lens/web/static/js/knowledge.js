/**
 * Knowledge views: system design (roles, ACL, gates) and recorded evaluation.
 * Numbers here are a transcription of the tracked hardened batch report;
 * the evaluation view labels them as a static snapshot, not a live feed.
 */

import { escapeHtml as esc } from "./api.js";
import { badge } from "./components.js";

/* ============================================================
   System design
   ============================================================ */

const STAGES = [
  { n: "01", name: "Monitor", note: "可选 · 事件响应工作流", optional: true },
  { n: "02", name: "Coordinate", note: "读取证据缺口并分派" },
  { n: "03", name: "Dispatch", note: "1–2 个专家任务，并发执行" },
  { n: "04", name: "Merge", note: "确定性校验与发布" },
  { n: "05", name: "Verify", note: "仅 Dynamic (with verifier)", optional: true },
  { n: "06", name: "Finalize", note: "接地门禁 · 接受或存疑" },
  { n: "07", name: "Report", note: "确定性渲染" },
];

const DECISIONS = [
  {
    name: "INVESTIGATE",
    tone: "info",
    rule: "本轮没有已选中的假设，且预算仍有剩余。",
    detail: "分配 1–2 个任务；每个任务必须写明角色、问题，以及一个能区分因果的判别标准（discriminator）。",
  },
  {
    name: "FINALIZE",
    tone: "success",
    rule: "一个假设已被跨来源证据支持，且门禁预检通过。",
    detail: "提交选中假设；同时给出停止理由。最终是否接受由 FinalizeGate 决定，不由协调者决定。",
  },
  {
    name: "ABSTAIN",
    tone: "warning",
    rule: "证据不足以区分竞争假设，或预算耗尽。",
    detail: "不选择假设，写出明确的停止理由；报告状态为 INCONCLUSIVE。",
  },
];

const BOUNDS = [
  ["4", "调查轮次", "每轮最多 2 个任务"],
  ["12", "工具调用", "跨角色共享的上限"],
  ["16", "模型请求", "包含决策、审查与修复"],
  ["600 s", "墙钟时间", "超时即有序终止"],
];

const GATES = [
  ["引用来源", "每条引用必须来自本次运行实际观察到的记录；未观察到的 ID 不能进入结论。"],
  ["来源多样性", "根因需要至少两个独立来源的支持，单一来源不足以定论。"],
  ["因果机制", "任务必须提供 cause-specific discriminator；与症状相关但机制不符的假设被拒绝。"],
  ["竞争解释", "仍有未决的竞争假设时，不允许 FINALIZE。"],
  ["预算审计", "轮次、工具、请求与时间均可复核；超限触发有序停止，而不是静默截断。"],
];

const INVARIANTS = [
  ["不可变上下文", "AgentContext 冻结签发身份与工具上限；任务只能收窄权限，不能提升。"],
  ["实际查询台账", "只有真正执行并返回的记录才能被引用，模型记忆不构成证据。"],
  ["公开文件白名单", "运行时只读取公开事件包；评测标签与私有答案不在可读路径内。"],
  ["回放路径约束", "回放只从允许的结果目录读取痕迹，并且不调用编排图、工具或提供方。"],
];

function aclCell(has) {
  // "is-empty", not "empty": .empty is a global empty-state block style.
  return `<td class="tool-cell"><span class="tool-dot ${has ? "" : "is-empty"}" aria-label="${has ? "允许" : "不允许"}">${
    has
      ? '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.2 4.2L19 7"/></svg>'
      : '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 12h12"/></svg>'
  }</span></td>`;
}

const ACL_ROLES = [
  { key: "coordinator", name: "协调者", tools: [] },
  { key: "logs", name: "日志代理", tools: ["query_logs"] },
  { key: "metrics", name: "指标代理", tools: ["query_metrics", "get_dependencies"] },
  { key: "database", name: "数据库代理", tools: ["get_db_*"] },
  { key: "changes", name: "变更代理", tools: ["query_changes", "get_config_diff"] },
  { key: "verifier", name: "验证者", tools: ["fetch_evidence_by_ids"] },
  { key: "reporter", name: "报告者", tools: ["fetch_evidence_by_ids"] },
  { key: "single", name: "单体代理", tools: ["query_logs", "query_metrics", "get_dependencies", "query_changes", "get_config_diff", "fetch_evidence_by_ids"] },
];

const ACL_COLUMNS = [
  ["日志", "query_logs"],
  ["指标", "query_metrics"],
  ["依赖", "get_dependencies"],
  ["变更", "query_changes"],
  ["配置差异", "get_config_diff"],
  ["数据库", "get_db_*"],
  ["证据取回", "fetch_evidence_by_ids"],
];

export function renderSystem(root) {
  root.innerHTML = `
    <div class="page-head">
      <h1 class="page-title type-heading-1">四个角色，一套可审计的契约</h1>
      <p class="page-desc">
        IncidentLens 不是“让多个模型各说一遍”。它把调查拆成可检查的职责：谁可以读什么、
        什么算证据、什么时候必须停止。模型只提出候选；是否成立由确定性代码判定。
      </p>
    </div>

    <section class="band" aria-labelledby="pipeline-title">
      <div class="band-head">
        <h2 class="section-title type-title-2" id="pipeline-title">一次调查的完整路径</h2>
        <span class="band-note">LangGraph StateGraph · 每个活跃阶段都有条件路由</span>
      </div>
      <ol class="stage-track">
        ${STAGES.map(
          (s) => `<li class="stage ${s.optional ? "is-optional" : ""}">
            <span class="stage-n">${s.n}</span>
            <span class="stage-name">${esc(s.name)}${s.optional ? badge("可选", "neutral") : ""}</span>
            <span class="stage-note">${esc(s.note)}</span>
          </li>`
        ).join("")}
      </ol>
      <p class="footnote">
        虚线阶段只在特定配置下运行：Monitor 仅用于事件响应工作流；Verify 仅用于
        Dynamic（+ Verifier）与 Single 的自审。Dynamic 是默认架构，跳过独立验证者。
      </p>
    </section>

    <section aria-labelledby="decision-title" class="section-gap">
      <h2 class="section-title type-title-2" id="decision-title">协调者只有三种动作</h2>
      <div class="decision-panel">
        ${DECISIONS.map(
          (d) => `<div class="decision-row" data-tone="${d.tone}">
            <div class="decision-head">${badge(d.name, d.tone, true)}</div>
            <p class="decision-rule">${esc(d.rule)}</p>
            <p class="decision-detail">${esc(d.detail)}</p>
          </div>`
        ).join("")}
      </div>
      <div class="bound-strip" role="list" aria-label="硬性预算">
        ${BOUNDS.map(
          ([value, label, note]) => `<div class="bound" role="listitem">
            <span class="bound-value">${esc(value)}</span>
            <span class="bound-label">${esc(label)}</span>
            <span class="bound-note">${esc(note)}</span>
          </div>`
        ).join("")}
      </div>
    </section>

    <section aria-labelledby="acl-title" class="section-gap">
      <div class="band-head">
        <h2 class="section-title type-title-2" id="acl-title">权限是代码，不是提示词</h2>
        <span class="band-note">角色 → 只读工具上限</span>
      </div>
      <div class="table-wrap card card-flush">
        <table class="data acl-table">
          <caption class="visually-hidden">每个角色被允许调用的只读工具</caption>
          <thead>
            <tr>
              <th scope="col">角色</th>
              ${ACL_COLUMNS.map(([label]) => `<th scope="col" class="col-tool">${esc(label)}</th>`).join("")}
            </tr>
          </thead>
          <tbody>
            ${ACL_ROLES.map(
              (r) => `<tr>
                <th scope="row"><span class="acl-role">${esc(r.name)}</span><span class="mono acl-id">${esc(r.key)}</span></th>
                ${ACL_COLUMNS.map(([, tool]) =>
                  aclCell(r.tools.some((t) => (t === "get_db_*" ? tool === "get_db_*" : t === tool)))
                ).join("")}
              </tr>`
            ).join("")}
          </tbody>
        </table>
      </div>
      <p class="footnote">
        数据库代理只在事件响应配置下启用。基准比较为各架构开启等价工具：
        metrics 与 single 额外获得五个只读 get_db_* 工具，以保证“单代理”不是被工具数量削弱的对照组。
        协调者、监控与修复方案代理没有任何读取工具。
      </p>
    </section>

    <section aria-labelledby="gates-title" class="section-gap">
      <div class="band-head">
        <h2 class="section-title type-title-2" id="gates-title">Grounding 由确定性门禁判定</h2>
        <span class="band-note">模型置信度不是接受信号</span>
      </div>
      <ol class="gate-list">
        ${GATES.map(
          ([name, desc], i) => `<li>
            <span class="gate-n">${String(i + 1).padStart(2, "0")}</span>
            <div><h3>${esc(name)}</h3><p>${esc(desc)}</p></div>
          </li>`
        ).join("")}
      </ol>
    </section>

    <section aria-labelledby="invariant-title" class="section-gap">
      <h2 class="section-title type-title-2" id="invariant-title">四条不可绕过的运行时约束</h2>
      <div class="invariant-grid">
        ${INVARIANTS.map(
          ([name, desc]) => `<article class="invariant">
            <h3>${esc(name)}</h3>
            <p>${esc(desc)}</p>
          </article>`
        ).join("")}
      </div>
    </section>

    <div class="next-band">
      <p><strong>这些约束如何被测量？</strong> 四种架构在同一模型、同一数据、同一预算下各跑 36 个案例。</p>
      <a class="btn btn-primary" href="#/evaluation">查看评测结果</a>
    </div>`;
}

/* ============================================================
   Evaluation (recorded batch, static snapshot)
   ============================================================ */

const BATCH = {
  id: "full144-hardened-c4-20261101",
  date: "2026-11-01",
  model: "auto/deepseek-v4.1-flash",
  cases: 36,
  identifiable: 29,
  abstainCases: 7,
  slots: 144,
  completed: 136,
  failures: 8,
  runtime: "4 h 39 min",
  rows: [
    { name: "Single", completed: "35/36", root: "25/28", abstain: "7/7", quality: 32, latency: 680.9, tokens: 245971 },
    { name: "Fixed-4", completed: "34/36", root: "15/27", abstain: "7/7", quality: 22, latency: 196.3, tokens: 58042 },
    { name: "Dynamic", primary: true, completed: "33/36", root: "27/27", abstain: "6/6", quality: 33, latency: 412.9, tokens: 149216 },
    { name: "Dynamic (with verifier)", completed: "34/36", root: "23/27", abstain: "7/7", quality: 30, latency: 503.8, tokens: 233772 },
  ],
  levers: [
    { name: "竞争性原因", values: ["6/7", "4/7", "7/7", "6/7"], ratio: [6 / 7, 4 / 7, 1, 6 / 7] },
    { name: "反事实配对", values: ["5/6", "3/6", "6/6", "4/6"], ratio: [5 / 6, 3 / 6, 1, 4 / 6] },
    { name: "标准事件", values: ["6/7", "3/7", "6/7", "6/7"], ratio: [6 / 7, 3 / 7, 6 / 7, 6 / 7] },
    { name: "边界条件", values: ["6/7", "4/7", "6/7", "5/7"], ratio: [6 / 7, 4 / 7, 6 / 7, 5 / 7] },
    { name: "缺失判别", values: ["7/7", "7/7", "6/7", "7/7"], ratio: [1, 1, 6 / 7, 1] },
    { name: "误导性证据", values: ["2/2", "1/2", "2/2", "2/2"], ratio: [1, 0.5, 1, 1] },
  ],
};

function bar(value, max, tone = "accent", label = "") {
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  return `<span class="bar" aria-hidden="true"><span class="bar-fill" data-tone="${tone}" style="--pct:${pct.toFixed(1)}"></span></span>${
    label ? `<span class="bar-label">${esc(label)}</span>` : ""
  }`;
}

function heat(value) {
  // 0..1 -> brand-red tint. Two bands with a gap in between: the light band
  // always takes dark ink, the dark band always takes white, so no cell lands
  // in the mid-tone zone where neither ink reaches 4.5:1. The tint is driven by
  // CSS custom properties so no presentational magic numbers leak inline.
  const strong = value >= 0.8;
  const pct = strong ? 80 + Math.round((value - 0.8) * 30) : Math.round(8 + value * 40);
  return `data-ink="${strong ? "light" : "dark"}" style="--heat:${pct}"`;
}

export function renderEvaluation(root) {
  const maxLatency = Math.max(...BATCH.rows.map((r) => r.latency));
  const maxTokens = Math.max(...BATCH.rows.map((r) => r.tokens));

  root.innerHTML = `
    <div class="page-head">
      <h1 class="page-title type-heading-1">协调是否值得它的成本？</h1>
      <p class="page-desc">
        同一模型、同一批 36 个加固案例、同一预算与工具，四种架构各跑一次，共 144 个匹配槽位。
        下表是一次已归档运行的真实数字，不是实时结果，也不是盲测。
      </p>
      <div class="run-tags">
        ${badge("RECORDED BATCH", "neutral", true)}
        ${badge(BATCH.date, "neutral")}
        ${badge(BATCH.model, "neutral")}
        ${badge("cache off · 1 repeat", "neutral")}
      </div>
    </div>

    <section class="stat-band" aria-label="批次概况">
      ${[
        [BATCH.cases, "加固案例", `${BATCH.identifiable} 可识别 · ${BATCH.abstainCases} 应弃权`],
        [BATCH.slots, "匹配槽位", `${BATCH.completed} 完成 · ${BATCH.failures} 技术失败`],
        ["0", "错误根因", "19 次漏判全部 INCONCLUSIVE"],
        [BATCH.runtime, "批处理耗时", "4 个并发任务"],
      ]
        .map(
          ([value, label, note]) => `<div class="stat">
            <span class="stat-value">${esc(String(value))}</span>
            <span class="stat-label">${esc(label)}</span>
            <span class="stat-note">${esc(note)}</span>
          </div>`
        )
        .join("")}
    </section>

    <section aria-labelledby="table-title" class="section-gap">
      <div class="band-head">
        <h2 class="section-title type-title-2" id="table-title">质量与成本</h2>
        <span class="band-note">质量成功率以全部 36 个案例为分母，技术失败不剔除</span>
      </div>
      <div class="table-wrap card card-flush">
        <table class="data eval-table">
          <thead>
            <tr>
              <th scope="col">架构</th>
              <th scope="col" class="num">完成</th>
              <th scope="col" class="num">根因正确</th>
              <th scope="col" class="num">正确弃权</th>
              <th scope="col">质量成功</th>
              <th scope="col" class="num">平均耗时</th>
              <th scope="col" class="num">平均 tokens</th>
            </tr>
          </thead>
          <tbody>
            ${BATCH.rows
              .map(
                (r) => `<tr class="${r.primary ? "is-primary" : ""}">
                  <th scope="row">
                    <span class="row-name">${esc(r.name)}</span>
                    ${r.primary ? badge("PRIMARY", "accent") : ""}
                  </th>
                  <td class="num mono">${esc(r.completed)}</td>
                  <td class="num mono">${esc(r.root)}</td>
                  <td class="num mono">${esc(r.abstain)}</td>
                  <td class="quality-cell">
                    ${bar(r.quality, 36, r.primary ? "brand" : "muted", `${r.quality}/36`)}
                  </td>
                  <td class="num mono">${r.latency.toFixed(1)} s</td>
                  <td class="num mono">${r.tokens.toLocaleString("en-US")}</td>
                </tr>`
              )
              .join("")}
          </tbody>
        </table>
      </div>
      <p class="footnote">
        根因正确率只统计“可识别且完成”的运行；弃权率只统计“应弃权且完成”的运行。两类分母不同，
        因此 27/27 与 6/6 不能相加成 33/33。
      </p>
    </section>

    <section aria-labelledby="tradeoff-title" class="section-gap">
      <h2 class="section-title type-title-2" id="tradeoff-title">同一个质量，不同的代价</h2>
      <div class="tradeoff-grid">
        <article class="chart-card">
          <h3>平均耗时</h3>
          ${BATCH.rows
            .map(
              (r) => `<div class="hbar">
                <span class="hbar-name">${esc(r.name)}</span>
                ${bar(r.latency, maxLatency, r.primary ? "brand" : "muted", `${r.latency.toFixed(0)} s`)}
              </div>`
            )
            .join("")}
        </article>
        <article class="chart-card">
          <h3>平均 tokens（仅完成运行）</h3>
          ${BATCH.rows
            .map(
              (r) => `<div class="hbar">
                <span class="hbar-name">${esc(r.name)}</span>
                ${bar(r.tokens, maxTokens, r.primary ? "brand" : "muted", `${Math.round(r.tokens / 1000)}k`)}
              </div>`
            )
            .join("")}
        </article>
      </div>
      <div class="finding-list">
        <article class="finding">
          <h3>Dynamic vs Single</h3>
          <p>质量 +1（33 对 32），平均耗时 <strong>−39.4%</strong>，tokens <strong>−39.3%</strong>。配对结果为 3 胜 2 负 31 平。</p>
        </article>
        <article class="finding">
          <h3>Dynamic vs Dynamic (with verifier)</h3>
          <p>质量 +3，耗时 <strong>−18.0%</strong>，tokens <strong>−36.2%</strong>。独立验证者多花 <strong>56.7%</strong> tokens，未带来可测收益。</p>
        </article>
        <article class="finding">
          <h3>Fixed-4 的便宜是假象</h3>
          <p>最快（196.3 s），但 27 个可识别案例中错误弃权 12 个，质量只有 22/36。</p>
        </article>
      </div>
    </section>

    <section aria-labelledby="lever-title" class="section-gap">
      <div class="band-head">
        <h2 class="section-title type-title-2" id="lever-title">难度杠杆下的表现</h2>
        <span class="band-note">单元格为“正确 / 该杠杆的合格运行”</span>
      </div>
      <div class="table-wrap card card-flush">
        <table class="data lever-table">
          <thead>
            <tr>
              <th scope="col">难度杠杆</th>
              ${BATCH.rows.map((r) => `<th scope="col" class="num">${esc(r.name)}</th>`).join("")}
            </tr>
          </thead>
          <tbody>
            ${BATCH.levers
              .map(
                (l) => `<tr>
                  <th scope="row">${esc(l.name)}</th>
                  ${l.values
                    .map((v, i) => `<td class="num mono heat-cell" ${heat(l.ratio[i])}>${esc(v)}</td>`)
                    .join("")}
                </tr>`
              )
              .join("")}
          </tbody>
        </table>
      </div>
      <p class="footnote">
        Dynamic 是唯一在竞争性原因上达到 7/7、在反事实配对上达到 6/6 的架构；
        它在所有杠杆上的剩余错误都是“未得出结论”，没有一次给出错误根因。
      </p>
    </section>

    <section aria-labelledby="boundary-title" class="section-gap">
      <h2 class="section-title type-title-2" id="boundary-title">这些数字不能证明什么</h2>
      <div class="boundary-card">
        <ul>
          <li><strong>不是盲测。</strong>36 个案例来自公开开发集，标签是评估者侧的候选标签，人工确认数为 0。</li>
          <li><strong>没有显著性。</strong>单模型（deepseek-v4.1-flash）、单次重复、温度 0；差异是描述性的，没有置信区间。</li>
          <li><strong>技术失败计入质量分母。</strong>8 次失败为 6 次结构化输出无效（5 次响应包缺少字符串内容、1 次截断且修复后仍无效）与 2 次 finding 身份不匹配，分布在四个架构上。</li>
          <li><strong>成本守卫是回放估计。</strong>−44.0% / −21.9% 来自冻结痕迹的重放估算，不是新的测量运行。</li>
          <li><strong>缓存与故障恢复只在 Mock 上测过。</strong>真实提供方的恢复行为没有独立测量。</li>
        </ul>
        <p class="boundary-source">
          数据源：<code>results/v16/wp-d/${esc(BATCH.id)}/</code> ·
          可复算报告：<code>analysis/wp_d/reports/hardened144-20261101/</code> ·
          完整口径见 <code>docs/EVALUATION.md</code>。
        </p>
      </div>
    </section>`;
}
