/** jj.mjs — 考满分「机经真题」板块（/jj/order/27..30）索引、详情抓取与文本提取。
 *
 *  纯增量模块：不改变 kmf.mjs 既有解析路径。
 *  - 索引：data/jj-index.json（tools/build_jj_index.py 生成；325 条，含免费/锁定标记）。
 *    板块：27=阅读 read、28=听力 listen、29=口语 speak、30=写作 write；期数 batch 1..25。
 *  - 详情页缓存与 kmf 共用 .data/cache/kmf/pages（命名 {section}-{hash}.html），
 *    使 search 的 kmf-cache 源自动纳入机经内容。
 *  - read/listen 详情复用 kmf.fetchKmfSet（逐题解析）；speak/write 抓整页并提取文本
 *    （口语题干在 p.item-desc；写作范文在 good-composition-cont js-essay）。
 */
import fs from 'node:fs';
import path from 'node:path';
import { DATA_DIR, htmlToText, normalize, readJson } from './util.mjs';
import {
  fetchKmfSet,
  fetchPage,
  KMF_PAGES_DIR,
  pageCachePath,
  parseListenTabs,
  parseReadTabs,
} from './kmf.mjs';

export const JJ_SECTIONS = ['read', 'listen', 'speak', 'write'];
export const JJ_SECTION_LABEL = { read: 'reading', listen: 'listening', speak: 'speaking', write: 'writing' };

let _idx;
export function jj() {
  if (!_idx) _idx = readJson(path.join(DATA_DIR, 'jj-index.json'));
  return _idx;
}

export function jjItems() {
  return jj().items || [];
}

/** 从详情页 URL 提取 {section, hash}；不匹配返回 null。 */
export function jjHashOf(url) {
  const m = /\/detail\/(read|listen|speak|write)\/([a-z0-9]+)\.html/.exec(String(url || ''));
  return m ? { section: m[1], hash: m[2] } : null;
}

let _map;
/** 页面 hash -> jj 条目。含两类：索引内 213 条免费入口页 hash；
 *  以及已缓存入口页的逐题 tab hash（read/listen 反查，同 kmfHashMap 思路）。 */
export function jjHashMap() {
  if (_map) return _map;
  const map = new Map();
  for (const it of jjItems()) {
    const h = jjHashOf(it.url);
    if (h) map.set(h.hash, it);
  }
  for (const it of jjItems()) {
    if (it.locked || !it.url) continue;
    const h = jjHashOf(it.url);
    if (!h || (h.section !== 'read' && h.section !== 'listen')) continue;
    let html;
    try {
      html = fs.readFileSync(path.join(KMF_PAGES_DIR, `${h.section}-${h.hash}.html`), 'utf8');
    } catch {
      continue;
    }
    const tabs = h.section === 'listen' ? parseListenTabs(html) : parseReadTabs(html);
    for (const t of tabs) {
      const th = jjHashOf(t.href);
      if (th && !map.has(th.hash)) map.set(th.hash, it);
    }
  }
  _map = map;
  return map;
}

/** 条目所属套次 ID（机经期数），如 jj-25。 */
export function jjSetId(item) {
  return item && item.batch ? `jj-${item.batch}` : null;
}

/** 筛选/分页（CLI 用）。 */
export function jjList({ section, batch, free, locked, page = 1, pageSize = 50 } = {}) {
  let items = jjItems();
  if (section) items = items.filter((x) => x.section === section);
  if (batch !== undefined) items = items.filter((x) => x.batch === batch);
  if (free) items = items.filter((x) => !x.locked);
  if (locked) items = items.filter((x) => x.locked);
  const total = items.length;
  const start = (page - 1) * pageSize;
  return { total, page, page_size: pageSize, items: items.slice(start, start + pageSize) };
}

/** 免费条目入口页缓存统计。 */
export function jjCacheStats() {
  let entry = 0;
  let free = 0;
  for (const it of jjItems()) {
    if (it.locked || !it.url) continue;
    free += 1;
    const h = jjHashOf(it.url);
    if (h && fs.existsSync(path.join(KMF_PAGES_DIR, `${h.section}-${h.hash}.html`))) entry += 1;
  }
  let dirPages = 0;
  try {
    dirPages = fs.readdirSync(KMF_PAGES_DIR).filter((f) => f.endsWith('.html')).length;
  } catch {
    /* 目录不可读 */
  }
  return { entry_pages_cached: entry, free_items: free, dir: KMF_PAGES_DIR, dir_pages: dirPages };
}

/** 汇总视图（CLI jj 无参数时）。 */
export function jjSummary() {
  const d = jj();
  return {
    source: d.source,
    built_at: d.built_at,
    time_dimension: d.time_dimension,
    exam_form: d.exam_form,
    counts: d.counts,
    lock_note: d.lock_note,
    cache: jjCacheStats(),
  };
}

/** 抓取一条详情。
 *  read/listen：fetchKmfSet 全题解析（题干/选项/答案/原文），缓存逐题页；
 *  speak/write：抓整页，提取文本（+ 口语题干 / 写作范文 / 音频直链）。
 *  业务失败返回 {ok:false,error}。 */
export async function fetchJjDetail({ url, refresh = false } = {}) {
  const h = jjHashOf(url);
  if (!h) return { ok: false, error: `无法识别的详情页 URL：${url}` };
  const meta = jjHashMap().get(h.hash) || null;
  const base = {
    section: h.section,
    url,
    label: meta ? meta.label : null,
    batch: meta ? meta.batch : null,
    locked: meta ? meta.locked : null,
    jj_item: meta,
  };
  if (h.section === 'read' || h.section === 'listen') {
    const r = await fetchKmfSet({ url, section: h.section, refresh });
    if (!r.ok) return { ok: false, error: r.error, url };
    return {
      ok: true,
      ...base,
      label: base.label || r.set.label,
      cached_pages_dir: KMF_PAGES_DIR,
      set: r.set,
    };
  }
  const page = await fetchPage(url, { refresh });
  if (!page.ok) return { ok: false, error: page.error, url };
  const html = page.body;
  const audio = /data-url="(https?:\/\/[^"]+\.mp3)"/.exec(html);
  const out = {
    ok: true,
    ...base,
    cached_page: pageCachePath(url),
    audio_url: audio ? audio[1] : null,
    text: normalize(htmlToText(html)),
  };
  if (h.section === 'speak') {
    const q = /<p class="item-desc js-translate-new"[^>]*>([\s\S]*?)<\/p>/.exec(html);
    out.question = q ? normalize(htmlToText(q[1])) : null;
  } else if (h.section === 'write') {
    const essay = /<div class="good-composition-cont js-essay[^>]*>([\s\S]*?)<\/div>\s*<\/div>/.exec(html);
    out.essay = essay ? normalize(htmlToText(essay[1])) : null;
  }
  return out;
}
