/**
 * pte.mjs — practicepteonline.com 源适配器（WordPress REST API）
 *
 * S04 重写要点：
 *  - DOM 解析交给 html-questions.mjs（parseHtml/collectQuestionGroups/collectAnswerSlots/collectPassages）
 *  - 网络层走 fetch-source.mjs（请求/字节预算、来源失败停止、checkpoint、raw 落盘去重）
 *  - 期望题号来自 data/expected-structure.json（S02 manifest；逐册逐套，不默认 40 题）
 *  - hub 页链接按标签核验身份（label 的 "书.套" 与 slug 分离记录）；错链接记 identity_conflict
 *  - Academic / General 严格分离，不用 General 回填 Academic
 *  - 纯函数 parsePtePage(raw, identity, expected) 可离线回归
 *
 * 接口：/wp-json/wp/v2/pages?slug=SLUG&_fields=id,slug,title,content
 * 答案在 <div id='bg-showmore-hidden-*'> 容器内（ol 或 "N. value" 编号段落）。
 */
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  parseHtml, collectAnswerSlots, collectQuestionGroups, collectPassages,
  collectAssets, collectInstructions, extractExplanations, extractAudio,
  collectReadingGroupStops, nodeText, normalizeWs,
} from "./html-questions.mjs";
import { createFetcher } from "./fetch-source.mjs";
import { resolveDataDir, readJson } from "./data-store.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));

export const PARSER_VERSION = "pte-s04-2026.10.2";
export const SOURCE_ID = "practicepteonline";

const BASE = "https://practicepteonline.com";
const API = BASE + "/wp-json/wp/v2/pages";
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36";
const REQUEST_HEADERS = { "user-agent": UA, accept: "application/json" };

/** 剑桥 N → 站点 hub 页面 ID（剑1–剑21，全部实测定位） */
export const HUBS = {
  1: 9322, 2: 9330, 3: 9341, 4: 9349, 5: 9357, 6: 9365, 7: 9374,
  8: 9382, 9: 9390, 10: 9404, 11: 9452, 12: 9463, 13: 7025, 14: 7051,
  15: 9314, 16: 9291, 17: 9277, 18: 9263, 19: 9255, 20: 12381, 21: 12724,
};

/** hub 页 slug（数字 ID 失效时按 slug 回落查询） */
export const HUB_SLUGS = {
  1: "official-ielts-tests-book-1", 2: "official-ielts-tests-book-2", 3: "official-ielts-tests-book-3",
  4: "official-ielts-tests-book-4", 5: "official-ielts-tests-book-5", 6: "official-ielts-tests-book-6",
  7: "official-ielts-tests-book-7", 8: "official-ielts-tests-book-8", 9: "official-ielts-tests-book-9",
  10: "official-ielts-tests-book-10", 11: "official-ielts-tests-book-11", 12: "official-ielts-tests-book-12",
  13: "official-ielts-tests-book-13", 14: "official-ielts-tests-book-14", 15: "official-ielts-tests-book-15",
  16: "official-ielts-tests-book-16", 17: "official-ielts-tests-book-17", 18: "official-ielts-tests-book-18",
  19: "official-ielts-book-19", 20: "official-ielts-tests-book-20", 21: "official-ielts-tests-book-21",
};

/**
 * 人工核验过的 hub 兜底（剑20/剑21 实测；与 hub 页标签交叉核对过）。
 * 仅当 hub 抓取失败或 hub 未给出该槽位时启用，provenance 记 manual_verified。
 */
const MANUAL_SLUGS = {
  20: {
    reading: { 1: "ielts-reading-test-310", 2: "ielts-reading-test-311", 3: "ielts-reading-test-312", 4: "ielts-reading-test-313" },
    listening: { 1: "ielts-listening-test-201", 2: "ielts-listening-test-202", 3: "ielts-listening-test-203", 4: "ielts-listening-test-204" },
  },
  21: {
    reading: { 1: "ielts-reading-test-316", 2: "ielts-reading-test-317", 3: "ielts-reading-test-318", 4: "ielts-reading-test-319" },
    listening: { 1: "ielts-listening-test-205", 2: "ielts-listening-test-206", 3: "ielts-listening-test-207", 4: "ielts-listening-test-208" },
  },
};

/* ------------------------ 期望题号（S02 expected-structure.json） ------------------------ */

