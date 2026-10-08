/**
 * pte.mjs — practicepteonline.com 源适配器（WordPress REST API）
 *
 * 为什么重要：这是目前唯一同时提供 **剑16–剑20 阅读+听力题目 + 40 题标准答案 + 音频** 的源，
 * 直接补上了此前「剑20 阅读」的缺口。
 *
 * 接口：/wp-json/wp/v2/pages?slug=SLUG&_fields=id,slug,title,content
 * 答案藏在页面 HTML 的 <div id='bg-showmore-hidden-*'> 内的 <ol><li> 列表里。
 */

const BASE = "https://practicepteonline.com";
const API = BASE + "/wp-json/wp/v2/pages";
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36";

/** 剑桥 N → 站点 hub 页面 ID（剑1–剑21，全部实测定位） */
export const HUBS = {
  1: 9322, 2: 9330, 3: 9341, 4: 9349, 5: 9357, 6: 9365, 7: 9374,
  8: 9382, 9: 9390, 10: 9404, 11: 9452, 12: 9463, 13: 7025, 14: 7051,
  15: 9314, 16: 9291, 17: 9277, 18: 9263, 19: 9255, 20: 12381, 21: 12724,
};

/** hub 页 slug（当数字 ID 失效时按 slug 回落查询） */
export const HUB_SLUGS = {
  1: "official-ielts-tests-book-1", 2: "official-ielts-tests-book-2", 3: "official-ielts-tests-book-3",
  4: "official-ielts-tests-book-4", 5: "official-ielts-tests-book-5", 6: "official-ielts-tests-book-6",
  7: "official-ielts-tests-book-7", 8: "official-ielts-tests-book-8", 9: "official-ielts-tests-book-9",
  10: "official-ielts-tests-book-10", 11: "official-ielts-tests-book-11", 12: "official-ielts-tests-book-12",
  13: "official-ielts-tests-book-13", 14: "official-ielts-tests-book-14", 15: "official-ielts-tests-book-15",
  16: "official-ielts-tests-book-16", 17: "official-ielts-tests-book-17", 18: "official-ielts-tests-book-18",
  19: "official-ielts-book-19", 20: "official-ielts-tests-book-20", 21: "official-ielts-tests-book-21",
};

/** 已知兜底：hub 页缺失 Academic Reading 链接时用（实测确认） */
const FALLBACK = {
  20: {
    reading: { 1: "ielts-reading-test-310", 2: "ielts-reading-test-311", 3: "ielts-reading-test-312", 4: "ielts-reading-test-313" },
  },
  21: {
    reading: { 1: "ielts-reading-test-316", 2: "ielts-reading-test-317", 3: "ielts-reading-test-318", 4: "ielts-reading-test-319" },
    listening: { 1: "ielts-listening-test-205", 2: "ielts-listening-test-206", 3: "ielts-listening-test-207", 4: "ielts-listening-test-208" },
  },
};

async function fetchJson(url, retries = 3) {
  let lastErr;
  for (let i = 0; i < retries; i++) {
    try {
      const r = await fetch(url, { headers: { "user-agent": UA, accept: "application/json" }, signal: AbortSignal.timeout(30000) });
      if (!r.ok) return { ok: false, status: r.status, error: "HTTP " + r.status };
      return { ok: true, status: r.status, body: await r.json() };
    } catch (e) { lastErr = e; if (i < retries - 1) await new Promise(s => setTimeout(s, 500 * (i + 1))); }
  }
  return { ok: false, status: -1, error: String(lastErr && lastErr.message || lastErr) };
}

const bySlug = (slug) => fetchJson(API + "?slug=" + encodeURIComponent(slug) + "&_fields=id,slug,title,content");
const byId = (id) => fetchJson(API + "/" + id + "?_fields=id,slug,title,content");

/* ------------------------------- HTML 工具 -------------------------------- */

/** 保留块级结构的纯文本化 */
function toText(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(p|div|li|tr|h[1-6]|td)>/gi, "\n")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&#8217;|&rsquo;|&#39;/g, "'")
    .replace(/&#8211;|&ndash;/g, "-").replace(/&quot;/g, '"').replace(/&#8216;|&lsquo;/g, "'")
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/[ \t\u00a0]+/g, " ")
    .replace(/\n{2,}/g, "\n")
    .trim();
}

