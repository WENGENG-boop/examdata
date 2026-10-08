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

// ---------------------------------------------------------------------------
// 详情 URL 严格解析与内容校验（安全边界，2026-10-05 修复）
// ---------------------------------------------------------------------------

/** 详情页路径：/detail/{read|listen|speak|write}/{hash}.html，可带单个数字后缀（实测仅 /1）。
 *  仅接受小写字母数字 hash；拒绝多余路径段、query、fragment。 */
const DETAIL_PATH_RE = /^\/detail\/(read|listen|speak|write)\/([a-z0-9]+)\.html(?:\/\d+)?$/;

/** 严格解析 kmf 详情页 URL。合法返回 {section, hash, pathname, url}，否则 null。
 *  只接受 https://toefl.kmf.com，禁止 userinfo、非默认端口、其它协议/域名/IP。 */
export function parseKmfDetailUrl(raw) {
  if (raw === undefined || raw === null) return null;
  const s = String(raw).trim();
  if (!s) return null;
  let u;
  try {
    u = new URL(s);
  } catch {
    return null;
  }
  if (u.protocol !== 'https:') return null;
  if (u.username || u.password) return null;
  if (u.hostname !== 'toefl.kmf.com') return null;
  if (u.port !== '') return null;
  if (u.search !== '') return null;
  if (u.hash !== '') return null;
  const m = DETAIL_PATH_RE.exec(u.pathname);
  if (!m) return null;
  return { section: m[1], hash: m[2], pathname: u.pathname, url: `https://toefl.kmf.com${u.pathname}` };
}

export function isKmfDetailUrl(raw) {
  return parseKmfDetailUrl(raw) !== null;
}

/** 把站内相对链接（tab href 等）解析为绝对 URL；不做合法性判断（调用方再校验）。 */
export function resolveKmfHref(href) {
  if (href === undefined || href === null) return null;
  const s = String(href).trim();
  if (!s) return null;
  if (/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(s) && !/^https?:/i.test(s)) return null;
  try {
    return new URL(s, KMF_BASE).href;
  } catch {
    return null;
  }
}

/** 重定向目标校验器：合法返回 null，非法返回原因字符串。每一跳都必须通过。 */
export function kmfRedirectValidator(target) {
  if (!parseKmfDetailUrl(target)) {
    return `仅允许跳转到 https://toefl.kmf.com/detail/{read|listen|speak|write}/{hash}.html`;
  }
  return null;
}

/** 详情页内容校验：确认页面含该科目必需的 DOM 结构，明显错误页（维护页/登录页/无题干）判失败。
 *  返回 {ok:true} 或 {ok:false, error}。 */
