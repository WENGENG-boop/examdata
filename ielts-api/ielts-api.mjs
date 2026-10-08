#!/usr/bin/env node
/**
 * ielts-api.mjs — Cambridge IELTS (剑4–剑20) 多源聚合 API
 * 无依赖，Node 18+ (global fetch)。
 *
 * 设计原则：题目、答案、音频、原文可以来自不同源，router 负责拼接。
 */

const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36";

/* ---------------------------------- 源定义 --------------------------------- */
export const SOURCES = {
  reader: {
    name: "userheyy/ielts-reader",
    kind: "github-raw",
    base: "https://raw.githubusercontent.com/userheyy/ielts-reader/master/",
    cdn: "https://cdn.jsdelivr.net/gh/userheyy/ielts-reader@master/",
    covers: { reading: [1, 19], listening: [1, 19], listening_script: [1, 19], answers: true, timestamps: "word" },
  },
  maslow: {
    name: "maslow/EnglishLearning",
    kind: "github-raw",
    base: "https://raw.githubusercontent.com/maslow/EnglishLearning/main/",
    cdn: "https://cdn.jsdelivr.net/gh/maslow/EnglishLearning@main/",
    covers: { listening_script: [1, 20], audio: [1, 20] },
  },
  tarof: {
    name: "TaroFlink/ielts-listening-practice",
    kind: "github-raw",
    base: "https://raw.githubusercontent.com/TaroFlink/ielts-listening-practice/main/",
    covers: { listening_qa: [16, 20] },
  },
  zeeklog: {
    name: "zeeklog/IELTS",
    kind: "github-raw",
    base: "https://raw.githubusercontent.com/zeeklog/IELTS/master/",
    covers: { pdf: [4, 18] },
  },
  minielts: {
    name: "mini-ielts.com",
    kind: "live-scrape",
    base: "https://mini-ielts.com/",
    covers: { reading_live: "recent-actual-tests", solutions: true },
  },
  pte: {
    name: "practicepteonline.com",
    kind: "wordpress-rest",
    base: "https://practicepteonline.com/wp-json/wp/v2/pages",
    covers: { reading_qa: [1, 21], listening_qa: [1, 21], audio: [1, 21], explanations: true },
    note: "★ 覆盖剑1–21 阅读/听力题目与答案（84 套阅读 + 84 套听力）",
  },
  lfs: {
    name: "BaBaLiBoo/IELTS-Resources",
    kind: "github-lfs",
    base: "https://media.githubusercontent.com/media/BaBaLiBoo/IELTS-Resources/main/",
    covers: { pdf: [1, 20], explain: [7, 20], audio: [20] },
    note: "★★ 提供剑1–19 整本 + 剑20 Test1 分册 PDF（20/20 实测）与剑7–20 精讲解析的源。走 Git LFS，必须用 media.githubusercontent.com（raw 只返回 130 字节指针）",
  },
  cam21: {
    name: "maqsudjon-cell/cambridge-21",
    kind: "github-raw",
    base: "https://raw.githubusercontent.com/maqsudjon-cell/cambridge-21/main/",
    cdn: "https://cdn.jsdelivr.net/gh/maqsudjon-cell/cambridge-21@main/",
    covers: { reading_qa: [21, 21], listening_qa: [21, 21], audio: [21, 21], transcript: [21, 21] },
    note: "★★ 覆盖剑桥21 的源：4 套阅读（160 条答案键）+ 4 套听力（160 题 / 147 条答案键）+ 16 段官方音频（已本地固化并按 sha256 核验）+ 逐句原文（说话人+时间戳）",
  },
  iprog: {
    name: "ieltsprogress.com",
    kind: "live-scrape",
    base: "https://ieltsprogress.com/",
    covers: { listening_answers: [3, 3] },
    note: "★ 剑3 听力 T1–T4 答案键（补齐 practicepteonline 未发布的 T2–T4，听力答案由此达 84/84；2026-10 实测仅剑3 听力系列存在）",
  },
};

/* --------------------------------- 工具函数 -------------------------------- */
const enc = encodeURI;

async function req(url, { as = "text", range, retries = 3 } = {}) {
  const headers = { "user-agent": UA, accept: as === "json" ? "application/json" : "*/*" };
  if (range) headers.range = range;
  let lastErr;
  for (let i = 0; i < retries; i++) {
    try {
      const r = await fetch(url, { headers, redirect: "follow", signal: AbortSignal.timeout(30000) });
      if (r.status >= 500 && i < retries - 1) { await new Promise(s => setTimeout(s, 300 * (i + 1))); continue; }
      if (as === "json") {
        // JSON 解析失败（响应截断/错误页/伪响应）不能算成功：否则下游对 null body 取属性会抛异常
        const body = await r.json().catch(() => undefined);
        if (body == null) {
          if (r.ok && i < retries - 1) { await new Promise(s => setTimeout(s, 400 * (i + 1))); continue; }
          return { status: r.status, ok: false, error: r.ok ? "invalid JSON body" : "HTTP " + r.status, contentType: r.headers.get("content-type"), bytes: r.headers.get("content-length"), body: null };
        }
        return { status: r.status, ok: r.ok, contentType: r.headers.get("content-type"), bytes: r.headers.get("content-length"), body };
      }
      const body = await r.text();
      return { status: r.status, ok: r.ok, contentType: r.headers.get("content-type"), bytes: r.headers.get("content-length"), body };
    } catch (e) {
      lastErr = e;
      if (i < retries - 1) await new Promise(s => setTimeout(s, 400 * (i + 1)));
    }
  }
  return { status: -1, ok: false, error: String(lastErr && lastErr.message || lastErr), body: null };
}

/** GitHub raw 取文件，404 时自动回落到 jsDelivr CDN */
async function gh(src, path, as = "text") {
  const tries = [SOURCES[src].base + enc(path)];
  if (SOURCES[src].cdn) tries.push(SOURCES[src].cdn + enc(path));
  let last;
  for (const u of tries) {
    try { last = await req(u, { as }); if (last.ok) return last; } catch (e) { last = { status: -1, ok: false, error: String(e) }; }
  }
  return last;
}

const pad = (n) => String(n).padStart(2, "0");
const validInteger = (value, low, high) =>
  (typeof value === "number" || (typeof value === "string" && /^\d+$/.test(value)))
  && Number.isInteger(Number(value)) && Number(value) >= low && Number(value) <= high;

function htmlToText(h) {
  return h
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(p|div|li|tr|h[1-6])>/gi, "\n")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&#39;|&rsquo;/g, "'").replace(/&quot;/g, '"')
    .replace(/[ \t]+/g, " ")
    .replace(/\n{2,}/g, "\n")
    .trim();
}

/* ==================== 0. practicepteonline（覆盖剑10–20，含剑20） ========= */
/** 剑N 的 hub 页 → 该书的 reading/listening 测试清单 */
export async function pteBook(book) {
  const m = await import("./pte.mjs");
  return m.bookTests(book);
}

/** 阅读：原文 + 题目 + 答案 + 逐题解析（剑10–20，含剑20） */
export async function pteReading(book, test) {
  const m = await import("./pte.mjs");
  return m.readingTest(book, test);
}

/* ========== 已核实的来源答案纠正（2026-10-03 独立复审逐条裁决） ==========
   裁决数据与守卫逻辑已迁移到 adjudications.mjs（单一真相源；45 条裁决 = 43 diff + 2 被比较器
   单字母子串 bug 掩盖的独立补验项；其中 7 条窄修正）。原值不匹配时不再强套，并记录
   adjudication_stale（上游值变动信号）。 */
import { applyAdjudications as applyAnswerCorrections } from "./adjudications.mjs";
export { applyAnswerCorrections };
import { assessTranscriptText, comparePartScript, SCRIPT_THRESHOLDS, unsegmentedFallback } from "./transcript-matcher.mjs";
import { loadResolverContext, resolveReading, resolveListening, resolveAudio, resolvePdf, resolveTest, RESOLVE_SCHEMA, RESOLVER_VERSION } from "./resolver.mjs";
import { coverageForTest, buildCoverage, summarizeCoverage, COVERAGE_SCHEMA, COVERAGE_VERSION } from "./coverage.mjs";
import { resolveDataDir } from "./data-store.mjs";

/* resolver 上下文（含最新 run 的索引/manifest），60s TTL 缓存；dataDir 变化即失效；completion 用 */
let __resolverCtxCache = { at: 0, dir: null, ctx: null };
function resolverCtxCached() {
  const dir = resolveDataDir();
  if (!__resolverCtxCache.ctx || __resolverCtxCache.dir !== dir || Date.now() - __resolverCtxCache.at > 60000) {
    __resolverCtxCache = { at: Date.now(), dir, ctx: loadResolverContext() };
  }
  return __resolverCtxCache.ctx;
}

/** 听力：题目 + 答案 + 音频（剑10–20，含剑20；含已核实的来源答案纠正） */
export async function pteListening(book, test) {
  const m = await import("./pte.mjs");
  return applyAnswerCorrections(book, test, await m.listeningTest(book, test));
}

/** 音频直链（practicepteonline 镜像） */
export async function pteAudio(book, test) {
  const m = await import("./pte.mjs");
  return m.audio(book, test);
}

