#!/usr/bin/env node
/** prefetch_jj.mjs — 批量预抓取 jj 机经板块免费条目到本地缓存（1 req/s，可断点续跑）。
 *
 *  read/listen：fetchKmfSet（入口页 + 逐题页，含题干/选项/答案）；
 *  speak/write：抓入口整页（供 search 文本检索与详情提取）。
 *  页面写入 .data/cache/kmf/pages（与 kmf 同目录，search 的 kmf-cache 源自动纳入）。
 *
 *  用法：
 *    node tools/prefetch_jj.mjs --limit=2              # 烟测
 *    node tools/prefetch_jj.mjs                        # 全部免费条目（213）
 *    node tools/prefetch_jj.mjs --section=read         # 仅阅读
 *    node tools/prefetch_jj.mjs --start=50 --limit=20  # 续跑片段
 *
 *  进度写入 probe/prefetch_jj_status.json，逐条明细见 stdout 日志。
 */
import fs from 'node:fs';
import path from 'node:path';
import { fetchKmfSet, fetchPage } from '../lib/kmf.mjs';
import { ROOT, readJson } from '../lib/util.mjs';

const args = {};
for (const a of process.argv.slice(2)) {
  const m = /^--([A-Za-z0-9_-]+)(?:=(.*))?$/.exec(String(a));
  if (m) args[m[1]] = m[2] === undefined ? true : m[2];
}

const idx = readJson(path.join(ROOT, 'data', 'jj-index.json'));
let entries = (idx.items || []).filter((e) => !e.locked && e.url);
if (args.section) entries = entries.filter((e) => e.section === args.section);
const start = Number(args.start || 0);
if (args.limit) entries = entries.slice(start, start + Number(args.limit));
else entries = entries.slice(start);

const statusPath = path.join(ROOT, 'probe', 'prefetch_jj_status.json');
const startedAt = new Date().toISOString();
const status = {
  tool: 'prefetch_jj',
  started_at: startedAt,
  total: entries.length,
  done: 0,
  ok_items: 0,
  incomplete_sets: 0,
  failed_items: 0,
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
    if (e.section === 'read' || e.section === 'listen') {
      r = await fetchKmfSet({ url: e.url, section: e.section, limit: 0 });
    } else {
      const p = await fetchPage(e.url);
      r = p.ok ? { ok: true, page: true } : { ok: false, error: p.error };
    }
  } catch (err) {
    r = { ok: false, error: String((err && err.message) || err) };
  }
  status.done = i + 1;
  if (r.ok) {
    if (r.set) {
      status.questions_fetched += r.set.fetched;
      if (r.set.complete) status.ok_items += 1;
      else {
        status.incomplete_sets += 1;
        status.errors.push({ label: e.label, url: e.url, kind: 'incomplete', errors: r.set.errors || [] });
      }
    } else {
      status.ok_items += 1;
    }
  } else {
    status.failed_items += 1;
    status.errors.push({ label: e.label, url: e.url, kind: 'failed', error: r.error });
  }
  if (Date.now() - lastLog > 5000 || i === entries.length - 1 || !r.ok) {
    const mins = ((Date.now() - Date.parse(startedAt)) / 60000).toFixed(1);
    console.log(
      `[${status.done}/${status.total}] ${mins}min ok=${status.ok_items} inc=${status.incomplete_sets} fail=${status.failed_items} q=${status.questions_fetched} :: ${e.section} ${e.label}`,
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
      ok_items: status.ok_items,
      incomplete_sets: status.incomplete_sets,
      failed_items: status.failed_items,
      questions_fetched: status.questions_fetched,
      error_entries: status.errors.length,
    },
    null,
    1,
  ),
);
