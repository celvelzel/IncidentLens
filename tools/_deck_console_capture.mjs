import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

// Re-capture presentation/assets/demo_console.png (deck slide 9, ppt/media image)
// from the current UI in ENGLISH, matching the previous framing:
// 1600x1080 viewport @ DSF 2 => 3200x2160, run view, demo mode ON, at the last saved event.
const base = process.env.BASE || 'http://127.0.0.1:8022';
const tracePath = process.env.TRACE || 'results/ui/run-61801977fe924a16a6e024405d40612d/trace.json';
const out = process.env.OUT || 'presentation/assets/demo_console.png';
fs.mkdirSync(path.dirname(out), { recursive: true });

const route = `${base}/#/run?path=${encodeURIComponent(tracePath)}&demo=1&step=last&lang=en`;
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1600, height: 1080 },
  deviceScaleFactor: 2,
});
// Force English BEFORE any page script runs; also covered by &lang=en in the hash.
await context.addInitScript(() => {
  try {
    localStorage.setItem('incident-lens-lang', 'en');
  } catch {
    /* ignore */
  }
});
const page = await context.newPage();
const errs = [];
page.on('console', (m) => {
  if (m.type() === 'error') errs.push(m.text());
});
page.on('pageerror', (e) => errs.push('pageerror: ' + e.message));

await page.goto(route, { waitUntil: 'domcontentloaded' });
// Wait for the i18n engine to settle in English and the run console to render.
await page.waitForFunction(
  () => window.__ilI18n && window.__ilI18n.getLang() === 'en' && document.querySelector('#replay-demo'),
  { timeout: 20000 },
).catch(() => {});
await page.waitForLoadState('networkidle').catch(() => {});
await page.waitForTimeout(2500);

// The language toggle shows the Chinese glyphs "中文" in English mode (so users can
// switch back). The deck screenshot must be pixel-level CJK-free, so keep the globe
// icon but hide the label text for this capture only (no engine/source change).
await page.evaluate(() => {
  const label = document.getElementById('lang-toggle-label');
  if (label) label.style.display = 'none';
});
await page.waitForTimeout(200);

const lang = await page.evaluate(() => window.__ilI18n && window.__ilI18n.getLang());
const demo = await page.locator('#replay-demo').isChecked().catch(() => null);
const jump = await page.locator('#replay-jump').inputValue().catch(() => null);
const positionText = await page.locator('#replay-position').innerText().catch(() => '');

// CJK sanity check on the rendered pixels: only VISIBLE text counts (the hidden
// toggle label is display:none, so it cannot appear in the screenshot).
const cjk = await page.evaluate(() => {
  const re = /[\u4e00-\u9fff]/;
  const visible = (el) => {
    let v = el;
    while (v && v.nodeType === 1) {
      const s = getComputedStyle(v);
      if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false;
      v = v.parentElement;
    }
    return true;
  };
  const hits = [];
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = w.nextNode())) {
    const t = n.data;
    if (!t || !re.test(t)) continue;
    if (!visible(n.parentElement)) continue;
    hits.push(t.replace(/\s+/g, ' ').trim().slice(0, 80));
  }
  // Attributes are not painted in a screenshot; report any (excl. the lang toggle aria)
  // purely as diagnostics.
  const attrs = ['aria-label', 'title', 'placeholder', 'alt'];
  for (const el of document.querySelectorAll('*')) {
    if (el.closest && el.closest('#lang-toggle')) continue;
    for (const a of attrs) {
      const v = el.getAttribute(a);
      if (v && re.test(v)) hits.push(`[${a}] ${v.slice(0, 80)}`);
    }
  }
  return hits;
});

console.log('lang:', lang, '| demo checkbox:', demo, '| jump value:', jump, '| position:', positionText.trim());
console.log('DOM CJK hits (excl #lang-toggle):', cjk.length, cjk.slice(0, 20));
console.log('page errors:', errs.length, errs.slice(0, 5));

await page.screenshot({ path: out });
const bytes = fs.statSync(out).size;
console.log('saved', out, 'bytes:', bytes);
await browser.close();
if (cjk.length) {
  console.error('CJK REMAINS IN EN UI — screenshot not acceptable');
  process.exit(3);
}
if (errs.length) {
  console.error('PAGE ERRORS PRESENT');
  process.exit(4);
}
