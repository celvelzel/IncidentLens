import { replayPrefix, replayBookmarks, eventCategory, evidenceContext } from "./replay.js";
import { metadataHtml, workflowHtml, historyHtml, reviewTimelineHtml, reliabilityHtml, jumpButton } from "./replay-panels.js";
/**
 * IncidentLens views: overview, investigate, run detail, library.
 */

import {
  escapeHtml,
  formatDateTime,
  formatDuration,
  formatTime,
  getCases,
  getMeta,
  getTraces,
  loadReplay,
  runInvestigation,
  ApiError,
  STATUS_META,
  HYPO_STATUS_META,
  EVENT_KIND,
  ROLE_LABEL,
  SOURCE_TYPE_META,
} from "./api.js";
import {
  badge,
  bindEvidenceChips,
  emptyState,
  evidenceChips,
  loadingBlock,
  skeletonRows,
  toast,
  workflowReportHtml,
  closeDrawer,
} from "./components.js";

Object.assign(ROLE_LABEL, { database: "数据库代理", monitoring: "监控代理", remediation: "修复方案代理" });
Object.assign(SOURCE_TYPE_META, { database: { label: "数据库", tone: "info" } });
Object.assign(EVENT_KIND, {
  INCIDENT_ALERT: { kind: "other", label: "监控判断", tone: "info" },
  PLAN_READY: { kind: "other", label: "建议方案就绪", tone: "info" },
  STOP: { kind: "other", label: "历史停止事件", tone: "neutral" },
  WORKFLOW_STOP_REQUESTED: { kind: "other", label: "停止请求", tone: "neutral" },
  NORMAL_TERMINATION: { kind: "other", label: "有序结束", tone: "neutral" },
  RUNTIME_FAILURE: { kind: "other", label: "运行失败", tone: "danger" },
  RUNTIME_ERROR: { kind: "other", label: "执行异常", tone: "danger" },
  STOP_TIMEOUT: { kind: "other", label: "停止确认超时", tone: "danger" },
  MODEL_FAILURE: { kind: "llm", label: "调用失败", tone: "warning" },
  MODEL_RECOVERED: { kind: "other", label: "调用失败已恢复", tone: "info" },
  REMEDIATION_FAILED: { kind: "other", label: "方案生成失败", tone: "danger" },
  DIAGNOSIS_ACCEPTED: { kind: "other", label: "诊断通过门禁", tone: "info" },
  STOP_ACK: { kind: "other", label: "停止确认", tone: "neutral" },
});

/* ============================================================
   Overview
   ============================================================ */

export async function renderOverview(root) {
  root.innerHTML = `
    <section class="hero" aria-labelledby="hero-title">
      <div class="hero-kicker">Evidence-Driven RCA Console</div>
      <h1 class="hero-title" id="hero-title">让每一次根因结论，都有据可查</h1>
      <p class="hero-desc">
        IncidentLens 以多智能体协作调查软件故障：协调者分派任务、专家代理在权限边界内取证、
        验证者交叉核对，最终输出带引用的根因报告 —— 或在证据不足时明确存疑。
      </p>
      <div class="hero-actions">
        <a class="btn btn-primary btn-lg" href="#/investigate">
          <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.8-3.8"/><path d="M11 8v6M8 11h6"/></svg>
          开始调查
        </a>
        <a class="btn btn-lg" href="#/library">
          <svg viewBox="0 0 24 24"><path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H10l2 2.5h6.5A1.5 1.5 0 0 1 20 8v10.5a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18.5z"/></svg>
          浏览痕迹档案
        </a>
      </div>
    </section>

    <div class="stack" style="margin-top:var(--sp-6)">
      <section aria-labelledby="stats-title">
        <h2 class="section-title" id="stats-title">运行概况</h2>
        <div class="kpi-grid" id="overview-stats">${skeletonRows(1, 92)}</div>
      </section>

      <section aria-labelledby="pipeline-title">
        <h2 class="section-title" id="pipeline-title">调查流水线</h2>
        <div class="pipeline">
          <div class="pipeline-stage"><h3>协调分派</h3><p>协调者阅读公开事件摘要，提出 1–2 个带判别标准的调查任务。</p></div>
          <div class="pipeline-stage"><h3>专家取证</h3><p>日志 / 指标 / 变更代理仅能调用各自角色被允许的工具。</p></div>
          <div class="pipeline-stage"><h3>校验合并</h3><p>批次结果对照签发身份与实际查询台账验证后统一合并。</p></div>
          <div class="pipeline-stage"><h3>验证审查</h3><p>验证者基于授权获取的记录给出充分 / 不足 / 冲突裁定。</p></div>
          <div class="pipeline-stage"><h3>落地报告</h3><p>通过接地门禁后输出引用报告；证据不足则明确存疑。</p></div>
        </div>
      </section>

      <section aria-labelledby="recent-title">
        <h2 class="section-title" id="recent-title">最近运行</h2>
        <div class="card card-flush" id="recent-runs">${skeletonRows(4, 40)}</div>
      </section>

      <section aria-labelledby="feature-title">
        <h2 class="section-title" id="feature-title">设计原则</h2>
        <div class="feature-grid">
          <div class="feature">
            <div class="feature-icon"><svg viewBox="0 0 24 24"><path d="M8 6.5h12M8 12h12M8 17.5h12"/><circle cx="4" cy="6.5" r="1.4"/><circle cx="4" cy="12" r="1.4"/><circle cx="4" cy="17.5" r="1.4"/></svg></div>
            <div><h3>引用或存疑</h3><p>结论必须引用确切记录；存在未决问题或竞争性假设时拒绝定论。</p></div>
          </div>
          <div class="feature">
            <div class="feature-icon"><svg viewBox="0 0 24 24"><path d="M12 3l7 3v5c0 4.4-3 8.4-7 10-4-1.6-7-5.6-7-10V6z"/><path d="M9.2 12l2 2 3.6-4"/></svg></div>
            <div><h3>权限边界取证</h3><p>只读工具、角色 ACL、不可变签发上下文与实际查询台账。</p></div>
          </div>
          <div class="feature">
            <div class="feature-icon"><svg viewBox="0 0 24 24"><path d="M4 8.5A8 8 0 0 1 18.6 6.2M20 15.5A8 8 0 0 1 5.4 17.8"/><path d="M18.5 2.5v3.8h-3.8M5.5 21.5v-3.8h3.8"/></svg></div>
            <div><h3>离线可重放</h3><p>已保存痕迹可完整回放，不再调用编排图、工具或模型提供方。</p></div>
          </div>
          <div class="feature">
            <div class="feature-icon"><svg viewBox="0 0 24 24"><path d="M13 3L5 13.5h5L11 21l8-10.5h-5z"/></svg></div>
            <div><h3>解释缓存复用</h3><p>精确或保守语义复用，严格命名空间与引用校验。</p></div>
          </div>
        </div>
      </section>
    </div>`;

  try {
    const [traces, cases] = await Promise.all([getTraces(), getCases()]);
    if (!root.isConnected) return;
    const resolved = traces.filter((t) => t.status === "RESOLVED").length;
    const inconclusive = traces.filter((t) => t.status === "INCONCLUSIVE").length;
    document.getElementById("overview-stats").innerHTML = [
      kpi("事件案例", cases.length, "公开数据集"),
      kpi("存档痕迹", traces.length, "results/ 全量"),
      kpi("已定位根因", resolved, traces.length ? `${Math.round((resolved / traces.length) * 100)}% 占比` : "—", "success"),
      kpi("明确存疑", inconclusive, "证据不足时拒绝猜测", "warning"),
    ].join("");
    renderRecentRuns(traces.slice(0, 6));
  } catch (err) {
    if (!root.isConnected) return;
    document.getElementById("overview-stats").innerHTML = "";
    document.getElementById("recent-runs").innerHTML = failedBanner(err);
  }
}

