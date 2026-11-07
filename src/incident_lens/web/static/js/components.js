/**
 * Shared UI components: badges, empty states, skeletons, toasts, drawer.
 *
 * Presentation-only module. Every exported name, signature, escaping rule
 * and asserted copy string is part of the test contract
 * (tests/integration/test_v12_ui.py, tests/web/*.test.mjs) and must not change.
 */

import { escapeHtml, SOURCE_TYPE_META, formatDateTime } from "./api.js";

/* ---------------- Badges ---------------- */

export function badge(text, tone = "neutral", withDot = false) {
  const cls = tone === "neutral" ? "badge" : `badge badge-${tone}`;
  return `<span class="${cls}">${withDot ? '<span class="dot" aria-hidden="true"></span>' : ""}${escapeHtml(text)}</span>`;
}

/* ---------------- Empty state ---------------- */

const EMPTY_ICON_SEARCH =
  '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.8-3.8"/></svg>';

export function emptyState({ title, desc = "", actionHtml = "", icon = null }) {
  const iconHtml = icon == null ? EMPTY_ICON_SEARCH : icon;
  return `
    <div class="empty">
      <div class="empty-icon" aria-hidden="true">${iconHtml}</div>
      <div class="empty-title">${escapeHtml(title)}</div>
      ${desc ? `<div class="empty-desc">${escapeHtml(desc)}</div>` : ""}
      ${actionHtml ? `<div class="empty-actions">${actionHtml}</div>` : ""}
    </div>`;
}

/* ---------------- Skeletons ---------------- */

/* Generic bars. Retained for compatibility, but layout-shaped skeletons
   below must be used for table / list / KPI / run-detail content. */
export function skeletonRows(count = 4, height = 44) {
  return Array.from({ length: count })
    .map(() => `<div class="skeleton skeleton-row" style="height:${height}px"></div>`)
    .join("");
}

/* Table-shaped: a header row plus `rows` body rows aligned to table.data. */
export function skeletonTable(rows = 6, cols = 8) {
  const cell = '<span></span>';
  const head = `<div class="skeleton-head" aria-hidden="true">${Array.from({ length: cols }).map(() => "<span></span>").join("")}</div>`;
  const body = Array.from({ length: rows })
    .map(() => `<div class="skeleton-line" aria-hidden="true">${Array.from({ length: cols }).map(() => cell).join("")}</div>`)
    .join("");
  return `<div class="skeleton-table" aria-busy="true" style="--skeleton-cols:repeat(${cols}, minmax(0, 1fr))"><span class="visually-hidden" role="status">加载中…</span>${head}${body}</div>`;
}

/* Case-item-shaped rows for a master list. */
export function skeletonList(count = 6) {
  const item = '<div class="skeleton-item" aria-hidden="true"><span class="skeleton"></span><span class="skeleton"></span><span class="skeleton"></span></div>';
  return `<div class="skeleton-list" aria-busy="true"><span class="visually-hidden" role="status">加载中…</span>${Array.from({ length: count }).map(() => item).join("")}</div>`;
}

/* KPI-sized blocks for a stat strip. */
export function skeletonKpi(count = 4) {
  const block = '<div class="skeleton-block" aria-hidden="true"><span class="skeleton"></span><span class="skeleton"></span></div>';
  return `<div class="skeleton-kpi" aria-busy="true" style="--skeleton-kpi-cols:${count}"><span class="visually-hidden" role="status">加载中…</span>${Array.from({ length: count }).map(() => block).join("")}</div>`;
}

