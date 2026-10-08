/** search.mjs — 关键词检索。
 *
 *  检索面（可用 --sources 选择）：
 *  - ddy-ddy   ：TPO 30–54 结构化阅读全文（标题+段落，实时拉取分片）
 *  - find-similar-tpo：已缓存到本地的 FindSimilarTPO 原文文件（不为搜索全量抓取；
 *                     未缓存的文件在结果中记 uncached，可用 questions/raw 命令补齐）
 *  - kmf-index ：考满分索引的标签（Official n Passage/Set/Q/Task）
 *  - kmf-cache ：已抓取到本地的考满分题目页内容（题干/选项/原文）
 *
 *  返回每条 {source, set_id, section, item, field, count, snippet, url?}。
 */
import fs from 'node:fs';
import path from 'node:path';
import { countOccurrences, htmlToText, normalize, snippet } from './util.mjs';
import { coverage, kmf } from './catalog.mjs';
import { jjHashMap, jjSetId, JJ_SECTION_LABEL } from './jj.mjs';
import { KMF_CACHE_DIR, KMF_PAGES_DIR, parseListenTabs, parseQuestion, parseReadTabs, parseSetLabel } from './kmf.mjs';
import { ddyFullText, findSimilarFullText, loadDdySets, parseFindSimilar, RAW_DIR } from './sources.mjs';

const SOURCE_IDS = ['ddy-ddy', 'find-similar-tpo', 'kmf-index', 'kmf-cache'];

function setOf(official) {
  return `tpo-${Number(official)}`;
}

function searchDdy(query, hits, stats) {
  return loadDdySets().then(({ items, errors }) => {
    stats.files_errors = errors;
    stats.items = items.length;
    for (const it of items) {
      const text = ddyFullText(it);
      const { count, first } = countOccurrences(text, query);
      if (count) {
        const tpo = Number(String(it.id).split('-')[1]);
        hits.push({
          source: 'ddy-ddy',
          set_id: `tpo-${tpo}`,
          ddy_id: it.id,
          tpo,
          section: 'reading',
          item: it.title,
          field: 'article',
          count,
          snippet: snippet(text, first),
          url: it.link || null,
        });
      }
    }
  });
}

function searchFindSimilar(query, hits, stats) {
  const dir = path.join(RAW_DIR, 'find-similar-tpo');
  stats.files_cached = 0;
  stats.files_uncached = [];
  if (!fs.existsSync(dir)) {
    stats.files_uncached = coverage().items.filter((x) => x.present).map((x) => x.file);
    return;
  }
  const cached = new Set(fs.readdirSync(dir).filter((f) => f.endsWith('.txt')));
  for (const it of coverage().items) {
    if (!it.present) continue;
    if (!cached.has(it.file)) {
      stats.files_uncached.push(it.file);
      continue;
    }
    stats.files_cached += 1;
    const parsed = parseFindSimilar(it.file, fs.readFileSync(path.join(dir, it.file), 'utf8'));
    const text = findSimilarFullText(parsed);
    const { count, first } = countOccurrences(text, query);
    if (count) {
      hits.push({
        source: 'find-similar-tpo',
        set_id: `tpo-${String(it.tpo).padStart(2, '0')}`,
        tpo: it.tpo,
        section: it.section === 'reading' ? 'reading' : 'listening',
        item: it.item,
        field: parsed.kind === 'reading' ? 'title+paragraphs' : parsed.segments.length ? 'segments' : 'paragraphs',
        count,
        snippet: snippet(text, first),
        url: parsed.kind === 'reading' ? null : null,
        file: it.file,
      });
    }
  }
}

function searchKmfIndex(query, hits, stats) {
  const items = kmf().items;
  stats.items = items.length;
  for (const it of items) {
    const { count, first } = countOccurrences(it.label, query);
    if (count) {
      hits.push({
        source: 'kmf-index',
        set_id: setOf(it.official),
        tpo: it.official,
        section: { read: 'reading', listen: 'listening', speak: 'speaking', write: 'writing' }[it.section],
        item: it.label,
        field: 'label',
        count,
        snippet: snippet(it.label, first),
        url: it.url,
      });
    }
  }
}

function pageHash(file) {
  return file.replace(/\.html$/, '').replace(/^(read|listen|speak|write)-/, '');
}

function hrefHash(href) {
  const m = /\/detail\/(?:read|listen|speak|write)\/([a-z0-9]+)\.html/.exec(String(href));
  return m ? m[1] : null;
}

let _hashMap = null;

/** 页面 hash -> kmf 索引条目。索引含四科入口页 hash（speak/write 每条即入口页）；
 *  read/listen 逐题页 hash 通过已缓存入口页的 tab 反查。 */