function kpi(label, value, foot, tone) {
  return `
    <div class="kpi">
      <div class="kpi-label">${escapeHtml(label)}</div>
      <div class="kpi-value" ${tone ? `style="color:var(--${tone})"` : ""}>${escapeHtml(String(value))}</div>
      <div class="kpi-foot">${escapeHtml(foot || "")}</div>
    </div>`;
}

function renderRecentRuns(traces) {
  const box = document.getElementById("recent-runs");
  if (!box) return;
  if (!traces.length) {
    box.innerHTML = emptyState({
      title: "还没有运行记录",
      desc: "发起一次调查，运行结果会自动归档到 results/ 目录。",
      actionHtml: '<a class="btn btn-primary" href="#/investigate">新建调查</a>',
    });
    return;
  }
  box.innerHTML = traceTable(traces);
  bindTraceRows(box);
}

function failedBanner(err) {
  const msg = err instanceof ApiError ? err.message : "加载失败，请稍后重试";
  return `<div class="alert alert-danger" style="margin:var(--sp-4)"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7.5V13M12 16.4v.1"/></svg><div class="alert-msg">${escapeHtml(msg)}</div></div>`;
}

/* ============================================================
   Shared trace table
   ============================================================ */

function traceTable(traces) {
  return `
    <div class="table-wrap">
      <table class="data">
        <thead>
          <tr>
            <th scope="col">事件</th>
            <th scope="col">状态</th>
            <th scope="col">提供方</th>
            <th scope="col">变体</th>
            <th scope="col">轮次</th>
            <th scope="col">耗时</th>
            <th scope="col">更新时间</th><th scope="col">演示</th>
          </tr>
        </thead>
        <tbody>
          ${traces
            .map((t) => {
              const status = STATUS_META[t.status] || { tone: "neutral", label: t.status || "未知" };
              return `
              <tr class="is-clickable" data-trace-path="${escapeHtml(t.path)}" tabindex="0" role="link"
                  aria-label="查看 ${escapeHtml(t.incident_id)} 的运行详情">
                <td><div class="cell-main mono">${escapeHtml(t.incident_id)}</div><div class="cell-sub mono">${escapeHtml(t.run_id || "")}</div></td>
                <td>${badge(status.label, status.tone, true)}</td>
                <td>${badge(t.provider === "mock" ? "MOCK" : t.provider === "real" ? "REAL" : "UNKNOWN", t.provider === "mock" ? "accent" : "info")}</td>
                <td class="mono">${escapeHtml(t.variant || "not recorded")}</td>
                <td class="mono">${t.rounds ?? "—"}</td>
                <td class="mono">${formatDuration(t.elapsed_ms)}</td>
                <td>${formatDateTime(t.modified_at)}</td><td><a class="btn btn-sm" data-demo-link href="#/run?path=${encodeURIComponent(t.path)}&demo=1">演示回放</a></td>
              </tr>`;
            })
            .join("")}
        </tbody>
      </table>
    </div>`;
}

function bindTraceRows(container) {
  container.querySelectorAll("tr[data-trace-path]").forEach((row) => {
    const open = () => {
      location.hash = `#/run?path=${encodeURIComponent(row.dataset.tracePath)}`;
    };
    row.addEventListener("click", e => { if (!e.target.closest('a')) open(); });
    row.addEventListener("keydown", (e) => {
      if (e.target === row && (e.key === "Enter" || e.key === " ")) {
        e.preventDefault();
        open();
      }
    });
  });
}

/* ============================================================
   Investigate
   ============================================================ */

