#!/usr/bin/env node
/** prefetch_kmf_sw.mjs — 批量预抓取 kmf TPO Official 口语/写作详情页到本地缓存（1 req/s，可断点续跑）。
 *
 *  覆盖 data/kmf-index.json 中 section=speak|write 的全部条目（Official 1–54）。
 *  speak 页提取：题干（p.item-desc）+ 音频直链；write 页提取：整页文本（Task 1 含阅读/听力
 *  材料；Task 2 为题干；范文不内嵌，页面不提供即如实为空）。
 *  页面写入 .data/cache/kmf/pages（与 kmf/jj 同目录，search 的 kmf-cache 源自动纳入）。
 *
 *  用法：
 *    node tools/prefetch_kmf_sw.mjs --limit=2              # 烟测
 *    node tools/prefetch_kmf_sw.mjs                        # 全部 speak+write（308）
 *    node tools/prefetch_kmf_sw.mjs --section=speak        # 仅口语
 *    node tools/prefetch_kmf_sw.mjs --start=100 --limit=50 # 续跑片段
 *
 *  进度写入 probe/prefetch_kmf_sw_status.json，逐条明细见 stdout 日志与 status.items。
 */
import fs from 'node:fs';
import path from 'node:path';
import { fetchKmfDetail } from '../lib/detail.mjs';
import { ROOT, readJson } from '../lib/util.mjs';

const args = {};
for (const a of process.argv.slice(2)) {
  const m = /^--([A-Za-z0-9_-]+)(?:=(.*))?$/.exec(String(a));
  if (m) args[m[1]] = m[2] === undefined ? true : m[2];
}

const idx = readJson(path.join(ROOT, 'data', 'kmf-index.json'));
let entries = (idx.items || []).filter((e) => e.section === 'speak' || e.section === 'write');
if (args.section) entries = entries.filter((e) => e.section === args.section);
const start = Number(args.start || 0);
if (args.limit) entries = entries.slice(start, start + Number(args.limit));
else entries = entries.slice(start);

const statusPath = path.join(ROOT, 'probe', 'prefetch_kmf_sw_status.json');
const startedAt = new Date().toISOString();
const status = {
  tool: 'prefetch_kmf_sw',
  started_at: startedAt,
  total: entries.length,
  done: 0,
  ok_items: 0,
  empty_items: 0,
  failed_items: 0,
  question_extracted: 0,
  audio_found: 0,
  current: null,
  items: [],
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
    r = await fetchKmfDetail({ url: e.url });
  } catch (err) {
    r = { ok: false, error: String((err && err.message) || err) };
  }
  status.done = i + 1;
  const rec = { section: e.section, label: e.label, url: e.url };
  if (r.ok) {
    const textLen = (r.text || '').length;
    const hasQuestion = !!r.question;
    const hasAudio = !!r.audio_url;
    // 内容判定：speak 有题干或有实质文本；write 有实质文本（登录墙/空页文本极短）。
    const contentOk = e.section === 'speak' ? hasQuestion || textLen >= 300 : textLen >= 300;
    Object.assign(rec, {
      ok: contentOk,
      question: hasQuestion,
      audio: hasAudio,
      text_len: textLen,
      cached_page: r.cached_page ? path.basename(r.cached_page) : null,
    });
    if (contentOk) {
      status.ok_items += 1;
      if (hasQuestion) status.question_extracted += 1;
      if (hasAudio) status.audio_found += 1;
    } else {
      status.empty_items += 1;
      status.errors.push({ label: e.label, url: e.url, kind: 'empty', text_len: textLen });
    }
  } else {
    Object.assign(rec, { ok: false, error: r.error });
    status.failed_items += 1;
    status.errors.push({ label: e.label, url: e.url, kind: 'failed', error: r.error });
  }
  status.items.push(rec);
  if (Date.now() - lastLog > 5000 || i === entries.length - 1 || !rec.ok) {
    const mins = ((Date.now() - Date.parse(startedAt)) / 60000).toFixed(1);
    console.log(
      `[${status.done}/${status.total}] ${mins}min ok=${status.ok_items} empty=${status.empty_items} fail=${status.failed_items} q=${status.question_extracted} a=${status.audio_found} :: ${e.section} ${e.label}`,
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
      empty_items: status.empty_items,
      failed_items: status.failed_items,
      question_extracted: status.question_extracted,
      audio_found: status.audio_found,
      error_entries: status.errors.length,
    },
    null,
    1,
  ),
);