/* Run-detail-shaped loading panel (header + KPI strip + tab bar + rows). */
export function loadingBlock(text = "加载中…") {
  const kpis = Array.from({ length: 4 })
    .map(() => '<div class="skeleton-block" aria-hidden="true"><span class="skeleton"></span><span class="skeleton"></span></div>')
    .join("");
  const rows = Array.from({ length: 4 })
    .map(() => '<div class="skeleton" aria-hidden="true"></div>')
    .join("");
  return `<div class="skeleton-panel" aria-busy="true" role="status">
    <span class="visually-hidden">${escapeHtml(text)}</span>
    <div class="skeleton-header" aria-hidden="true"><div class="skeleton"></div><div class="skeleton"></div></div>
    <div class="skeleton-kpi" aria-hidden="true">${kpis}</div>
    <div class="skeleton-tabs" aria-hidden="true"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div>
    <div class="skeleton-rows" aria-hidden="true">${rows}</div>
  </div>`;
}

/* ---------------- Toast ---------------- */

const TOAST_ICONS = {
  success: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4.5 12.5l5 5 10-11"/></svg>',
  error: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7.5V13M12 16.4v.1"/></svg>',
  info: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.6v.1"/></svg>',
};

export function toast(message, type = "info", timeout = 4200) {
  const region = document.getElementById("toast-region");
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.innerHTML = `${TOAST_ICONS[type] || TOAST_ICONS.info}<div class="toast-msg">${escapeHtml(message)}</div>`;
  region.appendChild(el);
  setTimeout(() => {
    el.classList.add("is-leaving");
    setTimeout(() => el.remove(), 260);
  }, timeout);
}

/* ---------------- Drawer ---------------- */

let lastFocused = null;
let previousOverflow = "";

export function openDrawer(title, bodyHtml) {
  const drawer = document.getElementById("drawer");
  const backdrop = document.getElementById("drawer-backdrop");
  lastFocused = document.activeElement;
  document.getElementById("drawer-title").textContent = title;
  document.getElementById("drawer-body").innerHTML = bodyHtml;
  drawer.hidden = false;
  backdrop.hidden = false;
  document.querySelector(".app-shell").inert = true;
  previousOverflow = document.body.style.overflow;
  document.body.style.overflow = "hidden";
  document.getElementById("drawer-close").focus();
  document.addEventListener("keydown", onDrawerKey);
}

export function closeDrawer() {
  document.getElementById("drawer").hidden = true;
  document.getElementById("drawer-backdrop").hidden = true;
  document.removeEventListener("keydown", onDrawerKey);
  document.querySelector(".app-shell").inert = false;
  document.body.style.overflow = previousOverflow;
  if (lastFocused?.isConnected) lastFocused.focus();
}

function onDrawerKey(event) {
  if (event.key === "Escape") {
    event.preventDefault();
    closeDrawer();
  }
  if (event.key === "Tab") {
    const items = [...document.getElementById("drawer").querySelectorAll(
      'button, a[href], input, select, textarea, [tabindex="0"], summary'
    )].filter((el) => !el.disabled && el.getClientRects().length);
    const first = items[0];
    const last = items.at(-1);
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first?.focus();
    }
  }
}

export function initDrawer() {
  document.getElementById("drawer-close").addEventListener("click", closeDrawer);
  document.getElementById("drawer-backdrop").addEventListener("click", closeDrawer);
}

/* ---------------- Evidence detail ---------------- */