let expectedDoc;
function loadExpectedDoc() {
  if (expectedDoc === undefined) {
    const file = path.join(HERE, "data", "expected-structure.json");
    expectedDoc = readJson(file, { missingOk: true }) || null;
  }
  return expectedDoc;
}

/**
 * 逐册逐套逐技能期望题号（来自 S02 有证据清单；不默认 40 题）。
 * @returns {{status, expected_total, numbers:number[], max:number, parts, source}|null}
 */
export function expectedFor(book, test, skill) {
  const doc = loadExpectedDoc();
  if (!doc || !Array.isArray(doc.books)) return null;
  const b = doc.books.find((x) => x.book === Number(book));
  if (!b) return null;
  let node = null;
  if (skill === "general_reading") {
    node = b.general && Array.isArray(b.general.tests) && b.general.tests[0] ? b.general.tests[0].reading : null;
  } else {
    const tests = Array.isArray(b.tests) ? b.tests : [];
    const t = tests.find((x) => Number(x.test) === Number(test)) || tests[Number(test) - 1];
    node = t ? t[skill] : null;
  }
  if (!node || !node.expected_total) return null;
  const numbers = [];
  const parts = Array.isArray(node.parts) ? node.parts : [];
  if (parts.length && parts.every((p) => Array.isArray(p.ranges) && p.ranges.length)) {
    for (const p of parts) for (const [a, z] of p.ranges) for (let n = a; n <= z; n++) numbers.push(n);
  } else {
    for (let n = 1; n <= node.expected_total; n++) numbers.push(n);
  }
  return {
    status: node.status ?? null,
    expected_total: node.expected_total,
    numbers,
    max: numbers.length ? Math.max(...numbers) : node.expected_total,
    parts,
    source: "data/expected-structure.json",
  };
}

/* ---------------------------------- 网络层 ---------------------------------- */

let sharedFetcher = null;

/** 测试用：清空共享 fetcher 缓存 */
export function resetFetcher() {
  sharedFetcher = null;
}

function getFetcher(opts = {}) {
  if (opts.fetcher) return opts.fetcher;
  if (!sharedFetcher) {
    const day = new Date().toISOString().slice(0, 10).replace(/-/g, "");
    sharedFetcher = createFetcher({
      root: opts.root || resolveDataDir(),
      runId: process.env.IELTS_RUN_ID || process.env.EXAMDATA_IELTS_RUN_ID || "pte-" + day,
    });
  }
  return sharedFetcher;
}

/** 抓 hub/题目页 JSON（落 raw；返回 {text, raw}）；opts.rawText 时直接复用不联网 */
async function fetchPage(url, opts = {}, meta = {}) {
  const f = getFetcher(opts);
  const r = await f.fetchToRaw({
    source: SOURCE_ID,
    url,
    headers: REQUEST_HEADERS,
    parserVersion: PARSER_VERSION,
    meta: { kind: "wp-page", ...meta },
  });
  const text = Buffer.isBuffer(r.body) ? r.body.toString("utf8") : String(r.body ?? "");
  return {
    text,
    raw: {
      sha256: r.sha256, bytes: r.bytes, deduped: !!r.deduped,
      body_path: r.bodyPath, meta_path: r.metaPath,
      status: r.status ?? null, final_url: r.final_url ?? url,
    },
  };
}

const pageUrlBySlug = (slug) => API + "?slug=" + encodeURIComponent(slug) + "&_fields=id,slug,title,content";
const pageUrlById = (id) => API + "/" + id + "?_fields=id,slug,title,content";

/* ------------------------------- 纯函数解析 -------------------------------- */

/** 从 raw（字符串或 WP 对象）取 {page, html, raw_kind}；无法解析返回 null */
function unwrapRaw(raw) {
  if (typeof raw === "string") {
    const t = raw.trim();
    if (t.startsWith("[") || t.startsWith("{")) {
      try {
        const j = JSON.parse(t);
        const first = Array.isArray(j) ? j[0] : j;
        if (first && typeof first === "object" && (first.content?.rendered || first.html)) {
          return { page: first, html: first.content?.rendered || first.html, raw_kind: "wp-json" };
        }
      } catch { /* 当作 HTML */ }
    }
    return { page: null, html: raw, raw_kind: "html" };
  }
  if (raw && typeof raw === "object") {
    const first = Array.isArray(raw) ? raw[0] : raw;
    if (first && typeof first === "object" && (first.content?.rendered || first.html)) {
      return { page: first, html: first.content?.rendered || first.html, raw_kind: "wp-object" };
    }
  }
  return null;
}

