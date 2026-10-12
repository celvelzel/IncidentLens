/**
 * IncidentLens API client and shared utilities.
 */

export async function api(path, options = {}) {
  const init = { headers: {}, ...options };
  if (init.body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(init.body);
  }
  let res;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError("network", "无法连接后端服务，请确认服务正在运行");
  }
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON response */
  }
  if (!res.ok) {
    const detail = data?.error || {};
    throw new ApiError(detail.code || `http_${res.status}`, detail.message || `请求失败 (${res.status})`);
  }
  return data;
}

export class ApiError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

export const getMeta = () => api("/api/meta");
export const getCases = () => api("/api/cases");
export const getTraces = () => api("/api/traces");
export const runInvestigation = (payload) => api("/api/run", { method: "POST", body: payload });
export const loadReplay = (path) => api("/api/replay", { method: "POST", body: { path } });

/* ---------------- formatting helpers ---------------- */

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function formatTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString("zh-CN", { hour12: false });
}

export function formatDateTime(epochOrIso) {
  const d = typeof epochOrIso === "number" ? new Date(epochOrIso * 1000) : new Date(epochOrIso);
  if (Number.isNaN(d.getTime())) return String(epochOrIso ?? "—");
  return d.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function formatDuration(ms) {
  if (ms == null) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`;
  return `${Math.floor(ms / 60_000)} m ${Math.round((ms % 60_000) / 1000)} s`;
}

export const STATUS_META = {
  RESOLVED: { tone: "success", label: "已定位根因" },
  INCONCLUSIVE: { tone: "warning", label: "证据不足 · 存疑" },
  ERROR: { tone: "danger", label: "运行错误" },
};

export const HYPO_STATUS_META = {
  SUPPORTED: { tone: "success", label: "SUPPORTED" },
  OPEN: { tone: "info", label: "OPEN" },
  REJECTED: { tone: "danger", label: "REJECTED" },
};

export const EVENT_KIND = {
  DECISION: { kind: "decision", label: "协调决策", tone: "accent" },
  REVIEW: { kind: "review", label: "验证审查", tone: "warning" },
  TOOL_CALL: { kind: "tool", label: "工具调用", tone: "info" },
  MERGE: { kind: "merge", label: "结果合并", tone: "success" },
  REPORT: { kind: "report", label: "报告生成", tone: "success" },
  LLM_CALL: { kind: "llm", label: "模型请求", tone: "neutral" },
  MODEL_FAILURE: { kind: "llm", label: "模型失败", tone: "danger" },
  CACHE_HIT: { kind: "cache", label: "缓存命中", tone: "neutral" },
  CACHE_STORE: { kind: "cache", label: "缓存写入", tone: "neutral" },
};

export const ROLE_LABEL = {
  coordinator: "协调者",
  logs: "日志调查员",
  metrics: "指标调查员",
  changes: "变更调查员",
  verifier: "验证者",
  reporter: "报告者",
  single: "单体代理",
  "": "运行时",
};

export const SOURCE_TYPE_META = {
  logs: { label: "日志", tone: "info" },
  metrics: { label: "指标", tone: "accent" },
  changes: { label: "变更", tone: "warning" },
  configs: { label: "配置", tone: "warning" },
  topology: { label: "拓扑", tone: "neutral" },
};