export function evidenceDrawerHtml(record, observation = null) {
  const src = SOURCE_TYPE_META[record.source_type] || { label: record.source_type, tone: "neutral" };
  const meta = Object.entries(record.metadata || {})
    .map(
      ([key, value]) => `
      <div class="kv-row"><dt>${escapeHtml(key)}</dt><dd class="mono">${escapeHtml(
        typeof value === "object" ? JSON.stringify(value) : value
      )}</dd></div>`
    )
    .join("");
  return `
    <div class="stack">
      <div class="chip-row">
        ${badge(src.label, src.tone)}
        ${badge(record.service, "neutral")}
      </div>
      <dl class="kv-list">
        <div class="kv-row"><dt>Evidence ID（原始 ID）</dt><dd class="mono">${escapeHtml(record.evidence_id)}</dd></div>
        <div class="kv-row"><dt>证据观察时间（事故时间）</dt><dd class="mono">${escapeHtml(record.observed_at)}</dd></div>
        <div class="kv-row"><dt>来源文件</dt><dd class="mono">${escapeHtml(record.source_path)}</dd></div>
        <div class="kv-row"><dt>事件</dt><dd class="mono">${escapeHtml(record.incident_id)}</dd></div>
        ${meta}
      </dl>
      <p class="text-muted">来源 Agent、查询执行时间、Findings / Hypotheses 关系与报告引用仅来自当前回放前缀。无法获得的原始证据不补造。</p>
      ${observation ? `<dl class="kv-list"><div class="kv-row"><dt>首次来源 Agent</dt><dd>${escapeHtml(observation.role || 'not recorded')}</dd></div><div class="kv-row"><dt>查询执行时间</dt><dd class="mono">${escapeHtml(observation.timestamp || 'not recorded')}</dd></div><div class="kv-row"><dt>来源工具 / 事件</dt><dd class="mono">${escapeHtml(observation.tool || 'not recorded')} / ${escapeHtml(observation.event_id || 'not recorded')}</dd></div></dl>
      <details><summary>已记录查询 / Task / Call</summary><pre class="json-block">${escapeHtml(JSON.stringify({task_id:observation.task_id,call_id:observation.call_id,args:observation.args,observations:observation.observations}, null, 2))}</pre></details>
      <h3>关联 Finding / Hypothesis</h3>
      ${(observation.findings || []).map(f=>`<p><strong>${escapeHtml(f.role)} · ${escapeHtml(f.relation)}</strong><br>${escapeHtml(f.claim)}<br><span class="tag-id">${escapeHtml(f.finding_id)}</span></p>`).join('') || '<p class="text-muted">当前前缀没有关联 Finding。</p>'}
      ${(observation.hypotheses || []).map(h=>`<p>${escapeHtml(h.failure_mode)} · ${escapeHtml(h.relation)} · ${escapeHtml(h.status)}</p>`).join('')}
      <h3>报告引用</h3>${observation.report_references ? `<p>${observation.report_references.supporting ? '最终报告支持证据' : observation.report_references.provisional ? '用于待确认解释，尚未支持最终诊断' : '未列为最终报告支持证据'}</p>${(observation.report_references.causal_chain || []).map(line=>`<p>${escapeHtml(line)}</p>`).join('')}${(observation.report_references.provisional_observations || []).map(line=>`<p>${escapeHtml(line)}</p>`).join('')}` : '<p class="text-muted">当前前缀尚未生成报告。</p>'}` : ""}
      <div class="field">
        <span class="field-label">原始摘录</span>
        <pre class="json-block is-wrapped">${escapeHtml(record.excerpt)}</pre>
      </div>
    </div>`;
}

export function bindEvidenceChips(root, evidenceIndex, provenance = {}) {
  root.querySelectorAll("[data-evidence-id]").forEach((chip) => {
    chip.addEventListener("click", () => {
      const id = chip.dataset.evidenceId;
      const record = evidenceIndex && Object.hasOwn(evidenceIndex, id) ? evidenceIndex[id] : null;
      if (!record) {
        toast(`证据 ${id} 未在本次运行索引中`, "error");
        return;
      }
      openDrawer(`证据 · ${id}`, evidenceDrawerHtml(record, provenance[id]));
    });
  });
}

export function evidenceChips(ids, evidenceIndex, { emptyText = "无" } = {}) {
  if (!ids?.length) return `<span class="text-muted">${escapeHtml(emptyText)}</span>`;
  return ids
    .map((id) => {
      const known = evidenceIndex && Object.hasOwn(evidenceIndex, id);
      return `<button type="button" class="evidence-chip" data-evidence-id="${escapeHtml(id)}" ${
        known ? "" : 'disabled title="unavailable in this prefix"'
      }>${escapeHtml(id)}</button>`;
    })
    .join("");
}

export function updatedSince(epoch) {
  return formatDateTime(epoch);
}