export async function renderInvestigate(root) {
  root.innerHTML = `
    <div class="page-head">
      <h1 class="page-title">新建调查</h1>
      <p class="page-desc">选择一个公开事件案例，配置提供方与缓存策略后发起多智能体调查。</p>
    </div>
    <div class="investigate-grid">
      <section class="card card-flush" aria-label="案例选择">
        <div class="card-header" style="flex-direction:column;align-items:stretch;gap:10px">
          <div>
            <div class="card-title">事件案例</div>
            <div class="card-subtitle" id="case-count">加载中…</div>
          </div>
          <div class="input-with-icon">
            <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.8-3.8"/></svg>
            <input class="input" id="case-search" type="search" placeholder="搜索事件 ID、标题或症状…" aria-label="搜索案例">
          </div>
        </div>
        <div class="case-list" id="case-list" role="group" aria-label="案例列表">${skeletonRows(6, 56)}</div>
      </section>
      <section class="stack" aria-label="运行配置">
        <div class="card case-detail-panel" id="case-detail">
          ${emptyState({ title: "未选择案例", desc: "从左侧列表中选择一个事件案例以查看详情。" })}
        </div>
        <div class="card stack" id="run-config" style="gap:var(--sp-4)"></div>
      </section>
    </div>`;

  let meta;
  let cases;
  try {
    [meta, cases] = await Promise.all([getMeta(), getCases()]);
    if (!root.isConnected) return;
  } catch (err) {
    if (!root.isConnected) return;
    document.getElementById("case-list").innerHTML = failedBanner(err);
    return;
  }

  const state = { selected: cases[0]?.incident_id ?? null, keyword: "", provider: "mock", cacheMode: "off", profile: "legacy_rca", monitorMode: "legacy", snapshot: "[]" };
  const listEl = document.getElementById("case-list");
  const searchEl = document.getElementById("case-search");

  function visibleCases() {
    const kw = state.keyword.trim().toLowerCase();
    if (!kw) return cases;
    return cases.filter((c) =>
      [c.incident_id, c.title, ...c.observed_symptoms].join(" ").toLowerCase().includes(kw)
    );
  }

  function renderCaseList() {
    const list = visibleCases();
    document.getElementById("case-count").textContent = `共 ${cases.length} 个案例 · 显示 ${list.length} 个`;
    if (!list.length) {
      listEl.innerHTML = emptyState({ title: "没有匹配的案例", desc: "换个关键词试试。" });
      return;
    }
    listEl.innerHTML = list
      .map(
        (c) => `
        <button type="button" class="case-item" data-case="${escapeHtml(c.incident_id)}"
                aria-pressed="${c.incident_id === state.selected}">
          <span class="case-item-head">
            <span class="mono">${escapeHtml(c.incident_id)}</span>
            ${badge(c.services.length + " 服务", "neutral")}
          </span>
          <span class="symptoms">${escapeHtml(c.observed_symptoms.join(" · "))}</span>
        </button>`
      )
      .join("");
    listEl.querySelectorAll("[data-case]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.selected = btn.dataset.case;
        renderCaseList();
        renderCaseDetail();
      });
    });
  }

  function renderCaseDetail() {
    const panel = document.getElementById("case-detail");
    const c = cases.find((item) => item.incident_id === state.selected);
    if (!c) {
      panel.innerHTML = emptyState({ title: "未选择案例", desc: "从左侧列表中选择一个事件案例以查看详情。" });
      return;
    }
    panel.innerHTML = `
      <div class="chip-row">
        <span class="tag-id">${escapeHtml(c.incident_id)}</span>
        ${badge(formatDateTime(c.started_at), "neutral")}
      </div>
      <div>
        <div class="card-title">${escapeHtml(c.title)}</div>
        <div class="card-subtitle">开始于 <span class="mono">${escapeHtml(c.started_at)}</span></div>
      </div>
      <div class="field">
        <span class="field-label">观察到的症状</span>
        <ul class="symptom-list">
          ${c.observed_symptoms.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}
        </ul>
      </div>
      <div class="field">
        <span class="field-label">涉及服务</span>
        <div class="service-tags">${c.services.map((s) => badge(s, "neutral")).join("")}</div>
      </div>`;
  }

  function renderRunConfig() {
    const box = document.getElementById("run-config");
    const defaults = meta.provider_defaults;
    const settingsError = meta.provider_settings_error;
    const b = state.profile === "incident_response" ? { ...meta.budget, max_rounds: 6, max_tool_calls: 24, max_llm_calls: 24 } : meta.budget;
    box.innerHTML = `
      <div class="card-title">运行配置</div>
      <div class="field">
        <span class="field-label" id="provider-label">模型提供方</span>
        <div class="segmented" role="group" aria-labelledby="provider-label">
          <button type="button" data-provider="mock" aria-pressed="${state.provider === "mock"}">Mock · 离线确定性</button>
          <button type="button" data-provider="real" aria-pressed="${state.provider === "real"}">Real · 真实模型</button>
        </div>
        <span class="field-hint">Mock 完全离线、可复现；Real 需要 .env 中的端点与密钥配置。</span>
      </div>
      <div class="field">
        <label class="field-label" for="cache-mode">本地解释缓存</label>
        <select class="select" id="cache-mode">
          <option value="off" ${state.cacheMode === "off" ? "selected" : ""}>off · 关闭</option>
          <option value="exact" ${state.cacheMode === "exact" ? "selected" : ""}>exact · 精确复用</option>
          <option value="semantic" ${state.cacheMode === "semantic" ? "selected" : ""}>semantic · 语义复用</option>
        </select>
      </div>
      <div class="field">
        <label class="field-label" for="workflow-profile">工作流</label>
        <select class="select" id="workflow-profile"><option value="legacy_rca" ${state.profile === "legacy_rca" ? "selected" : ""}>legacy_rca · 根因调查</option><option value="incident_response" ${state.profile === "incident_response" ? "selected" : ""}>incident_response · 监控、诊断与建议方案</option></select>
      </div>
      ${state.profile === "incident_response" ? `<div class="field"><label class="field-label" for="monitor-mode">监控模式</label><select class="select" id="monitor-mode">${[["legacy", "legacy · 沿用事件摘要"], ["manual_snapshot", "manual_snapshot · 公开观测快照"], ["offline_replay", "offline_replay · 按时间回放公开观测"]].map(([value, label]) => `<option value="${value}" ${state.monitorMode === value ? "selected" : ""}>${label}</option>`).join("")}</select></div>
      <div class="field" id="snapshot-field" ${state.monitorMode === "legacy" ? "hidden" : ""}><label class="field-label" for="monitor-snapshot">公开 EvidenceRecord 快照（JSON 数组）</label><textarea class="input workflow-snapshot" id="monitor-snapshot" rows="7" aria-describedby="snapshot-hint snapshot-error" spellcheck="false">${escapeHtml(state.snapshot)}</textarea><span class="field-hint" id="snapshot-hint">仅粘贴所选事件的公开观测记录。空数组不会触发告警。</span><p id="snapshot-error" class="workflow-input-error" role="alert" hidden></p></div>
      <p class="field-hint">PLAN_ONLY：仅生成建议方案，不执行修复，也不表示服务已恢复。</p>` : ""}
      <div id="real-options"></div>
      <div class="field">
        <span class="field-label">预算上限</span>
        ${state.profile === "incident_response" ? `<span class="field-hint">事件响应采用较高预算，为数据库调查、监控和建议方案预留调用。</span>` : ""}
        <div class="budget-note">
          ${badge(`${b.max_rounds} 轮`, "neutral")}
          ${badge(`${b.max_tool_calls} 次工具`, "neutral")}
          ${badge(`${b.max_llm_calls} 次模型请求`, "neutral")}
          ${badge(`${b.max_wall_seconds} 秒`, "neutral")}
        </div>
      </div>
      ${settingsError ? `<div class="alert alert-warning"><svg viewBox="0 0 24 24"><path d="M12 4L2.8 19.5h18.4z"/><path d="M12 10v4.2M12 17.3v.1"/></svg><div class="alert-msg">${escapeHtml(settingsError)}</div></div>` : ""}
      <button class="btn btn-primary btn-lg" id="run-btn" type="button" style="width:100%">
        <svg viewBox="0 0 24 24"><path d="M7 4.8v14.4L19 12z"/></svg>
        发起调查
      </button>`;

    box.querySelectorAll("[data-provider]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.provider = btn.dataset.provider;
        renderRunConfig();
      });
    });
    box.querySelector("#cache-mode").addEventListener("change", (e) => {
      state.cacheMode = e.target.value;
    });

    box.querySelector("#workflow-profile").addEventListener("change", (event) => {
      state.profile = event.target.value;
      if (state.profile === "legacy_rca") state.monitorMode = "legacy";
      renderRunConfig();
    });
    box.querySelector("#monitor-mode")?.addEventListener("change", (event) => {
      state.monitorMode = event.target.value;
      box.querySelector("#snapshot-field").hidden = state.monitorMode === "legacy";
    });
    box.querySelector("#monitor-snapshot")?.addEventListener("input", (event) => {
      state.snapshot = event.target.value;
      event.target.removeAttribute("aria-invalid");
      box.querySelector("#snapshot-error").hidden = true;
    });

    if (state.provider === "real") {
      const real = box.querySelector("#real-options");
      if (!defaults) {
        real.innerHTML = `<div class="alert alert-danger"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7.5V13M12 16.4v.1"/></svg><div class="alert-msg">项目本地的提供方请求设置无效，无法使用 Real 提供方。</div></div>`;
      } else {
        real.innerHTML = `
          <div class="stack" style="gap:var(--sp-3)">
            <div class="field">
              <label class="field-label" for="resp-format">结构化响应格式</label>
              <select class="select" id="resp-format">
                <option value="json_schema" ${defaults.response_format_mode === "json_schema" ? "selected" : ""}>json_schema · 严格模式</option>
                <option value="json_object" ${defaults.response_format_mode === "json_object" ? "selected" : ""}>json_object · JSON 模式</option>
              </select>
            </div>
            <div class="field">
              <label class="field-label" for="thinking-mode">思考模式</label>
              <select class="select" id="thinking-mode">
                <option value="" ${defaults.thinking == null ? "selected" : ""}>provider default · 提供方默认</option>
                <option value="disabled" ${defaults.thinking === "disabled" ? "selected" : ""}>disabled · 禁用</option>
                <option value="enabled" ${defaults.thinking === "enabled" ? "selected" : ""}>enabled · 启用</option>
              </select>
            </div>
            <div class="field">
              <label class="field-label" for="req-timeout">请求超时（秒）</label>
              <input class="input" id="req-timeout" type="number" min="1" step="1" value="${defaults.timeout}">
            </div>
          </div>`;
      }
    }

    box.querySelector("#run-btn").addEventListener("click", () => startRun(state, meta));
  }

  async function startRun(st, metaInfo) {
    if (st.running) return;
    if (!st.selected) {
      toast("请先选择一个事件案例", "error");
      return;
    }
    if (st.provider === "real" && !metaInfo.provider_defaults) {
      toast("提供方请求设置无效，无法运行", "error");
      return;
    }
    if (st.provider === "real" && !document.getElementById("req-timeout").reportValidity()) return;
    let snapshot = [];
    if (st.profile === "incident_response" && st.monitorMode !== "legacy") {
      try {
        snapshot = JSON.parse(st.snapshot);
        if (!Array.isArray(snapshot) || snapshot.some(record => !record || typeof record !== "object" || Array.isArray(record))) throw new Error("invalid snapshot");
      } catch {
        const input = document.getElementById("monitor-snapshot");
        const error = document.getElementById("snapshot-error");
        error.textContent = "请输入有效的公开 EvidenceRecord JSON 数组。";
        error.hidden = false;
        input.setAttribute("aria-invalid", "true");
        input.focus();
        return;
      }
    }
    st.running = true;
    const config = root.querySelector("#run-config");
    config.inert = true;
    const btn = document.getElementById("run-btn");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner" aria-hidden="true"></span> 正在调查公开证据…';
    const payload = { incident_id: st.selected, provider: st.provider, cache_mode: st.cacheMode,
      workflow: { profile: st.profile, monitor_mode: st.profile === "legacy_rca" ? "legacy" : st.monitorMode, snapshot } };
    if (st.provider === "real") {
      payload.response_format = document.getElementById("resp-format")?.value || null;
      payload.thinking = document.getElementById("thinking-mode")?.value || null;
      const timeout = parseFloat(document.getElementById("req-timeout")?.value);
      payload.timeout = Number.isFinite(timeout) ? timeout : null;
    }
    try {
      const result = await runInvestigation(payload);
      const status = result.trace?.state?.report?.status;
      const metaStatus = STATUS_META[status];
      toast(
        `调查完成 · ${metaStatus ? metaStatus.label : status}`,
        status === "RESOLVED" ? "success" : status === "INCONCLUSIVE" ? "info" : "error"
      );
      if (root.isConnected) location.hash = `#/run?path=${encodeURIComponent(result.path)}`;
    } catch (err) {
      btn.disabled = false;
      btn.innerHTML = '<svg viewBox="0 0 24 24"><path d="M7 4.8v14.4L19 12z"/></svg> 发起调查';
      toast(err instanceof ApiError ? `${err.code}: ${err.message}` : "调查失败", "error", 6000);
    } finally {
      st.running = false;
      config.inert = false;
    }
  }

  searchEl.addEventListener("input", () => {
    state.keyword = searchEl.value;
    renderCaseList();
  });
  renderCaseList();
  renderCaseDetail();
  renderRunConfig();
}