/* ============ 0b. Git LFS 镜像（剑19 整本 / 剑20 分册 PDF —— 补齐最后缺口） ======= */
/** 真题 PDF 直链（剑1–20；剑20 为 Test1 分册），自动识别 LFS 指针 */
export async function pdfLfs(book) {
  const m = await import("./lfs.mjs");
  return m.bookPdf(book);
}

/** 剑20 全套：4 个 Test PDF + 听力音频 */
export async function book20Set() {
  const m = await import("./lfs.mjs");
  return m.book20Set();
}

/** 探测任意 LFS 路径是否为真实文件 */
export async function lfsProbe(path, via = "media") {
  const m = await import("./lfs.mjs");
  return m.probe(path, { via });
}

/** 精讲解析 PDF（剑7–20 + 456 合辑） */
export async function explainPdf(book) {
  const m = await import("./lfs.mjs");
  return m.explainPdf(book);
}

/** 剑1–20 真题 PDF 覆盖自检（剑20 为 Test1 分册） */
export async function lfsCoverage(opts) {
  const m = await import("./lfs.mjs");
  return m.coverage(opts);
}

/* ========== 0b2. 剑21 完整书 PDF（社区镜像 —— 补齐剑21 缺口） ============ */
/** 剑21 整本 PDF 直链（44.1MB / 146 页完整书；GitHub raw 直链，非 LFS）
 *  2026-10 实测：HTTP 200、Content-Length 44148624、%PDF-1.6 Linearized；
 *  中文授权重印扫描版（含全部 4 套 Test + 原文 + 答案 + 样卷）。 */
export function pdf21() {
  return {
    ok: true, source: "aqinaq/agylshyn", book: 21,
    url: "https://raw.githubusercontent.com/aqinaq/agylshyn/main/site/pdf/ielts-21.pdf",
    bytes: 44148624, pages: 146,
    note: "剑21 完整书 PDF（146 页；社区镜像，中文授权重印扫描版）",
  };
}

/* ============================ 1. 阅读（本地解析，零网络） ======================== */
/** 剑N Test T 阅读整卷（或指定 Passage P）的原文、题目、答案（ielts-data 本地解析；剑12 web 编号 5–8 自动映射）。
 *  数据来自 resolver 索引（S05–S12 落盘），不再逐次网络抓取；旧 reader 网络实现保留为 readingEnriched。
 *  passage 缺省 = 整卷 3 篇；显式传 1–3 = 单篇（单篇与整卷同源同语义）。 */
export function reading(book, test, passage = null) {
  if (!validInteger(book, 1, 21)) return { ok: false, source: "ielts-data/resolver", schema: RESOLVE_SCHEMA, error: "book 需为 1–21" };
  if (!validInteger(test, 1, 8)) return { ok: false, source: "ielts-data/resolver", schema: RESOLVE_SCHEMA, error: "test 需为 1–8（剑12 起 web 编号 5–8 映射到本地 Test 1–4）" };
  const passageFilter = passage == null ? null : Number(passage);
  if (passageFilter != null && !validInteger(passageFilter, 1, 3)) {
    return { ok: false, source: "ielts-data/resolver", schema: RESOLVE_SCHEMA, error: "passage 需为 1–3（或缺省取整卷）" };
  }
  const r = resolveReading(book, test, { ctx: resolverCtxCached(), passage: passageFilter });
  if (!r || r.ok === false) {
    return {
      ok: false, source: "ielts-data/resolver", schema: RESOLVE_SCHEMA, resolver: RESOLVER_VERSION,
      book, test, passage: passageFilter, error: (r && r.error) || "not_found",
      code: (r && r.code) || null, expected: (r && r.expected) || null, status_reasons: (r && r.status_reasons) || [],
    };
  }
  const flat = [];
  for (const p of r.passages || []) {
    for (const q of p.questions || []) {
      flat.push({
        number: q.number, type: q.type, group_id: q.group_id, part: q.part, passage: q.passage,
        prompt: q.prompt, options: q.options || [], constraints: q.constraints || [],
        answer: q.answer ? q.answer.raw : null,
        answer_status: q.answer_status || null, answer_mode: q.answer_mode || null,
        question_id: q.id, assets: q.assets || [], source_refs: q.source_refs || [],
        classification_status: q.classification_status || null, classification_reason: q.classification_reason || null,
      });
    }
  }
  flat.sort((a, b) => a.number - b.number);
  return {
    ok: true, source: "ielts-data/" + ((r.source && r.source.kind) || "index"), schema: RESOLVE_SCHEMA, resolver: RESOLVER_VERSION,
    book: (r.identity && r.identity.book) ?? Number(book), test: (r.identity && r.identity.test) ?? Number(test),
    canonical_test: (r.identity && r.identity.test) ?? Number(test), requested_test: (r.identity && r.identity.requested_test) ?? Number(test),
    passage: passageFilter, run_id: r.run_id, status: r.status, status_reasons: r.status_reasons || [],
    numbers: r.numbers, page_ref: (r.source && r.source.page_ref) || null, raw_file: (r.source && r.source.raw_file) || null,
    passages: (r.passages || []).map((p) => ({
      passage: p.passage, part: p.part, title: p.title, paragraphs: p.paragraphs || [], tables: p.tables || [],
      figures: p.figures || [], images: p.images || [], content_present: !!p.content_present,
      numbers: p.numbers, status: p.status, status_reasons: p.status_reasons || [],
      questions: (p.questions || []).map((q) => ({ number: q.number, type: q.type, group_id: q.group_id, prompt: q.prompt, options: q.options || [], answer: q.answer ? q.answer.raw : null, answer_status: q.answer_status || null, question_id: q.id })),
      groups: p.groups || [],
    })),
    questions: flat,
    question_count: flat.length,
    answer_key: flat.map((q) => q.answer),
    answer_count: flat.filter((q) => q.answer_status === "attached" || (q.answer != null && q.answer !== "")).length,
    warnings: r.warnings || [],
  };
}

/* 旧 reader 网络实现（保留：中英对照精读/解析补充；主 reading 已改为本地解析） */
/** 剑N Test T Passage P 的原文、题目、答案、同义替换解析（reader 源；非法身份不发请求） */
export async function readingEnriched(book, test, passage = 1) {
  if (!validInteger(book, 1, 21) || !validInteger(test, 1, 4) || !validInteger(passage, 1, 3)) {
    return { ok: false, source: SOURCES.reader.name, error: "book 需为 1–21，test 需为 1–4，passage 需为 1–3" };
  }
  const path = "data/passages/c" + book + "-test" + test + "-p" + passage + ".json";
  const r = await gh("reader", path, "json");
  if (!r.ok) return { ok: false, source: SOURCES.reader.name, error: "HTTP " + r.status, hint: "该源覆盖剑1–19；剑20/21 见 pte-reading（题目+答案）或 zhan-reading（中英对照精读），整卷见 aggregate" };
  const d = r.body;
  const flat = [];
  for (const grp of d.questions || []) {
    for (const it of grp.items || []) {
      flat.push({
        number: it.number, type: grp.type, group: grp.title,
        prompt: it.prompt, answer: it.answer,
        evidence_sentence: it.evidence_sentence,
        paraphrase: it.paraphrase?.pairs || [],
        trap: it.paraphrase?.trap || null,
        explain: it.paraphrase?.explain || null,
      });
    }
  }
  return {
    ok: true, source: SOURCES.reader.name, book, test, passage,
    id: d.id, title: d.title, label: d.source, quality: d.quality,
    passage_text: (d.sentences || []).map(s => s.en).join("\n"),
    sentences: (d.sentences || []).map(s => ({ id: s.id, para: s.para, en: s.en, zh: s.zh, grammar: s.grammar })),
    questions: flat,
    question_count: flat.length,
    phrases: d.phrases || [],
  };
}

/** 列出某本书可用的阅读 passage */
export async function readingIndex() {
  const r = await gh("reader", "data/index.json", "json");
  if (!r.ok) return { ok: false, error: "HTTP " + r.status };
  const list = (r.body.passages || []).map(p => ({
    id: p.id, title: p.title, source: p.source,
    book: Number((p.id.match(/^c(\d+)-/) || [])[1]),
    test: Number((p.id.match(/-test(\d+)/) || [])[1]),
    passage: Number((p.id.match(/-p(\d+)$/) || [])[1]),
    question_count: p.question_count, quality: p.quality,
  }));
  return { ok: true, source: SOURCES.reader.name, total: list.length, passages: list };
}

/* ============================ 2. 听力原文（覆盖到剑21） ===================== */
/** 听力原文。test 给定时只拉该套四 Part 候选并逐 Part 比对（maslow/reader/ITO/cam21）；
 *  不给 test 时走整本路径（兼容旧返回形状 + S11 part_status/conflicts/provenance）。
 *  book 范围 1–21（剑21 由 cam21 + ITO 提供）。 */
export async function listeningScript(book, test, opts = {}) {
  if (!validInteger(book, 1, 21)) return { ok: false, source: SOURCES.maslow.name, error: "book 需为 1–21" };
  if (test === undefined || test === null) return wholeBookScript(book);
  if (!validInteger(test, 1, 4)) return { ok: false, source: SOURCES.maslow.name, error: "test 需为 1–4" };
  return testScript(book, test, opts);
}

const ITO_SOURCE = "ieltstrainingonline.com";

