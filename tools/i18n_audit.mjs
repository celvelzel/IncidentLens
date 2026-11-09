/**
 * IncidentLens i18n audit (Playwright, ESM).
 *
 * Starts its own server on --port (default 8033), loads every SPA route in
 * English mode (?lang=en + localStorage), and asserts there is ZERO CJK in
 * document.body text and in translatable attributes (aria-label, title,
 * placeholder, alt, aria-description, aria-placeholder).
 *
 * For the run route it also clicks every [data-tab] tab, opens every <details>,
 * steps through several replay positions and opens an evidence drawer, then
 * re-checks. It finally exercises the language toggle both ways.
 *
 * The only intentional CJK in English mode is the language-toggle control
 * (#lang-toggle, data-i18n-skip) whose label is "中文" so users can switch back.
 * That control is excluded from the audit and reported separately.
 *
 * Output: prints actionable leftover occurrences and writes a JSON + text report
 * under results/i18n-audit/.
 */
import { chromium } from "playwright";
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const ROOT = path.resolve(process.cwd());
const PORT = Number(process.env.PORT || 8033);
const HOST = "127.0.0.1";
const BASE = `http://${HOST}:${PORT}`;
const OUT_DIR = process.env.OUT || path.join("results", "i18n-audit");
const TRACE = "results/ui/run-61801977fe924a16a6e024405d40612d/trace.json";

const ROUTES = [
  { name: "overview", hash: "#/" },
  { name: "investigate", hash: "#/investigate", extended: "investigate" },
  { name: "library", hash: "#/library", extended: "library" },
  { name: "system", hash: "#/system" },
  { name: "evaluation", hash: "#/evaluation" },
  {
    name: "run",
    hash: `#/run?path=${TRACE}&step=last&demo=1`,
    interactive: true,
    extended: "run",
  },
];

fs.mkdirSync(OUT_DIR, { recursive: true });

/* ------------------------------------------------------------------ *
 * Server lifecycle
 * ------------------------------------------------------------------ */
let serverProc = null;
let serverLog = "";
let serverAlive = false;

function startServer() {
  serverProc = spawn(
    "./.venv/bin/python",
    ["-m", "incident_lens.web", "--port", String(PORT)],
    { cwd: ROOT, stdio: ["ignore", "pipe", "pipe"], env: { ...process.env } },
  );
  serverProc.stdout.on("data", (d) => (serverLog += d.toString()));
  serverProc.stderr.on("data", (d) => (serverLog += d.toString()));
  serverProc.on("exit", (code, sig) => {
    serverAlive = false;
    if (code !== 0 && code !== null) {
      serverLog += `\n[server exited code=${code} sig=${sig}]\n`;
    }
  });
}

async function waitForServer(timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`${BASE}/api/meta`, { signal: AbortSignal.timeout(2000) });
      if (res.ok) return true;
    } catch {
      /* not ready yet */
    }
    await new Promise((r) => setTimeout(r, 300));
  }
  return false;
}

function stopServer() {
  if (serverProc && serverProc.exitCode === null) {
    try {
      serverProc.kill("SIGTERM");
    } catch {
      /* ignore */
    }
    // Hard kill shortly after if it lingers.
    setTimeout(() => {
      try {
        if (serverProc.exitCode === null) serverProc.kill("SIGKILL");
      } catch {
        /* ignore */
      }
    }, 4000).unref?.();
  }
}

process.on("exit", stopServer);
process.on("SIGINT", () => {
  stopServer();
  process.exit(130);
});
process.on("SIGTERM", () => {
  stopServer();
  process.exit(143);
});

/* ------------------------------------------------------------------ *
 * In-page CJK scan
 * ------------------------------------------------------------------ */