/* ============================================================
   Run detail
   ============================================================ */

export async function renderRun(root, params) {
  const path = params.get("path");
  if (!path) {
    root.innerHTML = `
      <div class="page-head"><h1 class="page-title">运行详情</h1></div>
      <div class="card">${emptyState({
        title: "当前没有可查看的运行",
        desc: "发起一次新调查，或从痕迹档案库中选择一条已保存的痕迹进行回放。",
        actionHtml: `<div class="chip-row" style="justify-content:center">
          <a class="btn btn-primary" href="#/investigate">新建调查</a>
          <a class="btn" href="#/library">浏览档案库</a>
        </div>`,
      })}</div>`;
    return;
  }

  root.innerHTML = loadingBlock("正在加载运行痕迹…");
  let data;
  try {
    data = await loadReplay(path);
    if (!root.isConnected) return;
  } catch (err) {
    if (!root.isConnected) return;
    root.innerHTML = `<div class="card">${emptyState({
      title: "无法加载该痕迹",
      desc: err instanceof ApiError ? err.message : "请求失败，请重试。",
      actionHtml: '<a class="btn" href="#/library">返回档案库</a>',
    })}</div>`;
    return;
  }
  mountReplay(root, data,params.get('demo') === '1');
}

function mountReplay(root, data,demoMode = false) {
  const events = data.trace.state?.events || [];
  const bookmarks = replayBookmarks(data.trace);
  root.innerHTML = `<section class="card replay-console" aria-label="Investigation Replay">
    ${metadataHtml(data)}
    <div class="replay-controls">
      <button class="btn" data-step="first">首步</button><button class="btn" data-step="prev">上一步</button>
      <button class="btn btn-primary" id="replay-play">播放</button>
      <button class="btn" data-step="next">下一步</button><button class="btn" data-step="last">末步</button>
      <label>速度 <select class="select" id="replay-speed"><option value="1">1×</option><option value="2">2×</option><option value="4">4×</option></select></label>
      <output id="replay-position" aria-live="polite"></output>
    </div>
    <div class="replay-seek"><label for="replay-seek">Seek · 保存事件位置</label><input id="replay-seek" type="range" min="0" max="${events.length}" value="0"><label for="replay-jump">Jump</label><input class="input" id="replay-jump" type="number" min="0" max="${events.length}" value="0"><button class="btn" id="replay-jump-go">跳转</button></div>
    <details id="replay-chapters"><summary>演示章节 · 基于事件语义查找</summary><p class="text-muted">章节名称用于导航；只有跳转后才展示对应历史状态。</p><div class="replay-bookmarks">${bookmarks.map(b=>b.position == null ? `<button class="btn btn-sm" disabled title="Trace 未记录对应事件">${escapeHtml(b.label)} · 未记录</button>` : jumpButton(b.position,b.label,`data-bookmark="${b.id}"`)).join('')}</div></details>
    <details open><summary>Workflow · 共享状态编排与数据流</summary><div id="replay-workflow" aria-label="Workflow Overview"></div></details>
    <details><summary>Communication Timeline · 有序事件导航</summary><label for="replay-category">事件类别</label><select class="select" id="replay-category"><option value="all">全部</option>${['dispatch','task','evidence','findings','hypothesis','review','reliability','finalization','termination','other'].map(c=>`<option value="${c}">${c}</option>`).join('')}</select><div id="replay-events" class="replay-event-list"></div></details>
    <div id="replay-selection" aria-label="当前事件详情"></div>
    <div class="replay-analysis-grid"><details id="replay-hypotheses"><summary>Hypothesis Evolution · 已提交状态变化</summary><div id="replay-history"></div></details>
    <details id="replay-review-panel"><summary>Verifier Review / FinalizeGate</summary><div id="replay-reviews"></div></details></div>
    <details><summary>Provider Timeout / Recovery · 可靠性事件</summary><div id="replay-reliability"></div></details>
  </section><div id="replay-detail"></div>`;
  let position = 0, timer = null, activeTab = 'timeline', selectedRole = '', category = 'all';
  const play = root.querySelector('#replay-play');
  const pause = () => { clearTimeout(timer); timer = null; play.textContent = '播放'; play.setAttribute('aria-pressed', 'false'); };
  const resetInspector = () => {
    if (!document.getElementById('drawer').hidden) closeDrawer();
    document.getElementById('drawer-body').replaceChildren();
  };
  const seek = count => {
    pause(); resetInspector();
    position = Math.max(0,Math.min(events.length,Math.trunc(Number(count)) || 0));
    draw();
  };
  function draw() {
    const state = replayPrefix(data.trace, position);
    state.provenance = evidenceContext(state);
    const detail = root.querySelector('#replay-detail');
    activeTab = detail.querySelector('[aria-selected="true"]')?.dataset.tab || activeTab;
    drawRun(detail, { ...data, recorded: true, activeTab, trace: { ...data.trace, state }, report_md: state.report ? data.report_md : '' });
    root.querySelector('#replay-position').textContent = `${position} / ${events.length} 已保存事件`;
    root.querySelector('#replay-seek').value = position;
    root.querySelector('#replay-jump').value = position;
    root.querySelectorAll('[data-step]').forEach(b => { b.disabled = ['first','prev'].includes(b.dataset.step) ? position === 0 : position === events.length; });
    play.disabled = !events.length || position === events.length;
    root.querySelector('#replay-workflow').innerHTML = workflowHtml(state,selectedRole);
    root.querySelector('#replay-events').innerHTML = events.map((e,i)=>({e,i})).filter(({e})=>category === 'all' || eventCategory(e) === category).map(({e,i})=>jumpButton(i+1,`${i+1} · ${i < position ? `${e.role || 'runtime'} · ${e.event_type}` : '未播放事件'}`,`aria-current="${i+1 === position ? 'step' : 'false'}"`)).join('');
    root.querySelector('#replay-history').innerHTML = historyHtml(state);
    root.querySelector('#replay-reviews').innerHTML = reviewTimelineHtml(state);
    root.querySelector('#replay-reliability').innerHTML = reliabilityHtml(state);
    const e=state.events.at(-1), box=root.querySelector('#replay-selection');
    const ids=e ? [...new Set([...(e.evidence_ids || []),...(e.details?.result?.records || []).map(r=>r.evidence_id),...(e.details?.review?.cited_evidence_ids || [])])] : [];
    box.innerHTML = e ? `<h3>${escapeHtml(e.event_id)} · ${escapeHtml(e.role || 'runtime')} · ${escapeHtml(e.event_type)}</h3><p class="text-muted">执行事件时间：${escapeHtml(e.timestamp)} · ${escapeHtml(e.task_id || 'task not recorded')}</p>${e.details?.decision?.reason ? `<p>${escapeHtml(e.details.decision.reason)}</p>` : ''}${e.details?.decision?.hypothesis_updates?.length ? '<p class="text-muted">DECISION 包含提议；假设面板仅在 MERGE / HYPOTHESIS_RECONCILED 提交后更新。</p>' : ''}<details><summary>原始结构化事件详情</summary>${timelineBody(e)}</details><div class="cite-wrap">${evidenceChips(ids,state.evidence_index,{emptyText:'此事件没有公开证据引用'})}</div>` : `<h3>调查开始前</h3><p>${escapeHtml(state.public_summary.title || '')}</p><p>${escapeHtml((state.public_summary.observed_symptoms || []).join(' · '))}</p><p class="text-muted">仅已知公开事故摘要；尚未观察工具证据或形成假设。</p>`;
    root.querySelectorAll('[data-seek]').forEach(button=>button.onclick=()=>seek(button.dataset.seek));
    root.querySelectorAll('#replay-workflow [data-role]').forEach(button=>button.onclick=()=>{ selectedRole=selectedRole === button.dataset.role ? '' : button.dataset.role; draw(); });
    bindEvidenceChips(root.querySelector('.replay-console'),state.evidence_index,state.provenance);
  }
  function tick() {
    if (!root.isConnected || position >= events.length) { pause(); return; }
    resetInspector(); position++; draw();
    if (position >= events.length) { pause(); return; }
    timer = setTimeout(tick, 1000 / Number(root.querySelector('#replay-speed').value));
  }
  root.querySelectorAll('[data-step]').forEach(b => b.addEventListener('click', () => {
    seek(({first:0, prev:position-1, next:position+1, last:events.length})[b.dataset.step]);
  }));
  root.querySelector('#replay-seek').addEventListener('input',e=>seek(e.target.value));
  root.querySelector('#replay-jump-go').addEventListener('click',()=>seek(root.querySelector('#replay-jump').value));
  root.querySelector('#replay-jump').addEventListener('keydown',e=>{if(e.key === 'Enter') seek(e.target.value);});
  root.querySelector('#replay-category').addEventListener('change',e=>{category=e.target.value;draw();});
  root.querySelector('#replay-demo').addEventListener('change',e=>{
    root.classList.toggle('replay-demo',e.target.checked);
    ['replay-chapters','replay-hypotheses','replay-review-panel'].forEach(id=>root.querySelector(`#${id}`).open=e.target.checked);
  });
  play.addEventListener('click', () => { if (timer) pause(); else { play.textContent='暂停'; play.setAttribute('aria-pressed','true'); timer=setTimeout(tick,1000 / Number(root.querySelector('#replay-speed').value)); } });
  root.querySelector('#replay-speed').addEventListener('change', () => { if (timer) { clearTimeout(timer); timer=setTimeout(tick,1000 / Number(root.querySelector('#replay-speed').value)); } });
  window.addEventListener('hashchange', pause, {once:true});
  draw();
  if(demoMode) { const toggle=root.querySelector('#replay-demo'); toggle.checked=true; toggle.dispatchEvent(new Event('change')); }
}