function countScriptParts(s) {
  return s && s.ok ? Object.values(s.tests || {}).reduce((n, p) => n + Object.keys(p).length, 0) : 0;
}
function scriptChars(s) {
  if (!s || !s.ok) return 0;
  const inTests = Object.values(s.tests || {}).reduce((n, p) => n + Object.values(p).reduce((m, v) => m + String(v).length, 0), 0);
  return inTests + (s.text ? s.text.length : 0);
}
function scriptBasisSummary(partStatus) {
  const bases = Object.values(partStatus).flatMap((m) => Object.values(m).map((s) => s.complete_basis)).filter(Boolean);
  if (!bases.length) return null;
  if (bases.every((b) => b === "cross_source_agreement")) return "cross_source_agreement";
  if (bases.some((b) => b === "cross_source_agreement")) return "mixed";
  return "single_source_signals";
}
/** 通过质量门的 Part 数（镜像 comparePartScript 的拒绝条件：chars≥min、非 html、非广告） */
function countCleanScriptParts(s) {
  if (!s || !s.ok) return 0;
  let n = 0;
  for (const p of Object.values(s.tests || {})) {
    for (const txt of Object.values(p)) {
      const q = assessTranscriptText(txt);
      if (q.chars >= SCRIPT_THRESHOLDS.min_part_chars && !q.html_like && !q.ad_like) n++;
    }
  }
  return n;
}
function addMaslowCandidates(byPart, book, test, viaMaslow) {
  const t = (viaMaslow.tests && viaMaslow.tests["test" + test]) || {};
  let n = 0;
  for (let p = 1; p <= 4; p++) {
    const txt = t["part" + p];
    if (!txt || !txt.trim()) continue;
    (byPart[p] ||= []).push({
      source: SOURCES.maslow.name, text: txt,
      meta: {
        identity_basis: "maslow book_" + pad(book) + " audioscripts.md Test " + test + " PART " + p,
        source_ref: "maslow:ielts_listening/book_" + pad(book) + "/audioscripts.md#test" + test + "-part" + p,
      },
    });
    n++;
  }
  return n;
}
function addReaderCandidates(byPart, book, test, viaReader) {
  const t = (viaReader.tests && viaReader.tests["test" + test]) || {};
  let n = 0;
  for (let p = 1; p <= 4; p++) {
    const txt = t["part" + p];
    if (!txt || !txt.trim()) continue;
    const ref = "reader:data/listening/c" + book + "-test" + test + "-l" + p + ".json";
    (byPart[p] ||= []).push({ source: SOURCES.reader.name, text: txt, meta: { identity_basis: ref, source_ref: ref } });
    n++;
  }
  return n;
}
function addItoCandidates(byPart, ito) {
  let n = 0;
  for (let p = 1; p <= 4; p++) {
    const txt = ito.sections && ito.sections["section" + p];
    if (!txt || !txt.trim()) continue;
    (byPart[p] ||= []).push({
      source: ito.source, text: txt,
      meta: { identity_basis: "ito page " + (ito.slug || "?") + " section " + p, source_ref: "ito:" + (ito.slug || "") },
    });
    n++;
  }
  return n;
}
function addCam21Candidates(byPart, c21, test) {
  let n = 0;
  for (const s of c21.transcript || []) {
    const num = Number(s.section);
    if (!(num >= 1 && num <= 4)) continue;
    const txt = (s.lines || []).map((l) => (l.speaker ? l.speaker + ": " : "") + (l.text || "")).filter((x) => x.trim()).join("\n");
    if (!txt.trim()) continue;
    (byPart[num] ||= []).push({
      source: c21.source, text: txt,
      meta: { identity_basis: "cam21 t" + test + "-listening.html section " + num, source_ref: "cam21:t" + test + "-listening.html#section" + num },
    });
    n++;
  }
  return n;
}
async function itoScriptForTest(book, test) {
  const m = await import("./ito.mjs");
  return m.listeningScript(book, test);
}
async function cam21ScriptForTest(test) {
  const m = await import("./cam21.mjs");
  return m.listening(test);
}

/** S09 音频目录（audio-catalog.json）懒加载；缺失返回 null，不阻断原文接口。 */
let _audioCatalogCache = undefined;
async function loadAudioCatalogOnce() {
  if (_audioCatalogCache !== undefined) return _audioCatalogCache;
  try {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const { resolveDataDir } = await import("./data-store.mjs");
    const runsDir = path.join(resolveDataDir(), "runs");
    let best = null;
    for (const d of fs.readdirSync(runsDir, { withFileTypes: true })) {
      if (!d.isDirectory()) continue;
      const p = path.join(runsDir, d.name, "audio", "audio-catalog.json");
      try {
        const st = fs.statSync(p);
        if (!best || st.mtimeMs > best.mtimeMs) best = { p, mtimeMs: st.mtimeMs };
      } catch { /* 该 run 无音频目录，跳过 */ }
    }
    _audioCatalogCache = best ? JSON.parse(fs.readFileSync(best.p, "utf8")) : null;
  } catch {
    _audioCatalogCache = null;
  }
  return _audioCatalogCache;
}
async function audioRecordFor(book, test, part) {
  const cat = await loadAudioCatalogOnce();
  if (!cat) return null;
  const id = "cambridge:" + book + ":shared:listening:" + test + ":P" + part;
  const rec = (cat.records || []).find((r) => r.identity === id);
  if (!rec) return null;
  return {
    status: rec.status, source: rec.source || null,
    duration_sec: Number.isFinite(rec.duration_sec) ? rec.duration_sec : null,
    content_sha256: rec.content_sha256 || null, bytes: rec.bytes || null,
  };
}

/** 单套路径：拉该套四 Part 候选并逐 Part 比对（不拉整本 16 段）。 */
async function testScript(book, test, opts = {}) {
  const attempted = []; const okSources = []; const skips = [];
  const byPart = {};

  if (book <= 20) {
    attempted.push(SOURCES.maslow.name);
    const viaMaslow = await maslowScript(book);
    if (viaMaslow.ok && viaMaslow.format !== "raw") {
      if (addMaslowCandidates(byPart, book, test, viaMaslow)) okSources.push(SOURCES.maslow.name);
    } else if (viaMaslow.unsegmented) {
      skips.push({ source: SOURCES.maslow.name, reason: "unsegmented_raw" });
    } else {
      skips.push({ source: SOURCES.maslow.name, reason: "error: " + (viaMaslow.error || "unknown") });
    }
  }

  if (book <= 19) {
    attempted.push(SOURCES.reader.name);
    const viaReader = await readerScriptTest(book, test);
    if (viaReader.ok) {
      if (addReaderCandidates(byPart, book, test, viaReader)) okSources.push(SOURCES.reader.name);
    } else {
      skips.push({ source: SOURCES.reader.name, reason: viaReader.skipped === "known_uncovered" ? "not_covered" : "no_segments" });
    }
  }

  if (book === 21) {
    let c21 = opts.cam21;
    if (c21 === undefined) { attempted.push(SOURCES.cam21.name); c21 = await cam21ScriptForTest(test); }
    if (c21 && c21.ok) {
      if (addCam21Candidates(byPart, c21, test)) okSources.push(c21.source);
    } else {
      skips.push({ source: SOURCES.cam21.name, reason: c21 ? "error: " + (c21.error || "unknown") : "unavailable" });
    }
  }

  const missing = [1, 2, 3, 4].filter((p) => !(byPart[p] || []).length);
  const itoNeeded = book >= 10 && (missing.length > 0 || book >= 20 || opts.crossSource === true);
  if (itoNeeded) {
    attempted.push(ITO_SOURCE);
    const ito = await itoScriptForTest(book, test);
    if (ito && ito.ok) {
      if (addItoCandidates(byPart, ito)) okSources.push(ito.source);
    } else {
      skips.push({ source: ITO_SOURCE, reason: ito ? "error: " + (ito.error || "unknown") : "unavailable" });
    }
  }

  const tests = {}; const partStatus = {}; const conflicts = [];
  const sums = { parts_total: 4, ok: 0, review: 0, partial: 0, missing: 0, cross_source_agreement: 0 };
  let bytes = 0;
  const tKey = "test" + test;
  for (let p = 1; p <= 4; p++) {
    const audio = await audioRecordFor(book, test, p);
    const res = comparePartScript({
      identity: { book, test, part: "P" + p },
      candidates: byPart[p] || [],
      audio: audio ? { available: audio.status === "available" || audio.status === "verified", duration_sec: audio.duration_sec, source: audio.source } : null,
    });
    if (res.chosen) { (tests[tKey] ||= {})["part" + p] = res.chosen.text; bytes += res.chosen.text.length; }
    sums[res.status] = (sums[res.status] || 0) + 1;
    if (res.complete_basis === "cross_source_agreement") sums.cross_source_agreement++;
    const st = {
      status: res.status, complete_basis: res.complete_basis,
      chosen_source: res.chosen ? res.chosen.source : null,
      chosen_identity_basis: res.chosen ? res.chosen.identity_basis : null,
      alternatives: res.alternatives, rejected: res.rejected, conflicts: res.conflicts, audio: res.audio,
    };
    if (book === 20 && test === 2 && p === 4) st.dimensions = book20T2P4Dimensions(res, audio);
    partStatus["part" + p] = st;
    for (const c of res.conflicts) conflicts.push({ test, part: p, ...c });
  }

  const chosenSources = new Set(Object.values(partStatus).map((s) => s.chosen_source).filter(Boolean));
  const source = chosenSources.size === 1 ? [...chosenSources][0] : chosenSources.size ? "multi-source" : SOURCES.maslow.name;
  const completeness = { ...sums, complete_basis: scriptBasisSummary({ [tKey]: partStatus }) };
  const provenance = { sources_attempted: [...new Set(attempted)], sources_ok: [...new Set(okSources)], skips, generated_at: new Date().toISOString() };
  const partsWithText = Object.keys(tests[tKey] || {}).length;
  if (!partsWithText) {
    return { ok: false, source, book, test, error: "该套四 Part 均无可用原文", tests: {}, parts: 0, part_status: { [tKey]: partStatus }, conflicts, completeness, provenance };
  }
  return {
    ok: true, source, book, test, format: "multi-source-per-part",
    tests, parts: partsWithText, bytes,
    part_status: { [tKey]: partStatus }, conflicts, completeness, provenance,
  };
}