function scanCJK() {
  const CJK = /[\u4e00-\u9fff]/;
  const ATTRS = ["aria-label", "title", "placeholder", "alt", "aria-description", "aria-placeholder"];

  function cssPath(el) {
    if (!el || el.nodeType !== 1) return "body";
    const parts = [];
    let cur = el;
    while (cur && cur.nodeType === 1 && parts.length < 8) {
      if (cur.id) {
        parts.unshift(`#${cur.id}`);
        break;
      }
      let sel = cur.tagName.toLowerCase();
      const cls = cur.getAttribute("class");
      if (cls) sel += "." + cls.trim().split(/\s+/).slice(0, 3).join(".");
      const parent = cur.parentElement;
      if (parent) {
        const sibs = [...parent.children].filter((c) => c.tagName === cur.tagName);
        if (sibs.length > 1) sel += `:nth-of-type(${sibs.indexOf(cur) + 1})`;
      }
      parts.unshift(sel);
      cur = parent;
    }
    return parts.join(" > ");
  }

  function flagsFor(el) {
    const f = { langToggle: false, engineSkip: false, visible: true };
    let cur = el;
    while (cur && cur.nodeType === 1) {
      if (cur.id === "lang-toggle") f.langToggle = true;
      const tag = cur.tagName;
      if (
        ["SCRIPT", "STYLE", "PRE", "CODE", "TEXTAREA"].includes(tag) ||
        cur.hasAttribute("data-i18n-skip")
      ) {
        f.engineSkip = true;
      }
      cur = cur.parentElement;
    }
    // visibility (aligns roughly with innerText: skip display:none / hidden)
    let v = el;
    while (v && v.nodeType === 1) {
      const s = getComputedStyle(v);
      if (s.display === "none" || s.visibility === "hidden") {
        f.visible = false;
        break;
      }
      v = v.parentElement;
    }
    return f;
  }

  const hits = [];

  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const text = node.data;
    if (!text || !CJK.test(text)) continue;
    const el = node.parentElement;
    hits.push({
      kind: "text",
      selector: cssPath(el),
      text: text.replace(/\s+/g, " ").trim().slice(0, 240),
      ...flagsFor(el),
    });
  }

  for (const el of document.querySelectorAll("*")) {
    for (const attr of ATTRS) {
      if (!el.hasAttribute(attr)) continue;
      const val = el.getAttribute(attr);
      if (!val || !CJK.test(val)) continue;
      hits.push({
        kind: `attr:${attr}`,
        selector: cssPath(el),
        text: val.replace(/\s+/g, " ").trim().slice(0, 240),
        ...flagsFor(el),
      });
    }
  }

  return {
    title: document.title,
    lang: document.documentElement.lang,
    bodyText: document.body.innerText.slice(0, 4000),
    hits,
  };
}

function summarize(label, scan) {
  const intentional = scan.hits.filter((h) => h.langToggle);
  const skipRegion = scan.hits.filter((h) => !h.langToggle && h.engineSkip);
  const failures = scan.hits.filter((h) => !h.langToggle && !h.engineSkip && h.visible);
  const hidden = scan.hits.filter((h) => !h.langToggle && !h.engineSkip && !h.visible);
  return { label, title: scan.title, lang: scan.lang, intentional, skipRegion, failures, hidden, total: scan.hits.length };
}

/* ------------------------------------------------------------------ *
 * Page helpers
 * ------------------------------------------------------------------ */
async function openRoute(browser, route) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  await context.addInitScript(() => {
    try {
      localStorage.setItem("incident-lens-lang", "en");
    } catch {
      /* ignore */
    }
  });
  const page = await context.newPage();
  const pageErrors = [];
  page.on("console", (m) => {
    if (m.type() === "error") pageErrors.push(m.text());
  });
  page.on("pageerror", (e) => pageErrors.push("pageerror: " + e.message));

  const url = `${BASE}/?lang=en${route.hash}`;
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page
    .waitForFunction(
      () => {
        const m = document.getElementById("main");
        return window.__ilI18n && window.__ilI18n.getLang() === "en" && m && m.innerText.trim().length > 0;
      },
      { timeout: 20000 },
    )
    .catch(() => {});
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(900);
  return { context, page, pageErrors, url };
}

async function openAllDetails(page) {
  await page.evaluate(() => {
    document.querySelectorAll("details").forEach((d) => {
      d.open = true;
    });
  });
  await page.waitForTimeout(250);
}

async function scanPage(page) {
  return await page.evaluate(scanCJK);
}

/**
 * Extra, deeper interactions per route to shake out gaps in controls that are
 * not exercised by a plain page load. Each state is scanned independently.
 */