export function validateKmfContent(section, html) {
  const h = String(html || '');
  if (!h.trim()) return { ok: false, error: '页面内容为空' };
  if (section === 'read') {
    if (!/id="js-stem-cont"/.test(h)) return { ok: false, error: '缺少阅读原文容器（#js-stem-cont）' };
    if (!/class="inner js-translate-new" data-qid="\d+"/.test(h)) return { ok: false, error: '缺少题目容器（inner js-translate-new）' };
    if (!/g-hl-2/.test(h)) return { ok: false, error: '缺少答案标记（g-hl-2）' };
  } else if (section === 'listen') {
    if (!/class="question-cont js-translate-new" data-qid="\d+"/.test(h)) return { ok: false, error: '缺少题目容器（question-cont js-translate-new）' };
    if (!/data-href="\/detail\/listen\//.test(h)) return { ok: false, error: '缺少听力题目 tab（data-href=/detail/listen/）' };
    if (!/class="true-answer/.test(h)) return { ok: false, error: '缺少答案标记（true-answer）' };
  } else if (section === 'speak') {
    const m = /<p class="item-desc js-translate-new"[^>]*>([\s\S]*?)<\/p>/.exec(h);
    if (!m || normalize(htmlToText(m[1])).length < 10) return { ok: false, error: '缺少口语题干（item-desc 为空或过短）' };
  } else if (section === 'write') {
    const m = /<div class="content-subject js-translate-content"[^>]*>([\s\S]*?)<\/div>/.exec(h);
    if (!m || normalize(htmlToText(m[1])).length < 10) return { ok: false, error: '缺少写作题干（content-subject 为空或过短）' };
  } else {
    return { ok: false, error: `未知 section：${section}` };
  }
  return { ok: true };
}

export function pageCachePath(url) {
  const p = parseKmfDetailUrl(url);
  if (p) return path.join(KMF_PAGES_DIR, `${p.section}-${p.hash}.html`);
  const m = /\/detail\/(read|listen|speak|write)\/([a-z0-9]+)\.html/.exec(String(url));
  const key = m
    ? `${m[1]}-${m[2]}`
    : crypto.createHash('sha1').update(String(url)).digest('hex').slice(0, 16);
  return path.join(KMF_PAGES_DIR, `${key}.html`);
}

/** 抓单页（带磁盘缓存）。refresh=true 时强制重抓。
 *  安全顺序：先严格校验 URL（失败在读缓存之前返回）→ 读缓存（命中也要过内容校验）→
 *  联网（每一跳重定向先校验）→ 内容校验通过才写入缓存。 */
export async function fetchPage(url, { refresh = false, ttlMs = 30 * 24 * 3600 * 1000 } = {}) {
  const parsed = parseKmfDetailUrl(url);
  if (!parsed) {
    return {
      ok: false,
      url: String(url),
      error: `非法的详情页 URL（仅允许 https://toefl.kmf.com/detail/{read|listen|speak|write}/{hash}.html）：${String(url)}`,
    };
  }
  const file = pageCachePath(parsed.url);
  if (!refresh) {
    try {
      const st = fs.statSync(file);
      if (Date.now() - st.mtimeMs < ttlMs) {
        const body = fs.readFileSync(file, 'utf8');
        const v = validateKmfContent(parsed.section, body);
        if (!v.ok) {
          return { ok: false, url: parsed.url, status: 200, cached: true, error: `缓存内容校验失败：${v.error}` };
        }
        return {
          ok: true,
          status: 200,
          body,
          url: parsed.url,
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
    r = await httpGet(parsed.url, { timeoutMs: 25000, validateRedirect: kmfRedirectValidator });
  } catch (err) {
    return { ok: false, url: parsed.url, error: `请求失败：${String((err && err.message) || err)}` };
  }
  if (r.status !== 200) {
    return { ok: false, url: parsed.url, status: r.status, error: `HTTP ${r.status}` };
  }
  const v = validateKmfContent(parsed.section, r.body);
  if (!v.ok) {
    return { ok: false, url: parsed.url, status: 200, error: `内容校验失败：${v.error}` };
  }
  ensureDir(KMF_PAGES_DIR);
  fs.writeFileSync(file, r.body, 'utf8');
  return { ok: true, status: 200, body: r.body, url: parsed.url, cached: false, fetchedAt: new Date().toISOString() };
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
  const re = /<li class="normal[^"]*">\s*<div class="options-sn">\s*<span class="g-formbg g-(?:radio|checkbox)"><\/span>\s*([A-Z])\.?\s*<\/div>\s*([\s\S]*?)<\/li>/g;
  const out = [];
  for (const m of attrs(scope, re)) {
    out.push({ key: m[1], text: normalize(htmlToText(m[2])) });
  }
  return out;
}

/** 多选题（"Select the TWO answers"）用 answers-checkbox 表单；普通单选题用 answers-radio。 */
function isMultiSelectForm(html) {
  return /class="[^"]*answers-checkbox/.test(html);
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
  if (kind === 'listen') {
    // 听力答案在 span.true-answer 内直出；表格题答案带 &nbsp; 实体，先转文本再取字母。
    const m = /<span class="true-answer[^"]*"[^>]*>([\s\S]*?)<\/span>/.exec(html);
    if (!m) return null;
    const text = normalize(htmlToText(m[1]));
    const am = /正确答案[：:]\s*([A-Z][A-Z\s]*)/.exec(text);
    if (!am) return null;
    const letters = am[1].match(/[A-Z]+/g);
    return letters || null;
  }
  const m = /正确答案[：:]\s*<b class="g-hl-2">([\s\S]*?)<\/b>/.exec(html);
  if (!m) return null;
  const letters = normalize(m[1]).match(/[A-Z]+/g);
  return letters || null;
}

/** 听力表格题：table.content-logic，top-title 行为列名，main-list 行为待判断条目。
 *  无表格时返回 null。 */
function parseListenTable(html) {
  const tbl = /<table class="content-logic">([\s\S]*?)<\/table>/.exec(html);
  if (!tbl) return null;
  const inner = tbl[1];
  const columns = [];
  const head = /<tr class="top-title">([\s\S]*?)<\/tr>/.exec(inner);
  if (head) {
    for (const c of attrs(head[1], /<td[^>]*>([\s\S]*?)<\/td>/g)) {
      columns.push(normalize(htmlToText(c[1])));
    }
    while (columns.length && columns[0] === '') columns.shift();
  }
  const rows = [];
  for (const r of attrs(inner, /<tr class="main-list">([\s\S]*?)<\/tr>/g)) {
    const left = /<td class="main-list-left">([\s\S]*?)<\/td>/.exec(r[1]);
    if (!left) continue;
    const cells = attrs(r[1], /<td class="normal main-list-right">[\s\S]*?<\/td>/g).length;
    rows.push({ label: normalize(htmlToText(left[1])), cells });
  }
  if (!rows.length) return null;
  return { columns, rows };
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
    const answer = parseAnswerLetters(html, 'listen');
    const tableRaw = parseListenTable(html);
    let table = null;
    if (tableRaw) {
      const letters = Array.isArray(answer) ? answer : [];
      table = {
        columns: tableRaw.columns,
        rows: tableRaw.rows.map((r, i) => ({ label: r.label, answer: letters[i] ?? null })),
        answer_letters: letters.slice(),
      };
    }
    return {
      qid: m[1],
      type: table ? 'table_choice' : 'multiple_choice',
      stem: normalize(htmlToText(m[2])),
      insert_sentence: null,
      options: parseListenOptions(html),
      answer,
      analysis: parseAnalysis(html),
      audio_url: audio ? audio[1] : null,
      ...(table ? { table } : {}),
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
      ...(isMultiSelectForm(html) ? { multi_select: true } : {}),
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

/** 可作答内容缺口：按题型检查必要字段（与页级 complete 分开表达）。
 *  返回缺失项名称数组；空数组表示该题可作答内容完整。 */
function questionContentGaps(q) {
  const missing = [];
  if (q.type === 'table_choice') {
    const t = q.table;
    const columns = t && Array.isArray(t.columns) ? t.columns : [];
    const rows = t && Array.isArray(t.rows) ? t.rows : [];
    if (columns.length < 2) missing.push('table_columns');
    if (!rows.length) missing.push('table_rows');
    if (rows.some((r) => !r.label)) missing.push('table_row_label');
    const answers = Array.isArray(q.answer) ? q.answer : [];
    if (answers.length !== rows.length) missing.push('table_answer_count');
    else if (answers.some((a) => (a.charCodeAt(0) - 65) >= columns.length)) missing.push('table_answer_range');
  } else if (q.type === 'insert_sentence') {
    if (!q.insert_sentence) missing.push('insert_sentence');
    if (!q.answer || !q.answer.length) missing.push('answer');
  } else {
    if (!q.options || q.options.length < 2) missing.push('options');
    if (!q.answer || !q.answer.length) missing.push('answer');
    if (!q.stem) missing.push('stem');
  }
  return missing;
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
    const qUrl = resolveKmfHref(tab.href);
    if (!qUrl || !isKmfDetailUrl(qUrl)) {
      errors.push({ label: tab.label, url: String(tab.href), error: '题目链接非法（仅允许 kmf 详情页）' });
      continue;
    }
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
      ...(q.multi_select ? { multi_select: true } : {}),
      ...(q.table ? { table: q.table } : {}),
    });
  }

  const contentGaps = [];
  for (const q of questions) {
    const missing = questionContentGaps(q);
    if (missing.length) contentGaps.push({ qid: q.qid, label: q.label, type: q.type, missing });
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
      content_complete:
        questions.length === expected && errors.length === 0 && contentGaps.length === 0,
      questions,
      errors: errors.length ? errors : undefined,
      content_gaps: contentGaps.length ? contentGaps : undefined,
    },
  };
}