/**
 * 纯函数：解析 practicepteonline 题目页。
 * @param {string|object} raw WP REST JSON 文本/对象，或纯 HTML
 * @param {{book,test,skill,slug?,page_id?}} identity skill ∈ listening|academic_reading|general_reading|academic_writing|speaking
 * @param {{numbers,expected_total,max,status,parts,source}|null} expected 期望题号（expectedFor 产物）
 */
export function parsePtePage(raw, identity = {}, expected = null) {
  const warnings = [];
  const id = identity || {};
  const book = id.book ?? null;
  const test = id.test ?? null;
  const skill = id.skill ?? null;

  const unwrapped = unwrapRaw(raw);
  if (!unwrapped || !unwrapped.html) {
    return { ok: false, source: SOURCE_ID, book, test, skill, error: "no_html", warnings: [{ kind: "no_html" }] };
  }
  const { page, html, raw_kind } = unwrapped;
  const root = parseHtml(html);

  const maxN = expected && Number.isFinite(expected.max) ? Math.max(expected.max, 1) : 45;
  const isReading = skill === "academic_reading" || skill === "general_reading";
  const isListening = skill === "listening";

  const ans = collectAnswerSlots(root, { maxNumber: maxN });
  let groups = collectQuestionGroups(root, { maxNumber: maxN, stopAtHeadings: !isListening });
  // 阅读页：先按篇目标题/页分隔符求截断点，再重建题组，阻止 shared_prompt 吞掉下一篇文章标题与正文
  if (isReading) {
    const stops = collectReadingGroupStops(root, groups.groups);
    if (stops.stopBlocks.size > 0) {
      groups = collectQuestionGroups(root, { maxNumber: maxN, stopAtHeadings: !isListening, stopBlocks: stops.stopBlocks });
    }
  }
  const passages = isReading
    ? collectPassages(root, { groups: groups.groups, expectedPassages: expected && expected.parts ? expected.parts.length : null })
    : { passages: [], notes: [] };
  const assets = collectAssets(root, { baseUrl: BASE });
  const audio = extractAudio(root, { baseUrl: BASE });
  const explanations = extractExplanations(root);
  const instructions = collectInstructions(groups.groups);

  // 答案条目：按题号索引（首次出现优先；重复题号记录）
  const answerMap = new Map();
  const duplicateAnswers = [];
  for (const e of ans.entries) {
    if (answerMap.has(e.number)) duplicateAnswers.push(e.number);
    else answerMap.set(e.number, e);
  }

  // 槽位：跨组按题号合并（组合题 23-24 等重复编号保留组列表）
  const kindRank = (k) => (k === "derived" ? 0 : k === "multi_select" ? 1 : 2);
  const slotByNumber = new Map();
  for (const g of groups.groups) {
    for (const s of g.slots) {
      const cur = slotByNumber.get(s.number);
      if (!cur) {
        slotByNumber.set(s.number, {
          number: s.number, prompt: s.prompt || "", kind: s.kind,
          options: s.options || [], group: g.index, groups: [g.index], source_ref: s.source_ref,
        });
      } else {
        if (!cur.groups.includes(g.index)) cur.groups.push(g.index);
        const richer = kindRank(s.kind) > kindRank(cur.kind);
        if (richer || (!cur.prompt && s.prompt)) {
          cur.prompt = s.prompt || cur.prompt;
          cur.kind = richer ? s.kind : cur.kind;
          if (s.options && s.options.length) cur.options = s.options;
          if (s.source_ref) cur.source_ref = s.source_ref;
        }
      }
    }
  }

  // 题号全集：期望清单优先；缺失时由答案+槽位推导（并如实标注 derived）
  const expNumbers = expected && Array.isArray(expected.numbers) && expected.numbers.length ? expected.numbers.slice() : null;
  const numbers = expNumbers || [...new Set([...answerMap.keys(), ...slotByNumber.keys()])].sort((a, b) => a - b);
  const expected_source = expNumbers ? (expected.source || "manifest") : "derived";

  if (expNumbers) {
    const beyond = [...answerMap.keys()].filter((n) => !expNumbers.includes(n)).sort((a, b) => a - b);
    if (beyond.length) warnings.push({ kind: "answers_beyond_expected", numbers: beyond });
  }

  const questions = numbers.map((n) => {
    const slot = slotByNumber.get(n) || null;
    const entry = answerMap.get(n) || null;
    return {
      number: n,
      prompt: slot ? slot.prompt : "",
      group: slot ? slot.group : null,
      groups: slot ? slot.groups : [],
      kind: slot ? slot.kind : null,
      options: slot ? slot.options : [],
      answer: entry && entry.raw !== "" ? entry.raw : null,
      answer_form: entry ? entry.form : null,
      explanation: explanations[n] || null,
      source_ref: slot ? slot.source_ref : null,
    };
  });

  const answer_key = numbers.map((n) => {
    const e = answerMap.get(n);
    return e && e.raw !== "" ? e.raw : null;
  });
  const questions_missing = questions.filter((q) => !slotByNumber.has(q.number)).map((q) => q.number);
  const answer_missing = [];
  const answer_missing_detail = [];
  for (const n of numbers) {
    const e = answerMap.get(n);
    if (!e) { answer_missing.push(n); answer_missing_detail.push({ number: n, reason: "absent" }); }
    else if (e.raw === "") { answer_missing.push(n); answer_missing_detail.push({ number: n, reason: "empty" }); }
  }

  const nonempty = ans.entries.filter((e) => e.raw !== "").length;
  const emptySlots = ans.entries.length - nonempty;
  const counts = {
    container_entries: ans.entries.length,
    nonempty_slots: nonempty,
    empty_slots: emptySlots,
    answer_slots_filled: nonempty,
    group_slots_covered: numbers.filter((n) => slotByNumber.has(n)).length,
    question_groups: groups.groups.filter((g) => !g.structural).length,
    structural_groups: groups.groups.filter((g) => g.structural).length,
    passages: passages.passages.length,
  };

  // 警告汇总
  for (const n of passages.notes) warnings.push(n);
  for (const n of groups.notes) warnings.push(n);
  for (const n of ans.notes) warnings.push(n);
  if ((isReading || isListening) && groups.groups.length === 0) {
    warnings.push({ kind: "no_question_groups_for_skill", skill });
  }
  if (duplicateAnswers.length) warnings.push({ kind: "duplicate_answer_numbers", numbers: [...new Set(duplicateAnswers)] });
  const outOfRange = groups.groups.reduce((s, g) => s + (g.out_of_range ? g.out_of_range.length : 0), 0);
  if (outOfRange) warnings.push({ kind: "out_of_range_question_lines", count: outOfRange });
  if (questions_missing.length) warnings.push({ kind: "questions_missing", numbers: questions_missing });
  if (answer_missing.length) warnings.push({ kind: "answers_missing", numbers: answer_missing });

  const slug = (page && page.slug) || id.slug || null;
  return {
    ok: true,
    source: SOURCE_ID,
    source_name: "practicepteonline.com",
    book, test, skill,
    slug,
    page_id: (page && page.id) || id.page_id || null,
    title: (page && (page.title?.rendered || page.title)) || id.title || null,
    url: slug ? BASE + "/" + slug + "/" : null,
    raw_kind,
    parser_version: PARSER_VERSION,
    expected: expected
      ? { status: expected.status ?? null, expected_total: expected.expected_total ?? null, source: expected.source ?? null, max: expected.max ?? null }
      : null,
    expected_source,
    passages: passages.passages,
    passage: isReading ? passages.passages.flatMap((p) => p.paragraphs.map((x) => x.text)) : undefined,
    instructions,
    question_groups: groups.groups,
    questions,
    answer_slots: ans.entries.map((e) => ({ number: e.number, raw: e.raw, form: e.form, source_ref: e.source_ref })),
    answer_key,
    answer_count: counts.answer_slots_filled,
    question_count: numbers.length - questions_missing.length,
    expected_total: expected ? (expected.expected_total ?? numbers.length) : numbers.length,
    questions_missing,
    answer_missing,
    answer_missing_detail,
    counts,
    warnings,
    parse_status: warnings.length === 0 ? "ok" : "partial",
    partial_reasons: [...new Set(warnings.map((w) => w.kind))],
    audio,
    assets,
  };
}

