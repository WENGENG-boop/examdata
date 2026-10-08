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
    note: "★★ 唯一提供剑1–20 完整原版 PDF（20/20 实测）与剑7–20 精讲解析的源。走 Git LFS，必须用 media.githubusercontent.com（raw 只返回 130 字节指针）",
  },
  cam21: {
    name: "maqsudjon-cell/cambridge-21",
    kind: "github-raw",
    base: "https://raw.githubusercontent.com/maqsudjon-cell/cambridge-21/main/",
    cdn: "https://cdn.jsdelivr.net/gh/maqsudjon-cell/cambridge-21@main/",
    covers: { reading_qa: [21, 21], listening_qa: [21, 21], audio: [21, 21], transcript: [21, 21] },
    note: "★★ 唯一覆盖剑桥21 的源：4 套完整阅读（160 答案）+ 4 套听力（147 答案）+ 16 段官方音频（实测 10.7MB 真实 MP3）+ 逐句原文（说话人+时间戳）",
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
   仅修正与官方答案键明确冲突的 practicepteonline 听力条目；保留原值与依据以便溯源。
   完整 45 条裁决（43 diff + 2 被比较器单字母 bug 掩盖项）：
   tmp_audit_ielts/repair-20261003-152644/answer_adjudications.json */
const PTE_ANSWER_CORRECTIONS = {
  "5-1": { 4: { from: "palisades", to: "Pallisades", basis: "官方答案页 p153；原文 p129 逐字母拼读" } },
  "5-2": { 9: { from: "grantigham", to: "Grantingham", basis: "官方答案页 p155；原文 p135 'speak to John Grantingham'" } },
  "5-4": { 19: { from: "end newsletter", to: "send (out/the) newsletter(s)", basis: "官方答案页 p159；原文 p149 'send out newsletters'" } },
  "6-4": { 6: { from: "conference park", to: "conference pack", basis: "官方答案页 p158；原文 p146 'all in our conference pack'" } },
  "7-2": {
    2: { from: "730453", to: "(a) dentist", basis: "官方答案页 p159；730453 是题干给定联系电话，非答案" },
    12: { from: "newton", to: "Newtown", basis: "官方答案页 p159；原文 p142 'stop D Newtown'" },
  },
  "17-4": { 38: { from: "Stream", to: "steam", basis: "官方答案页 p125 列分析 token='steam'；原文 p80 蒸发过程" } },
};

/** 应用纠正表（非破坏性；仅当当前值与记录原值完全一致时替换，防上游变化误改） */
export function applyAnswerCorrections(book, test, r) {
  const table = PTE_ANSWER_CORRECTIONS[`${book}-${test}`];
  if (!table || !r || !r.ok || !Array.isArray(r.answer_key)) return r;
  const applied = [];
  const answer_key = r.answer_key.map((v, i) => {
    const c = table[i + 1];
    if (c && v === c.from) { applied.push({ question: i + 1, from: c.from, to: c.to, basis: c.basis }); return c.to; }
    return v;
  });
  const questions = Array.isArray(r.questions)
    ? r.questions.map((q) => { const c = table[q.number]; return c && q.answer === c.from ? { ...q, answer: c.to } : q; })
    : r.questions;
  return applied.length ? { ...r, answer_key, questions, answer_corrections: applied } : r;
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

/* ============ 0b. Git LFS 镜像（剑19/剑20 完整 PDF —— 补齐最后缺口） ======= */
/** 整本 PDF 直链（剑18/19/20），自动识别 LFS 指针 */
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

/** 剑1–20 整本 PDF 覆盖自检 */
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

/* ============================ 1. 阅读（含答案+解析） ======================== */
/** 剑N Test T Passage P 的原文、题目、答案、同义替换解析 */
export async function reading(book, test, passage = 1) {
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

/* ============================ 2. 听力原文（覆盖到剑20） ===================== */
/** 整本听力 audioscripts.md（剑1–20，含剑20） */
export async function listeningScript(book) {
  if (!validInteger(book, 1, 20)) return { ok: false, source: SOURCES.maslow.name, error: "book 需为 1–20" };
  // 主源：maslow 整本 audioscripts.md
  const viaMaslow = await maslowScript(book);
  const mPartsEarly = viaMaslow.ok ? Object.values(viaMaslow.tests || {}).reduce((n, p) => n + Object.keys(p).length, 0) : 0;
  const mCharsEarly = viaMaslow.ok
    ? Object.values(viaMaslow.tests || {}).reduce((n, p) => n + Object.values(p).reduce((m, v) => m + String(v).length, 0), 0) + (viaMaslow.text ? viaMaslow.text.length : 0)
    : 0;
  // maslow 已是完整 16 Part 且正文充足（≥40k 字符）时无需再拉 reader，省 16 次请求
  const maslowGood = mPartsEarly >= 16 && mCharsEarly >= 40000;
  const viaReader = maslowGood ? { ok: false, skipped: true } : await readerScript(book);

  const count = (s) => s.ok ? Object.values(s.tests || {}).reduce((n, p) => n + Object.keys(p).length, 0) : 0;
  const chars = (s) => {
    if (!s.ok) return 0;
    const inTests = Object.values(s.tests || {}).reduce((n, p) => n + Object.values(p).reduce((m, v) => m + String(v).length, 0), 0);
    return inTests + (s.text ? s.text.length : 0);
  };
  const mParts = count(viaMaslow), rParts = count(viaReader);
  const mChars = chars(viaMaslow), rChars = chars(viaReader);

  // 选取更完整的源：先比 Part 数，再比正文字符数
  // （实测剑4–10 maslow 文件仅 ~11k 字符属截断，reader 有 ~58k；剑11+ 反之）
  const useReader = rParts > mParts || (rParts === mParts && rChars > mChars * 1.3);

  if (useReader) {
    return { ok: true, source: SOURCES.reader.name, book, format: "reader-segments",
      tests: viaReader.tests, parts: rParts, bytes: rChars,
      note: "选用 reader 逐句时间轴（含说话人与中英对照）",
      alternatives: { maslow: { parts: mParts, chars: mChars } } };
  }
  if (viaMaslow.ok) {
    return { ...viaMaslow, parts: mParts, alternatives: { reader: { parts: rParts, chars: rChars } } };
  }
  if (viaReader.ok) {
    return { ok: true, source: SOURCES.reader.name, book, format: "reader-segments", tests: viaReader.tests, parts: rParts, bytes: rChars };
  }
  return { ok: false, source: SOURCES.maslow.name, error: "两源均缺失" };
}

/** reader 覆盖情况缓存（避免对不存在的书反复发起 16 次请求） */
const readerCover = new Map();

/** 从 reader 逐句时间轴重建 Part 级原文（含说话人） */
async function readerScript(book) {
  // 先用 T1P1 做一次廉价探测：reader 只覆盖剑1–19，剑20/21 直接跳过
  if (readerCover.get(book) === false) return { ok: false, skipped: true };
  const probe = await listeningSegments(book, 1, 1);
  if (!(probe.segments || []).length) { readerCover.set(book, false); return { ok: false, skipped: true }; }
  readerCover.set(book, true);

  const tests = {};
  let bytes = 0;
  for (let t = 1; t <= 4; t++) {
    const parts = {};
    for (let p = 1; p <= 4; p++) {
      if (t === 1 && p === 1) { /* 已探测 */ }
      const s = (t === 1 && p === 1) ? probe : await listeningSegments(book, t, p);
      const segs = s.segments || [];
      if (!segs.length) continue;
      // 还原成带说话人的剧本体
      const lines = [];
      for (const g of segs) {
        const who = g.speaker ? g.speaker + ": " : "";
        const en = String(g.en || "").trim();
        if (!en) continue;
        // 剥离行首标题标记与孤立项目符（部分册首段是 "SECTION n: •"）
        let line = (who + en).replace(/^(?:PART|SECTION)\s*\d+\s*[:：]\s*/, "");
        line = line.replace(/^[•·]\s*/, "");
        if (!line) continue;
        lines.push(line);
      }
      const txt = lines.join("\n");
      if (txt.length > 200) { parts["part" + p] = txt; bytes += txt.length; }
    }
    if (Object.keys(parts).length) tests["test" + t] = parts;
  }
  if (!Object.keys(tests).length) return { ok: false };
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
  // 少数文件未分 Part：整份作为 text 返回，由上层用 reader 补
  if (!Object.keys(tests).length) {
    if (md.trim().length < 200 || /<(?:!doctype|html|head|body|script)\b/i.test(md)) {
      return { ok: false, source: SOURCES.maslow.name, book, error: "响应不含可用听力原文" };
    }
    return { ok: true, source: SOURCES.maslow.name, book, format: "raw", tests: {}, text: md, parts: 0, bytes: md.length, warning: "该本未按 Part 分节" };
  }
  return { ok: true, source: SOURCES.maslow.name, book, format: "markdown-split", tests, parts: partCount, bytes: md.length };
}

/** 听力音频直链（剑1–20，Part 级） */
export function listeningAudio(book, test, part) {
  if (!validInteger(book, 1, 20) || !validInteger(test, 1, 4) || !validInteger(part, 1, 4)) {
    return { ok: false, source: SOURCES.maslow.name, error: "book 需为 1–20，test/part 需为 1–4" };
  }
  const path = "ielts_listening/book_" + pad(book) + "/test_" + test + "_part_" + part + ".mp3";
  return { ok: true, source: SOURCES.maslow.name, book, test, part, url: SOURCES.maslow.base + enc(path), cdn: SOURCES.maslow.cdn + enc(path), type: "audio/mpeg" };
}

/** 听力分类索引（320 个 Part，含音频路径与原文质量标注） */
export async function listeningIndex() {
  const r = await gh("maslow", "ielts_index/listening_index.json", "json");
  if (!r.ok) return { ok: false, error: "HTTP " + r.status };
  return { ok: true, source: SOURCES.maslow.name, ...r.body };
}

/* ==================== 3. 听力题目+答案（剑16–20，含剑20） ================== */
export async function listeningQA(book, test) {
  const path = "data/ielts_" + book + "_test_" + test + "/ielts_" + book + "_test_" + test + "_master.json";
  const r = await gh("tarof", path, "json");
  if (!r.ok) return { ok: false, source: SOURCES.tarof.name, error: "HTTP " + r.status, hint: "该源覆盖剑16–20听力" };
  const d = r.body;
  return {
    ok: true, source: SOURCES.tarof.name, book, test,
    title: d.test_title, total_questions: d.total_questions, parts_count: d.parts_count,
    questions: (d.questions || []).map(q => ({
      q_num: q.q_num, part: q.part, type: q.type, instruction: q.instruction,
      prompt: q.prompt, options: q.options,
      answer: q.target_answer, acceptable: q.acceptable_variants || [], distractors: q.distractors || [],
      timestamps: q.timestamps, acoustics: q.acoustic_profile,
    })),
  };
}

/* ================ 4. 听力逐句时间轴（剑1–19，词级时间戳） ================== */
export async function listeningSegments(book, test, part) {
  const path = "data/listening/c" + book + "-test" + test + "-l" + part + ".json";
  const r = await gh("reader", path, "json");
  if (!r.ok) return { ok: false, source: SOURCES.reader.name, error: "HTTP " + r.status, hint: "覆盖剑1–19" };
  const d = r.body;
  return {
    ok: true, source: SOURCES.reader.name, book, test, part, label: d.source,
    audio: d.audio, practice_unit: d.practice_unit,
    segments: (d.segments || []).map(s => ({ id: s.id, start: s.start, speaker: s.speaker, en: s.en, zh: s.zh, words: s.words })),
  };
}

/* ============================ 5. 官方书 PDF（剑4–18） ====================== */
export function pdf(book) {
  const name = "剑桥雅思真题" + book + ".pdf";
  return { ok: book >= 4 && book <= 18, source: SOURCES.zeeklog.name, book, url: SOURCES.zeeklog.base + enc(name), note: book >= 19 ? "该源无剑19/20 PDF，改用 reader 结构化数据" : "整本书 PDF" };
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
  const out = { book, test, generated_at: new Date().toISOString(), parts: {}, warnings: [] };

  // 并发拉取所有候选源
  const isC21 = book === 21;
  const isB3 = book === 3;
  const isZ = book === 20 || book === 21;
  const [pteR, pteL, readerR, tarofL, script, scriptFallback, c21R, c21L, ipL, zR] = await Promise.allSettled([
    pteReading(book, test),
    pteListening(book, test),
    reading(book, test, 1),
    listeningQA(book, test),
    listeningScript(book),
    pteAudio(book, test),
    isC21 ? cam21Reading(test) : Promise.resolve(null),
    isC21 ? cam21Listening(test) : Promise.resolve(null),
    isB3 ? iprogListening(book, test) : Promise.resolve(null),
    isZ ? zhanReading(book, test, 1) : Promise.resolve(null),
  ]);

  const val = (s) => (s.status === "fulfilled" ? s.value : null);

  /* ---- 阅读：剑21 优先 cam21（唯一含剑21 完整原文的源），其余用 practicepteonline，再回落 reader ---- */
  const c21r = val(c21R);
  if (c21r?.ok) {
    out.parts.reading = {
      ok: true, source: c21r.source, book: 21, test, title: c21r.title,
      passages: c21r.passages, questions: c21r.questions,
      answer_key: c21r.answer_key, answer_count: c21r.counts.answers,
      note: "剑21 专属源：3 篇原文 + 40 题 + 40 答案",
    };
  }
  const pr = val(pteR);
  if (pr?.ok && !out.parts.reading) {
    out.parts.reading = {
      ok: true, source: pr.source, book, test, title: pr.title, url: pr.url,
      passage: pr.passage, instructions: pr.instructions,
      questions: pr.questions, answer_key: pr.answer_key, answer_count: pr.answer_count,
      questions_missing: pr.questions_missing || [],
      note: "含原文+题目+答案+逐题解析",
    };
  }
  const rr = val(readerR);
  if (rr?.ok) {
    // reader 提供更细的精读数据（中英对照、语法、同义替换），作为补充而非替换
    out.parts.reading_enriched = {
      ok: true, source: rr.source, passage_id: rr.id, label: rr.label,
      sentences: rr.sentences, phrases: rr.phrases,
      note: "精读补充：逐句中英对照 + 语法点 + 同义替换",
    };
    if (!out.parts.reading) {
      out.parts.reading = { ok: true, source: rr.source, book, test, title: rr.title, questions: rr.questions };
    }
  }
  // 剑20/21：reader 无数据，精读槽位回落小站备考（逐句中英对照）
  const zr = val(zR);
  if (zr?.ok && !out.parts.reading_enriched) {
    out.parts.reading_enriched = {
      ok: true, source: zr.source, section_id: zr.section_id, url: zr.url,
      sentences: zr.sentences,
      note: "精读补充（剑20/21）：逐句中英对照（小站备考；题目解析需登录，不在本接口范围）",
    };
  }
  if (!out.parts.reading) {
    out.warnings.push("阅读缺失：cam21 / practicepteonline / reader 均无此书数据");
  }

  /* ---- 听力题目+答案：剑21 优先 cam21，其余 practicepteonline，再回落 TaroFlink ---- */
  const c21l = val(c21L);
  if (c21l?.ok) {
    out.parts.listening_qa = {
      ok: true, source: c21l.source, book: 21, test, title: c21l.title,
      sections: c21l.sections, audio: c21l.audio.map((a) => a.url),
      questions: c21l.questions, answer_key: c21l.answer_key,
      answer_count: c21l.counts.answers,
      note: "剑21 专属源：4 Section + 官方音频 + 逐句原文（说话人 + 时间戳）",
    };
    out.parts.listening_transcript = {
      ok: true, source: c21l.source, sections: c21l.transcript,
      lines: c21l.counts.transcript_lines,
      note: "官方逐句原文，含说话人与时间戳",
    };
  }
  const pl = val(pteL);
  if (pl?.ok && !out.parts.listening_qa) {
    out.parts.listening_qa = {
      ok: true, source: pl.source, book, test, title: pl.title, url: pl.url,
      audio: pl.audio, instructions: pl.instructions,
      questions: pl.questions, answer_key: pl.answer_key, answer_count: pl.answer_count,
      questions_missing: pl.questions_missing || [],
    };
  } else if (!out.parts.listening_qa) {
    const tl = val(tarofL);
    if (tl?.ok) {
      out.parts.listening_qa = tl;
    } else {
      // 兜底：ieltsprogress.com 答案键（剑3 听力 T2–T4 —— pte 未发布的最后缺口）
      const ip = val(ipL);
      // 最后一层：reader 的逐句时间轴自带题干（部分册 pte 未发布，如剑3 T2–T4）
      const rs = await listeningSegments(book, test, 1);
      const segs = rs.ok ? (rs.segments || []) : [];
      if (ip?.ok) {
        out.parts.listening_qa = {
          ok: true, source: ip.source, book, test, url: ip.url,
          note: "practicepteonline 未发布该套；答案键来自 ieltsprogress.com" + (segs.length ? "，原文/词级时间轴见 segments" : ""),
          questions: [], answer_key: ip.answer_key, answer_count: ip.answer_count,
          segments: segs,
        };
        if (!segs.length) out.warnings.push("听力原文缺失：该套仅有答案键（ieltsprogress.com）");
      } else if (segs.length) {
        out.parts.listening_qa = {
          ok: true, source: rs.source, book, test,
          note: "pte 未发布该套，改用 reader 逐句时间轴（含说话人与词级时间戳）；答案键请以官方为准",
          questions: [], answer_key: [],
          segments: segs,
        };
        out.warnings.push("听力答案缺失：该套 pte 未发布，仅提供原文与时间轴");
      } else {
        out.warnings.push("听力题目+答案缺失（pte 覆盖剑1–21，cam21 覆盖剑21，TaroFlink 覆盖剑16–20）");
      }
    }
  }

  /* ---- 听力原文（剑1–20；剑21 源暂无，属可选槽位） ---- */
  const sc = val(script);
  if (sc?.ok) {
    const t = sc.tests["test" + test] || {};
    out.parts.listening_script = { ok: true, source: sc.source, book, test, parts: Object.keys(t), text: t };
  } else if (out.parts.listening_transcript) {
    // cam21 的官方逐句原文同样满足「听力原文」槽位
    out.parts.listening_script = {
      ok: true, source: out.parts.listening_transcript.source, book, test,
      format: "transcript-lines",
      text: Object.fromEntries(out.parts.listening_transcript.sections.map((s) => [
        "section" + s.section,
        s.lines.map((l) => (l.speaker ? l.speaker + ": " : "") + l.text).join("\n"),
      ])),
      note: "由 cam21 官方逐句原文（含说话人与时间戳）拼装",
    };
  } else {
    out.warnings.push("听力原文缺失");
  }

  /* ---- 音频：双源冗余 ---- */
  const audioParts = [1, 2, 3, 4].map(p => listeningAudio(book, test, p));
  const pa = val(scriptFallback);
  out.parts.listening_audio = audioParts;
  if (pa?.ok && pa.url) out.parts.listening_audio_alt = { source: pa.source, url: pa.url };

  /* ---- 整本 PDF：优先 LFS 镜像（剑18/19/20），回落 zeeklog（剑4–18），剑21 用社区镜像 ---- */
  const lp = await pdfLfs(book).catch(() => null);
  if (lp?.ok) {
    out.parts.pdf = { ok: true, source: lp.source, book, url: lp.url, bytes: lp.bytes, note: lp.note };
  } else {
    const p = pdf(book);
    if (p.ok) out.parts.pdf = p;
    else if (book === 21) out.parts.pdf = pdf21();
  }
  if (book === 20) {
    const s = await book20Set().catch(() => null);
    if (s?.ok) out.parts.pdf_book20_tests = { ok: true, source: s.source, pdfs: s.pdfs, audio: s.audio };
  }

  out.sources_used = [...new Set(
    Object.values(out.parts)
      .flatMap(v => (Array.isArray(v) ? v.map(x => x.source) : [v.source]))
      .filter(Boolean)
  )];
  out.completeness = {
    reading: !!out.parts.reading,
    listening_qa: !!out.parts.listening_qa,
    listening_script: !!out.parts.listening_script,
    audio: audioParts.length === 4,
    pdf: !!out.parts.pdf,
  };
  out.score = Object.values(out.completeness).filter(Boolean).length + "/5";
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