function kmfHashMap() {
  if (_hashMap) return _hashMap;
  const map = new Map();
  for (const it of kmf().items) {
    const h = hrefHash(it.url);
    if (h) map.set(h, it);
  }
  try {
    for (const f of fs.readdirSync(KMF_PAGES_DIR)) {
      if (!f.endsWith('.html')) continue;
      const entryItem = map.get(pageHash(f));
      if (!entryItem) continue; // 只把「入口页」当作反查依据
      const html = fs.readFileSync(path.join(KMF_PAGES_DIR, f), 'utf8');
      const tabs = f.startsWith('listen-')
        ? parseListenTabs(html)
        : f.startsWith('read-')
          ? parseReadTabs(html)
          : []; // speak/write 无逐题页
      for (const t of tabs) {
        const th = hrefHash(t.href);
        if (th && !map.has(th)) map.set(th, entryItem);
      }
    }
  } catch {
    /* 缓存目录不可读时忽略 */
  }
  _hashMap = map;
  return map;
}

function kmfMetaForPage(hash, html) {
  const direct = kmfHashMap().get(hash);
  if (direct) return direct;
  const label = parseSetLabel(html);
  if (label) {
    const byLabel = kmf().items.find((x) => x.label === label);
    if (byLabel) return byLabel;
  }
  return null;
}

/** 解析文本侧车缓存目录（.data/cache/kmf/text/*.txt），避免每次检索重解析整页 HTML。 */
const KMF_TEXT_DIR = path.join(KMF_CACHE_DIR, 'text');

function kmfPageText(file) {
  const htmlPath = path.join(KMF_PAGES_DIR, file);
  const textPath = path.join(KMF_TEXT_DIR, `${file.replace(/\.html$/, '')}.txt`);
  try {
    if (fs.statSync(textPath).mtimeMs >= fs.statSync(htmlPath).mtimeMs) {
      return fs.readFileSync(textPath, 'utf8');
    }
  } catch {
    /* 无侧车缓存或已过期 */
  }
  const text = normalize(htmlToText(fs.readFileSync(htmlPath, 'utf8')));
  try {
    fs.mkdirSync(KMF_TEXT_DIR, { recursive: true });
    fs.writeFileSync(textPath, text, 'utf8');
  } catch {
    /* 写失败不影响检索 */
  }
  return text;
}

function searchKmfCache(query, hits, stats) {
  stats.pages = 0;
  stats.unmapped_pages = [];
  if (!fs.existsSync(KMF_PAGES_DIR)) return;
  for (const f of fs.readdirSync(KMF_PAGES_DIR)) {
    if (!f.endsWith('.html')) continue;
    stats.pages += 1;
    const section = f.startsWith('listen-')
      ? 'listen'
      : f.startsWith('speak-')
        ? 'speak'
        : f.startsWith('write-')
          ? 'write'
          : 'read';
    const text = kmfPageText(f);
    const { count, first } = countOccurrences(text, query);
    if (!count) continue;
    const html = fs.readFileSync(path.join(KMF_PAGES_DIR, f), 'utf8');
    const hash = pageHash(f);
    const meta = kmfMetaForPage(hash, html);
    const jjMeta = meta ? null : jjHashMap().get(hash) || null;
    if (!meta && !jjMeta) stats.unmapped_pages.push(f);
    const q = parseQuestion(html, section);
    hits.push({
      source: 'kmf-cache',
      set_id: meta ? setOf(meta.official) : jjMeta ? jjSetId(jjMeta) : null,
      tpo: meta ? meta.official : null,
      section: JJ_SECTION_LABEL[section],
      item: meta ? meta.label : jjMeta ? jjMeta.label : f,
      field: q ? `q${q.qid}` : 'page',
      count,
      snippet: snippet(text, first),
      url: meta ? meta.url : jjMeta ? jjMeta.url : null,
      page: f,
    });
  }
}

/**
 * 关键词检索。sources 为 null 时用全部；query 为空返回 ok:false。
 */
export async function search(query, { sources = null, limit = 20 } = {}) {
  const q = normalize(query || '');
  if (!q) return { ok: false, error: '缺少查询关键词（--q=...）' };
  let picked = SOURCE_IDS;
  if (sources && sources.length) {
    picked = SOURCE_IDS.filter((s) => sources.includes(s));
    const unknown = sources.filter((s) => !SOURCE_IDS.includes(s));
    if (unknown.length) {
      return { ok: false, error: `未知 source：${unknown.join(',')}（可用 ${SOURCE_IDS.join('/')}）` };
    }
  }
  const hits = [];
  const stats = {};
  const tasks = {
    'ddy-ddy': () => searchDdy(q, hits, (stats['ddy-ddy'] = {})),
    'find-similar-tpo': () => searchFindSimilar(q, hits, (stats['find-similar-tpo'] = {})),
    'kmf-index': () => searchKmfIndex(q, hits, (stats['kmf-index'] = {})),
    'kmf-cache': () => searchKmfCache(q, hits, (stats['kmf-cache'] = {})),
  };
  for (const s of picked) await tasks[s]();
  hits.sort((a, b) => b.count - a.count || String(a.source).localeCompare(String(b.source)));
  return {
    ok: true,
    query: q,
    sources_searched: picked,
    sources_stats: stats,
    total_matches: hits.length,
    returned: Math.min(limit, hits.length),
    hits: hits.slice(0, limit),
  };
}

export { SOURCE_IDS };
