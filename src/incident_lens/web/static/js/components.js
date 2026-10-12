/**
 * Shared UI components: badges, empty states, toasts, drawer.
 */

import { escapeHtml, SOURCE_TYPE_META, formatDateTime } from "./api.js";

export function badge(text, tone = "neutral", withDot = false) {
  const cls = tone === "neutral" ? "badge" : `badge badge-${tone}`;
  return `<span class="${cls}">${withDot ? '<span class="dot" aria-hidden="true"></span>' : ""}${escapeHtml(text)}</span>`;
}

export function emptyState({ title, desc = "", actionHtml = "" }) {
  return `
    <div class="empty">
      <div class="empty-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.8-3.8"/></svg>
      </div>
      <div class="empty-title">${escapeHtml(title)}</div>
      ${desc ? `<div class="empty-desc">${escapeHtml(desc)}</div>` : ""}
      ${actionHtml}
    </div>`;
}

export function skeletonRows(count = 4, height = 44) {
  return Array.from({ length: count })
    .map(() => `<div class="skeleton" style="height:${height}px;margin-bottom:10px"></div>`)
    .join("");
}

export function loadingBlock(text = "加载中…") {
  return `<div class="loading-block"><span class="spinner spinner-lg" role="status" aria-label="加载中"></span><span>${escapeHtml(text)}</span></div>`;
}

/* ---------------- Toast ---------------- */

const TOAST_ICONS = {
  success: '<svg viewBox="0 0 24 24"><path d="M4.5 12.5l5 5 10-11"/></svg>',
  error: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7.5V13M12 16.4v.1"/></svg>',
  info: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.6v.1"/></svg>',
};

export function toast(message, type = "info", timeout = 4200) {
  const region = document.getElementById("toast-region");
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.innerHTML = `${TOAST_ICONS[type] || TOAST_ICONS.info}<div class="toast-msg">${escapeHtml(message)}</div>`;
  region.appendChild(el);
  setTimeout(() => {
    el.style.opacity = "0";
    el.style.transition = "opacity 240ms ease";
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

export function evidenceDrawerHtml(record) {
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
        <div class="kv-row"><dt>观察时间</dt><dd class="mono">${escapeHtml(record.observed_at)}</dd></div>
        <div class="kv-row"><dt>来源文件</dt><dd class="mono">${escapeHtml(record.source_path)}</dd></div>
        <div class="kv-row"><dt>事件</dt><dd class="mono">${escapeHtml(record.incident_id)}</dd></div>
        ${meta}
      </dl>
      <div class="field">
        <span class="field-label">原始摘录</span>
        <pre class="json-block" style="white-space:pre-wrap">${escapeHtml(record.excerpt)}</pre>
      </div>
    </div>`;
}

export function bindEvidenceChips(root, evidenceIndex) {
  root.querySelectorAll("[data-evidence-id]").forEach((chip) => {
    chip.addEventListener("click", () => {
      const id = chip.dataset.evidenceId;
      const record = evidenceIndex[id];
      if (!record) {
        toast(`证据 ${id} 未在本次运行索引中`, "error");
        return;
      }
      openDrawer(`证据 · ${id}`, evidenceDrawerHtml(record));
    });
  });
}

export function evidenceChips(ids, evidenceIndex, { emptyText = "无" } = {}) {
  if (!ids?.length) return `<span class="text-muted">${escapeHtml(emptyText)}</span>`;
  return ids
    .map((id) => {
      const known = evidenceIndex?.[id] !== undefined;
      return `<button type="button" class="evidence-chip" data-evidence-id="${escapeHtml(id)}" ${
        known ? "" : 'aria-disabled="true"'
      }>${escapeHtml(id)}</button>`;
    })
    .join("");
}

export function updatedSince(epoch) {
  return formatDateTime(epoch);
}
