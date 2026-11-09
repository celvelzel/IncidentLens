/**
 * IncidentLens DOM-based i18n engine (zh/en).
 *
 * The SPA source modules author their markup in Chinese. This engine leaves the
 * source untouched: it walks the rendered DOM (text nodes + a small set of
 * translatable attributes) and swaps Chinese for English in place while the
 * active language is English, restoring the originals when it is Chinese.
 *
 * Default language is `zh`, so existing behaviour/tests are unchanged unless a
 * caller opts into English (via ?lang=en, #/route?lang=en, or localStorage).
 *
 * Catalog contract (each ./i18n/catalog.*.js default export):
 *   {
 *     exact:     { "中文": "English", ... },              // whole-node matches
 *     templates: [ { zh: "共 {} 条", en: "{} total" } ],  // {} wildcards
 *     fragments: [ [ /中文/g, "English" ], ... ],         // regex replacements
 *     phrases:   [ [ "中文", "English" ], ... ],          // substring replacements
 *   }
 * Catalogs are optional and loaded with a graceful per-module fallback so a
 * missing/broken catalog never breaks the app.
 */

const LANG_STORAGE_KEY = "incident-lens-lang";
const CATALOG_PATHS = [
  "./i18n/catalog.shell.js",
  "./i18n/catalog.api.js",
  "./i18n/catalog.components.js",
  "./i18n/catalog.views.js",
  "./i18n/catalog.knowledge.js",
  "./i18n/catalog.orchestration.js",
  "./i18n/catalog.replay.js",
];

const SKIP_TAGS = new Set(["SCRIPT", "STYLE", "PRE", "CODE", "TEXTAREA"]);
const TRANSLATABLE_ATTRS = [
  "aria-label",
  "title",
  "placeholder",
  "alt",
  "aria-description",
  "aria-placeholder",
];

