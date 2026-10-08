/** sources.mjs — 两个 GitHub 公开源的拉取与解析。
 *
 *  - FindSimilarTPO（SAOHPRWHG/FindSimilarTPO）：TPO 阅读原文与听力原文（无题无答案）。
 *    文件名：<n>-<k>.txt 阅读、L<n>-<k>.txt 讲座、C<n>-<k>.txt 对话。
 *    格式：阅读 = 首行标题 + 空行分段；讲座/对话出现说话人标签行时切分为 segments，
 *    否则为纯段落。
 *  - ddy-ddy/TOEFL-TPO：TPO 30–54 结构化阅读（id/title/link/article[]，全量文本）。
 *
 *  全部原始文件缓存于 .data/cache/raw（不提交 git）。抓取缓慢节流，失败不伪造。
 */
import fs from 'node:fs';
import path from 'node:path';
import { CACHE_DIR, ensureDir, httpGet, normalize, sleep } from './util.mjs';
import { coverage, ddy } from './catalog.mjs';

export const RAW_DIR = path.join(CACHE_DIR, 'raw');
export const FS_BASE = 'https://raw.githubusercontent.com/SAOHPRWHG/FindSimilarTPO/master/data/TPO/';
export const DDY_BASE = 'https://raw.githubusercontent.com/ddy-ddy/TOEFL-TPO/master/data/json/';
export const DDY_FILES = ['tpo-30-35.json', 'tpo-36-40.json', 'tpo-41-45.json', 'tpo-46-50.json', 'tpo-51-54.json'];

const RAW_TTL_MS = 30 * 24 * 3600 * 1000;

/** 抓原始文件（带磁盘缓存）。rel 形如 "find-similar-tpo/1-1.txt"。 */
export async function fetchCached(rel, url, { refresh = false, ttlMs = RAW_TTL_MS } = {}) {
  const file = path.join(RAW_DIR, rel);
  if (!refresh) {
    try {
      const st = fs.statSync(file);
      if (Date.now() - st.mtimeMs < ttlMs) {
        return { ok: true, body: fs.readFileSync(file, 'utf8'), cached: true, file, fetchedAt: new Date(st.mtimeMs).toISOString() };
      }
    } catch {
      /* 无缓存 */
    }
  }
  await sleep(700 + Math.random() * 400);
  let r;
  try {
    r = await httpGet(url, { timeoutMs: 30000 });
  } catch (err) {
    return { ok: false, url, error: `请求失败：${String((err && err.message) || err)}` };
  }
  if (r.status !== 200) return { ok: false, url, status: r.status, error: `HTTP ${r.status}` };
  ensureDir(path.dirname(file));
  fs.writeFileSync(file, r.body, 'utf8');
  return { ok: true, body: r.body, cached: false, file, fetchedAt: new Date().toISOString() };
}