function book20T2P4Dimensions(res, audio) {
  return {
    text: { status: res.status, chosen_source: res.chosen ? res.chosen.source : null, complete_basis: res.complete_basis },
    pdf_audioscript: { status: "source_missing", evidence: "evidence/S06-book20-structure.json", note: "book20-test2.pdf 无 audioscript 章节（S06 结构核对）" },
    audio: audio
      ? { status: audio.status, identity: "cambridge:20:shared:listening:2:P4", source: audio.source, duration_sec: audio.duration_sec, content_sha256: audio.content_sha256 }
      : { status: "unknown", identity: "cambridge:20:shared:listening:2:P4" },
    note: "文本与音频两个维度独立标注；pdf_audioscript 缺失不代表音频缺失",
  };
}

/** 整本路径：maslow + reader 逐 Part 比对，缺口补 ITO；剑21 走 cam21+ITO 四套合并。
 *  兼容旧形状（source/tests/parts/bytes/alternatives），新增 part_status/conflicts/provenance/completeness。 */
async function wholeBookScript(book) {
  if (book === 21) return cam21WholeBook();
  const attempted = []; const okSources = []; const skips = [];

  attempted.push(SOURCES.maslow.name);
  const viaMaslow = await maslowScript(book);
  if (!viaMaslow.ok && viaMaslow.unsegmented) skips.push({ source: SOURCES.maslow.name, reason: "unsegmented_raw" });
  const mCharsEarly = viaMaslow.ok ? scriptChars(viaMaslow) : 0;
  const mCleanEarly = countCleanScriptParts(viaMaslow);
  // maslow 16 Part 全部通过质量门（≥min_part_chars、非 html/广告）且正文充足（≥40k 字符）时
  // 无需再拉 reader，省 16 次请求；该捷径只给 single_source_signals 依据，不宣称跨源验证完整（S11）
  const maslowGood = mCleanEarly >= 16 && mCharsEarly >= 40000;
  let viaReader;
  if (maslowGood) {
    viaReader = { ok: false, skipped: "maslow_good" };
    skips.push({ source: SOURCES.reader.name, reason: "maslow_complete_shortcut_single_source" });
  } else {
    attempted.push(SOURCES.reader.name);
    viaReader = await readerScript(book);
    if (!viaReader.ok) skips.push({ source: SOURCES.reader.name, reason: viaReader.skipped === "known_uncovered" ? "not_covered" : "no_segments" });
  }

  const mParts = countScriptParts(viaMaslow), rParts = countScriptParts(viaReader);
  const mChars = scriptChars(viaMaslow), rChars = scriptChars(viaReader);

  const perTest = [];
  const itoTests = new Set();
  for (let t = 1; t <= 4; t++) {
    const byPart = {};
    if (viaMaslow.ok && viaMaslow.format !== "raw" && addMaslowCandidates(byPart, book, t, viaMaslow)) okSources.push(SOURCES.maslow.name);
    if (viaReader.ok && addReaderCandidates(byPart, book, t, viaReader)) okSources.push(SOURCES.reader.name);
    perTest.push(byPart);
    const missing = [1, 2, 3, 4].filter((p) => !(byPart[p] || []).length);
    if (book >= 10 && (missing.length || (book === 20 && t === 2))) itoTests.add(t);
  }

  const tests = {}; const partStatus = {}; const conflicts = [];
  const sums = { parts_total: 16, ok: 0, review: 0, partial: 0, missing: 0, cross_source_agreement: 0 };
  let bytes = 0;
  for (let t = 1; t <= 4; t++) {
    const byPart = perTest[t - 1];
    if (itoTests.has(t)) {
      attempted.push(ITO_SOURCE);
      const ito = await itoScriptForTest(book, t);
      if (ito && ito.ok) { if (addItoCandidates(byPart, ito)) okSources.push(ito.source); }
      else skips.push({ source: ITO_SOURCE, reason: ito ? "error: " + (ito.error || "unknown") : "unavailable" });
    }
    const tStatus = {};
    for (let p = 1; p <= 4; p++) {
      const audio = await audioRecordFor(book, t, p);
      const res = comparePartScript({
        identity: { book, test: t, part: "P" + p },
        candidates: byPart[p] || [],
        audio: audio ? { available: audio.status === "available" || audio.status === "verified", duration_sec: audio.duration_sec, source: audio.source } : null,
      });
      if (res.chosen) { (tests["test" + t] ||= {})["part" + p] = res.chosen.text; bytes += res.chosen.text.length; }
      sums[res.status] = (sums[res.status] || 0) + 1;
      if (res.complete_basis === "cross_source_agreement") sums.cross_source_agreement++;
      const st = {
        status: res.status, complete_basis: res.complete_basis,
        chosen_source: res.chosen ? res.chosen.source : null,
        chosen_identity_basis: res.chosen ? res.chosen.identity_basis : null,
        alternatives: res.alternatives, rejected: res.rejected, conflicts: res.conflicts, audio: res.audio,
      };
      if (book === 20 && t === 2 && p === 4) st.dimensions = book20T2P4Dimensions(res, audio);
      tStatus["part" + p] = st;
      for (const c of res.conflicts) conflicts.push({ test: t, part: p, ...c });
    }
    partStatus["test" + t] = tStatus;
  }

  const chosenSources = new Set(Object.values(partStatus).flatMap((m) => Object.values(m).map((s) => s.chosen_source)).filter(Boolean));
  const source = chosenSources.size === 1 ? [...chosenSources][0] : chosenSources.size ? "multi-source" : SOURCES.maslow.name;
  const completeness = { ...sums, complete_basis: scriptBasisSummary(partStatus) };
  const provenance = { sources_attempted: [...new Set(attempted)], sources_ok: [...new Set(okSources)], skips, generated_at: new Date().toISOString() };
  const alternatives = { maslow: { parts: mParts, chars: mChars }, reader: { parts: rParts, chars: rChars } };
  const partsWithText = Object.values(tests).reduce((n, t) => n + Object.keys(t).length, 0);

  if (!partsWithText) {
    const fb = viaMaslow.unsegmented ? unsegmentedFallback(viaMaslow.text) : null;
    if (fb) {
      return { ok: false, source: SOURCES.maslow.name, book, error: "该本未按 Part 分节（unsegmented）", format: "raw",
        unsegmented: fb, tests: {}, parts: 0, bytes: fb.bytes,
        part_status: partStatus, conflicts, completeness, provenance, alternatives, warning: fb.warning };
    }
    if (viaMaslow.ok || viaReader.ok) {
      return { ok: false, source, book, error: "无可用 Part 文本", tests: {}, parts: 0,
        part_status: partStatus, conflicts, completeness, provenance, alternatives };
    }
    return { ok: false, source: SOURCES.maslow.name, book, error: "两源均缺失",
      part_status: partStatus, conflicts, completeness, provenance, alternatives };
  }

  const out = { ok: true, source, book, format: "multi-source-per-part", tests, parts: partsWithText, bytes,
    part_status: partStatus, conflicts, completeness, provenance, alternatives };
  if (viaMaslow.unsegmented) out.unsegmented_maslow = { bytes: (viaMaslow.text || "").length, warning: viaMaslow.warning || "该本未按 Part 分节" };
  return out;
}

/** 剑21 整本：cam21 + ITO 逐套比对后合并（每套 1 + ≤6 请求）。 */
async function cam21WholeBook() {
  const tests = {}; const partStatus = {}; const conflicts = [];
  const sums = { parts_total: 16, ok: 0, review: 0, partial: 0, missing: 0, cross_source_agreement: 0 };
  const attempted = new Set(); const okSources = new Set(); const skips = [];
  let bytes = 0; let partsTotal = 0;
  for (let t = 1; t <= 4; t++) {
    const r = await testScript(21, t, {});
    if (r.provenance) {
      for (const s of r.provenance.sources_attempted || []) attempted.add(s);
      for (const s of r.provenance.sources_ok || []) okSources.add(s);
      for (const s of r.provenance.skips || []) skips.push({ test: t, ...s });
    }
    const tKey = "test" + t;
    partStatus[tKey] = (r.part_status && r.part_status[tKey]) || {};
    if (r.ok) {
      tests[tKey] = r.tests[tKey];
      bytes += r.bytes || 0;
      partsTotal += r.parts || 0;
    }
    for (const c of r.conflicts || []) conflicts.push({ test: t, ...c });
    if (r.completeness) for (const k of Object.keys(sums)) sums[k] += r.completeness[k] || 0;
  }
  const chosenSources = new Set(Object.values(partStatus).flatMap((m) => Object.values(m).map((s) => s.chosen_source)).filter(Boolean));
  const source = chosenSources.size === 1 ? [...chosenSources][0] : chosenSources.size ? "multi-source" : SOURCES.cam21.name;
  const completeness = { ...sums, complete_basis: scriptBasisSummary(partStatus) };
  const provenance = { sources_attempted: [...attempted], sources_ok: [...okSources], skips, generated_at: new Date().toISOString() };
  if (!partsTotal) {
    return { ok: false, source, book: 21, error: "剑21 四套均无可用原文", tests: {}, parts: 0,
      part_status: partStatus, conflicts, completeness, provenance };
  }
  return { ok: true, source, book: 21, format: "multi-source-per-part", tests, parts: partsTotal, bytes,
    part_status: partStatus, conflicts, completeness, provenance };
}