/* ------------------------------ hub 链接解析 ------------------------------- */

const RE_LINK = /href=["']([^"']+)["'][^>]*>([\s\S]{0,300}?)<\/a>/gi;

function labelText(fragment) {
  return normalizeWs(nodeText(parseHtml(fragment || ""), { block: false }));
}

/** slug → 技能种类；未识别返回 null */
function kindOfSlug(slug) {
  if (/(?:^|\/)ielts-general-reading-test-/.test(slug)) return "general_reading";
  if (/(?:^|\/)ielts-reading-test-/.test(slug)) return "academic_reading";
  if (/(?:^|\/)ielts-listening-test-/.test(slug)) return "listening";
  if (/(?:^|\/)ielts-writing-test-/.test(slug)) return "writing";
  if (/(?:^|\/)ielts-speaking-test-/.test(slug)) return "speaking";
  return null;
}

function labelKind(label) {
  if (/general\s+reading/i.test(label)) return "general_reading";
  if (/academic\s+reading|reading\s+passage/i.test(label)) return "academic_reading";
  if (/listening/i.test(label)) return "listening";
  if (/writing/i.test(label)) return "writing";
  if (/speaking/i.test(label)) return "speaking";
  return null;
}

/**
 * 解析 hub 页 content.rendered → 槽位表。
 * 返回 {slots:{kind:{idx:slug}}, provenance, conflicts, unassigned}
 */