const SPEAKER_RX = /^[A-Z][A-Z .'()-]{1,40}$/;

export function looksLikeSpeaker(block) {
  const b = normalize(block);
  if (!b || b.length > 40) return false;
  if (!SPEAKER_RX.test(b)) return false;
  if (/[.!?;:,'"]$/.test(b)) return false;
  return b.split(/\s+/).length <= 4;
}

export function detectKind(file) {
  if (/^L/i.test(file)) return 'lecture';
  if (/^C/i.test(file)) return 'conversation';
  return 'reading';
}

/** 解析 FindSimilarTPO 原文文件 -> {kind, title, paragraphs, segments, chars} */
export function parseFindSimilar(file, text) {
  const kind = detectKind(file);
  const clean = String(text).replace(/\r\n/g, '\n').replace(/\u00a0/g, ' ').trim();
  const blocks = clean
    .split(/\n\s*\n/)
    .map((b) => normalize(b))
    .filter(Boolean);
  const result = { kind, title: null, paragraphs: [], segments: [], chars: clean.length };
  if (!blocks.length) return result;

  if (kind === 'reading') {
    result.title = blocks[0];
    result.paragraphs = blocks.slice(1);
    return result;
  }

  const speakerMode = looksLikeSpeaker(blocks[0]);
  if (!speakerMode) {
    result.paragraphs = blocks;
    return result;
  }
  let current = null;
  for (const block of blocks) {
    if (looksLikeSpeaker(block)) {
      current = { speaker: block, text: '' };
      result.segments.push(current);
    } else if (current) {
      current.text = current.text ? `${current.text}\n${block}` : block;
    } else {
      result.segments.push({ speaker: null, text: block });
    }
  }
  result.paragraphs = result.segments.map((s) => s.text);
  return result;
}

export function findSimilarFullText(parsed) {
  if (!parsed) return '';
  const parts = [];
  if (parsed.title) parts.push(parsed.title);
  parts.push(...(parsed.paragraphs || []));
  return parts.join('\n\n');
}

/** 覆盖清单（离线，来自 data/coverage.json）。 */
export function findSimilarIndex() {
  const cov = coverage();
  return cov.items.map((it) => ({
    tpo: it.tpo,
    section: it.section,
    item: it.item,
    file: it.file,
    present: it.present,
    chars: it.chars,
    url: it.present ? FS_BASE + it.file : null,
  }));
}

/** 拉取某套 TPO 的全部 FindSimilarTPO 文件并解析（按需，网络+缓存）。 */
export async function loadFindSimilarTpo(tpo, { refresh = false, presentOnly = true } = {}) {
  const items = findSimilarIndex().filter((x) => x.tpo === tpo && (!presentOnly || x.present));
  const out = [];
  const errors = [];
  for (const it of items) {
    const r = await fetchCached(`find-similar-tpo/${it.file}`, FS_BASE + it.file, { refresh });
    if (!r.ok) {
      errors.push({ file: it.file, error: r.error });
      out.push({ ...it, ok: false, error: r.error });
      continue;
    }
    out.push({ ...it, ok: true, cached: r.cached, parsed: parseFindSimilar(it.file, r.body) });
  }
  return { tpo, items: out, fetched: out.filter((x) => x.ok).length, expected: items.length, errors };
}

/** 拉取单个 FindSimilarTPO 文件（CLI get 用）。 */
export async function loadFindSimilarFile(file, { refresh = false } = {}) {
  const meta = findSimilarIndex().find((x) => x.file === file);
  const r = await fetchCached(`find-similar-tpo/${file}`, FS_BASE + file, { refresh });
  if (!r.ok) return { ok: false, error: r.error, file };
  const parsed = parseFindSimilar(file, r.body);
  return { ok: true, file, url: FS_BASE + file, meta: meta || null, cached: r.cached, parsed };
}

/** ddy-ddy 结构化阅读：拉取 5 个分片并合并（网络+缓存）。 */
export async function loadDdySets({ refresh = false } = {}) {
  const items = [];
  const errors = [];
  const files = [];
  for (const f of DDY_FILES) {
    const r = await fetchCached(`ddy-ddy/${f}`, DDY_BASE + f, { refresh });
    if (!r.ok) {
      errors.push({ file: f, error: r.error });
      files.push({ file: f, ok: false, error: r.error });
      continue;
    }
    let arr;
    try {
      arr = JSON.parse(r.body);
    } catch (err) {
      const error = `JSON 解析失败：${String((err && err.message) || err)}`;
      errors.push({ file: f, error });
      files.push({ file: f, ok: false, error });
      continue;
    }
    for (const x of arr) items.push(x);
    files.push({ file: f, ok: true, cached: r.cached, count: arr.length });
  }
  return { items, errors, files, fetched_files: files.filter((x) => x.ok).length, total_files: DDY_FILES.length };
}

export function ddyIndex() {
  return ddy();
}

export async function loadDdyItem(id, { refresh = false } = {}) {
  const { items, errors } = await loadDdySets({ refresh });
  const found = items.find((x) => x.id === id);
  if (!found) return { ok: false, error: `未找到 ddy 条目：${id}`, errors: errors.length ? errors : undefined };
  return { ok: true, item: { id: found.id, title: found.title, link: found.link, paragraphs: (found.article || []).length, chars: (found.article || []).join('').length, article: found.article } };
}

export function ddyFullText(item) {
  return [item.title, ...(item.article || [])].join('\n\n');
}
