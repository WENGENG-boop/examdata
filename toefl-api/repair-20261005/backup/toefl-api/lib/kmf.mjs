/** kmf.mjs — 考满分（toefl.kmf.com）题目页解析与抓取。
 *
 *  页面结构（2026-10 实测，样本见 probe/）：
 *  - 阅读入口页 /detail/read/{hash}.html：含整套文章原文（#js-stem-cont）、首题、
 *    以及 Q1..Qn 的 tab（<a class="question-link" href="/detail/read/{hash}.html/1">）。
 *    单题页与入口页同构，只是显示不同题目。
 *  - 听力入口页 /detail/listen/{hash}.html：含首题与 Q1..Qn 的 tab
 *    （<li data-qid data-href="/detail/listen/{hash}.html">Q1</li>），首题带 mp3 直链。
 *  - 答案在 DOM 中直出（无需登录）：阅读 <b class="g-hl-2">、听力
 *    <span class="true-answer">；官方解析有登录门槛，取不到时为 null。
 *
 *  抓取遵守 1 req/s 限速；页面缓存于 .data/cache/kmf/pages（不提交 git）。
 */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {
  CACHE_DIR,
  ensureDir,
  htmlToText,
  httpGet,
  normalize,
  sleep,
} from './util.mjs';

export const KMF_BASE = 'https://toefl.kmf.com';
export const KMF_CACHE_DIR = path.join(CACHE_DIR, 'kmf');
export const KMF_PAGES_DIR = path.join(KMF_CACHE_DIR, 'pages');

const THROTTLE_MS = 1100;
let lastFetchAt = 0;

async function throttle() {
  const wait = lastFetchAt + THROTTLE_MS - Date.now();
  if (wait > 0) await sleep(wait);
  lastFetchAt = Date.now();
}

export function pageCachePath(url) {
  const m = /\/detail\/(read|listen|speak|write)\/([a-z0-9]+)\.html/.exec(String(url));
  const key = m
    ? `${m[1]}-${m[2]}`
    : crypto.createHash('sha1').update(String(url)).digest('hex').slice(0, 16);
  return path.join(KMF_PAGES_DIR, `${key}.html`);
}

/** 抓单页（带磁盘缓存）。refresh=true 时强制重抓。 */
export async function fetchPage(url, { refresh = false, ttlMs = 30 * 24 * 3600 * 1000 } = {}) {
  const file = pageCachePath(url);
  if (!refresh) {
    try {
      const st = fs.statSync(file);
      if (Date.now() - st.mtimeMs < ttlMs) {
        return {
          ok: true,
          status: 200,
          body: fs.readFileSync(file, 'utf8'),
          url,
          cached: true,
          fetchedAt: new Date(st.mtimeMs).toISOString(),
        };
      }
    } catch {
      /* 无缓存 */
    }
  }
  await throttle();
  let r;
  try {
    r = await httpGet(url, { timeoutMs: 25000 });
  } catch (err) {
    return { ok: false, url, error: `请求失败：${String((err && err.message) || err)}` };
  }
  if (r.status !== 200) {
    return { ok: false, url, status: r.status, error: `HTTP ${r.status}` };
  }
  ensureDir(KMF_PAGES_DIR);
  fs.writeFileSync(file, r.body, 'utf8');
  return { ok: true, status: 200, body: r.body, url, cached: false, fetchedAt: new Date().toISOString() };
}

function attrs(html, re) {
  const out = [];
  let m;
  re.lastIndex = 0;
  while ((m = re.exec(html)) !== null) out.push(m);
  return out;
}

/** 套次标题（页面首个非空 i-title js-top-title），如 "Official 54 Passage 1"。 */
export function parseSetLabel(html) {
  const re = /<h4 class="i-title js-top-title">([\s\S]*?)<\/h4>/g;
  for (const m of attrs(html, re)) {
    const t = normalize(htmlToText(m[1]));
    if (t) return t;
  }
  return null;
}

function dedupeTabs(tabs) {
  const seen = new Set();
  const out = [];
  for (const t of tabs) {
    if (seen.has(t.qid)) continue;
    seen.add(t.qid);
    out.push(t);
  }
  return out;
}