/** reader 覆盖情况缓存（避免对不存在的书反复发起请求） */
const readerCover = new Map();
/** T1P1 探针分段缓存：单套路径 test=1 时复用，省 1 次请求 */
const readerProbe = new Map();

/** 从 reader 逐句时间轴重建 Part 级文本（含说话人；剥离标题标记与项目符） */
function readerSegmentsToText(segs) {
  const lines = [];
  for (const g of segs || []) {
    const who = g.speaker ? g.speaker + ": " : "";
    const en = String(g.en || "").trim();
    if (!en) continue;
    // 剥离行首标题标记与孤立项目符（部分册首段是 "SECTION n: •"）
    let line = (who + en).replace(/^(?:PART|SECTION)\s*\d+\s*[:：]\s*/, "");
    line = line.replace(/^[•·]\s*/, "");
    if (!line) continue;
    lines.push(line);
  }
  return lines.join("\n");
}

/** reader 覆盖探测（T1P1 一次）。reader 只覆盖剑1–19，剑20/21 直接判 known_uncovered（不发请求）。
 *  成功时把探针分段存入 readerProbe 供单套路径复用。返回 true | "known_uncovered" | "probe_empty"。 */
async function ensureReaderCover(book) {
  if (book > 19) return "known_uncovered";
  if (readerCover.has(book)) return readerCover.get(book);
  const probe = await listeningSegments(book, 1, 1);
  const segs = probe.segments || [];
  if (!segs.length) { readerCover.set(book, "probe_empty"); return "probe_empty"; }
  readerCover.set(book, true);
  readerProbe.set(book, segs);
  return true;
}

/** 单套路径：只拉该套四 Part（test=1 时 P1 复用探针缓存）。 */
async function readerScriptTest(book, test) {
  const cover = await ensureReaderCover(book);
  if (cover !== true) return { ok: false, source: SOURCES.reader.name, book, test, skipped: cover };
  const parts = {}; let bytes = 0;
  for (let p = 1; p <= 4; p++) {
    const s = (test === 1 && p === 1) ? { segments: readerProbe.get(book) } : await listeningSegments(book, test, p);
    const txt = readerSegmentsToText(s.segments);
    if (txt.length > 200) { parts["part" + p] = txt; bytes += txt.length; }
  }
  if (!Object.keys(parts).length) return { ok: false, source: SOURCES.reader.name, book, test, skipped: "no_segments" };
  return { ok: true, source: SOURCES.reader.name, book, test, tests: { ["test" + test]: parts }, bytes };
}

/** 从 reader 逐句时间轴重建整本原文（剑1–19）。 */
async function readerScript(book) {
  const cover = await ensureReaderCover(book);
  if (cover !== true) return { ok: false, skipped: cover };
  const tests = {};
  let bytes = 0;
  for (let t = 1; t <= 4; t++) {
    const parts = {};
    for (let p = 1; p <= 4; p++) {
      const s = (t === 1 && p === 1) ? { segments: readerProbe.get(book) } : await listeningSegments(book, t, p);
      const txt = readerSegmentsToText(s.segments);
      if (txt.length > 200) { parts["part" + p] = txt; bytes += txt.length; }
    }
    if (Object.keys(parts).length) tests["test" + t] = parts;
  }
  if (!Object.keys(tests).length) return { ok: false, skipped: "no_segments" };
  return { ok: true, source: SOURCES.reader.name, tests, bytes };
}

/** maslow 整本 audioscripts.md 解析 */
async function maslowScript(book) {
  const path = "ielts_listening/book_" + pad(book) + "/audioscripts.md";
  const r = await gh("maslow", path);
  if (!r.ok) return { ok: false, source: SOURCES.maslow.name, error: "HTTP " + r.status };
  let md = r.body;
  // 规范化：独立成行的 **PART n** / **SECTION n** 粗体标记按标题处理（剑17–20 混用 ## 与 **）
  md = md.replace(/^[ \t]*\*\*[ \t]*(PART|SECTION)[ \t]*(\d+)[ \t]*\*\*[ \t]*$/gim, "## $1 $2");
  // 去掉纯星号装饰行（**** / **）
  md = md.replace(/^[ \t]*\*+[ \t]*$/gm, "");
  const tests = {};
  // Test 标题：兼容 "# Test 1" / "## Test 1" / "## TEST 1"
  const re = /#+\s*Test\s*(\d+)([\s\S]*?)(?=#+\s*Test\s*\d+|$)/gi;
  let m;
  while ((m = re.exec(md))) {
    const t = Number(m[1]);
    // 去掉正文里混入的表格分隔行
    let body = m[2].replace(/^\s*\|\s*$/gm, "");
    // 截断答案区与站内导航垃圾（剑1/2 的 "LISTENING KEYS"；剑11–13/17–20 的 "**Cam N Listening Test M**"）
    const junk = body.search(/^[ \t]*(?:LISTENING KEYS\b|\*{2,3}[ \t]*(?:Answer[ \t]+)?Cam[ \t]*\d+[ \t]+Listening[ \t]+Test\b)/im);
    if (junk > 0) body = body.slice(0, junk);
    const parts = {};
    // Part 标题：兼容 "PART 1" / "SECTION 1"（剑5–16 用 SECTION，剑17+ 用 PART）
    const pr = /#+\s*(?:PART|SECTION)\s*(\d+)([\s\S]*?)(?=#+\s*(?:PART|SECTION)\s*\d+|$)/gi;
    let pm;
    while ((pm = pr.exec(body))) {
      const txt = pm[2].trim();
      if (txt) parts["part" + pm[1]] = txt;
    }
    if (Object.keys(parts).length) tests["test" + t] = parts;
  }
  const partCount = Object.values(tests).reduce((n, p) => n + Object.keys(p).length, 0);
  // 少数文件未分 Part：raw 未分节不算完整原文（ok:false + unsegmented:true），由上层用 reader/ITO 补
  if (!Object.keys(tests).length) {
    if (md.trim().length < 200 || /<(?:!doctype|html|head|body|script)\b/i.test(md)) {
      return { ok: false, source: SOURCES.maslow.name, book, error: "响应不含可用听力原文" };
    }
    return { ok: false, source: SOURCES.maslow.name, book, format: "raw", unsegmented: true, tests: {}, text: md, parts: 0, bytes: md.length, warning: "该本未按 Part 分节（unsegmented）" };
  }
  return { ok: true, source: SOURCES.maslow.name, book, format: "markdown-split", tests, parts: partCount, bytes: md.length };
}

/** 听力音频（剑1–21，Part 级；本地 audio-catalog 身份核验优先，返回真实文件与镜像直链） */
export function listeningAudio(book, test, part) {
  if (!validInteger(book, 1, 21) || !validInteger(test, 1, 4) || !validInteger(part, 1, 4)) {
    return { ok: false, source: "ielts-data/resolver", schema: RESOLVE_SCHEMA, error: "book 需为 1–21，test/part 需为 1–4" };
  }
  const r = resolveAudio(book, test, { ctx: resolverCtxCached(), part: Number(part) });
  if (!r || r.ok === false) return { ok: false, source: "ielts-data/resolver", schema: RESOLVE_SCHEMA, error: (r && r.error) || "not_found" };
  const slot = (r.parts || []).find((x) => Number(String(x.part).replace(/^P/, "")) === Number(part)) || (r.parts || [])[0] || null;
  const rec = slot && slot.record;
  if (!rec) {
    return { ok: false, source: "ielts-data/resolver", schema: RESOLVE_SCHEMA, resolver: RESOLVER_VERSION, book, test, part, error: "audio_catalog 无该 Part 记录", identity: (slot && slot.identity) || null };
  }
  const urls = rec.urls || [];
  const raw = urls.find((u) => u.via === "raw") || urls[0] || null;
  const cdn = urls.find((u) => u.via === "cdn") || urls.find((u) => u !== raw) || null;
  return {
    ok: rec.status === "available" || rec.status === "verified",
    source: "ielts-data/audio-catalog", schema: RESOLVE_SCHEMA, resolver: RESOLVER_VERSION,
    book, test, part, identity: slot.identity, status: rec.status,
    url: raw ? raw.url : null, cdn: cdn ? cdn.url : null, type: "audio/mpeg",
    audio_id: rec.audio_id, identity_status: rec.identity_status, content_sha256: rec.content_sha256,
    bytes: rec.bytes, duration_sec: rec.duration_sec, container: rec.container, codec: rec.codec,
    sample_rate: rec.sample_rate, channels: rec.channels, file_path: rec.file_path, file_exists: rec.file_exists,
    local_samples: rec.local_samples, verification_refs: rec.verification_refs, fetched_at: rec.fetched_at, error: rec.error ?? null,
    note: "本地 audio-catalog 身份核验 + 镜像直链；本地文件路径见 file_path",
  };
}