async function runExtended(page, kind, addCheck) {
  if (kind === "investigate") {
    for (const p of ["real", "mock"]) {
      await page.locator(`[data-provider="${p}"]`).first().click({ timeout: 3000 }).catch(() => {});
      await page.waitForTimeout(450);
      addCheck(`ext:provider=${p}`, await scanPage(page));
    }
    for (const sel of ["#cache-mode", "#workflow-profile"]) {
      const el = page.locator(sel);
      if (!(await el.count())) continue;
      const vals = await el.locator("option").evaluateAll((os) => os.map((o) => o.value));
      for (const v of vals) {
        await el.selectOption(v).catch(() => {});
        await page.waitForTimeout(350);
        addCheck(`ext:${sel}=${v}`, await scanPage(page));
      }
    }
    const mm = page.locator("#monitor-mode");
    if (await mm.count()) {
      const vals = await mm.locator("option").evaluateAll((os) => os.map((o) => o.value));
      for (const v of vals) {
        await mm.selectOption(v).catch(() => {});
        await page.waitForTimeout(350);
        addCheck(`ext:monitor=${v}`, await scanPage(page));
      }
    }
  } else if (kind === "library") {
    const ls = page.locator("#lib-search");
    if (await ls.count()) {
      await ls.fill("61801977").catch(() => {});
      await page.waitForTimeout(450);
      addCheck("ext:search", await scanPage(page));
      await ls.fill("zzz-no-match").catch(() => {});
      await page.waitForTimeout(450);
      addCheck("ext:search-empty", await scanPage(page));
      await ls.fill("").catch(() => {});
      await page.waitForTimeout(350);
    }
    const provChips = page.locator("[data-provider]");
    const pc = await provChips.count();
    for (let i = 0; i < pc; i++) {
      await provChips.nth(i).click({ timeout: 3000 }).catch(() => {});
      await page.waitForTimeout(350);
      addCheck(`ext:provider#${i}`, await scanPage(page));
    }
    const st = page.locator("#lib-status");
    if (await st.count()) {
      const vals = await st.locator("option").evaluateAll((os) => os.map((o) => o.value));
      for (const v of vals) {
        await st.selectOption(v).catch(() => {});
        await page.waitForTimeout(350);
        addCheck(`ext:status=${v}`, await scanPage(page));
      }
    }
  } else if (kind === "run") {
    // timeline role chips + show-LLM + expand cards
    await page.locator('[data-tab="timeline"]').click({ timeout: 3000 }).catch(() => {});
    await page.waitForTimeout(350);
    const roleChips = page.locator("#run-tab-panel [data-role]");
    const rc = await roleChips.count();
    for (let i = 0; i < rc; i++) {
      await roleChips.nth(i).click({ timeout: 3000 }).catch(() => {});
      await page.waitForTimeout(250);
      addCheck(`ext:timeline.role#${i}`, await scanPage(page));
    }
    const llm = page.locator("#show-llm");
    if (await llm.count()) {
      await llm.check().catch(() => {});
      await page.waitForTimeout(450);
      addCheck("ext:show-llm", await scanPage(page));
    }
    const heads = page.locator(".tl-head");
    const hc = await heads.count();
    for (let i = 0; i < Math.min(hc, 8); i++) {
      await heads.nth(i).click({ timeout: 3000 }).catch(() => {});
      await page.waitForTimeout(150);
    }
    addCheck("ext:timeline.expanded", await scanPage(page));
    // evidence source chips + search
    await page.locator('[data-tab="evidence"]').click({ timeout: 3000 }).catch(() => {});
    await page.waitForTimeout(400);
    const srcChips = page.locator("#run-tab-panel [data-source]");
    const sc = await srcChips.count();
    for (let i = 0; i < sc; i++) {
      await srcChips.nth(i).click({ timeout: 3000 }).catch(() => {});
      await page.waitForTimeout(250);
      addCheck(`ext:evidence.source#${i}`, await scanPage(page));
    }
    const evs = page.locator("#ev-search");
    if (await evs.count()) {
      await evs.fill("x").catch(() => {});
      await page.waitForTimeout(400);
      addCheck("ext:evidence.search", await scanPage(page));
      await evs.fill("").catch(() => {});
      await page.waitForTimeout(250);
    }
    // report + hypotheses details
    for (const tab of ["report", "hypotheses", "findings"]) {
      await page.locator(`[data-tab="${tab}"]`).click({ timeout: 3000 }).catch(() => {});
      await page.waitForTimeout(350);
      await openAllDetails(page);
      addCheck(`ext:tab-details:${tab}`, await scanPage(page));
    }
    // replay category options
    const cat = page.locator("#replay-category");
    if (await cat.count()) {
      const vals = await cat.locator("option").evaluateAll((os) => os.map((o) => o.value));
      for (const v of vals) {
        await cat.selectOption(v).catch(() => {});
        await page.waitForTimeout(300);
        addCheck(`ext:category=${v}`, await scanPage(page));
      }
    }
    // demo toggle off/on
    const demo = page.locator("#replay-demo");
    if (await demo.count()) {
      await demo.uncheck().catch(() => {});
      await page.waitForTimeout(400);
      addCheck("ext:demo=off", await scanPage(page));
      await demo.check().catch(() => {});
      await page.waitForTimeout(400);
      addCheck("ext:demo=on", await scanPage(page));
    }
    // step buttons
    for (const s of ["first", "next", "prev", "last"]) {
      await page.locator(`[data-step="${s}"]`).first().click({ timeout: 3000 }).catch(() => {});
      await page.waitForTimeout(400);
      addCheck(`ext:step=${s}`, await scanPage(page));
    }
    // bookmarks
    const bms = page.locator("[data-bookmark]");
    const bc = await bms.count();
    for (let i = 0; i < Math.min(bc, 6); i++) {
      await bms.nth(i).click({ timeout: 3000 }).catch(() => {});
      await page.waitForTimeout(400);
      addCheck(`ext:bookmark#${i}`, await scanPage(page));
    }
    // workflow role buttons
    const wf = page.locator("#replay-workflow [data-role]");
    const wc = await wf.count();
    for (let i = 0; i < Math.min(wc, 10); i++) {
      await wf.nth(i).click({ timeout: 3000 }).catch(() => {});
      await page.waitForTimeout(300);
      addCheck(`ext:workflow.role#${i}`, await scanPage(page));
    }
  }
}