/** 阅读 tab：Q1..Qn -> [{label, qid, href}]（页面顶部与主区各有一份，按 qid 去重） */
export function parseReadTabs(html) {
  const re = /data-qid="(\d+)"[^>]*>\s*<a\s+href="([^"]+)"\s+class="question-link">\s*(Q\d+)\s*<\/a>/g;
  const out = [];
  for (const m of attrs(html, re)) {
    out.push({ qid: m[1], href: m[2], label: m[3] });
  }
  return dedupeTabs(out);
}

/** 听力 tab：[{label, qid, href}]（同样两份，按 qid 去重） */
export function parseListenTabs(html) {
  const re = /data-qid="(\d+)"\s+data-href="([^"]+)">\s*(Q\d+)\s*<\/li>/g;
  const out = [];
  for (const m of attrs(html, re)) {
    out.push({ qid: m[1], href: m[2], label: m[3] });
  }
  return dedupeTabs(out);
}

/** 阅读文章原文（#js-stem-cont 内所有段落），取不到时 null。 */
export function parsePassage(html) {
  const m = /id="js-stem-cont">([\s\S]*?)<\/div>\s*<\/li>/.exec(html);
  if (!m) return null;
  const text = htmlToText(m[1]);
  return text || null;
}

function parseReadOptions(html) {
  const block = /<div class="question-form">([\s\S]*?)<\/ul>/.exec(html);
  const scope = block ? block[1] : html;
  const re = /<li class="normal[^"]*">\s*<div class="options-sn">\s*<span class="g-formbg g-radio"><\/span>\s*([A-Z])\.?\s*<\/div>\s*([\s\S]*?)<\/li>/g;
  const out = [];
  for (const m of attrs(scope, re)) {
    out.push({ key: m[1], text: normalize(htmlToText(m[2])) });
  }
  return out;
}

function parseListenOptions(html) {
  const re = /<li class="questions-list">\s*<p class="question-list-detail">\s*<span class="question-list-number">\s*([A-Z])\.\s*<\/span>\s*([\s\S]*?)<\/p>/g;
  const out = [];
  for (const m of attrs(html, re)) {
    out.push({ key: m[1], text: normalize(htmlToText(m[2])) });
  }
  return out;
}

function parseAnswerLetters(html, kind) {
  const re =
    kind === 'listen'
      ? /<span class="true-answer answer-hide">\s*正确答案[：:]\s*([A-Z][A-Z\s]*?)\s*<\/span>/
      : /正确答案[：:]\s*<b class="g-hl-2">([\s\S]*?)<\/b>/;
  const m = re.exec(html);
  if (!m) return null;
  const letters = normalize(m[1]).match(/[A-Z]+/g);
  return letters || null;
}

function parseAnalysis(html) {
  const m = /<div class="analytical-detail-cont[\s\S]*?">([\s\S]*?)<\/div>\s*<\/div>/.exec(html);
  if (!m) return null;
  const text = normalize(htmlToText(m[1]));
  if (!text || text.length < 40) return null;
  if (/^登录[\s\S]*官方解析/.test(text)) return null;
  return text;
}

/** 解析单题页。section: "read" | "listen"。解析不到题干时返回 null。 */
export function parseQuestion(html, section) {
  if (section === 'listen') {
    const m = /<div class="question-cont js-translate-new" data-qid="(\d+)">[\s\S]*?<div class="question-title">\s*([\s\S]*?)\s*<!--音频播放按钮-->/.exec(html);
    if (!m) return null;
    const audio = /data-url="(https?:\/\/[^"]+\.mp3)"/.exec(html);
    return {
      qid: m[1],
      type: 'multiple_choice',
      stem: normalize(htmlToText(m[2])),
      insert_sentence: null,
      options: parseListenOptions(html),
      answer: parseAnswerLetters(html, 'listen'),
      analysis: parseAnalysis(html),
      audio_url: audio ? audio[1] : null,
    };
  }
  const m = /<div class="inner js-translate-new" data-qid="(\d+)">\s*<h3 class="question-title">([\s\S]*?)<\/h3>/.exec(html);
  if (m) {
    return {
      qid: m[1],
      type: 'multiple_choice',
      stem: normalize(htmlToText(m[2])),
      insert_sentence: null,
      options: parseReadOptions(html),
      answer: parseAnswerLetters(html, 'read'),
      analysis: parseAnalysis(html),
      audio_url: null,
    };
  }
  // 插入句子题：无 h3；题干在 insert-article，待插入句在 insert-desc，答案为方块位置字母。
  const ins = /<div class="inner js-translate-new" data-qid="(\d+)">\s*<p class="insert-article">([\s\S]*?)<\/p>[\s\S]*?<p class="insert-desc">([\s\S]*?)<\/p>/.exec(html);
  if (ins) {
    return {
      qid: ins[1],
      type: 'insert_sentence',
      stem: normalize(htmlToText(ins[2])),
      insert_sentence: normalize(htmlToText(ins[3])),
      options: [],
      answer: parseAnswerLetters(html, 'read'),
      analysis: parseAnalysis(html),
      audio_url: null,
    };
  }
  return null;
}