/** 听力分类索引（320 个 Part，含音频路径与原文质量标注） */
export async function listeningIndex() {
  const r = await gh("maslow", "ielts_index/listening_index.json", "json");
  if (!r.ok) return { ok: false, error: "HTTP " + r.status };
  return { ok: true, source: SOURCES.maslow.name, ...r.body };
}

/* ==================== 3. 听力题目+答案（本地解析，剑1–21） ================== */
export async function listeningQA(book, test, opts = {}) {
  if (opts.json) {
    // 兼容旧调用（测试注入 master JSON）：形状与 provenance 逐字保留
    const path = "data/ielts_" + book + "_test_" + test + "/ielts_" + book + "_test_" + test + "_master.json";
    const d = opts.json;
    return {
      ok: true, source: SOURCES.tarof.name, book, test, skill: "listening",
      title: d.test_title, total_questions: d.total_questions, parts_count: d.parts_count,
      questions: (d.questions || []).map(q => ({
        q_num: q.q_num, number: q.q_num, part: q.part, type: q.type, instruction: q.instruction,
        prompt: q.prompt, options: q.options,
        answer: q.target_answer, acceptable: q.acceptable_variants || [], distractors: q.distractors || [],
        timestamps: q.timestamps, acoustics: q.acoustic_profile,
        alignment_status: "unverified",
      })),
      provenance: {
        source: SOURCES.tarof.name, path,
        alignment: "unverified",
        note: "TaroFlink timestamps 原样保留；音频 hash 与时间基准待 S10 核验，未核验前 alignment_status=unverified",
      },
    };
  }
  if (!validInteger(book, 1, 21)) return { ok: false, source: "ielts-data/resolver", schema: RESOLVE_SCHEMA, error: "book 需为 1–21" };
  if (!validInteger(test, 1, 8)) return { ok: false, source: "ielts-data/resolver", schema: RESOLVE_SCHEMA, error: "test 需为 1–8（剑12 起 web 编号 5–8 映射到本地 Test 1–4）" };
  const r = resolveListening(book, test, { ctx: resolverCtxCached() });
  if (!r || r.ok === false) return { ok: false, source: "ielts-data/resolver", schema: RESOLVE_SCHEMA, error: (r && r.error) || "not_found" };
  const flat = [];
  const parts = (r.parts || []).map((p) => {
    for (const q of p.questions || []) {
      flat.push({
        q_num: q.number, number: q.number, part: Number(String(p.part).replace(/^P/, "")), part_label: p.part,
        group_id: q.group_id || null, type: q.type, instruction: q.instruction || null, prompt: q.prompt || null, options: q.options || [],
        answer: q.answer ? q.answer.raw : null,
        acceptable: (q.answer && q.answer.accept) || [],
        answer_status: q.answer_status || null, answer_form: q.answer ? q.answer.form : null, answer_source: q.answer ? q.answer.source : null,
        timestamps: null, alignment_status: q.audio_alignment ? q.audio_alignment.status : "unverified",
        audio_alignment: q.audio_alignment || null,
        question_id: q.id, assets: q.assets || [], constraints: q.constraints || [],
      });
    }
    const aud = p.audio || null;
    const align = p.alignment || null;
    return {
      part: Number(String(p.part).replace(/^P/, "")), part_label: p.part, status: p.status, status_reasons: p.status_reasons || [],
      numbers: p.numbers, questions_count: (p.questions || []).length,
      audio: aud ? { audio_id: aud.audio_id, status: aud.status, content_sha256: aud.content_sha256, duration_sec: aud.duration_sec, file_path: aud.file_path, file_exists: aud.file_exists, url: (aud.urls && aud.urls[0] && aud.urls[0].url) || null } : null,
      alignment: align ? { status: align.status, method: align.method, counts: align.counts, audio_sha256: align.audio_sha256 } : null,
      script: p.script ? { status: p.script.status, source: p.script.source, timestamp_status: p.script.timestamp_status, chars: p.script.chars } : null,
    };
  });
  flat.sort((a, b) => a.number - b.number);
  return {
    ok: true, source: "ielts-data/resolver", schema: RESOLVE_SCHEMA, resolver: RESOLVER_VERSION,
    book: (r.identity && r.identity.book) ?? Number(book), test: (r.identity && r.identity.test) ?? Number(test),
    skill: "listening", canonical_test: (r.identity && r.identity.test) ?? Number(test), web_test: r.web_test,
    total_questions: flat.length, parts_count: parts.length, status: r.status, status_reasons: r.status_reasons || [],
    numbers: r.numbers, parts,
    questions: flat,
    answer_groups: r.answer_groups || [],
    provenance: {
      source: "ielts-data/resolver", run_id: r.run_id,
      page_ref: (r.source && r.source.page_ref) || null, raw_file: (r.source && r.source.raw_file) || null,
      alignment: "per-question", note: "本地解析（S05–S12 落盘索引）；逐题音频对齐状态见 questions[].alignment_status",
    },
    warnings: r.warnings || [],
  };
}

/* ================ 4. 听力逐句时间轴（剑1–19，词级时间戳） ================== */
export async function listeningSegments(book, test, part, opts = {}) {
  const path = "data/listening/c" + book + "-test" + test + "-l" + part + ".json";
  const r = opts.json ? { ok: true, body: opts.json } : await gh("reader", path, "json");
  if (!r.ok) return { ok: false, source: SOURCES.reader.name, error: "HTTP " + r.status, hint: "覆盖剑1–19" };
  const d = r.body;
  return {
    ok: true, source: SOURCES.reader.name, book, test, part, label: d.source,
    audio: d.audio, practice_unit: d.practice_unit,
    segments: (d.segments || []).map(s => ({ id: s.id, start: s.start, speaker: s.speaker, en: s.en, zh: s.zh, words: s.words })),
    alignment_status: "unverified",
    provenance: {
      source: SOURCES.reader.name, path,
      alignment: "unverified",
      note: "词级时间戳为源侧提供；音频 hash 与时间基准待 S10 核验",
    },
  };
}

/* ============================ 5. 官方书 PDF（剑1–21，本地优先） ============ */
/** 整本/分册 PDF：本地已有文件优先，LFS/社区镜像直链补充（只给链接与存在性，不下载） */
export function pdf(book, test = null) {
  if (!validInteger(book, 1, 21)) {
    return { ok: false, source: "ielts-data/resolver", schema: RESOLVE_SCHEMA, error: "book 需为 1–21" };
  }
  if (test != null && !validInteger(test, 1, 4)) {
    return { ok: false, source: "ielts-data/resolver", schema: RESOLVE_SCHEMA, error: "test 需为 1–4（或缺省）" };
  }
  const r = resolvePdf(book, test == null ? null : Number(test), { scope: test == null ? "book" : "test" });
  if (!r || r.ok === false) return { ok: false, source: "ielts-data/resolver", schema: RESOLVE_SCHEMA, error: (r && r.error) || "not_found" };
  const files = (r.files || []).map((f) => ({ ...f, url: f.url || null }));
  const firstUrl = files.find((f) => f.url) || null;
  const local = files.find((f) => f.kind === "local_book_pdf") || null;
  return {
    ok: files.some((f) => f.exists === true) || files.some((f) => !!f.url),
    source: "ielts-data/resolver", schema: RESOLVE_SCHEMA, resolver: RESOLVER_VERSION,
    book: r.book, test: r.test, scope: r.scope, files, warnings: r.warnings || [],
    url: firstUrl ? firstUrl.url : null,
    local: local ? { path: local.path, exists: local.exists, bytes: local.bytes } : null,
    note: "本地优先；链接为 LFS/社区镜像（不下载、不代下）",
  };
}

/* ========================= 6. mini-ielts 实时抓取 ========================= */
export async function miniList(page = 1) {
  const r = await req(SOURCES.minielts.base + "reading?page=" + page);
  if (!r.ok) return { ok: false, error: "HTTP " + r.status };
  const items = [];
  const re = /href="\/(\d+)\/reading\/([a-z0-9-]+)"/gi;
  let m;
  while ((m = re.exec(r.body))) items.push({ id: Number(m[1]), slug: m[2], url: SOURCES.minielts.base + m[1] + "/reading/" + m[2] });
  const uniq = [...new Map(items.map(i => [i.id, i])).values()];
  return { ok: true, source: SOURCES.minielts.name, page, count: uniq.length, tests: uniq };
}

/** 从 view-solution 页面解析官方答案表 */
export async function miniSolution(id, slug) {
  const url = SOURCES.minielts.base + id + "/view-solution/reading/" + slug;
  const r = await req(url);
  if (!r.ok) return { ok: false, error: "HTTP " + r.status };
  const txt = htmlToText(r.body);
  const start = txt.indexOf("Answer Table");
  if (start < 0) return { ok: false, error: "answer table not found" };
  const slice = txt.slice(start, start + 3000);
  const answers = [];
  const re = /(\d{1,2})\.\s+(.+?)(?=\s+\d{1,2}\.\s|$)/g;
  let m;
  while ((m = re.exec(slice))) answers.push({ number: Number(m[1]), answer: m[2].trim() });
  answers.sort((a, b) => a.number - b.number);
  return { ok: true, source: SOURCES.minielts.name, id, slug, url, answers, count: answers.length };
}