export function parseHubLinks(html, book) {
  const slots = { academic_reading: {}, general_reading: {}, listening: {}, writing: {}, speaking: {} };
  const provenance = { academic_reading: {}, general_reading: {}, listening: {}, writing: {}, speaking: {} };
  const conflicts = [];
  const unassigned = [];
  const positionals = { academic_reading: 0, general_reading: 0, listening: 0, writing: 0, speaking: 0 };

  for (const m of String(html || "").matchAll(RE_LINK)) {
    const rawHref = m[1];
    if (/^(mailto:|#|javascript:)/i.test(rawHref)) continue;
    const slug = rawHref
      .replace(/^https?:\/\/practicepteonline\.com/i, "")
      .replace(/^\/+/, "")
      .replace(/\/+$/, "");
    const kind = kindOfSlug(slug);
    if (!kind) continue;
    const label = labelText(m[2]);
    const lk = labelKind(label);
    if (lk && lk !== kind) {
      conflicts.push({ kind, slug, label, reason: "kind_mismatch", label_kind: lk });
      continue;
    }
    const dotted = /(\d+)\s*\.\s*(\d+)\s*$/.exec(label);
    const plain = /(?:^|\s)(\d+)\s*$/.exec(label);
    let idx = null;
    let bookClaim = null;
    if (dotted) { bookClaim = Number(dotted[1]); idx = Number(dotted[2]); }
    else if (plain) { idx = Number(plain[1]); }
    if (bookClaim != null && bookClaim !== Number(book)) {
      conflicts.push({ kind, slug, label, reason: "book_mismatch", expected_book: Number(book), label_book: bookClaim });
      continue;
    }
    if (idx == null) {
      positionals[kind] += 1;
      idx = positionals[kind];
      provenance[kind][idx] = { slug, label, origin: "positional" };
    } else if (idx < 1 || idx > 4) {
      unassigned.push({ kind, slug, label, reason: "index_out_of_range", index: idx });
      continue;
    }
    if (slots[kind][idx]) {
      conflicts.push({ kind, slug, label, reason: "duplicate_index", index: idx, kept: slots[kind][idx] });
      continue;
    }
    slots[kind][idx] = slug;
    if (!provenance[kind][idx]) provenance[kind][idx] = { slug, label, origin: "hub_link" };
  }
  return { slots, provenance, conflicts, unassigned };
}

/* -------------------------------- 对外接口 -------------------------------- */

/**
 * hub 页 → 逐套 slug 表（Academic/General 分离；标签核验；人工兜底仅补缺）。
 * @returns {{ok, source, book, hub_id, title, url, reading, listening, general, writing, speaking, provenance, conflicts, unassigned}}
 */
export async function bookTests(book, opts = {}) {
  const b = Number(book);
  let hubRaw = opts.hubRaw ?? null;
  let hub_id = HUBS[b] || null;
  let url = null;
  let fetchError = null;

  if (hubRaw == null) {
    try {
      if (hub_id) {
        url = pageUrlById(hub_id);
        hubRaw = (await fetchPage(url, opts, { kind: "hub", book: b })).text;
      }
    } catch (e) {
      fetchError = String((e && e.message) || e);
    }
    if (hubRaw == null && HUB_SLUGS[b]) {
      try {
        url = pageUrlBySlug(HUB_SLUGS[b]);
        hubRaw = (await fetchPage(url, opts, { kind: "hub", book: b, via: "slug" })).text;
      } catch (e) {
        fetchError = String((e && e.message) || e);
      }
    }
  }

  const result = {
    ok: false, source: SOURCE_ID, book: b,
    hub_id, title: null, url,
    reading: {}, listening: {}, general: {}, writing: {}, speaking: {},
    provenance: { reading: {}, general: {}, listening: {}, writing: {}, speaking: {} },
    conflicts: [], unassigned: [],
    error: null,
  };
  if (hubRaw == null) {
    result.error = fetchError || "hub page unavailable";
    // 抓取失败时的最后手段：人工核验兜底
    const manual = MANUAL_SLUGS[b];
    if (manual) {
      for (const [k, map] of Object.entries(manual)) {
        const target = k === "reading" ? result.reading : result.listening;
        for (const [t, slug] of Object.entries(map)) {
          target[t] = slug;
          result.provenance[k === "reading" ? "reading" : "listening"][t] = { slug, label: null, origin: "manual_verified" };
        }
      }
    }
    result.ok = Object.keys(result.reading).length > 0 || Object.keys(result.listening).length > 0;
    return result;
  }

  const unwrapped = unwrapRaw(hubRaw);
  const page = unwrapped ? unwrapped.page : null;
  if (page) {
    result.title = page.title?.rendered || page.title || null;
    if (page.id) result.hub_id = page.id;
  }
  const html = unwrapped ? unwrapped.html : "";
  const parsed = parseHubLinks(html, b);
  result.reading = parsed.slots.academic_reading;
  result.general = parsed.slots.general_reading;
  result.listening = parsed.slots.listening;
  result.writing = parsed.slots.writing;
  result.speaking = parsed.slots.speaking;
  result.provenance = {
    reading: parsed.provenance.academic_reading,
    general: parsed.provenance.general_reading,
    listening: parsed.provenance.listening,
    writing: parsed.provenance.writing,
    speaking: parsed.provenance.speaking,
  };
  result.conflicts = parsed.conflicts;
  result.unassigned = parsed.unassigned;

  // 人工核验兜底只补缺口（不覆盖 hub 结果）
  const manual = MANUAL_SLUGS[b];
  if (manual) {
    for (const [k, map] of Object.entries(manual)) {
      const target = k === "reading" ? result.reading : result.listening;
      for (const [t, slug] of Object.entries(map)) {
        if (!target[t]) {
          target[t] = slug;
          result.provenance[k === "reading" ? "reading" : "listening"][t] = { slug, label: null, origin: "manual_verified" };
        } else if (target[t] !== slug) {
          result.conflicts.push({ kind: k, slug, label: null, reason: "manual_hub_mismatch", index: Number(t), hub_slug: target[t] });
        }
      }
    }
  }

  result.ok = Object.keys(result.reading).length > 0 || Object.keys(result.listening).length > 0;
  return result;
}

/** 取测试页 slug（variant: academic|general） */
function pickSlug(bt, kind, test) {
  const map = kind === "general" ? bt.general : bt[kind];
  return map ? map[test] : null;
}

async function loadTestPage(slug, opts, meta) {
  if (opts.rawText != null) {
    return { text: opts.rawText, raw: { sha256: null, reused_local: true, note: "opts.rawText" } };
  }
  return fetchPage(pageUrlBySlug(slug), opts, meta);
}

/** 阅读：原文 + 题目 + 答案 + 逐题解析（variant: academic 默认 / general） */
export async function readingTest(book, test, opts = {}) {
  const variant = opts.variant === "general" ? "general" : "academic";
  const skill = variant === "general" ? "general_reading" : "academic_reading";
  const bt = await bookTests(book, opts);
  const slug = pickSlug(bt, variant === "general" ? "general" : "reading", test);
  if (!slug) {
    return {
      ok: false, source: SOURCE_ID, book, test, skill,
      error: `no ${variant} reading test ${test} for book ${book}`,
      available: Object.keys(variant === "general" ? bt.general : bt.reading),
    };
  }
  const { text, raw } = await loadTestPage(slug, opts, { kind: "reading", book, test, variant });
  const expected = expectedFor(book, test, skill);
  const parsed = parsePtePage(text, { book, test, skill, slug }, expected);
  return { ...parsed, slug, variant, raw: raw || null, book_tests: { conflicts: bt.conflicts, provenance: bt.provenance[variant === "general" ? "general" : "reading"] } };
}

/** 听力：题目 + 答案 + 音频（含已核实的来源答案纠正由 ielts-api.mjs 应用） */
export async function listeningTest(book, test, opts = {}) {
  const bt = await bookTests(book, opts);
  const slug = pickSlug(bt, "listening", test);
  if (!slug) {
    return {
      ok: false, source: SOURCE_ID, book, test, skill: "listening",
      error: `no listening test ${test} for book ${book}`,
      available: Object.keys(bt.listening),
    };
  }
  const { text, raw } = await loadTestPage(slug, opts, { kind: "listening", book, test });
  const expected = expectedFor(book, test, "listening");
  const parsed = parsePtePage(text, { book, test, skill: "listening", slug }, expected);
  return { ...parsed, slug, raw: raw || null, book_tests: { conflicts: bt.conflicts, provenance: bt.provenance.listening } };
}

/** 仅要音频直链 */
export async function audio(book, test, opts = {}) {
  const r = await listeningTest(book, test, opts);
  return {
    ok: !!(r.ok && r.audio && r.audio.length),
    source: SOURCE_ID, book, test,
    url: r.audio?.[0] || null, all: r.audio || [], error: r.error || null,
  };
}

/**
 * 源侧已知数据缺口（非代码缺陷，均经实测确认）：
 *  - 剑3 听力 T2–T4：hub 页只挂了 1 套（test-59），其余 3 套站点未发布；
 *    答案键已由 ieltsprogress.com 兜底补齐（见 iprog.mjs），题目原文由 reader 逐句时间轴提供
 *  - 剑1 T2 听力：答案页只有 39 条（官方书该套为 41 题，站点缺第 40–41 题）
 *  - 剑20/剑21：站点编号为全站连续号（如 test-310），标签 "TEST 1..4" 核验后按套号映射
 */
export const KNOWN_GAPS = {
  listening: {
    "3-2": "practicepteonline 未发布（hub 仅挂 test-59）；答案键由 ieltsprogress.com 兜底",
    "3-3": "practicepteonline 未发布（hub 仅挂 test-59）；答案键由 ieltsprogress.com 兜底",
    "3-4": "practicepteonline 未发布（hub 仅挂 test-59）；答案键由 ieltsprogress.com 兜底",
  },
  partial_answers: { "listening/1-2": "答案页仅 39 条（官方书该套 41 题，缺第 40–41 题）" },
};

const countSlots = (o) => Object.keys(o || {}).filter((k) => /^\d+$/.test(k)).length;

/** 覆盖自检：每本 hub 的 reading/listening/general 套数（只数数字槽位） */
export async function coverage(opts = {}) {
  const out = {};
  const books = Object.keys(HUBS).map(Number);
  for (const b of books) {
    try {
      const bt = await bookTests(b, opts);
      out[b] = {
        reading: countSlots(bt.reading),
        listening: countSlots(bt.listening),
        general_reading: countSlots(bt.general),
        writing: countSlots(bt.writing),
        ok: bt.ok,
        error: bt.error || null,
        conflicts: bt.conflicts.length,
      };
    } catch (e) {
      out[b] = { reading: 0, listening: 0, general_reading: 0, writing: 0, ok: false, error: String((e && e.message) || e), conflicts: 0 };
    }
  }
  const totalR = Object.values(out).reduce((s, x) => s + x.reading, 0);
  const totalL = Object.values(out).reduce((s, x) => s + x.listening, 0);
  return {
    ok: true, source: SOURCE_ID,
    total_reading: totalR, total_listening: totalL,
    known_gaps: KNOWN_GAPS,
    books: out,
  };
}
