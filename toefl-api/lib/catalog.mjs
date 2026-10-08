/** catalog.mjs — 目录模型：把三份索引合并成「套次（TPO）」视图与筛选、覆盖统计。 */
import fs from 'node:fs';
import path from 'node:path';
import { DATA_DIR, readJson } from './util.mjs';
import { pageCachePath } from './kmf.mjs';

let _cov, _ddy, _kmf;

export function coverage() {
  if (!_cov) _cov = readJson(path.join(DATA_DIR, 'coverage.json'));
  return _cov;
}
export function ddy() {
  if (!_ddy) _ddy = readJson(path.join(DATA_DIR, 'ddy-index.json'));
  return _ddy;
}
export function kmf() {
  if (!_kmf) _kmf = readJson(path.join(DATA_DIR, 'kmf-index.json'));
  return _kmf;
}

export function eras() {
  return [
    { id: 'tpo-01-10', tpo_min: 1, tpo_max: 10 },
    { id: 'tpo-11-20', tpo_min: 11, tpo_max: 20 },
    { id: 'tpo-21-30', tpo_min: 21, tpo_max: 30 },
    { id: 'tpo-31-40', tpo_min: 31, tpo_max: 40 },
    { id: 'tpo-41-50', tpo_min: 41, tpo_max: 50 },
    { id: 'tpo-51-54', tpo_min: 51, tpo_max: 54 },
  ];
}

export function eraOf(n) {
  const e = eras().find((x) => n >= x.tpo_min && n <= x.tpo_max);
  return e ? e.id : null;
}

export function tpoRange() {
  const ks = Object.keys(perOfficial());
  return { min: Math.min(...ks.map(Number)), max: Math.max(...ks.map(Number)) };
}

let _per;
export function perOfficial() {
  if (_per) return _per;
  _per = {};
  const touch = (n) => (_per[n] = _per[n] || { reading: 0, listening: 0, speaking: 0, writing: 0 });
  for (const it of coverage().items) {
    if (it.present) {
      const sec = it.section === 'reading' ? 'reading' : 'listening';
      touch(it.tpo)[sec] += 1;
    }
  }
  for (const it of ddy().items) {
    const n = Number(String(it.id).split('-')[1]);
    touch(n).reading_ddy = (touch(n).reading_ddy || 0) + 1;
  }
  for (const it of kmf().items) {
    const sec = { read: 'reading', listen: 'listening', speak: 'speaking', write: 'writing' }[it.section];
    touch(it.official)[sec] += 1;
  }
  return _per;
}

function kmfBy(section, official) {
  return kmf().items.filter((x) => x.section === section && x.official === official);
}

const fsKeys = { reading: {}, listening: {} };
function fsBy(tpo) {
  const key = `t${tpo}`;
  if (!fsKeys.reading[key]) {
    fsKeys.reading[key] = coverage().items.filter((x) => x.tpo === tpo && x.section === 'reading');
    fsKeys.listening[key] = coverage().items.filter((x) => x.tpo === tpo && x.section === 'listening');
  }
  return { reading: fsKeys.reading[key], listening: fsKeys.listening[key] };
}

export function buildSet(tpo) {
  const fs = fsBy(tpo);
  const ddyItems = ddy().items.filter((x) => String(x.id).startsWith(`tpo-${tpo}-`));
  const ddyBy = {};
  for (const d of ddyItems) ddyBy[Number(String(d.id).split('-')[2])] = d;

  const readingItems = fs.reading.map((it) => {
    const k = Number(String(it.item).split('-')[1]);
    const d = ddyBy[k];
    const kk = kmfBy('read', tpo).find((x) => x.label === `Official ${tpo} Passage ${k}`);
    const out = {
      item: it.item,
      title: d ? d.title : null,
      title_source: d ? 'ddy-ddy' : null,
      content: { 'find-similar-tpo': { present: it.present, chars: it.chars, file: it.file } },
    };
    if (d) out.content['ddy-ddy'] = { present: true, paragraphs: d.paragraphs, chars: d.chars };
    if (kk) out.kmf = { label: kk.label, url: kk.url };
    return out;
  });

  const listeningItems = fs.listening.map((it) => ({
    item: it.item,
    content: { 'find-similar-tpo': { present: it.present, chars: it.chars, file: it.file } },
  }));

  const section = (items, extra) => ({ items, kmf_extra: extra });
  const sections = {
    reading: section(readingItems, []),
    listening: section(listeningItems, kmfBy('listen', tpo).map((x) => ({ label: x.label, url: x.url }))),
    speaking: section([], kmfBy('speak', tpo).map((x) => ({ label: x.label, url: x.url }))),
    writing: section([], kmfBy('write', tpo).map((x) => ({ label: x.label, url: x.url }))),
  };

  const src = new Set();
  for (const it of [...readingItems, ...listeningItems]) {
    if (it.content['find-similar-tpo']?.present) src.add('find-similar-tpo');
    if (it.content['ddy-ddy']?.present) src.add('ddy-ddy');
  }
  for (const sec of Object.values(sections)) if (sec.kmf_extra.length) src.add('kmf');
  if (readingItems.some((x) => x.kmf)) src.add('kmf');

  return {
    set_id: `tpo-${tpo}`,
    exam_family: 'tpo',
    tpo,
    era: eraOf(tpo),
    exam_date: null,
    exam_date_note: 'TPO 无官方逐年发布日；以编号与编号分区表达时间维度',
    sections,
    sources: [...src].sort(),
  };
}