/* ===================== 7. 聚合路由：跨源拼装一套完整题 ==================== */
export async function aggregate({ book, test } = {}) {
  const out = { ok: false, book, test, generated_at: new Date().toISOString(), parts: {}, warnings: [] };
  if (!validInteger(book, 1, 21)) return { ...out, error: "book 需为 1–21" };
  if (!validInteger(test, 1, 8)) return { ...out, error: "test 需为 1–8（剑12 起 web 编号 5–8 映射到本地 Test 1–4）" };
  const b = Number(book), t = Number(test);
  out.book = b; out.test = t;

  // 整卷本地解析（零网络：索引/规范化数据来自 ielts-data，S05–S12 落盘）
  const ctx = resolverCtxCached();
  const rt = resolveTest(b, t, { ctx });
  if (!rt || rt.ok === false) {
    out.warnings.push("整卷解析失败：" + ((rt && rt.error) || "unknown"));
    return { ...out, error: (rt && rt.error) || "resolve_failed" };
  }
  const rr = rt.reading || {};
  const rl = rt.listening || {};
  out.ok = true;
  out.schema = RESOLVE_SCHEMA;
  out.resolver = RESOLVER_VERSION;
  out.run_id = rt.run_id;
  out.identity = rt.identity || null;
  out.web_test = rl.web_test ?? null;

  /* ---- 阅读：本地解析（3 篇全文 + 题目 + 答案；单篇与整卷同源同语义） ---- */
  if (rr.ok === false) {
    out.parts.reading = {
      ok: false, source: "ielts-data/resolver", schema: RESOLVE_SCHEMA, code: rr.code || null,
      error: rr.error || "reading 不可用", expected: rr.expected || null, status_reasons: rr.status_reasons || [],
    };
    out.warnings.push("阅读缺失：" + (rr.error || rr.code || "unknown"));
  } else {
    const readingQuestions = [];
    for (const p of rr.passages || []) for (const q of p.questions || []) readingQuestions.push(q);
    readingQuestions.sort((a, b2) => a.number - b2.number);
    out.parts.reading = {
      ok: true, source: "ielts-data/resolver", schema: RESOLVE_SCHEMA, resolver: RESOLVER_VERSION,
      book: (rr.identity && rr.identity.book) ?? b, test: (rr.identity && rr.identity.test) ?? t,
      canonical_test: (rr.identity && rr.identity.test) ?? t, requested_test: (rr.identity && rr.identity.requested_test) ?? t,
      status: rr.status, status_reasons: rr.status_reasons || [], numbers: rr.numbers,
      page_ref: (rr.source && rr.source.page_ref) || null, raw_file: (rr.source && rr.source.raw_file) || null,
      passages: (rr.passages || []).map((p) => ({
        passage: p.passage, part: p.part, title: p.title, paragraphs: p.paragraphs || [], tables: p.tables || [],
        figures: p.figures || [], images: p.images || [], content_present: !!p.content_present,
        numbers: p.numbers, status: p.status, status_reasons: p.status_reasons || [],
        questions_count: (p.questions || []).length, groups: p.groups || [],
      })),
      questions: readingQuestions.map((q) => ({
        number: q.number, part: q.part, passage: q.passage, group_id: q.group_id || null, type: q.type,
        prompt: q.prompt || null, options: q.options || [], constraints: q.constraints || [],
        answer: q.answer ? q.answer.raw : null, answer_status: q.answer_status || null,
        question_id: q.id, assets: q.assets || [],
      })),
      question_count: readingQuestions.length,
      answer_key: readingQuestions.map((q) => (q.answer ? q.answer.raw : null)),
      answer_count: readingQuestions.filter((q) => q.answer_status === "attached" || (q.answer && q.answer.raw != null && q.answer.raw !== "")).length,
      answer_groups: rr.answer_groups || [],
      note: "本地解析（ielts-data 索引）：3 篇原文 + 逐题 + 答案；reader 精读见 reading-enriched 命令",
    };
    out.warnings.push(...(rr.warnings || []));
  }

  /* ---- 听力题目+答案：本地解析（4 Part 逐题 + 答案 + 对齐状态） ---- */
  const listeningQuestions = [];
  for (const p of rl.parts || []) for (const q of p.questions || []) listeningQuestions.push({ ...q, part_label: p.part });
  listeningQuestions.sort((a, b2) => a.number - b2.number);
  out.parts.listening_qa = {
    ok: true, source: "ielts-data/resolver", schema: RESOLVE_SCHEMA, resolver: RESOLVER_VERSION,
    book: (rl.identity && rl.identity.book) ?? b, test: (rl.identity && rl.identity.test) ?? t,
    canonical_test: (rl.identity && rl.identity.test) ?? t, web_test: rl.web_test ?? null,
    status: rl.status, status_reasons: rl.status_reasons || [], numbers: rl.numbers,
    page_ref: (rl.source && rl.source.page_ref) || null, raw_file: (rl.source && rl.source.raw_file) || null,
    parts: (rl.parts || []).map((p) => ({
      part: Number(String(p.part).replace(/^P/, "")), part_label: p.part, status: p.status, status_reasons: p.status_reasons || [],
      numbers: p.numbers, questions_count: (p.questions || []).length, groups: p.groups || [],
      audio: p.audio ? { audio_id: p.audio.audio_id, status: p.audio.status, content_sha256: p.audio.content_sha256, duration_sec: p.audio.duration_sec, file_path: p.audio.file_path, file_exists: p.audio.file_exists } : null,
      alignment: p.alignment ? { status: p.alignment.status, counts: p.alignment.counts, audio_sha256: p.alignment.audio_sha256 } : null,
      script: p.script ? { status: p.script.status, source: p.script.source, timestamp_status: p.script.timestamp_status ?? null, chars: p.script.chars || 0 } : null,
    })),
    questions: listeningQuestions.map((q) => ({
      number: q.number, part: Number(String(q.part).replace(/^P/, "")), part_label: q.part,
      group_id: q.group_id || null, type: q.type, instruction: q.instruction || null, prompt: q.prompt || null,
      options: q.options || [], constraints: q.constraints || [],
      answer: q.answer ? q.answer.raw : null, acceptable: (q.answer && q.answer.accept) || [],
      answer_status: q.answer_status || null, question_id: q.id,
      alignment_status: q.audio_alignment ? q.audio_alignment.status : "unverified",
    })),
    question_count: listeningQuestions.length,
    answer_key: listeningQuestions.map((q) => (q.answer ? q.answer.raw : null)),
    answer_count: listeningQuestions.filter((q) => q.answer_status === "attached" || (q.answer && q.answer.raw != null && q.answer.raw !== "")).length,
    answer_groups: rl.answer_groups || [],
    note: "本地解析：4 Part 逐题 + 答案 + 逐题音频对齐状态（alignment_status）",
  };
  out.warnings.push(...(rl.warnings || []));

  /* ---- 听力原文：逐 Part（本地 script 索引；含来源与截尾状态） ---- */
  const scriptParts = {};
  const scriptText = {};
  for (const p of rl.parts || []) {
    const partNo = Number(String(p.part).replace(/^P/, ""));
    const s = p.script || null;
    scriptParts[partNo] = s
      ? { part: partNo, status: s.status, source: s.source || null, timestamp_status: s.timestamp_status ?? null, chars: s.chars || 0, reason: s.reason ?? null }
      : { part: partNo, status: "missing", source: null, timestamp_status: null, chars: 0 };
    if (s && s.text) scriptText["part" + partNo] = s.text;
  }
  const scriptOk = [1, 2, 3, 4].every((n) => scriptParts[n] && scriptParts[n].status === "available");
  out.parts.listening_script = {
    ok: scriptOk, source: "ielts-data/script-index", schema: RESOLVE_SCHEMA,
    book: b, test: t, parts: Object.keys(scriptText), part_status: scriptParts, text: scriptText,
    note: scriptOk ? "4 Part 原文齐备（本地 script 索引，经来源/截尾质量门）" : "部分 Part 原文缺失或未通过质量门（见 part_status）",
  };
  const segParts = (rl.parts || []).filter((p) => p.script && Array.isArray(p.script.segments) && p.script.segments.length);
  if (segParts.length) {
    out.parts.listening_transcript = {
      ok: true, source: "ielts-data/script-index",
      sections: segParts.map((p) => ({
        section: Number(String(p.part).replace(/^P/, "")),
        lines: (p.script.segments || []).map((sg) => ({ speaker: sg.sp ?? null, timestamp: sg.t ?? null, text: sg.text, number: sg.q ?? null })),
      })),
      note: "官方逐句原文（含说话人与时间戳；cam21 源）",
    };
  }

  /* ---- 音频：Part 级（本地 audio-catalog 身份核验 + 本地文件） ---- */
  const ar = resolveAudio(b, t, { ctx });
  out.parts.listening_audio = (ar.parts || []).map((x) => {
    const rec = x.record;
    const partNo = Number(String(x.part).replace(/^P/, ""));
    if (!rec) return { ok: false, source: "ielts-data/audio-catalog", part: partNo, part_label: x.part, identity: x.identity, status: "missing", error: "audio_catalog 无该 Part 记录" };
    return {
      ok: rec.status === "available" || rec.status === "verified",
      source: "ielts-data/audio-catalog", part: partNo, part_label: x.part, identity: x.identity,
      status: rec.status, audio_id: rec.audio_id, identity_status: rec.identity_status ?? null,
      content_sha256: rec.content_sha256 ?? null, bytes: rec.bytes ?? null, duration_sec: rec.duration_sec ?? null,
      container: rec.container ?? null, codec: rec.codec ?? null, sample_rate: rec.sample_rate ?? null, channels: rec.channels ?? null,
      file_path: rec.file_path ?? null, file_exists: rec.file_exists === true,
      url: (rec.urls && rec.urls[0] && rec.urls[0].url) || null,
    };
  });
  if (ar.full_test) {
    const f = ar.full_test;
    out.parts.listening_audio_full = {
      ok: f.status === "available" || f.status === "verified", source: "ielts-data/audio-catalog",
      identity: f.identity, status: f.status, content_sha256: f.content_sha256 ?? null, duration_sec: f.duration_sec ?? null,
      file_path: f.file_path ?? null, file_exists: f.file_exists === true,
      note: "整卷音频记录（full_test 候选；不冒充已验证）",
    };
  }

  /* ---- 整本/分套 PDF（本地优先 + LFS/社区镜像；book20 分册 scope=test） ---- */
  out.parts.pdf = pdf(b, t);

  /* ---- 写/说：开放题预期清单（无唯一标准答案；样文不得当标准答案） ---- */
  const openSkillPart = (node, skillName) => ({
    ok: true, source: "ielts-data/manifest", open_response: true,
    ...(node || { status: "source_missing", content_status: "source_missing", parts: [], note: skillName + " 为开放任务（无唯一标准答案）；缺原书内容" }),
  });
  out.parts.writing = openSkillPart(rt.writing, "Writing");
  out.parts.speaking = openSkillPart(rt.speaking, "Speaking");

  out.sources_used = [...new Set(
    Object.values(out.parts)
      .flatMap((v) => (Array.isArray(v) ? v.map((x) => x && x.source) : [v && v.source]))
      .filter(Boolean)
  )];
  const audioSlot = Array.isArray(out.parts.listening_audio) ? out.parts.listening_audio : [];
  out.completeness = {
    reading: out.parts.reading.ok === true && out.parts.reading.status === "complete",
    listening_qa: out.parts.listening_qa.status === "complete",
    listening_script: scriptOk,
    audio: audioSlot.length === 4 && audioSlot.every((a) => a.ok === true && a.file_exists === true),
    pdf: (out.parts.pdf.files || []).some((f) => f.exists === true),
    writing: !!(rt.writing && rt.writing.status === "verified"),
    speaking: !!(rt.speaking && rt.speaking.status === "verified"),
  };
  const legacySlots = ["reading", "listening_qa", "listening_script", "audio", "pdf"];
  out.score = legacySlots.filter((k) => out.completeness[k] === true).length + "/5";
  out.availability_score = {
    value: out.score,
    deprecated: true,
    note: "旧 score 仅统计 5 个分片槽位（reading/listening_qa/listening_script/audio/pdf）的严格完整计数；不代表每题答案正确；权威完成度见 completion（ielts.coverage/1）",
  };
  try {
    const cov = coverageForTest(ctx, b, t);
    if (cov && cov.ok) {
      out.completion = {
        schema: cov.schema,
        version: cov.version,
        resolver: cov.resolver,
        run_id: cov.run_id,
        book: cov.book,
        test: cov.test,
        units: cov.units.map((u) => ({
          unit_id: u.unit_id,
          skill: u.skill,
          variant: u.variant,
          status: u.status,
          status_reasons: u.status_reasons,
          numbers: u.numbers,
          missing_group_members: u.missing_group_members,
          missing_assets: u.missing_assets,
          missing_options: u.missing_options,
          unknown_types: u.unknown_types,
          empty_answers: u.empty_answers,
          answer_conflicts: u.answer_conflicts,
          identity_conflicts: u.identity_conflicts,
          official: u.official,
          script_parts: u.script_parts,
          audio: u.audio,
          alignment: u.alignment,
          passages: u.passages,
          denominator: u.denominator,
          completion: u.completion,
        })),
        completion: cov.completion,
      };
    } else if (cov && cov.ok === false) {
      out.warnings.push("completion 不可用：" + cov.error);
    }
  } catch (e) {
    out.warnings.push("completion 计算异常：" + ((e && e.message) || e));
  }
  return out;
}

