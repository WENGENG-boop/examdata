/**
 * iprog.mjs — ieltsprogress.com 答案源
 *
 * 为什么重要：practicepteonline 未发布剑3 听力 Test 2–4（hub 只挂 Test 1），
 * 导致此前听力答案覆盖停在 81/84。ieltsprogress.com 提供剑3 听力 T1–T4
 * 全套 40 题答案键（免费公开，无需登录），补上最后 3 个缺口。
 *
 * 实测（2026-10）：仅剑3 听力系列存在；剑1/2/4/10/20/21 与剑3 阅读均无对应页面。
 *
 * 页面结构：答案在 <figure class="wp-block-table"><table><td> 单元格内，
 * 以 <br> 分隔的 "N. value" 列表（40 条，个别条目混有 <meta charset> 残留）。
 */

const BASE = "https://ieltsprogress.com";
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36";

function decodeEntities(s) {
  return s
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(Number(d)))
    .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"').replace(/&apos;|&#39;|&rsquo;|&#8217;/g, "'");
}

async function get(url, retries = 3) {
  let lastErr;
  for (let i = 0; i < retries; i++) {
    try {
      const r = await fetch(url, {
        headers: { "user-agent": UA, accept: "text/html,*/*" },
        redirect: "follow",
        signal: AbortSignal.timeout(30000),
      });
      if (r.status >= 500 && i < retries - 1) { await new Promise(s => setTimeout(s, 400 * (i + 1))); continue; }
      return { ok: r.ok, status: r.status, html: await r.text() };
    } catch (e) { lastErr = e; if (i < retries - 1) await new Promise(s => setTimeout(s, 500 * (i + 1))); }
  }
  return { ok: false, status: -1, error: String(lastErr && lastErr.message || lastErr), html: "" };
}

/** 从页面所有 <td> 中挑出题号最多的单元格，解析为按题号 1..40 的答案数组 */
function extractAnswerTable(html) {
  const cells = [...html.matchAll(/<td[^>]*>([\s\S]*?)<\/td>/gi)].map(m => m[1]);
  let best = null, bestN = 0;
  for (const c of cells) {
    const text = c.replace(/<br\s*\/?>/gi, "\n").replace(/<[^>]+>/g, "");
    const lines = text.split("\n").map(s => s.trim()).filter(Boolean);
    let n = 0;
    for (const ln of lines) if (/^\d{1,2}\.\s*\S/.test(ln)) n++;
    if (n > bestN) { bestN = n; best = lines; }
  }
  if (bestN < 20) return [];
  const map = new Map();
  for (const ln of best) {
    const m = /^(\d{1,2})\.\s*([\s\S]*)$/.exec(ln);
    if (!m) continue;
    const n = Number(m[1]);
    const v = decodeEntities(m[2]).trim();
    if (n >= 1 && n <= 40 && v && !map.has(n)) map.set(n, v);
  }
  const out = [];
  for (let i = 1; i <= 40; i++) if (map.has(i)) out[i - 1] = map.get(i);
  return out;
}

/** 剑3 听力 T1–T4 答案键（该源实测仅覆盖剑3 听力） */
export async function listeningAnswers(book, test) {
  const b = Number(book), t = Number(test);
  if (!Number.isInteger(b) || !Number.isInteger(t) || b !== 3 || t < 1 || t > 4) {
    return { ok: false, source: "ieltsprogress.com", book, test, error: "该源仅覆盖剑3 听力 T1–T4" };
  }
  const slug = "cambridge-ielts-3-listening-test-" + t + "-answers";
  const url = BASE + "/" + slug + "/";
  const r = await get(url);
  if (!r.ok) return { ok: false, source: "ieltsprogress.com", book, test, url, error: r.error || "HTTP " + r.status };
  const answers = extractAnswerTable(r.html);
  if (!answers.length) return { ok: false, source: "ieltsprogress.com", book, test, url, error: "no answer table found" };
  return {
    ok: true, source: "ieltsprogress.com", book, test, url,
    title: "Cambridge 3 Listening Test " + t + " Answers",
    answer_key: answers, answer_count: answers.length,
    note: "仅答案键；题干与原文请配合 practicepteonline / reader 源使用",
  };
}

/** 覆盖自检：剑3 听力 T1–T4 四套答案键 */
export async function coverage() {
  const books = {};
  for (let t = 1; t <= 4; t++) {
    const r = await listeningAnswers(3, t);
    books["3-" + t] = r.ok ? r.answer_count : 0;
  }
  const total = Object.values(books).reduce((a, b) => a + b, 0);
  return { ok: true, source: "ieltsprogress.com", coverage: books, total_answers: total, tests_covered: Object.values(books).filter(Boolean).length + "/4" };
}
