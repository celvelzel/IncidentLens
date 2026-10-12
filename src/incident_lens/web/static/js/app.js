/**
 * IncidentLens SPA bootstrap: hash router, shell behavior, theme.
 */

import { getMeta } from "./api.js";
import { closeDrawer, initDrawer } from "./components.js";
import { renderInvestigate, renderLibrary, renderOverview, renderRun } from "./views.js";

const ROUTES = {
  overview: { match: /^\/$/, title: "总览", view: renderOverview },
  investigate: { match: /^\/investigate$/, title: "新建调查", view: renderInvestigate },
  run: { match: /^\/run$/, title: "运行详情", view: renderRun },
  library: { match: /^\/library$/, title: "痕迹档案库", view: renderLibrary },
};

const main = document.getElementById("main");
const topbarTitle = document.getElementById("topbar-title");

function parseHash() {
  const raw = (location.hash || "#/").slice(1);
  const [path, query = ""] = raw.split("?");
  return { path: path || "/", params: new URLSearchParams(query) };
}

let renderToken = 0;

async function route() {
  const { path, params } = parseHash();
  const entry = Object.values(ROUTES).find((r) => r.match.test(path)) || ROUTES.overview;
  const token = ++renderToken;

  document.querySelectorAll("[data-nav]").forEach((link) => {
    const href = link.getAttribute("href").slice(1).split("?")[0];
    const active = href === path || (href === "/run" && path === "/run");
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  topbarTitle.textContent = entry.title;
  if (!document.getElementById("drawer").hidden) closeDrawer();
  closeSidebar();

  const viewRoot = document.createElement("div");
  main.replaceChildren(viewRoot);
  const rendering = entry.view(viewRoot, params);
  main.focus({ preventScroll: true });
  window.scrollTo({ top: 0 });
  await rendering;
  if (token !== renderToken) return;
}

/* ---------------- Sidebar (mobile) ---------------- */

const sidebar = document.getElementById("sidebar");
const scrim = document.getElementById("scrim");
const menuBtn = document.getElementById("menu-btn");
const mobileNav = window.matchMedia("(max-width: 860px)");
const mainArea = document.querySelector(".main-area");

function openSidebar() {
  sidebar.classList.add("is-open");
  scrim.hidden = false;
  menuBtn.setAttribute("aria-expanded", "true");
  sidebar.inert = false;
  mainArea.inert = true;
  document.body.style.overflow = "hidden";
  sidebar.querySelector("a").focus();
}

function closeSidebar() {
  sidebar.classList.remove("is-open");
  scrim.hidden = true;
  menuBtn.setAttribute("aria-expanded", "false");
  sidebar.inert = mobileNav.matches;
  mainArea.inert = false;
  document.body.style.overflow = "";
}

menuBtn.addEventListener("click", () => {
  if (sidebar.classList.contains("is-open")) closeSidebar();
  else openSidebar();
});
scrim.addEventListener("click", () => {
  closeSidebar();
  menuBtn.focus();
});
mobileNav.addEventListener("change", closeSidebar);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && sidebar.classList.contains("is-open")) {
    closeSidebar();
    menuBtn.focus();
  }
  if (event.key === "Tab" && sidebar.classList.contains("is-open")) {
    const items = [...sidebar.querySelectorAll('a[href], button')];
    if (event.shiftKey && document.activeElement === items[0]) {
      event.preventDefault();
      items.at(-1).focus();
    } else if (!event.shiftKey && document.activeElement === items.at(-1)) {
      event.preventDefault();
      items[0].focus();
    }
  }
});

document.querySelector(".skip-link").addEventListener("click", (event) => {
  event.preventDefault();
  main.focus();
  main.scrollIntoView();
});

/* ---------------- Theme ---------------- */

const THEME_KEY = "incident-lens-theme";

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    /* storage unavailable */
  }
}

function initTheme() {
  let saved = null;
  try {
    saved = localStorage.getItem(THEME_KEY);
  } catch {
    /* storage unavailable */
  }
  if (saved === "light" || saved === "dark") {
    applyTheme(saved);
    return;
  }
  applyTheme(window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark");
}

document.getElementById("theme-toggle").addEventListener("click", () => {
  applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
});

/* ---------------- Sidebar health meta ---------------- */

async function refreshMeta() {
  const box = document.getElementById("sidebar-meta");
  const text = document.getElementById("sidebar-meta-text");
  try {
    const meta = await getMeta();
    const b = meta.budget;
    box.classList.remove("is-offline");
    text.textContent = `预算 ${b.max_rounds}轮 · ${b.max_tool_calls}工具 · ${b.max_llm_calls}请求`;
  } catch {
    box.classList.add("is-offline");
    text.textContent = "后端不可用";
  }
}

/* ---------------- Boot ---------------- */

initTheme();
initDrawer();
window.addEventListener("hashchange", route);
route();
refreshMeta();