function absUrl(href) {
  if (/^https?:\/\//.test(href)) return href;
  return KMF_BASE + (href.startsWith('/') ? href : `/${href}`);
}

/**
 * 抓取一整套（阅读一篇或听力一个 Set）的全部题目。
 * - entryUrl: 索引中的入口 URL
 * - limit: >0 时最多取前 N 题（含入口页自带的首题）
 * 业务失败返回 {ok:false,error}；部分题抓取失败返回 {ok:true,set:{complete:false,errors:[…]}}。
 */
export async function fetchKmfSet({ url, section, refresh = false, limit = 0, log = () => {} }) {
  if (!url) return { ok: false, error: '缺少 url' };
  if (section !== 'read' && section !== 'listen') {
    return { ok: false, error: `不支持的 section：${section}（仅 read/listen 有逐题内容）` };
  }
  const entry = await fetchPage(url, { refresh });
  if (!entry.ok) return { ok: false, error: `入口页抓取失败：${entry.error}`, url };

  const tabs = section === 'listen' ? parseListenTabs(entry.body) : parseReadTabs(entry.body);
  const label = parseSetLabel(entry.body);
  const entryQuestion = parseQuestion(entry.body, section);
  if (!tabs.length && !entryQuestion) {
    return { ok: false, error: '页面未包含题目标签，无法定位题目', url };
  }
  const effectiveTabs = tabs.length
    ? tabs
    : [{ qid: entryQuestion.qid, href: url, label: 'Q1' }];
  const wanted = limit > 0 ? effectiveTabs.slice(0, limit) : effectiveTabs;

  const questions = [];
  const errors = [];
  const seen = new Set();
  for (const tab of wanted) {
    const qUrl = absUrl(tab.href);
    if (seen.has(tab.qid)) continue;
    seen.add(tab.qid);
    let q = null;
    let from = 'entry';
    if (entryQuestion && entryQuestion.qid === tab.qid) {
      q = entryQuestion;
    } else {
      from = qUrl;
      const page = await fetchPage(qUrl, { refresh });
      log(`  ${tab.label} ${qUrl} ${page.ok ? 'ok' : 'FAIL'}`);
      if (!page.ok) {
        errors.push({ label: tab.label, url: qUrl, error: page.error });
        continue;
      }
      q = parseQuestion(page.body, section);
      if (!q) {
        errors.push({ label: tab.label, url: qUrl, error: '解析失败：未找到题干' });
        continue;
      }
    }
    questions.push({
      label: tab.label,
      qid: q.qid,
      url: qUrl,
      from,
      type: q.type,
      stem: q.stem,
      insert_sentence: q.insert_sentence ?? null,
      options: q.options,
      answer: q.answer,
      analysis: q.analysis,
      audio_url: q.audio_url,
    });
  }

  const audio = questions.find((q) => q.audio_url)?.audio_url || null;
  const passage = section === 'read' ? parsePassage(entry.body) : null;
  const expected = wanted.length;
  return {
    ok: true,
    set: {
      source: 'kmf',
      url,
      section,
      label,
      passage,
      audio_url: audio,
      expected,
      fetched: questions.length,
      complete: questions.length === expected && errors.length === 0,
      questions,
      errors: errors.length ? errors : undefined,
    },
  };
}