/* ============================== 8. 覆盖率自检 ============================= */
export async function coverage() {
  const m = await import("./pte.mjs");
  const out = { ok: true, source: "multi", pte_books: {}, reader_reading: {}, tarof_listening: {}, script: {}, pdf: {} };

  // practicepteonline：剑10–20 每本的 reading/listening 套数（关键：含剑20）
  const pc = await m.coverage();
  for (const [b, v] of Object.entries(pc.books)) out.pte_books[b] = v;

  // reader：剑1–19 阅读篇数
  const idx = await readingIndex();
  if (idx.ok) for (const p of idx.passages) out.reader_reading[p.book] = (out.reader_reading[p.book] || 0) + 1;

  // TaroFlink：剑16–20 听力题数
  for (let b = 16; b <= 20; b++) {
    const q = await listeningQA(b, 1);
    out.tarof_listening[b] = q.ok ? q.questions.length : 0;
  }

  // 听力原文：剑18–20
  for (const b of [18, 19, 20]) {
    const s = await listeningScript(b);
    out.script[b] = s.ok ? Object.keys(s.tests).length : 0;
  }

  // PDF：LFS 镜像（剑18/19/20，真实文件）优先
  const lm = await import("./lfs.mjs");
  out.pdf_lfs = {};
  for (const b of [18, 19, 20]) {
    const r = await lm.bookPdf(b);
    out.pdf_lfs[b] = { ok: r.ok, mb: r.bytes ? +(r.bytes / 1048576).toFixed(1) : null };
  }
  out.pdf_zeeklog = {};
  for (const b of [4, 18, 19, 20]) out.pdf_zeeklog[b] = pdf(b).ok;
  return out;
}
/* ============================ 剑桥21（cam21.mjs） ========================== */

/** 剑21 阅读（原文 + 题目 + 答案） */
export async function cam21Reading(test) {
  const m = await import("./cam21.mjs");
  return m.reading(test);
}

/** 剑21 听力（题目 + 答案 + 音频 + 逐句原文） */
export async function cam21Listening(test) {
  const m = await import("./cam21.mjs");
  return m.listening(test);
}

/** 剑21 音频直链 */
export async function cam21Audio(test, section = 1) {
  const m = await import("./cam21.mjs");
  return m.audio(test, section);
}

/** 剑21 整本 */
export async function cam21Full(test) {
  const m = await import("./cam21.mjs");
  return m.fullTest(test);
}

/** 剑21 索引 */
export async function cam21Index() {
  const m = await import("./cam21.mjs");
  const [r, l] = await Promise.all([m.readingIndex(), m.listeningIndex()]);
  return { ok: r.ok && l.ok, source: m.SOURCE, book: 21, reading: r.tests, listening: l.tests };
}

/** 剑21 覆盖自检 */
export async function cam21Coverage() {
  const m = await import("./cam21.mjs");
  return m.coverage();
}
/* ======================= 听力交叉源（ito.mjs） ========================= */

/** ieltstrainingonline 听力原文（剑10–21） */
export async function itoScript(book, test) {
  const m = await import("./ito.mjs");
  return m.listeningScript(book, test);
}

/** ieltstrainingonline 听力题目+答案（剑10–21） */
export async function itoListening(book, test) {
  const m = await import("./ito.mjs");
  return m.listeningTest(book, test);
}

/** ieltstrainingonline 覆盖自检 */
export async function itoCoverage() {
  const m = await import("./ito.mjs");
  return m.coverage();
}
/* =================== 听力答案兜底源（iprog.mjs） ======================= */

/** ieltsprogress.com 剑3 听力 T1–T4 答案键 */
export async function iprogListening(book, test) {
  const m = await import("./iprog.mjs");
  return m.listeningAnswers(book, test);
}

/** ieltsprogress 覆盖自检 */
export async function iprogCoverage() {
  const m = await import("./iprog.mjs");
  return m.coverage();
}
/* ================ 剑20/21 阅读精读（zhan.mjs） ================ */

/** 小站备考剑20/21 阅读逐句中英对照（Test T Passage P） */
export async function zhanReading(book, test, passage = 1) {
  const m = await import("./zhan.mjs");
  return m.reading(book, test, passage);
}

/** 小站备考索引（剑20/21 每 Test 3 篇） */
export async function zhanIndex(book) {
  const m = await import("./zhan.mjs");
  return m.index(book);
}

/** 小站备考覆盖自检 */
export async function zhanCoverage() {
  const m = await import("./zhan.mjs");
  return m.coverage();
}

/* ===================== 9. resolver / coverage 包装导出（S12） =====================
   规范化解析（identity/阅读/听力/音频/PDF）与覆盖度（completion 权威对象）由
   resolver.mjs / coverage.mjs 提供；此处统一再导出，供 CLI、HTTP 服务与
   FastAPI 包装层共用同一入口（不改变既有导出）。 */
export * from "./resolver.mjs";
export * from "./coverage.mjs";
export * from "./v2-api.mjs";