const CJK_RE = /[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/;

/* ------------------------------------------------------------------ *
 * Catalog loading + merge
 * ------------------------------------------------------------------ */

// Top-level await: load every catalog independently; swallow failures.
const rawMods = await Promise.all(
  CATALOG_PATHS.map((p) =>
    import(p)
      .then((m) => m.default)
      .catch(() => null),
  ),
);

const exact = Object.create(null);
const exactSeen = new Set();
const templates = [];
const templateSeen = new Set();
const fragments = [];
const fragmentSeen = new Set();
const phrases = [];
const phraseSeen = new Set();
const phraseMap = new Map();

function normalizeKey(value) {
  return String(value).replace(/\s+/g, " ").trim();
}

for (const mod of rawMods) {
  if (!mod || typeof mod !== "object") continue;

  if (mod.exact && typeof mod.exact === "object") {
    for (const [rawKey, value] of Object.entries(mod.exact)) {
      const key = normalizeKey(rawKey);
      if (!key || exactSeen.has(key)) continue;
      exactSeen.add(key);
      exact[key] = value;
    }
  }

  if (Array.isArray(mod.templates)) {
    for (const tpl of mod.templates) {
      if (!tpl || typeof tpl.zh !== "string" || typeof tpl.en !== "string") continue;
      const zhNorm = normalizeKey(tpl.zh);
      if (!zhNorm || templateSeen.has(zhNorm)) continue;
      templateSeen.add(zhNorm);
      templates.push({ zh: zhNorm, en: tpl.en });
    }
  }

  if (Array.isArray(mod.fragments)) {
    for (const frag of mod.fragments) {
      if (!Array.isArray(frag) || frag.length < 2) continue;
      const pattern = frag[0];
      const repl = frag[1];
      const dedupeKey =
        pattern instanceof RegExp
          ? `re:${pattern.source}/${pattern.flags}`
          : `str:${String(pattern)}`;
      if (fragmentSeen.has(dedupeKey)) continue;
      fragmentSeen.add(dedupeKey);
      fragments.push([pattern, repl]);
    }
  }

  if (Array.isArray(mod.phrases)) {
    for (const pair of mod.phrases) {
      if (!Array.isArray(pair) || pair.length < 2) continue;
      const zh = normalizeKey(pair[0]);
      if (!zh || phraseSeen.has(zh)) continue;
      phraseSeen.add(zh);
      phrases.push([zh, pair[1]]);
      phraseMap.set(zh, pair[1]);
    }
  }
}

// One combined global regex for phrases, longest keys first so greedy overlaps
// resolve to the most specific phrase.
let phraseRegex = null;
if (phrases.length) {
  const orderedKeys = [...phrases.map((p) => p[0])].sort((a, b) => b.length - a.length);
  phraseRegex = new RegExp(orderedKeys.map(escapeRegExp).join("|"), "g");
}

/* ------------------------------------------------------------------ *
 * Translation lookup
 * ------------------------------------------------------------------ */

let currentLang = "zh";

function escapeRegExp(str) {
  return String(str).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Split a string into leading whitespace, core, and trailing whitespace.
 * Only meaningful for strings that are not entirely whitespace.
 */
function splitEdgeWhitespace(value) {
  let start = 0;
  let end = value.length;
  while (start < end && /\s/.test(value[start])) start += 1;
  while (end > start && /\s/.test(value[end - 1])) end -= 1;
  return {
    lead: value.slice(0, start),
    core: value.slice(start, end),
    trail: value.slice(end),
  };
}

function normalizeForMatch(value) {
  return value.replace(/\s+/g, " ").trim();
}

function templatePattern(zh) {
  const parts = zh.split("{}");
  return "^" + parts.map(escapeRegExp).join("(.+?)") + "$";
}

/**
 * Translate a single logical string. Returns the input unchanged when not in
 * English mode or when the string contains no CJK characters.
 */
export function translate(value) {
  if (currentLang !== "en") return value;
  if (typeof value !== "string" || !value) return value;
  if (!CJK_RE.test(value)) return value;

  const { lead, core, trail } = splitEdgeWhitespace(value);
  if (!core) return value;
  const norm = normalizeForMatch(core);

  // (a) exact whole-string match
  if (Object.prototype.hasOwnProperty.call(exact, norm)) {
    return lead + exact[norm] + trail;
  }

  // (b) templates: escaped static parts with {} -> non-greedy capture
  for (const tpl of templates) {
    let re;
    try {
      re = new RegExp(templatePattern(tpl.zh));
    } catch {
      continue;
    }
    const match = norm.match(re);
    if (match) {
      let captureIndex = 1;
      const filled = tpl.en.replace(/\{\}/g, () => {
        const captured = match[captureIndex];
        captureIndex += 1;
        return captured === undefined ? "" : captured;
      });
      return lead + filled + trail;
    }
  }

  // (c) fragments: regex replacements over the original string
  let result = value;
  for (const [pattern, repl] of fragments) {
    let re = pattern;
    if (pattern instanceof RegExp && !pattern.global) {
      try {
        re = new RegExp(pattern.source, pattern.flags + "g");
      } catch {
        re = pattern;
      }
    }
    try {
      result = result.replace(re, repl);
    } catch {
      /* ignore malformed fragment */
    }
  }

  // (d) phrases: single combined global regex, zh -> en via map
  if (phraseRegex) {
    phraseRegex.lastIndex = 0;
    result = result.replace(phraseRegex, (matched) =>
      phraseMap.has(matched) ? phraseMap.get(matched) : matched,
    );
  }

  return result;
}

/* ------------------------------------------------------------------ *
 * DOM application
 * ------------------------------------------------------------------ */

const textOriginals = new WeakMap(); // Text node -> original source text
const attrOriginals = new WeakMap(); // Element -> Map<attr, original value>

function shouldSkipElement(el) {
  if (!el || el.nodeType !== 1) return false;
  if (SKIP_TAGS.has(el.tagName)) return true;
  return el.hasAttribute("data-i18n-skip");
}

function translateTextNode(node) {
  const data = node.data;
  if (data == null || !data.trim()) return;

  if (currentLang === "en") {
    let original = textOriginals.get(node);
    if (original === undefined) {
      original = data;
      textOriginals.set(node, original);
    }
    const translated = translate(original);
    if (node.data !== translated) node.data = translated;
  } else if (textOriginals.has(node)) {
    const original = textOriginals.get(node);
    if (node.data !== original) node.data = original;
  }
}

function translateAttributes(el) {
  let map = attrOriginals.get(el);

  if (currentLang === "en") {
    for (const attr of TRANSLATABLE_ATTRS) {
      if (!el.hasAttribute(attr)) continue;
      if (!map) {
        map = new Map();
        attrOriginals.set(el, map);
      }
      let original;
      if (map.has(attr)) {
        original = map.get(attr);
      } else {
        original = el.getAttribute(attr);
        map.set(attr, original);
      }
      if (original == null || !original.trim()) continue;
      const translated = translate(original);
      if (el.getAttribute(attr) !== translated) el.setAttribute(attr, translated);
    }
  } else if (map) {
    for (const attr of TRANSLATABLE_ATTRS) {
      if (!map.has(attr)) continue;
      const original = map.get(attr);
      if (el.getAttribute(attr) !== original) el.setAttribute(attr, original);
    }
  }
}

function walk(node) {
  if (node.nodeType === 3) {
    translateTextNode(node);
    return;
  }
  if (node.nodeType !== 1) return;
  if (shouldSkipElement(node)) return;

  translateAttributes(node);

  for (let child = node.firstChild; child; child = child.nextSibling) {
    walk(child);
  }
}

/**
 * Apply the current language to the subtree rooted at `root`.
 */
export function applyTranslations(root) {
  if (!root) return;
  walk(root);
}

/* ------------------------------------------------------------------ *
 * Meta (title / description) — driven by the shell catalog (merged first,
 * so shell keys always win in `translate`).
 * ------------------------------------------------------------------ */

let titleOriginal = null;
let descriptionOriginal = null;

function captureMetaOriginals() {
  if (titleOriginal === null) titleOriginal = document.title;
  if (descriptionOriginal === null) {
    const meta = document.querySelector('meta[name="description"]');
    if (meta) descriptionOriginal = meta.getAttribute("content");
  }
}

function applyMetaTranslations() {
  captureMetaOriginals();
  if (titleOriginal !== null) document.title = translate(titleOriginal);
  if (descriptionOriginal !== null) {
    const meta = document.querySelector('meta[name="description"]');
    if (meta) meta.setAttribute("content", translate(descriptionOriginal));
  }
}

/* ------------------------------------------------------------------ *
 * Language toggle UI
 * ------------------------------------------------------------------ */

function updateLangToggle() {
  const button = document.getElementById("lang-toggle");
  const label = document.getElementById("lang-toggle-label");
  if (!button) return;
  if (currentLang === "en") {
    if (label) label.textContent = "中文";
    button.setAttribute("aria-label", "切换到中文");
  } else {
    if (label) label.textContent = "English";
    button.setAttribute("aria-label", "Switch language to English");
  }
}

let toggleWired = false;

function wireLangToggle() {
  if (toggleWired) return;
  const button = document.getElementById("lang-toggle");
  if (!button) return;
  button.addEventListener("click", () => {
    toggleLang();
  });
  toggleWired = true;
}

/* ------------------------------------------------------------------ *
 * Public API
 * ------------------------------------------------------------------ */

function persistLang(lang) {
  try {
    localStorage.setItem(LANG_STORAGE_KEY, lang);
  } catch {
    /* storage unavailable */
  }
}

function normalizeLang(value) {
  if (value == null) return null;
  const normalized = String(value).trim().toLowerCase();
  if (!normalized) return null;
  if (normalized === "en" || normalized.startsWith("en-") || normalized.startsWith("en_")) {
    return "en";
  }
  if (normalized === "zh" || normalized.startsWith("zh-") || normalized.startsWith("zh_")) {
    return "zh";
  }
  return null;
}

function resolveInitialLang() {
  // 1) hash query string: "#/route?lang=en"
  const hash = typeof location !== "undefined" ? location.hash || "" : "";
  const queryIndex = hash.indexOf("?");
  if (queryIndex !== -1) {
    try {
      const hashParams = new URLSearchParams(hash.slice(queryIndex + 1));
      const fromHash = normalizeLang(hashParams.get("lang"));
      if (fromHash) return fromHash;
    } catch {
      /* ignore malformed hash */
    }
  }

  // 2) URL search string: "?lang=en"
  try {
    const searchParams = new URLSearchParams(location.search);
    const fromSearch = normalizeLang(searchParams.get("lang"));
    if (fromSearch) return fromSearch;
  } catch {
    /* ignore malformed search */
  }

  // 3) persisted preference
  try {
    const saved = normalizeLang(localStorage.getItem(LANG_STORAGE_KEY));
    if (saved) return saved;
  } catch {
    /* storage unavailable */
  }

  // 4) default
  return "zh";
}

export function getLang() {
  return currentLang;
}

/**
 * Set the active language, persist it, and re-render the DOM in place.
 */
export function setLang(lang) {
  currentLang = normalizeLang(lang) || "zh";
  persistLang(currentLang);
  document.documentElement.lang = currentLang === "en" ? "en" : "zh-CN";
  applyMetaTranslations();
  updateLangToggle();
  applyTranslations(document.body);
  return currentLang;
}

export function toggleLang() {
  return setLang(currentLang === "en" ? "zh" : "en");
}

/* ------------------------------------------------------------------ *
 * MutationObserver: keep dynamically rendered content translated
 * ------------------------------------------------------------------ */

let observer = null;
let applyFrame = null;

function scheduleApply() {
  if (applyFrame !== null) return;
  if (typeof requestAnimationFrame === "function") {
    applyFrame = requestAnimationFrame(() => {
      applyFrame = null;
      applyTranslations(document.body);
    });
  } else {
    applyFrame = setTimeout(() => {
      applyFrame = null;
      applyTranslations(document.body);
    }, 0);
  }
}

function handleCharacterDataMutation(node) {
  if (!node || node.nodeType !== 3) return;
  const original = textOriginals.get(node);
  if (original === undefined) return; // new node; applyTranslations will store it
  const current = node.data;
  const translated = translate(original);
  if (current !== translated && current !== original) {
    // Programmatic textContent update: adopt the fresh text as the new source.
    textOriginals.set(node, current);
  }
}

function startObserver() {
  if (observer || typeof MutationObserver !== "function" || !document.body) return;
  observer = new MutationObserver((records) => {
    for (const record of records) {
      if (record.type === "characterData") {
        handleCharacterDataMutation(record.target);
      }
    }
    scheduleApply();
  });
  observer.observe(document.body, {
    subtree: true,
    childList: true,
    characterData: true,
  });
}

/* ------------------------------------------------------------------ *
 * Boot
 * ------------------------------------------------------------------ */

/**
 * Initialize the engine. Safe to call more than once (idempotent).
 */
export function initI18n() {
  currentLang = resolveInitialLang();
  persistLang(currentLang);
  document.documentElement.lang = currentLang === "en" ? "en" : "zh-CN";
  captureMetaOriginals();
  applyMetaTranslations();
  updateLangToggle();
  wireLangToggle();
  applyTranslations(document.body);
  startObserver();
  return currentLang;
}

// Auto-initialize in the browser. Guard so the module can also be imported in
// non-DOM contexts (e.g. Node tooling) purely for its pure functions.
if (typeof document !== "undefined" && typeof window !== "undefined") {
  initI18n();
  // QA / integration surface.
  window.__ilI18n = { getLang, setLang, translate };
}