/** 提取 40 题标准答案（顺序即题号 1..40）
 *  站点有两种排布：
 *   (A) <ol><li>False</li>...</ol>             → 直接按 <li> 顺序
 *   (B) <p>1. Egg<br /> 2. Tower<br />...</p>  → 解析 "N. value" 键值对
 */
function extractAnswers(html) {
  const m = /bg-showmore-hidden-[^'"]*['"][^>]*>([\s\S]*?)<\/div>/i.exec(html);
  if (!m) return [];
  const block = m[1];

  // 形态 A：有序列表
  const li = [...block.matchAll(/<li[^>]*>([\s\S]*?)<\/li>/gi)]
    .map(x => toText(x[1]).replace(/\s+/g, " ").trim())
    .filter(Boolean);
  if (li.length >= 10) return li;

  // 形态 B：编号段落 "1. x 2. y"。按 "N." 标记切分取值（值可空：源站存在 "34." 空值，不能吞掉下一题 "35."）
  // 标记要求点号后是空白或结尾，避免把 "3.5" 这类小数当成题号
  const text = toText(block).replace(/\s+/g, " ");
  const toks = [...text.matchAll(/(?:^|\s)(\d{1,2})\s*[.\uFF0E](?=\s|$)/g)];
  const pairs = [];
  for (let i = 0; i < toks.length; i++) {
    const n = Number(toks[i][1]);
    const start = toks[i].index + toks[i][0].length;
    const end = i + 1 < toks.length ? toks[i + 1].index : text.length;
    const v = text.slice(start, end).trim().replace(/[\s;]+$/, "");
    if (n >= 1 && n <= 40 && v.length < 120) pairs.push({ n, v });
  }
  if (pairs.filter(p => p.v).length >= 10) {
    const map = new Map();
    for (const p of pairs) if (p.v && !map.has(p.n)) map.set(p.n, p.v);
    const out = [];
    for (let i = 1; i <= 40; i++) if (map.has(i)) out[i - 1] = map.get(i);
    return out;
  }
  return li;
}

/** 提取逐题解析（"Question 1. ..." 段落） */
function extractExplanations(html) {
  const i = html.search(/Explanations\s*:/i);
  if (i < 0) return {};
  const txt = toText(html.slice(i));
  const out = {};
  const re = /Question\s+(\d{1,2})\s*[\.\):]?\s*([\s\S]*?)(?=Question\s+\d{1,2}\s*[\.\):]|$)/gi;
  let m;
  while ((m = re.exec(txt))) {
    const n = Number(m[1]);
    const body = m[2].replace(/\s+/g, " ").trim();
    if (body.length > 20) out[n] = body.slice(0, 1200);
  }
  return out;
}

