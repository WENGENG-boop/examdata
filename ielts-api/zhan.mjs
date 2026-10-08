/**
 * zhan.mjs — 小站备考（top.zhan.com）剑20/21 阅读逐句中英对照
 *
 * 为什么重要：reader（userheyy/ielts-reader）只覆盖剑1–19，剑20/21 的
 * 「阅读精读（逐句中英对照）」此前为已知缺口。top.zhan.com 的 review 页面
 * 公开内嵌 data-translation 属性（无需登录），提供剑20/21 全部 24 篇
 * 阅读文章的逐句翻译。题目逐题解析需登录，不在本适配器范围内。
 *
 * 结构：
 *   索引页  /ielts/read/jianqiao-jian{21,37}.html
 *           → <h2>剑雅 20/21 – TestN</h2> 分组，卡片 data-ielts-row="sectionId"
 *   正文页  /ielts/read/review-{sectionId}-1-1.html
 *           → <span class="phase" data-translation="中文"><span class="text">English</span></span>
 */

const BASE = "https://top.zhan.com";
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36";

/** 剑桥 N → 索引页 slug（实测：剑20→jian21、剑21→jian37，URL 数字与册号不同） */
const INDEX_SLUG = { 20: "jianqiao-jian21", 21: "jianqiao-jian37" };

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

/** 索引页 → { test1: [sectionId...], ... }（每 Test 三个 Passage 按顺序）；opts.html 用于离线测试注入 */
export async function index(book, opts = {}) {
  const b = Number(book);
  const slug = INDEX_SLUG[b];
  if (!slug) return { ok: false, source: "top.zhan.com", book, error: "该源覆盖剑20/21（实测）" };
  const url = BASE + "/ielts/read/" + slug + ".html";
  let r;
  if (typeof opts.html === "string") r = { ok: true, status: 200, html: opts.html };
  else r = await get(url);
  if (!r.ok) return { ok: false, source: "top.zhan.com", book, url, error: r.error || "HTTP " + r.status };

  const tests = {};
  // 按 <h2>…TestN…</h2> 切段，段内取 data-ielts-row（保持文档顺序 = Passage 1..3）
  const parts = r.html.split(/<h2>[^<]*Test\s*(\d)[^<]*<\/h2>/i);
  for (let i = 1; i < parts.length; i += 2) {
    const t = Number(parts[i]);
    const seg = parts[i + 1] || "";
    const ids = [...seg.matchAll(/data-ielts-row="(\d+)"/g)].map(m => Number(m[1]));
    if (ids.length) tests["test" + t] = ids;
  }
  const total = Object.values(tests).reduce((n, a) => n + a.length, 0);
  if (!total) return { ok: false, source: "top.zhan.com", book, url, error: "index parse failed" };
  return {
    ok: true, source: "top.zhan.com", book, url, tests, total,
    answer_authority: false, close_reading: true,
    provenance: { source: "top.zhan.com", kind: "close_reading_translation" },
  };
}

/** review 页 → 逐句 [{en, zh}]（空占位段自动跳过）；opts.html 用于离线测试注入 */
export async function passage(sectionId, opts = {}) {
  const sid = Number(sectionId);
  if (!Number.isInteger(sid) || sid <= 0) return { ok: false, source: "top.zhan.com", error: "sectionId required" };
  const url = BASE + "/ielts/read/review-" + sid + "-1-1.html";
  let r;
  if (typeof opts.html === "string") r = { ok: true, status: 200, html: opts.html };
  else r = await get(url);
  if (!r.ok) return { ok: false, source: "top.zhan.com", section_id: sid, url, error: r.error || "HTTP " + r.status };

  const sentences = [];
  const re = /<span class="phase" data-translation="([^"]*)"><span class="text">([\s\S]*?)<\/span><\/span>/g;
  let m;
  while ((m = re.exec(r.html))) {
    const zh = decodeEntities(m[1]).replace(/\s+/g, " ").trim();
    const en = decodeEntities(m[2].replace(/<[^>]+>/g, " ")).replace(/\s+/g, " ").trim();
    if (!en && !zh) continue;
    sentences.push({ en, zh });
  }
  if (!sentences.length) return { ok: false, source: "top.zhan.com", section_id: sid, url, error: "no translation pairs found" };
  return {
    ok: true, source: "top.zhan.com", section_id: sid, url, sentences, count: sentences.length,
    answer_authority: false, close_reading: true,
    provenance: { source: "top.zhan.com", kind: "close_reading_translation" },
  };
}

/** 剑20/21 Test T Passage P 的逐句中英对照；opts.html 透传给 index/passage（离线测试） */
export async function reading(book, test, passageNo = 1, opts = {}) {
  const idx = await index(book, opts);
  if (!idx.ok) return idx;
  const ids = idx.tests["test" + Number(test)] || [];
  const sid = ids[Number(passageNo) - 1];
  if (!sid) return { ok: false, source: "top.zhan.com", book, test, passage: passageNo, error: "no such passage（test 1–4 × passage 1–3）" };
  const p = await passage(sid, opts);
  if (!p.ok) return { ...p, book, test, passage: passageNo };
  return { ...p, book, test, passage: passageNo };
}

/** 覆盖自检：剑20/21 各 Test 的 section 数 */
export async function coverage() {
  const out = {};
  for (const b of [20, 21]) {
    const idx = await index(b);
    out[b] = idx.ok ? Object.fromEntries(Object.entries(idx.tests).map(([k, v]) => [k, v.length])) : 0;
  }
  const ok = out[20] && out[21];
  return { ok: !!ok, source: "top.zhan.com", coverage: out, note: "每 Test 3 篇 Passage（剑20/21 各 12 篇）" };
}

/** 内部函数（测试用） */
export const __internals = { decodeEntities };