function drawRun(root, data) {
  const { trace, report_md: reportMd, recorded } = data;
  const state = trace.state;
  const report = state.report || { status: "not recorded" };
  const status = STATUS_META[report.status] || { tone: "neutral", label: report.status };
  const evidenceIndex = state.evidence_index || {};
  const cacheHits = state.events.filter((e) => e.event_type === "CACHE_HIT").length;
  const b = state.budgets;

  root.innerHTML = `
    <div class="run-head">
      <div>
        <div class="run-head-id">
          <h1 class="mono">${escapeHtml(state.incident_id)}</h1>
          ${badge(status.label, status.tone, true)}
          ${badge(state.workflow_status || "not recorded")}
          ${trace.provider === "mock" ? badge("MOCK", "accent") : trace.provider === "real" ? badge("REAL", "info") : badge("PROVIDER UNKNOWN", "warning")}
          ${badge("Recorded Replay", "neutral")}
        </div>
        <div class="run-head-meta">
          <span>运行 <span class="mono">${escapeHtml(state.run_id)}</span></span>
          <span>模型 <span class="mono">${escapeHtml(trace.model_id || "unknown")}</span></span>
          <span>变体 <span class="mono">${escapeHtml(trace.variant || "not recorded")}</span></span>
          <span>缓存 <span class="mono">${escapeHtml(trace.cache_mode || "not recorded")}</span></span>
          <span>录制总耗时 <span class="mono">${formatDuration(trace.elapsed_ms)}</span></span>
          <span>来源指纹 <span class="mono">${escapeHtml(trace.source_hash || trace.dataset_hash || "not recorded")}</span></span>
        </div>
      </div>
      <div class="run-head-actions">
        ${state.report ? `
        <a class="btn btn-sm" href="/api/download?path=${encodeURIComponent(data.path)}&kind=trace" download>
          <svg viewBox="0 0 24 24"><path d="M12 4v11M7.5 11.5L12 16l4.5-4.5"/><path d="M4.5 19.5h15"/></svg>
          trace.json
        </a>
        <a class="btn btn-sm" href="/api/download?path=${encodeURIComponent(data.path)}&kind=report" download>
          <svg viewBox="0 0 24 24"><path d="M12 4v11M7.5 11.5L12 16l4.5-4.5"/><path d="M4.5 19.5h15"/></svg>
          report.md
        </a>` : '<span class="text-muted">完整 Trace / Report 下载在 REPORT 事件后解锁</span>'}
      </div>
    </div>

    ${trace.provider === "mock" ? `<div class="alert alert-info" style="margin-bottom:var(--sp-5)"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.6v.1"/></svg><div class="alert-msg"><strong>MOCK 离线确定性策略</strong> —— 以下结果用于演示流水线正确性，不代表真实模型的准确性。</div></div>` : ""}

    <div class="kpi-grid" style="margin-bottom:var(--sp-6)">
      ${kpiBar("调查轮次", state.round_index, b.max_rounds)}
      ${kpiBar("工具调用", state.tool_calls_used, b.max_tool_calls)}
      ${kpiBar("模型请求", state.llm_calls_used, b.max_llm_calls)}
      ${kpi("缓存命中", cacheHits, trace.cache_mode === "off" ? "缓存已关闭" : `缓存模式 ${trace.cache_mode}`)}
      ${kpi("证据记录", Object.keys(evidenceIndex).length, "本次运行观察")}
    </div>

    <div class="card card-flush" style="margin-bottom:var(--sp-5)">
      <div class="tabs" role="tablist" aria-label="运行详情视图" id="run-tabs">
        <button class="tab" role="tab" data-tab="timeline" aria-selected="true">调查时间线 <span class="count">${state.events.filter((e) => e.event_type !== "LLM_CALL").length}</span></button>
        <button class="tab" role="tab" data-tab="hypotheses" aria-selected="false">假设看板 <span class="count">${state.hypotheses.length}</span></button>
        <button class="tab" role="tab" data-tab="evidence" aria-selected="false">证据登记 <span class="count">${Object.keys(evidenceIndex).length}</span></button>
        <button class="tab" role="tab" data-tab="findings" aria-selected="false">调查发现 <span class="count">${state.findings.length}</span></button>
        <button class="tab" role="tab" data-tab="report" aria-selected="false">根因报告</button>
      </div>
      <div class="card-body" id="run-tab-panel" role="tabpanel" tabindex="0"></div>
    </div>`;

  const tabs = root.querySelectorAll("[data-tab]");
  const panel = root.querySelector("#run-tab-panel");
  const renderers = {
    timeline: () => renderTimeline(panel, state),
    hypotheses: () => renderHypotheses(panel, state, evidenceIndex),
    evidence: () => renderEvidence(panel, state),
    findings: () => renderFindings(panel, state, evidenceIndex),
    report: () => state.report ? renderReport(panel, state, reportMd) : panel.innerHTML = emptyState({ title: "Report not recorded at this step" }),
  };

  function activate(name) {
    tabs.forEach((t) => {
      const selected = t.dataset.tab === name;
      t.id = `tab-${t.dataset.tab}`;
      t.setAttribute("aria-controls", "run-tab-panel");
      t.setAttribute("aria-selected", String(selected));
      t.tabIndex = selected ? 0 : -1;
    });
    data.activeTab = name;
    panel.setAttribute("aria-labelledby", `tab-${name}`);
    renderers[name]();
  }

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => activate(tab.dataset.tab));
    tab.addEventListener("keydown", (e) => {
      const list = [...tabs];
      const idx = list.indexOf(tab);
      let next;
      if (e.key === "ArrowRight") next = list[(idx + 1) % list.length];
      if (e.key === "ArrowLeft") next = list[(idx - 1 + list.length) % list.length];
      if (e.key === "Home") next = list[0];
      if (e.key === "End") next = list.at(-1);
      if (next) {
        e.preventDefault();
        activate(next.dataset.tab);
        next.focus();
      }
    });
  });
  activate(data.activeTab || "timeline");
}

function kpiBar(label, used = 0, max = "not recorded") {
  const pct = Number.isFinite(max) && max > 0 ? Math.min(100, Math.round((used / max) * 100)) : 0;
  return `
    <div class="kpi">
      <div class="kpi-label">${escapeHtml(label)}</div>
      <div class="kpi-value">${used}<small> / ${max}</small></div>
      <div class="kpi-bar"><span style="width:${pct}%"></span></div>
    </div>`;
}

/* ---------------- Timeline ---------------- */

function renderTimeline(panel, state) {
  const roles = [...new Set(state.events.map((e) => e.role).filter(Boolean))].sort();
  const tlState = { role: "all", showLlm: false };

  function draw() {
    const events = state.events.filter((e) => {
      if (e.event_type === "LLM_CALL" && !tlState.showLlm) return false;
      if (tlState.role !== "all" && e.role !== tlState.role) return false;
      return true;
    });
    panel.innerHTML = `
      <div class="timeline-toolbar">
        <div class="chip-row" role="group" aria-label="按角色筛选">
          <button class="chip" data-role="all" aria-pressed="${tlState.role === "all"}">全部</button>
          ${roles
            .map(
              (r) => `<button class="chip" data-role="${escapeHtml(r)}" aria-pressed="${tlState.role === r}">${escapeHtml(
                ROLE_LABEL[r] || r
              )}</button>`
            )
            .join("")}
        </div>
        <label class="chip" style="cursor:pointer">
          <input type="checkbox" id="show-llm" ${tlState.showLlm ? "checked" : ""} style="accent-color:var(--accent)">
          显示模型请求
        </label>
      </div>
      ${
        events.length
          ? `<div class="timeline">${events.map((e) => timelineEvent(e)).join("")}</div>`
          : emptyState({ title: "没有匹配的事件", desc: "调整筛选条件后重试。" })
      }`;

    panel.querySelectorAll("[data-role]").forEach((chip) => {
      chip.addEventListener("click", () => {
        tlState.role = chip.dataset.role;
        draw();
      });
    });
    panel.querySelector("#show-llm").addEventListener("change", (e) => {
      tlState.showLlm = e.target.checked;
      draw();
    });
    panel.querySelectorAll(".tl-event").forEach((card) => {
      card.querySelector(".tl-head").addEventListener("click", () => {
        const open = card.dataset.open === "true";
        card.dataset.open = String(!open);
        const body = card.querySelector(".tl-body");
        if (body) body.hidden = open;
        card.querySelector(".tl-head").setAttribute("aria-expanded", String(!open));
      });
    });
  }
  draw();
}

function timelineEvent(event) {
  const meta = EVENT_KIND[event.event_type] || { kind: "other", label: event.event_type, tone: "neutral" };
  const roleLabel = event.role ? ROLE_LABEL[event.role] || event.role : "运行时";
  const expanded = ["DECISION", "REVIEW"].includes(event.event_type);
  let label = meta.label;
  if (event.event_type === "TOOL_CALL") {
    const result = event.details?.result || {};
    label += ` · ${event.details?.tool_name || "tool"} · ${result.record_count ?? 0} 条记录`;
  }
  return `
    <article class="tl-event" data-kind="${meta.kind}" data-open="${expanded}">
      <button type="button" class="tl-head" aria-expanded="${expanded}">
        ${badge(roleLabel, meta.tone === "neutral" ? "neutral" : meta.tone)}
        <span class="tl-label">${escapeHtml(label)}</span>
        <span class="tl-time">${formatTime(event.timestamp)}${
          event.elapsed_ms != null ? ` · ${formatDuration(event.elapsed_ms)}` : ""
        }</span>
        <svg class="tl-chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>
      </button>
      <div class="tl-body" ${expanded ? "" : "hidden"}>${timelineBody(event)}</div>
    </article>`;
}

function timelineBody(event) {
  const d = event.details || {};
  const parts = [];
  if (event.message) parts.push(`<p class="tl-msg">${escapeHtml(event.message)}</p>`);

  if (d.decision) {
    const dec = d.decision;
    parts.push(`<div class="chip-row">${badge(`动作 · ${dec.action}`, dec.action === "INVESTIGATE" ? "info" : dec.action === "FINALIZE" ? "success" : "warning")}</div>`);
    if (dec.assignments?.length) {
      parts.push(`<div class="assign-list">${dec.assignments
        .map(
          (t) => `<div class="assign-item">
            <div class="chip-row" style="margin-bottom:6px">${badge(t.role, "neutral")} <span class="tag-id">${escapeHtml(t.task_id || "")}</span></div>
            <div class="q">${escapeHtml(t.question)}</div>
            <div class="disc">判别标准：${escapeHtml(t.expected_discriminator)}</div>
          </div>`
        )
        .join("")}</div>`);
    }
    if (dec.stop_reason) parts.push(`<p>停止原因：${escapeHtml(dec.stop_reason)}</p>`);
  } else if (d.review) {
    const rev = d.review;
    const tone = rev.verdict === "sufficient" ? "success" : rev.verdict === "conflicted" ? "danger" : "warning";
    parts.push(`<div class="chip-row">${badge(`裁定 · ${rev.verdict}`, tone)} <span class="tag-id">${escapeHtml(rev.target_hypothesis_id)}</span></div>`);
    parts.push(`<p>${escapeHtml(rev.rationale)}</p>`);
    if (rev.contradictions?.length) {
      parts.push(`<div class="alert alert-warning"><svg viewBox="0 0 24 24"><path d="M12 4L2.8 19.5h18.4z"/><path d="M12 10v4.2M12 17.3v.1"/></svg><div class="alert-msg">${rev.contradictions
        .map(escapeHtml)
        .join("<br>")}</div></div>`);
    }
    if (rev.requested_checks?.length) {
      parts.push(`<div class="assign-list">${rev.requested_checks
        .map((t) => `<div class="assign-item"><div class="chip-row" style="margin-bottom:6px">${badge(t.role, "neutral")}</div><div class="q">${escapeHtml(t.question)}</div></div>`)
        .join("")}</div>`);
    }
  } else if (event.event_type === "TOOL_CALL") {
    const result = d.result || {};
    parts.push(
      `<div class="chip-row">${result.ok ? badge("成功", "success") : badge(`失败 · ${result.error_code || "error"}`, "danger")}${
        event.evidence_ids?.length ? badge(`${event.evidence_ids.length} 条证据`, "info") : ""
      }</div>`
    );
    if (d.args || d.arguments) parts.push(`<pre class="json-block">${escapeHtml(JSON.stringify(d.args || d.arguments, null, 2))}</pre>`);
    parts.push(`<pre class="json-block">${escapeHtml(JSON.stringify({ ok: result.ok, record_count: result.record_count, elapsed_ms: result.elapsed_ms, error_code: result.error_code ?? null }, null, 2))}</pre>`);
  } else if (Object.keys(d).length) {
    parts.push(`<pre class="json-block">${escapeHtml(JSON.stringify(d, null, 2))}</pre>`);
  }
  if (event.evidence_ids?.length && event.event_type !== "TOOL_CALL") {
    parts.push(`<div class="cite-wrap">${event.evidence_ids.map((id) => `<span class="tag-id">${escapeHtml(id)}</span>`).join("")}</div>`);
  }
  return parts.join("") || '<p class="text-muted">无附加详情</p>';
}

/* ---------------- Hypotheses ---------------- */

function renderHypotheses(panel, state, evidenceIndex) {
  if (!state.hypotheses.length) {
    panel.innerHTML = emptyState({ title: "本次运行未产生假设", desc: "not recorded in this event prefix" });
    return;
  }
  const rootCauseId = state.report?.root_cause?.hypothesis_id;
  panel.innerHTML = `
    <div class="hypo-grid">
      ${state.hypotheses
        .map((h) => {
          const effective = rootCauseId === h.hypothesis_id ? "SUPPORTED" : h.status;
          const meta = HYPO_STATUS_META[effective] || HYPO_STATUS_META.OPEN;
          return `
          <article class="hypo-card" data-status="${escapeHtml(effective)}">
            <div class="hypo-top">
              <span class="hypo-service">${escapeHtml(h.culprit_service)}</span>
              ${badge(meta.label, meta.tone, true)}
            </div>
            <p class="hypo-mode">${escapeHtml(h.failure_mode)}</p>
            <div class="hypo-cites">
              <div class="chip-group"><span class="cite-label">支持</span>${evidenceChips(h.support_ids, evidenceIndex)}</div>
              <div class="chip-group"><span class="cite-label">反对</span>${evidenceChips(h.against_ids, evidenceIndex)}</div>
            </div>
            ${h.open_questions?.length ? `<div class="field"><span class="field-label">未决问题</span><ul class="symptom-list">${h.open_questions.map((q) => `<li>${escapeHtml(q)}</li>`).join("")}</ul></div>` : ""}
            <div class="text-muted mono" style="font-size:var(--text-xs)">${escapeHtml(h.hypothesis_id)}</div>
          </article>`;
        })
        .join("")}
    </div>`;
  bindEvidenceChips(panel, evidenceIndex, state.provenance);
}

/* ---------------- Evidence ---------------- */

function renderEvidence(panel, state) {
  const records = Object.values(state.evidence_index || {});
  const evState = { keyword: "", source: "all" };
  const sources = [...new Set(records.map((r) => r.source_type))].sort();

  function draw() {
    const kw = evState.keyword.trim().toLowerCase();
    const list = records.filter((r) => {
      if (evState.source !== "all" && r.source_type !== evState.source) return false;
      if (!kw) return true;
      return [r.evidence_id, r.service, r.excerpt, r.source_path].join(" ").toLowerCase().includes(kw);
    });
    panel.innerHTML = `
      <div class="evidence-toolbar" style="margin:calc(-1 * var(--sp-5));margin-bottom:0;padding:var(--sp-4) var(--sp-5)">
        <div class="input-with-icon" style="flex:1;max-width:340px">
          <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.8-3.8"/></svg>
          <input class="input" id="ev-search" type="search" placeholder="搜索证据 ID、服务或摘录…" value="${escapeHtml(evState.keyword)}" aria-label="搜索证据">
        </div>
        <div class="chip-row" role="group" aria-label="按来源筛选">
          <button class="chip" data-source="all" aria-pressed="${evState.source === "all"}">全部</button>
          ${sources
            .map(
              (s) => `<button class="chip" data-source="${escapeHtml(s)}" aria-pressed="${evState.source === s}">${escapeHtml(
                SOURCE_TYPE_META[s]?.label || s
              )}</button>`
            )
            .join("")}
        </div>
      </div>
      ${
        list.length
          ? `<div class="table-wrap"><table class="data">
        <thead><tr><th scope="col">证据 ID</th><th scope="col">来源</th><th scope="col">服务</th><th scope="col">观察时间</th><th scope="col">摘录</th></tr></thead>
        <tbody>
          ${list
            .map((r) => {
              const src = SOURCE_TYPE_META[r.source_type] || { label: r.source_type, tone: "neutral" };
              return `
            <tr class="is-clickable" data-ev="${escapeHtml(r.evidence_id)}" tabindex="0" role="button" aria-label="查看证据 ${escapeHtml(r.evidence_id)}">
              <td class="mono cell-main">${escapeHtml(r.evidence_id)}</td>
              <td>${badge(src.label, src.tone)}</td>
              <td class="mono">${escapeHtml(r.service)}</td>
              <td class="mono">${formatTime(r.observed_at)}</td>
              <td><div class="evidence-excerpt">${escapeHtml(r.excerpt)}</div></td>
            </tr>`;
            })
            .join("")}
        </tbody></table></div>`
          : emptyState({ title: "没有匹配的证据记录" })
      }`;

    const search = panel.querySelector("#ev-search");
    search.addEventListener("input", () => {
      evState.keyword = search.value;
      const pos = search.selectionStart;
      draw();
      const next = panel.querySelector("#ev-search");
      next.focus();
      next.setSelectionRange(pos, pos);
    });
    panel.querySelectorAll("[data-source]").forEach((chip) => {
      chip.addEventListener("click", () => {
        evState.source = chip.dataset.source;
        draw();
      });
    });
    panel.querySelectorAll("[data-ev]").forEach((row) => {
      const open = () => {
        const record = state.evidence_index[row.dataset.ev];
        import("./components.js").then(({ openDrawer, evidenceDrawerHtml }) => {
          openDrawer(`证据 · ${record.evidence_id}`, evidenceDrawerHtml(record, state.provenance?.[record.evidence_id]));
        });
      };
      row.addEventListener("click", open);
      row.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          open();
        }
      });
    });
  }
  draw();
}

/* ---------------- Findings ---------------- */

function renderFindings(panel, state, evidenceIndex) {
  if (!state.findings.length) {
    panel.innerHTML = emptyState({ title: "尚无调查发现", desc: "专家代理完成调查后，发现会汇总到这里。" });
    return;
  }
  const RELATION_META = {
    supports: { tone: "success", label: "支持" },
    refutes: { tone: "danger", label: "反驳" },
    neutral: { tone: "neutral", label: "中立" },
  };
  panel.innerHTML = `
    <div class="table-wrap"><table class="data">
      <thead><tr><th scope="col">角色</th><th scope="col">结论陈述</th><th scope="col">关系</th><th scope="col">置信</th><th scope="col">引用证据</th></tr></thead>
      <tbody>
        ${state.findings
          .map((f) => {
            const rel = RELATION_META[f.relation] || RELATION_META.neutral;
            return `
          <tr>
            <td>${badge(ROLE_LABEL[f.role] || f.role, "neutral")}<div class="cell-sub mono">${escapeHtml(f.task_id)}</div></td>
            <td style="max-width:380px"><div class="cell-main" style="font-weight:450">${escapeHtml(f.claim)}</div></td>
            <td>${badge(rel.label, rel.tone)}</td>
            <td>${badge(f.confidence_qualifier, f.confidence_qualifier === "supported" ? "success" : "neutral")}</td>
            <td><div class="cite-wrap">${evidenceChips(f.evidence_ids, evidenceIndex)}</div></td>
          </tr>`;
          })
          .join("")}
      </tbody>
    </table></div>`;
  bindEvidenceChips(panel, evidenceIndex, state.provenance);
}

/* ---------------- Report ---------------- */

export function renderReport(panel, state, reportMd) {
  const report = state.report;
  const status = STATUS_META[report.status] || { tone: "neutral", label: report.status };
  const evidenceIndex = state.evidence_index || {};
  const rootCause = report.root_cause;
  const provisional = report.provisional_hypotheses || [];
  const assessmentLabel = { CONFIRMED: "已确认", LIKELY: "较可能（未确认）", INSUFFICIENT: "证据不足" }[report.assessment_level];
  panel.innerHTML = `
    <div class="report-hero" data-status="${escapeHtml(report.status)}">
      <div style="flex:1;min-width:220px">
        <div class="chip-row" style="margin-bottom:8px">${badge(status.label, status.tone, true)}${assessmentLabel ? badge(assessmentLabel, rootCause ? "success" : "neutral") : ""}</div>
        <div class="report-hero-title">${escapeHtml(rootCause ? rootCause.failure_mode : "尚未确认根因")}</div>
        <div class="report-hero-sub">${
          rootCause
            ? `责任服务 <span class="mono">${escapeHtml(rootCause.culprit_service)}</span> · 假设 <span class="mono">${escapeHtml(rootCause.hypothesis_id)}</span>`
            : provisional.length
              ? "尚未确认根因；以下保留已调查的解释、观察和关键缺口。"
              : "目前没有足够证据支持具体的根因解释。"
        }</div>
      </div>
    </div>

    ${provisional.length ? `<div class="report-section"><h3>待确认的解释</h3>
      <p class="text-secondary">按已观察到的机制与来源支持排列，顺序不是正确概率。</p>
      <div class="stack">${provisional.map((h, index) => `<div class="assign-item">
        <div class="q">${index + 1}. ${escapeHtml(h.culprit_service)} · ${escapeHtml(h.failure_mode)}</div>
        <div class="cite-wrap">${evidenceChips(h.support_ids, evidenceIndex)}</div>
        ${h.against_ids?.length ? `<p class="text-secondary">尚待解释的反对证据</p><div class="cite-wrap">${evidenceChips(h.against_ids, evidenceIndex)}</div>` : ""}
      </div>`).join("")}</div></div>` : ""}

    ${report.provisional_observations?.length ? `<div class="report-section"><h3>已有观察（归因尚未确认）</h3>
      <ul class="symptom-list">${report.provisional_observations.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ul></div>` : ""}

    ${report.causal_chain?.length ? `<div class="report-section"><h3>因果链</h3><ol class="causal-chain">${report.causal_chain.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ol></div>` : ""}

    ${report.supporting_evidence_ids?.length ? `<div class="report-section">
      <h3>支持证据</h3>
      <div class="cite-wrap">${evidenceChips(report.supporting_evidence_ids, evidenceIndex)}</div>
    </div>` : ""}

    ${report.rejected_hypotheses?.length ? `<div class="report-section"><h3>已排除假设</h3>
      <div class="stack" style="gap:var(--sp-3)">
        ${report.rejected_hypotheses
          .map(
            (h) => `<div class="assign-item">
              <div class="chip-row" style="margin-bottom:6px">${badge(h.culprit_service, "neutral")}${badge("REJECTED", "danger")}</div>
              <div class="q">${escapeHtml(h.failure_mode)}</div>
              <div class="disc">反对证据：${h.against_ids.map(escapeHtml).join("、") || "—"}</div>
            </div>`
          )
          .join("")}
      </div></div>` : ""}

    ${report.unresolved?.length ? `<div class="report-section"><h3>关键缺口</h3><ul class="symptom-list">${report.unresolved.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ul></div>` : ""}
    ${report.next_steps?.length ? `<div class="report-section"><h3>建议下一步</h3><p class="text-secondary">以下检查尚未执行，可能需要补采新数据。</p>
      <ul class="symptom-list">${report.next_steps.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ul></div>` : ""}
    ${report.optional_questions?.length ? `<div class="report-section"><h3>可选补充（不阻止作答）</h3>
      <ul class="symptom-list">${report.optional_questions.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ul></div>` : ""}
    ${report.assessment_basis?.length ? `<div class="report-section"><h3>判断依据</h3>
      <ul class="symptom-list">${report.assessment_basis.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ul></div>` : ""}

    <div class="report-section">
      <h3>停止原因</h3>
      <p class="text-secondary">${escapeHtml(report.stop_reason)}</p>
    </div>

    ${workflowReportHtml(state, evidenceIndex)}

    <details style="margin-top:var(--sp-4)">
      <summary style="cursor:pointer;color:var(--text-3);font-size:var(--text-sm)">查看 Markdown 原文</summary>
      <pre class="json-block" style="margin-top:var(--sp-3);white-space:pre-wrap">${escapeHtml(reportMd || "")}</pre>
    </details>`;
  bindEvidenceChips(panel, evidenceIndex, state.provenance);
}

/* ============================================================
   Library
   ============================================================ */

export async function renderLibrary(root) {
  root.innerHTML = `
    <div class="page-head">
      <h1 class="page-title">痕迹档案库</h1>
      <p class="page-desc">results/ 目录下所有已保存的调查痕迹。点击任意一条进行离线回放 —— 不再调用编排图、工具或模型。</p>
    </div>
    <div class="library-toolbar">
      <div class="input-with-icon" style="flex:1;max-width:360px">
        <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.8-3.8"/></svg>
        <input class="input" id="lib-search" type="search" placeholder="搜索事件 ID 或运行 ID…" aria-label="搜索痕迹">
      </div>
      <div class="filters">
        <div class="chip-row" role="group" aria-label="按提供方筛选" id="lib-provider-chips">
          <button class="chip" data-provider="all" aria-pressed="true">全部</button>
          <button class="chip" data-provider="mock" aria-pressed="false">Mock</button>
          <button class="chip" data-provider="real" aria-pressed="false">Real</button>
        </div>
        <select class="select" id="lib-status" style="width:auto" aria-label="按状态筛选">
          <option value="all">全部状态</option>
          <option value="RESOLVED">已定位根因</option>
          <option value="INCONCLUSIVE">明确存疑</option>
          <option value="ERROR">运行错误</option>
        </select>
      </div>
    </div>
    <div class="card card-flush" id="lib-table">${skeletonRows(6, 40)}</div>`;

  let traces;
  try {
    traces = await getTraces();
    if (!root.isConnected) return;
  } catch (err) {
    if (!root.isConnected) return;
    document.getElementById("lib-table").innerHTML = failedBanner(err);
    return;
  }

  const libState = { keyword: "", provider: "all", status: "all" };

  function draw() {
    const kw = libState.keyword.trim().toLowerCase();
    const list = traces.filter((t) => {
      if (libState.provider !== "all" && t.provider !== libState.provider) return false;
      if (libState.status !== "all" && t.status !== libState.status) return false;
      if (!kw) return true;
      return [t.incident_id, t.run_id, t.path].join(" ").toLowerCase().includes(kw);
    });
    const box = document.getElementById("lib-table");
    if (!list.length) {
      box.innerHTML = emptyState({
        title: traces.length ? "没有匹配的痕迹" : "档案库为空",
        desc: traces.length ? "调整搜索或筛选条件。" : "通过命令行或新建调查发起一次运行后，痕迹会出现在这里。",
      });
      return;
    }
    box.innerHTML = traceTable(list);
    bindTraceRows(box);
  }

  document.getElementById("lib-search").addEventListener("input", (e) => {
    libState.keyword = e.target.value;
    draw();
  });
  document.querySelectorAll("#lib-provider-chips [data-provider]").forEach((chip) => {
    chip.addEventListener("click", () => {
      libState.provider = chip.dataset.provider;
      document.querySelectorAll("#lib-provider-chips [data-provider]").forEach((c) =>
        c.setAttribute("aria-pressed", String(c === chip))
      );
      draw();
    });
  });
  document.getElementById("lib-status").addEventListener("change", (e) => {
    libState.status = e.target.value;
    draw();
  });
  draw();
}