export function hasAny(tpo) {
  const p = perOfficial()[tpo];
  if (!p) return false;
  return Object.values(p).some((v) => v > 0);
}

export function listSets({ tpo, tpoMin, tpoMax, era, section, page = 1, pageSize = 20 } = {}) {
  const range = tpoRange();
  let ns = [];
  for (let n = range.min; n <= range.max; n++) if (hasAny(n)) ns.push(n);
  if (tpo !== undefined) ns = ns.filter((n) => n === tpo);
  if (tpoMin !== undefined) ns = ns.filter((n) => n >= tpoMin);
  if (tpoMax !== undefined) ns = ns.filter((n) => n <= tpoMax);
  if (era !== undefined) ns = ns.filter((n) => eraOf(n) === era);
  ns.sort((a, b) => b - a);
  const total = ns.length;
  const start = (page - 1) * pageSize;
  const slice = ns.slice(start, start + pageSize);
  const sets = slice.map((n) => {
    const s = buildSet(n);
    if (section) {
      const pick = { [section]: s.sections[section] };
      if (!pick[section]) throw new Error(`未知 section：${section}（可用 reading/listening/speaking/writing）`);
      s.sections = pick;
    }
    return s;
  });
  return { total, page, page_size: pageSize, tpo_range: range, sets };
}

export function coverageSummary() {
  const cov = coverage();
  const k = kmf();
  const per = perOfficial();
  const officials = Object.keys(per).map(Number).sort((a, b) => a - b);
  const compact = {};
  for (const n of officials) {
    const p = per[n];
    compact[n] = { read: p.reading, listen: p.listening, speak: p.speaking, write: p.writing };
  }
  const kmfCounts = {};
  for (const it of k.items) kmfCounts[it.section] = (kmfCounts[it.section] || 0) + 1;
  const sw = k.items.filter((x) => x.section === 'speak' || x.section === 'write');
  const swCached = {
    indexed: sw.length,
    cached: sw.filter((x) => fs.existsSync(pageCachePath(x.url))).length,
    note: 'speaking/writing 索引条目的本地缓存页计数（detail 抓取产物）',
  };
  return {
    sources: {
      'find-similar-tpo': {
        counts: cov.counts,
        empty_tpos: cov.empty_tpos,
        duplicates: cov.duplicates,
        duplicates_count: Object.keys(cov.duplicates).length,
        raw_base: cov.raw_base,
        content: cov.content_type,
      },
      'ddy-ddy': {
        counts: ddy().counts,
        content: ddy().content_type,
        raw_base: ddy().raw_base,
      },
      kmf: {
        counts: kmfCounts,
        officials_covered: k.officials_covered,
        content: 'metadata index only（题目/答案按需实时抓取并本地缓存）',
        speaking_writing_cached: swCached,
      },
    },
    per_official: compact,
    notes: [
      'kmf 索引仅含标签与 URL；题目/答案在 questions 命令按需抓取。',
      'Official 26/31 在所有主张源中缺失。',
      'FindSimilarTPO 存在 6 组重复内容（见 duplicates）。',
      'speaking/writing 内容用 detail 命令抓取；speaking_writing_cached 为索引条目中已有本地缓存页的数量。',
    ],
  };
}