/* ------------------------------------------------------------------ *
 * Main
 * ------------------------------------------------------------------ */
const report = {
  generatedAt: new Date().toISOString(),
  base: BASE,
  node: process.version,
  routes: [],
  toggle: null,
  pageErrors: {},
  pass: false,
};

function log(...args) {
  console.log(...args);
}

function failDetail(s) {
  for (const h of s.failures) {
    log(`      [${h.kind}] ${h.selector}`);
    log(`         text: ${JSON.stringify(h.text)}`);
  }
  if (s.hidden.length) {
    log(`      (hidden/offscreen CJK, informational: ${s.hidden.length})`);
    for (const h of s.hidden) log(`        hidden [${h.kind}] ${h.selector} :: ${JSON.stringify(h.text)}`);
  }
  if (s.skipRegion.length) {
    log(`      (engine-skip region CJK, informational: ${s.skipRegion.length})`);
    for (const h of s.skipRegion) log(`        skip [${h.kind}] ${h.selector} :: ${JSON.stringify(h.text)}`);
  }
}

await (async () => {
  log(`i18n audit starting; server port ${PORT}, out ${OUT_DIR}`);
  startServer();
  const ready = await waitForServer();
  if (!ready) {
    log("FATAL: server did not become ready. Log:\n" + serverLog);
    report.fatal = "server not ready";
    fs.writeFileSync(path.join(OUT_DIR, "audit-report.json"), JSON.stringify(report, null, 2));
    stopServer();
    process.exit(1);
  }
  log(`server ready at ${BASE}`);

  const browser = await chromium.launch({ headless: true });
  let anyFail = false;

  try {
    for (const route of ROUTES) {
      log(`\n=== route ${route.name} :: ${route.hash} ===`);
      const { context, page, pageErrors, url } = await openRoute(browser, route);
      const checks = [];
      const addCheck = (label, scan) => {
        const s = summarize(label, scan);
        checks.push(s);
        const status = s.failures.length === 0 ? "PASS" : "FAIL";
        log(
          `  [${status}] ${label}: failures=${s.failures.length} intentional(toggle)=${s.intentional.length} pageTitle=${JSON.stringify(s.title)} lang=${s.lang}`,
        );
        if (s.failures.length) failDetail(s);
        if (s.failures.length) anyFail = true;
        return s;
      };

      addCheck("initial", await scanPage(page));

      if (route.extended) {
        await runExtended(page, route.extended, addCheck);
      }

      if (route.interactive) {
        // 1) every [data-tab] tab
        const tabNames = await page.$$eval("[data-tab]", (els) => els.map((e) => e.dataset.tab));
        log(`  tabs found: ${JSON.stringify(tabNames)}`);
        for (const name of tabNames) {
          await page.locator(`[data-tab="${name}"]`).click({ timeout: 5000 }).catch(() => {});
          await page.waitForTimeout(500);
          await openAllDetails(page);
          addCheck(`tab:${name}`, await scanPage(page));
        }

        // 2) open all details on the default tab
        await page.locator('[data-tab="timeline"]').click({ timeout: 5000 }).catch(() => {});
        await page.waitForTimeout(300);
        await openAllDetails(page);
        addCheck("details-open", await scanPage(page));

        // 3) step through replay positions
        const maxPos = Number(
          (await page.locator("#replay-jump").getAttribute("max").catch(() => "0")) || 0,
        );
        log(`  replay max position: ${maxPos}`);
        const positions = [...new Set([0, 1, 2, Math.floor(maxPos / 2), Math.max(0, maxPos - 1), maxPos].filter((p) => p >= 0 && p <= maxPos))];
        for (const p of positions) {
          await page.locator("#replay-jump").fill(String(p)).catch(() => {});
          await page.locator("#replay-jump-go").click({ timeout: 5000 }).catch(() => {});
          await page.waitForTimeout(500);
          await openAllDetails(page);
          addCheck(`replay@${p}`, await scanPage(page));
        }

        // 4) evidence drawer
        await page.locator("#replay-jump").fill(String(maxPos)).catch(() => {});
        await page.locator("#replay-jump-go").click({ timeout: 5000 }).catch(() => {});
        await page.waitForTimeout(500);
        const evTab = page.locator('[data-tab="evidence"]');
        if (await evTab.count()) {
          await evTab.click().catch(() => {});
          await page.waitForTimeout(400);
          const rows = page.locator("[data-ev]");
          const rowCount = await rows.count();
          log(`  evidence rows: ${rowCount}`);
          if (rowCount > 0) {
            await rows.first().click({ timeout: 5000 }).catch(() => {});
            await page.waitForTimeout(600);
            const drawerOpen = await page.evaluate(() => {
              const d = document.getElementById("drawer");
              return d && !d.hidden;
            });
            log(`  drawer open: ${drawerOpen}`);
            await openAllDetails(page);
            const drawerScan = await scanPage(page);
            // Focus detail on drawer hits while still reporting full page.
            addCheck("evidence-drawer", drawerScan);
            const drawerTextCJK = await page.evaluate(() => {
              const body = document.getElementById("drawer-body");
              const CJK = /[\u4e00-\u9fff]/;
              return body && CJK.test(body.innerText) ? body.innerText.match(/[\u4e00-\u9fff]+/g) : [];
            });
            log(`  drawer-body CJK fragments: ${JSON.stringify(drawerTextCJK)}`);
            if (drawerTextCJK && drawerTextCJK.length) anyFail = true;
            await page.locator("#drawer-close").click({ timeout: 3000 }).catch(() => {});
            await page.waitForTimeout(300);
          }
        }

        // 5) various replay category + details states
        await openAllDetails(page);
        addCheck("post-interactions", await scanPage(page));
      }

      report.routes.push({ route: route.name, url, pageErrors, checks });
      report.pageErrors[route.name] = pageErrors;
      if (pageErrors.length) log(`  page errors: ${JSON.stringify(pageErrors)}`);
      await context.close();
    }

    /* ---------------- Toggle test ---------------- */
    log(`\n=== toggle test (overview) ===`);
    {
      const route = ROUTES[0];
      const { context, page, pageErrors } = await openRoute(browser, route);
      const enScan = await scanPage(page);
      const enFail = summarize("toggle:en", enScan).failures.length;
      log(`  initial EN failures=${enFail}`);
      // click toggle -> expect Chinese restored
      await page.locator("#lang-toggle").click({ timeout: 5000 });
      await page.waitForTimeout(700);
      const zhScan = await page.evaluate(() => {
        const CJK = /[\u4e00-\u9fff]/;
        return {
          lang: document.documentElement.lang,
          label: document.getElementById("lang-toggle-label")?.textContent,
          cjkCount: (document.body.innerText.match(/[\u4e00-\u9fff]/g) || []).length,
          sampleCjk: (document.body.innerText.match(/[\u4e00-\u9fff]+/g) || []).slice(0, 8),
        };
      });
      log(`  after toggle -> zh: lang=${zhScan.lang} label=${JSON.stringify(zhScan.label)} cjkCount=${zhScan.cjkCount} sample=${JSON.stringify(zhScan.sampleCjk)}`);
      // click back -> expect English restored
      await page.locator("#lang-toggle").click({ timeout: 5000 });
      await page.waitForTimeout(700);
      const backScan = await scanPage(page);
      const backFail = summarize("toggle:back-en", backScan).failures.length;
      const backState = await page.evaluate(() => ({
        lang: document.documentElement.lang,
        label: document.getElementById("lang-toggle-label")?.textContent,
      }));
      log(`  after toggle back -> en: lang=${backState.lang} label=${JSON.stringify(backState.label)} failures=${backFail}`);

      const togglePass =
        enFail === 0 &&
        zhScan.lang === "zh-CN" &&
        zhScan.cjkCount > 0 &&
        backState.lang === "en" &&
        backFail === 0;
      report.toggle = {
        initialEnFailures: enFail,
        zh: zhScan,
        backEn: { ...backState, failures: backFail },
        pass: togglePass,
      };
      log(`  toggle PASS=${togglePass}`);
      if (!togglePass) anyFail = true;
      report.pageErrors["toggle"] = pageErrors;
      await context.close();
    }
  } finally {
    await browser.close();
    stopServer();
  }

  report.pass = !anyFail;
  report.serverLog = serverLog.slice(-4000);
  fs.writeFileSync(path.join(OUT_DIR, "audit-report.json"), JSON.stringify(report, null, 2));

  // Build a readable text report.
  const lines = [];
  lines.push(`# IncidentLens i18n audit — ${report.generatedAt}`);
  lines.push(`Base: ${BASE}  Node: ${process.version}`);
  lines.push("");
  for (const r of report.routes) {
    lines.push(`## Route ${r.route}`);
    lines.push(`URL: ${r.url}`);
    for (const c of r.checks) {
      lines.push(`- [${c.failures.length === 0 ? "PASS" : "FAIL"}] ${c.label} — failures=${c.failures.length}, intentional-toggle=${c.intentional.length}, hidden=${c.hidden.length}, skipRegion=${c.skipRegion.length}`);
      for (const h of c.failures) lines.push(`    - [${h.kind}] ${h.selector} :: ${JSON.stringify(h.text)}`);
    }
    if (r.pageErrors.length) lines.push(`Page errors: ${JSON.stringify(r.pageErrors)}`);
    lines.push("");
  }
  lines.push(`## Toggle`);
  lines.push(JSON.stringify(report.toggle, null, 2));
  lines.push("");
  lines.push(`## RESULT: ${report.pass ? "PASS (0 CJK in EN on all routes + interactions)" : "FAIL"}`);
  const txt = lines.join("\n");
  fs.writeFileSync(path.join(OUT_DIR, "audit.log"), txt);
  log("\n" + txt);
  log(`\nwrote ${path.join(OUT_DIR, "audit-report.json")} and ${path.join(OUT_DIR, "audit.log")}`);

  if (!report.pass) {
    log("\nAUDIT RESULT: FAIL");
    process.exit(2);
  }
  log("\nAUDIT RESULT: PASS");
  process.exit(0);
})();
