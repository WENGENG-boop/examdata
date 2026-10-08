#!/usr/bin/env node
/** prefetch_kmf.mjs — 批量预抓取 kmf 阅读/听力逐题页到本地缓存（1 req/s，可断点续跑）。
 *
 * 用法：
 *   node tools/prefetch_kmf.mjs --limit=2                 # 烟测
 *   node tools/prefetch_kmf.mjs                           # 全量 read+listen
 *   node tools/prefetch_kmf.mjs --section=read            # 仅阅读
 *   node tools/prefetch_kmf.mjs --start=100 --limit=50    # 续跑片段
 *
 * 说明：复用 lib/kmf.mjs 的 fetchKmfSet（内含 1.1s 限速与 30 天页面缓存），
 * 页面写入 .data/cache/kmf/pages（gitignore，版权内容不入 git）。
 * 进度写入 probe/prefetch_kmf_status.json，逐条明细见 stdout 日志。
 */
import fs from 'node:fs';
import path from 'node:path';
import { fetchKmfSet } from '../lib/kmf.mjs';
import { ROOT, readJson } from '../lib/util.mjs';

const args = {};
for (const a of process.argv.slice(2)) {
  const m = /^--([A-Za-z0-9_-]+)(?:=(.*))?$/.exec(String(a));
  if (m) args[m[1]] = m[2] === undefined ? true : m[2];
}

const idx = readJson(path.join(ROOT, 'data', 'kmf-index.json'));
const all = Array.isArray(idx)
  ? idx
  : [idx.entries, idx.items, ...Object.values(idx)].find(
      (v) => Array.isArray(v) && v.some((x) => x && typeof x === 'object' && 'section' in x),
    );
if (!Array.isArray(all)) {
  console.error('无法在 kmf-index.json 中定位条目数组');
  process.exit(2);
}

let entries = all.filter((e) => e.section === 'read' || e.section === 'listen');
if (args.section) entries = entries.filter((e) => e.section === args.section);
const start = Number(args.start || 0);
if (args.limit) entries = entries.slice(start, start + Number(args.limit));
else entries = entries.slice(start);

const statusPath = path.join(ROOT, 'probe', 'prefetch_kmf_status.json');
const startedAt = new Date().toISOString();
const status = {
  tool: 'prefetch_kmf',
  started_at: startedAt,
  total: entries.length,
  done: 0,
  ok_sets: 0,
  incomplete_sets: 0,
  failed_sets: 0,
  questions_fetched: 0,
  current: null,
  errors: [],
  finished_at: null,
};

function saveStatus() {
  fs.mkdirSync(path.dirname(statusPath), { recursive: true });
  fs.writeFileSync(statusPath, JSON.stringify(status, null, 1));
}

saveStatus();
let lastLog = 0;

for (let i = 0; i < entries.length; i++) {
  const e = entries[i];
  status.current = { i: i + 1, section: e.section, label: e.label, url: e.url };
  let r;
  try {
    r = await fetchKmfSet({ url: e.url, section: e.section, limit: 0 });
  } catch (err) {
    r = { ok: false, error: String((err && err.message) || err) };
  }
  status.done = i + 1;
  if (r.ok) {
    status.questions_fetched += r.set.fetched;
    if (r.set.complete) status.ok_sets += 1;
    else {
      status.incomplete_sets += 1;
      status.errors.push({ label: e.label, url: e.url, kind: 'incomplete', errors: r.set.errors || [] });
    }
  } else {
    status.failed_sets += 1;
    status.errors.push({ label: e.label, url: e.url, kind: 'failed', error: r.error });
  }
  if (Date.now() - lastLog > 5000 || i === entries.length - 1 || !r.ok) {
    const mins = ((Date.now() - Date.parse(startedAt)) / 60000).toFixed(1);
    console.log(
      `[${status.done}/${status.total}] ${mins}min ok=${status.ok_sets} inc=${status.incomplete_sets} fail=${status.failed_sets} q=${status.questions_fetched} :: ${e.section} ${e.label}`,
    );
    lastLog = Date.now();
  }
  if (status.done % 10 === 0) saveStatus();
}

status.finished_at = new Date().toISOString();
status.current = null;
saveStatus();
console.log(
  JSON.stringify(
    {
      done: status.done,
      ok_sets: status.ok_sets,
      incomplete_sets: status.incomplete_sets,
      failed_sets: status.failed_sets,
      questions_fetched: status.questions_fetched,
      error_entries: status.errors.length,
    },
    null,
    1,
  ),
);