/** 提取页面内嵌音频（相对路径补全） */
function extractAudio(html) {
  const urls = [...html.matchAll(/<audio[^>]*>[\s\S]*?<source[^>]*src=["']([^"']+)["']/gi)].map(m => m[1]);
  urls.push(...[...html.matchAll(/src=["']([^"']*\.mp3[^"']*)["']/gi)].map(m => m[1]));
  return [...new Set(urls)].map(u => u.startsWith("http") ? u : BASE + u.replace(/\?.*$/, ""));
}

/** 截掉 "Show Answers" 按钮及其后的答案区（防止答案表混入题干） */
function questionsOnly(html) {
  const cut = html.search(/bg-showmore-action|Show Answers/i);
  return cut > 0 ? html.slice(0, cut) : html;
}

/** 提取题干。四种排布（同一题号取最先命中者）：
 *   (A) "12. prompt text"          → 数字+点号，同一行内跟题干
 *   (D) "28…….prompt text"         → 数字后跟省略号/连续点号
 *   (B) "…(7) ____" 内嵌占位符     → 填空题（题号在句中）
 *   (C) "12 prompt text"           → 数字后直接空格+题干（站点常见，无点号）
 */
function extractQuestions(text) {
  const out = [];
  const seen = new Set();
  const push = (n, prompt) => {
    if (n < 1 || n > 40 || seen.has(n)) return;
    const p = (prompt || "").replace(/\s+/g, " ").trim();
    if (!p || p.length < 2) return;
    seen.add(n);
    out.push({ number: n, prompt: p.slice(0, 400) });
  };

  // 形态 A：行首 "N. prompt"（点号后限同一行，避免把下一行当成题干）
  const reA = /(?:^|\n)[ \t]*(\d{1,2})[ \t]*[.．)）][ \t]*([^\n]{2,400})/g;
  let m;
  while ((m = reA.exec(text))) push(Number(m[1]), m[2]);

  // 形态 D：行首 "N…….prompt"（省略号或连续点号）
  const reD = /(?:^|\n)[ \t]*(\d{1,2})[.．…]{2,}[ \t]*([^\n]{2,400})/g;
  while ((m = reD.exec(text))) push(Number(m[1]), m[2]);

  // 形态 B：句中 "(N)" 占位符，取所在行作为题干
  const reB = /\((\d{1,2})\)/g;
  while ((m = reB.exec(text))) {
    const n = Number(m[1]);
    if (seen.has(n)) continue;
    const lineStart = text.lastIndexOf("\n", m.index) + 1;
    let lineEnd = text.indexOf("\n", m.index);
    if (lineEnd < 0) lineEnd = text.length;
    push(n, text.slice(lineStart, lineEnd).replace(/\(\d{1,2}\)/g, "[$&]"));
  }

  // 形态 C：行首 "N prompt"（无点号）
  const reC = /(?:^|\n)[ \t]*(\d{1,2})[ \t]+([^\n]{2,400})/g;
  while ((m = reC.exec(text))) push(Number(m[1]), m[2]);

  return out.sort((a, b) => a.number - b.number);
}

/** 提取题型指令（"Complete the notes below..." / "Choose the correct letter..."） */
function extractInstructions(text) {
  const pats = [
    /Do the following statements agree[\s\S]{0,220}?NOT GIVEN[^\n]{0,60}/gi,
    /Complete the (?:notes|summary|table|sentences|flow-chart|form)[^\n]{0,200}/gi,
    /Choose the correct letter[^\n]{0,120}/gi,
    /Choose (?:ONE|TWO|NO MORE THAN [A-Z]+)[^\n]{0,140}/gi,
    /Match each [^\n]{0,160}/gi,
    /Label the [^\n]{0,160}/gi,
    /Answer the questions below[^\n]{0,120}/gi,
  ];
  const out = [];
  for (const p of pats) for (const m of text.matchAll(p)) {
    const s = m[0].replace(/\s+/g, " ").trim();
    if (s.length > 8 && !out.includes(s)) out.push(s);
  }
  return out.slice(0, 12);
}

/** 阅读原文正文（截取 Reading Passage 之前的段落） */
function extractPassage(html) {
  const cut = html.search(/Questions?\s+1\s*[-–]/i);
  const body = cut > 0 ? html.slice(0, cut) : html;
  const paras = [...body.matchAll(/<p[^>]*>([\s\S]*?)<\/p>/gi)]
    .map(m => toText(m[1]).replace(/\s+/g, " ").trim())
    .filter(t => t.length > 80 && !/cookie|advertisement|subscribe|share this/i.test(t));
  return paras;
}

/* -------------------------------- 对外接口 -------------------------------- */

/** hub 页 → { reading: {test: slug}, listening: {test: slug} } */
export async function bookTests(book) {
  const id = HUBS[book];
  const reading = {}, listening = {};
  let title = null;

  if (id) {
    let r = await byId(id);
    let page = Array.isArray(r.body) ? r.body[0] : r.body;
    // 数字 ID 失效时按 slug 回落
    if (!page && HUB_SLUGS[book]) {
      const s = await bySlug(HUB_SLUGS[book]);
      page = Array.isArray(s.body) ? s.body[0] : s.body;
    }
    if (page) {
      title = page.title?.rendered;
      const c = page.content?.rendered || "";
      // Academic / General 分开收集，阅读槽位优先 Academic，General 仅补空缺
      const academic = {}, general = {};
      let aIdx = 0, gIdx = 0, lIdx = 0;
      // 窗口 200：剑21 hub 的链接内 HTML 长 98–105 字符，80 会漏配（2026-10 实测）
      for (const m of c.matchAll(/href=["']([^"']+)["'][^>]*>([\s\S]{0,200}?)<\/a>/gi)) {
        const url = m[1].replace(/^https?:\/\/practicepteonline\.com/, "").replace(/\/$/, "");
        const label = toText(m[2]).replace(/\s+/g, " ").trim();
        const rl = /(?:ielts-)?reading-test-([\w-]+)/i.exec(url);
        const ll = /(?:ielts-)?listening-(?:test-)?(\d+)/i.exec(url);
        // 标签形如 "Academic Reading Test 18.1" / "Listening 13.1" / "LISTENING TEST 1"
        const dotted = label.match(/(\d+)\.(\d+)\s*$/);
        const plain = label.match(/(\d+)\s*$/);
        const tail = dotted ? Number(dotted[2]) : plain ? Number(plain[1]) : NaN;
        const idx = Number.isFinite(tail) && tail >= 1 && tail <= 4 ? tail : null;
        const slug = url.replace(/^\/+/, "");
        if (rl && /reading/i.test(label)) {
          if (/general/i.test(label)) general[idx ?? ++gIdx] = slug;
          else academic[idx ?? ++aIdx] = slug;
        } else if (ll && /listening/i.test(label)) {
          listening[idx ?? ++lIdx] = slug;
        }
      }
      Object.assign(reading, academic);
      for (const k of Object.keys(general)) if (!reading[k]) reading[k] = general[k];
      reading.general = general;
    }
  }

  // hub 页缺 Academic Reading / Listening 链接时的兜底（剑20、剑21 实测需要）
  // 注意：只有当前槽位是 General（或为空）时才覆盖为 Academic
  const fb = FALLBACK[book];
  if (fb) {
    const hasAcademic = Object.keys(reading).some(k => /^\d+$/.test(k) && !/general/i.test(reading[k]));
    if (!hasAcademic && fb.reading) {
      for (const [t, slug] of Object.entries(fb.reading)) reading[Number(t)] = slug;
    }
    const hasListen = Object.keys(listening).some(k => /^\d+$/.test(k));
    if (!hasListen && fb.listening) {
      for (const [t, slug] of Object.entries(fb.listening)) listening[Number(t)] = slug;
    }
  }

  const ok = Object.keys(reading).length > 0 || Object.keys(listening).length > 0;
  return { ok, source: "practicepteonline.com", book, hub_id: id || null, title, reading, listening };
}

/** questions 里缺失的题号（1..40，源站组合题不单独编号时会出现） */
function missingNumbers(questions) {
  const have = new Set(questions.map(q => q.number));
  const miss = [];
  for (let i = 1; i <= 40; i++) if (!have.has(i)) miss.push(i);
  return miss;
}

/** 阅读：原文 + 题目 + 答案 + 解析 */
export async function readingTest(book, test) {
  const bt = await bookTests(book);
  const slug = bt.reading?.[test];
  if (!slug) return { ok: false, source: "practicepteonline.com", error: "no reading test " + test + " for book " + book, available: Object.keys(bt.reading || {}) };

  const r = await bySlug(slug);
  if (!r.ok || !r.body?.[0]) return { ok: false, source: "practicepteonline.com", error: r.error || "slug not found: " + slug };

  const page = r.body[0];
  const html = page.content?.rendered || "";
  const answers = extractAnswers(html);
  const text = toText(html);
  const questions = extractQuestions(toText(questionsOnly(html)));

  // 答案按序对应题号 1..40
  const merged = questions.map(q => ({
    number: q.number,
    prompt: q.prompt,
    answer: answers[q.number - 1] ?? null,
    explanation: null,
  }));
  const explanations = extractExplanations(html);
  for (const q of merged) if (explanations[q.number]) q.explanation = explanations[q.number];

  return {
    ok: true, source: "practicepteonline.com", book, test, slug,
    page_id: page.id, title: page.title?.rendered, url: BASE + "/" + slug + "/",
    passage: extractPassage(html),
    instructions: extractInstructions(text),
    questions: merged,
    answer_key: answers,
    answer_count: answers.length,
    question_count: merged.length,
    questions_missing: missingNumbers(merged),
  };
}

/** 听力：题目 + 答案 + 音频 */
export async function listeningTest(book, test) {
  const bt = await bookTests(book);
  const slug = bt.listening?.[test];
  if (!slug) return { ok: false, source: "practicepteonline.com", error: "no listening test " + test + " for book " + book, available: Object.keys(bt.listening || {}) };

  const r = await bySlug(slug);
  if (!r.ok || !r.body?.[0]) return { ok: false, source: "practicepteonline.com", error: r.error || "slug not found: " + slug };

  const page = r.body[0];
  const html = page.content?.rendered || "";
  const answers = extractAnswers(html);
  const text = toText(html);
  const questions = extractQuestions(toText(questionsOnly(html)));
  const explanations = extractExplanations(html);

  const merged = questions.map(q => ({
    number: q.number, prompt: q.prompt,
    answer: answers[q.number - 1] ?? null,
    explanation: explanations[q.number] || null,
  }));

  return {
    ok: true, source: "practicepteonline.com", book, test, slug,
    page_id: page.id, title: page.title?.rendered, url: BASE + "/" + slug + "/",
    audio: extractAudio(html),
    instructions: extractInstructions(text),
    questions: merged,
    answer_key: answers,
    answer_count: answers.length,
    question_count: merged.length,
    questions_missing: missingNumbers(merged),
  };
}

/** 仅要音频直链 */
export async function audio(book, test) {
  const r = await listeningTest(book, test);
  return { ok: r.ok, source: "practicepteonline.com", book, test, url: r.audio?.[0] || null, all: r.audio || [], error: r.error };
}

/** 覆盖自检：剑10–20 每本的 reading/listening 数量 */
/** 只统计数字槽位（排除 general 等元数据键） */
const countSlots = (o) => Object.keys(o || {}).filter(k => /^\d+$/.test(k)).length;

/**
 * 源侧已知数据缺口（非代码缺陷，均经实测确认）：
 *  - 剑3 听力 T2–T4：hub 页只挂了 1 套（test-59），其余 3 套站点未发布；
 *    答案键已由 ieltsprogress.com 兜底补齐（见 iprog.mjs），题目原文由 reader 逐句时间轴提供
 *  - 剑1 T2 听力：答案页只有 39 条（官方书该套为 41 题，站点缺第 40–41 题）
 *  - 剑21：听力/阅读已覆盖，但站点无 Academic 链接，靠 FALLBACK 补齐
 */
export const KNOWN_GAPS = {
  listening: {
    "3-2": "practicepteonline 未发布（hub 仅挂 test-59）；答案键由 ieltsprogress.com 兜底",
    "3-3": "practicepteonline 未发布（hub 仅挂 test-59）；答案键由 ieltsprogress.com 兜底",
    "3-4": "practicepteonline 未发布（hub 仅挂 test-59）；答案键由 ieltsprogress.com 兜底",
  },
  partial_answers: { "listening/1-2": "答案页仅 39 条（官方书该套 41 题，缺第 40–41 题）" },
};

export async function coverage() {
  const out = {};
  const books = Object.keys(HUBS).map(Number);
  const results = await Promise.all(books.map(async (b) => [b, await bookTests(b)]));
  for (const [b, bt] of results) {
    out[b] = {
      reading: countSlots(bt.reading),
      listening: countSlots(bt.listening),
      general_reading: countSlots(bt.reading?.general),
    };
  }
  const totalR = Object.values(out).reduce((s, x) => s + x.reading, 0);
  const totalL = Object.values(out).reduce((s, x) => s + x.listening, 0);
  return {
    ok: true, source: "practicepteonline.com",
    total_reading: totalR, total_listening: totalL,
    known_gaps: KNOWN_GAPS,
    books: out,
  };
}