export function workflowReportHtml(state, evidenceIndex = {}) {
  const report = state.report || {};
  const alert = state.incident_alert;
  const plan = report.remediation_plan;
  const taskRecords = state.task_records || [];
  const termination = report.termination || state.termination;
  const list = (title, values) => values?.length ? `<section class="workflow-plan-section"><h4>${escapeHtml(title)}</h4><ul class="symptom-list">${values.map(value => `<li>${escapeHtml(value)}</li>`).join("")}</ul></section>` : "";
  if (!alert && !plan && !taskRecords.length && !report.diagnosis_status && !termination) return "";
  return `<section class="report-section workflow-result" aria-label="事件响应工作流">
    <h3>事件响应工作流</h3>
    <dl class="workflow-status-grid">
      <div><dt>诊断状态</dt><dd>${badge(report.diagnosis_status || report.status, "neutral")}</dd></div>
      <div><dt>方案状态</dt><dd>${badge(report.remediation_status || "NOT_STARTED", report.remediation_status === "PLAN_FAILED" ? "danger" : "neutral")}</dd></div>
      <div><dt>工作流状态</dt><dd>${badge(report.workflow_status || state.workflow_status || "FINISHED", (report.workflow_status || state.workflow_status) === "FAILED" ? "danger" : "neutral")}</dd></div>
    </dl>
    ${termination ? `<section class="workflow-plan-section"><h4>终止结果</h4><div class="chip-row">${badge(termination.reason, termination.outcome === "FAILED" ? "danger" : "neutral")}${badge(termination.outcome)}</div><p>停止确认：${termination.stop_completed ? "已完成" : "未完成"}${termination.failure_stage ? ` · 失败阶段：${escapeHtml(termination.failure_stage)}` : ""}</p></section>` : ""}
    ${alert ? `<section class="workflow-plan-section"><h4>监控告警 · ${escapeHtml(alert.status)}</h4><p>${escapeHtml(alert.summary)}</p><div class="chip-row">${(alert.affected_services || []).map(service => badge(service)).join("")}</div><div class="cite-wrap">${evidenceChips(alert.evidence_ids, evidenceIndex)}</div></section>` : ""}
    ${plan ? `<div class="plan-only-note" role="note"><strong>PLAN_ONLY · 仅生成建议方案</strong><p>方案尚未执行；诊断完成和方案就绪不表示服务已恢复。变更前需操作人员确认。</p></div>
      <p>${escapeHtml(plan.objective)}</p><div class="chip-row">${plan.affected_services.map(service => badge(service)).join("")}</div>
      <div class="workflow-plan-grid">${list("建议动作", plan.actions)}${list("执行前提", plan.preconditions)}${list("风险", plan.risks)}${list("验证步骤", plan.verification_steps)}${list("回滚", plan.rollback)}</div>
      <div class="workflow-plan-section"><h4>方案引用证据</h4><div class="cite-wrap">${evidenceChips(plan.evidence_ids, evidenceIndex)}</div><p class="text-muted mono workflow-version">根因版本 ${escapeHtml(plan.root_cause_version)}</p></div>` : ""}
    ${taskRecords.length ? `<details class="workflow-plan-section"><summary>任务与重试记录 · ${taskRecords.length}</summary><div class="table-wrap"><table class="data"><thead><tr><th scope="col">任务 / 尝试</th><th scope="col">角色</th><th scope="col">状态</th><th scope="col">错误</th></tr></thead><tbody>${taskRecords.map(task => `<tr><td class="mono">${escapeHtml(task.task_id)}<div class="cell-sub">${escapeHtml(task.attempt_id)} · 第 ${escapeHtml(task.attempt)} 次</div></td><td>${escapeHtml(task.role)}</td><td>${badge(task.status)}</td><td>${escapeHtml(task.error_code || "—")}</td></tr>`).join("")}</tbody></table></div></details>` : ""}
  </section>`;
}
