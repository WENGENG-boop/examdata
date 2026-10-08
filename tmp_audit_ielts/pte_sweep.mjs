#!/usr/bin/env node
/**
 * pte_sweep.mjs — 独立审查：practicepteonline 适配器 84 套全覆盖复现
 *
 * 只读脚本：不修改被测项目任何文件。
 * 运行：node C:/Users/weo/Desktop/api/tmp_audit_ielts/pte_sweep.mjs
 * 输出：pte_sweep.json（全量原始数据 + summary） / pte_sweep.log（进度）
 */

import { writeFileSync, appendFileSync } from "node:fs";
import { pteReading, pteListening, pteBook } from "file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs";

const OUT_JSON = "C:/Users/weo/Desktop/api/tmp_audit_ielts/pte_sweep.json";
const OUT_LOG = "C:/Users/weo/Desktop/api/tmp_audit_ielts/pte_sweep.log";

const CONCURRENCY = 3;
const RETRY_WAIT_MS = 3000;
const CALL_WATCHDOG_MS = 120000;

const log = (s) => {
  const line = `[${new Date().toISOString()}] ${s}`;
  process.stdout.write(line + "\n");
  appendFileSync(OUT_LOG, line + "\n");
};

/* --------------------------- 工具：数组统计 --------------------------- */
const norm = (v) => (v == null ? "" : String(v).replace(/\s+/g, " ").trim());

function answerStats(key) {
  const arr = Array.isArray(key) ? key : [];
  const dense = Array.from({ length: arr.length }, (_, i) => (arr[i] === undefined ? null : arr[i]));
  const nonempty = dense.map(norm).filter((v) => v.length > 0);
  const uniq = [...new Set(nonempty)];
  const uniqCi = [...new Set(nonempty.map((v) => v.toLowerCase()))];
  return {
    array_length: dense.length,
    nonempty_count: nonempty.length,
    empty_entries: dense.length - nonempty.length,
    unique_count: uniq.length,
    unique_count_case_insensitive: uniqCi.length,
    all_same: nonempty.length >= 2 && uniq.length === 1,
    first3: dense.slice(0, 3).map(norm),
    last3: dense.slice(-3).map(norm),
    sample_unique: uniq.slice(0, 8),
  };
}

const isNetworkish = (err) =>
  /fetch failed|timeout|timed out|ETIMEDOUT|ECONNRESET|ECONNREFUSED|EAI_AGAIN|socket|network|aborted|terminated|HTTP 5\d\d|HTTP -1|watchdog/i
    .test(String(err || ""));

function watchdog(promise, ms) {
  return new Promise((resolve) => {
    const t = setTimeout(() => resolve({ __synthetic: true, ok: false, error: `local watchdog timeout after ${ms}ms` }), ms);
    Promise.resolve(promise).then(
      (v) => { clearTimeout(t); resolve(v); },
      (e) => { clearTimeout(t); resolve({ __synthetic: true, ok: false, error: "THROW: " + String((e && e.stack) || e) }); },
    );
  });
}

/** 带重试的调用：网络异常重试 1 次，间隔 3 秒 */
async function callWithRetry(fn, label) {
  const t0 = Date.now();
  let attempts = 0;
  let retried = false;
  let res;
  for (;;) {
    attempts++;
    res = await watchdog(fn(), CALL_WATCHDOG_MS);
    const failed = !res || res.ok === false || res.__synthetic;
    const errText = res && res.error;
    if (!failed || attempts >= 2 || !isNetworkish(errText)) break;
    retried = true;
    log(`RETRY ${label} after ${RETRY_WAIT_MS}ms (attempt ${attempts}: ${String(errText).slice(0, 160)})`);
    await new Promise((s) => setTimeout(s, RETRY_WAIT_MS));
  }
  return { res: res || { ok: false, error: "null result" }, attempts, retried, ms: Date.now() - t0 };
}

/* ------------------------------ 采集记录 ------------------------------ */
function recordReading(b, t, res, attempts, retried, ms) {
  const ok = !!res.ok;
  return {
    book: b, test: t, ok,
    error: ok ? null : (res.error ?? "unknown"),
    slug: res.slug ?? null,
    page_id: res.page_id ?? null,
    title: res.title ?? null,
    answer_count: ok ? (res.answer_count ?? null) : null,
    question_count: ok ? (res.question_count ?? null) : null,
    answer_key: ok ? Array.from({ length: (res.answer_key || []).length }, (_, i) => (res.answer_key[i] === undefined ? null : res.answer_key[i])) : null,
    passage_paragraphs: ok ? (Array.isArray(res.passage) ? res.passage.length : null) : null,
    instructions_count: ok ? (res.instructions || []).length : null,
    ms, attempts, retried,
    answer_stats: ok ? answerStats(res.answer_key) : null,
  };
}

function recordListening(b, t, res, attempts, retried, ms) {
  const ok = !!res.ok;
  const audio = ok && Array.isArray(res.audio) ? res.audio : [];
  return {
    book: b, test: t, ok,
    error: ok ? null : (res.error ?? "unknown"),
    slug: res.slug ?? null,
    page_id: res.page_id ?? null,
    title: res.title ?? null,
    answer_count: ok ? (res.answer_count ?? null) : null,
    question_count: ok ? (res.question_count ?? null) : null,
    answer_key: ok ? Array.from({ length: (res.answer_key || []).length }, (_, i) => (res.answer_key[i] === undefined ? null : res.answer_key[i])) : null,
    audio_count: ok ? audio.length : null,
    audio_first2: audio.slice(0, 2),
    ms, attempts, retried,
    answer_stats: ok ? answerStats(res.answer_key) : null,
  };
}

/* ------------------------------ 任务编排 ------------------------------ */
const BOOKS = Array.from({ length: 21 }, (_, i) => i + 1);
const TESTS = [1, 2, 3, 4];

const tasks = [];
for (const b of BOOKS) tasks.push({ kind: "book", b, label: `pteBook(${b})` });
for (const b of BOOKS) for (const t of TESTS) tasks.push({ kind: "reading", b, t, label: `pteReading(${b},${t})` });
for (const b of BOOKS) for (const t of TESTS) tasks.push({ kind: "listening", b, t, label: `pteListening(${b},${t})` });

const results = { reading: [], listening: [], books: [] };
let done = 0;

async function runTask(task) {
  if (task.kind === "book") {
    const { res, attempts, retried, ms } = await callWithRetry(() => pteBook(task.b), task.label);
    results.books.push({
      book: task.b,
      ok: !!res.ok,
      error: res.ok ? null : (res.error ?? null),
      hub_id: res.hub_id ?? null,
      title: res.title ?? null,
      reading_keys: Object.keys(res.reading || {}),
      listening_keys: Object.keys(res.listening || {}),
      reading_map: res.reading ?? null,
      listening_map: res.listening ?? null,
      ms, attempts, retried,
    });
  } else if (task.kind === "reading") {
    const { res, attempts, retried, ms } = await callWithRetry(() => pteReading(task.b, task.t), task.label);
    results.reading.push(recordReading(task.b, task.t, res, attempts, retried, ms));
  } else {
    const { res, attempts, retried, ms } = await callWithRetry(() => pteListening(task.b, task.t), task.label);
    results.listening.push(recordListening(task.b, task.t, res, attempts, retried, ms));
  }
  done++;
  if (done % 10 === 0 || done === tasks.length) log(`progress ${done}/${tasks.length}`);
}

async function worker(queue) {
  for (;;) {
    const task = queue.shift();
    if (!task) return;
    try { await runTask(task); }
    catch (e) { log(`WORKER ERROR ${task.label}: ${String(e && e.stack || e)}`); }
  }
}

const startedAt = new Date();
log(`start: ${tasks.length} tasks, concurrency ${CONCURRENCY}, node ${process.version}`);

const queue = tasks.slice();
await Promise.all(Array.from({ length: CONCURRENCY }, () => worker(queue)));

const finishedAt = new Date();
log(`collection done in ${finishedAt - startedAt}ms; reading=${results.reading.length} listening=${results.listening.length} books=${results.books.length}`);

/* -------------------------------- 汇总 -------------------------------- */
const byBT = (a) => a.slice().sort((x, y) => (x.book - y.book) || (x.test - y.test));
results.reading = byBT(results.reading);
results.listening = byBT(results.listening);
results.books.sort((x, y) => x.book - y.book);

const sum = (a, f) => a.reduce((s, x) => s + (f(x) ?? 0), 0);

function suspicious(rows, kind) {
  const out = [];
  for (const r of rows) {
    if (!r.ok) continue;
    const reasons = [];
    if ((r.answer_count ?? 0) < 30) reasons.push(`answer_count=${r.answer_count}<30`);
    if (!r.answer_key || r.answer_key.length === 0) reasons.push("answer_key 为空");
    if (r.answer_stats?.all_same) reasons.push(`全部答案相同=${r.answer_stats.sample_unique[0]}`);
    if ((r.question_count ?? 0) === 0) reasons.push("question_count=0");
    if (r.answer_stats && r.answer_stats.nonempty_count < (r.answer_count ?? 0)) {
      reasons.push(`非空条目数 ${r.answer_stats.nonempty_count} < answer_count ${r.answer_count}`);
    }
    if (kind === "listening" && (r.audio_count ?? 0) === 0) reasons.push("audio 为空");
    if (reasons.length) out.push({ book: r.book, test: r.test, slug: r.slug, reasons });
  }
  return out;
}

const summary = {
  reading_ok: results.reading.filter((r) => r.ok).length,
  reading_total_combos: results.reading.length,
  listening_ok: results.listening.filter((r) => r.ok).length,
  listening_total_combos: results.listening.length,
  reading_answers_by_answer_count: sum(results.reading, (r) => r.ok ? r.answer_count : 0),
  reading_answers_by_nonempty: sum(results.reading, (r) => r.ok ? r.answer_stats.nonempty_count : 0),
  listening_answers_by_answer_count: sum(results.listening, (r) => r.ok ? r.answer_count : 0),
  listening_answers_by_nonempty: sum(results.listening, (r) => r.ok ? r.answer_stats.nonempty_count : 0),
  reading_question_count_sum: sum(results.reading, (r) => r.ok ? r.question_count : 0),
  listening_question_count_sum: sum(results.listening, (r) => r.ok ? r.question_count : 0),
  listening_audio_urls_total: sum(results.listening, (r) => r.ok ? r.audio_count : 0),
  books_ok: results.books.filter((b) => b.ok).length,
  reading_answers_all_identical: results.reading.filter((r) => r.ok && r.answer_stats.all_same).length,
  listening_answers_all_identical: results.listening.filter((r) => r.ok && r.answer_stats.all_same).length,
  failures: [
    ...results.reading.filter((r) => !r.ok).map((r) => ({ kind: "reading", book: r.book, test: r.test, error: r.error })),
    ...results.listening.filter((r) => !r.ok).map((r) => ({ kind: "listening", book: r.book, test: r.test, error: r.error })),
    ...results.books.filter((b) => !b.ok).map((b) => ({ kind: "book", book: b.book, error: b.error })),
  ],
  suspicious_reading: suspicious(results.reading, "reading"),
  suspicious_listening: suspicious(results.listening, "listening"),
  retried_calls: [...results.reading, ...results.listening, ...results.books]
    .filter((r) => r.retried)
    .map((r) => ({ kind: r.test !== undefined ? (r.audio_count !== undefined ? "listening" : "reading") : "book", book: r.book, test: r.test ?? null, attempts: r.attempts })),
};

/* ------------------------------ 专项核验 ------------------------------ */
const findR = (b, t) => results.reading.find((r) => r.book === b && r.test === t) || null;
const findL = (b, t) => results.listening.find((r) => r.book === b && r.test === t) || null;
const findB = (b) => results.books.find((x) => x.book === b) || null;

const b3 = findB(3), b21 = findB(21);
const spot_checks = {
  "pteBook(3).listening_keys": b3 ? b3.listening_keys : null,
  "pteBook(3).listening_map": b3 ? b3.listening_map : null,
  "pteBook(3).reading_keys": b3 ? b3.reading_keys : null,
  "pteListening(3,2)": findL(3, 2) ? { ok: findL(3, 2).ok, error: findL(3, 2).error } : null,
  "pteListening(3,3)": findL(3, 3) ? { ok: findL(3, 3).ok, error: findL(3, 3).error } : null,
  "pteListening(3,4)": findL(3, 4) ? { ok: findL(3, 4).ok, error: findL(3, 4).error } : null,
  "pteListening(1,2)": findL(1, 2) ? {
    ok: findL(1, 2).ok, error: findL(1, 2).error,
    answer_count: findL(1, 2).answer_count,
    nonempty_count: findL(1, 2).answer_stats?.nonempty_count ?? null,
    answer_key: findL(1, 2).answer_key,
  } : null,
  "pteBook(21).reading_keys": b21 ? b21.reading_keys : null,
  "pteBook(21).listening_keys": b21 ? b21.listening_keys : null,
  "pteBook(21).reading_map": b21 ? b21.reading_map : null,
  "pteBook(21).listening_map": b21 ? b21.listening_map : null,
};

const output = {
  meta: {
    task: "practicepteonline 适配器 84 套全覆盖独立复现",
    module: "file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs",
    node: process.version,
    started_at: startedAt.toISOString(),
    finished_at: finishedAt.toISOString(),
    elapsed_ms: finishedAt - startedAt,
    concurrency: CONCURRENCY,
    retry_policy: `网络异常重试 1 次，间隔 ${RETRY_WAIT_MS}ms`,
    task_counts: { books: results.books.length, reading: results.reading.length, listening: results.listening.length },
  },
  summary,
  spot_checks,
  reading: results.reading,
  listening: results.listening,
  books: results.books,
};

writeFileSync(OUT_JSON, JSON.stringify(output, null, 2));
log(`wrote ${OUT_JSON}`);

/* ------------------------------- stdout ------------------------------- */
const line = (s) => process.stdout.write(s + "\n");
line("");
line("================= SUMMARY =================");
line(`阅读 ok:            ${summary.reading_ok}/${summary.reading_total_combos}`);
line(`听力 ok:            ${summary.listening_ok}/${summary.listening_total_combos}`);
line(`阅读答案总数 (answer_count 之和): ${summary.reading_answers_by_answer_count}`);
line(`阅读答案总数 (非空条目之和):     ${summary.reading_answers_by_nonempty}`);
line(`听力答案总数 (answer_count 之和): ${summary.listening_answers_by_answer_count}`);
line(`听力答案总数 (非空条目之和):     ${summary.listening_answers_by_nonempty}`);
line(`阅读题目数之和: ${summary.reading_question_count_sum} / 听力题目数之和: ${summary.listening_question_count_sum}`);
line(`听力音频 URL 总数: ${summary.listening_audio_urls_total}`);
line(`pteBook ok: ${summary.books_ok}/21`);
line(`答案全部相同的组合: reading=${summary.reading_answers_all_identical} listening=${summary.listening_answers_all_identical}`);
line("");
line(`--- ok=false 组合 (${summary.failures.length}) ---`);
for (const f of summary.failures) line(`  ${f.kind} ${f.book}-${f.test ?? "-"} :: ${f.error}`);
line("");
line(`--- 可疑组合 reading (${summary.suspicious_reading.length}) ---`);
for (const s of summary.suspicious_reading) line(`  reading ${s.book}-${s.test} [${s.slug}] :: ${s.reasons.join(" | ")}`);
line("");
line(`--- 可疑组合 listening (${summary.suspicious_listening.length}) ---`);
for (const s of summary.suspicious_listening) line(`  listening ${s.book}-${s.test} [${s.slug}] :: ${s.reasons.join(" | ")}`);
line("");
line("--- 专项核验 ---");
line(JSON.stringify(spot_checks, null, 2));
line("");
line("--- 每套明细 (book-test: kind ok ans/ques nonempty uniq ms) ---");
for (const r of [...results.reading, ...results.listening]) {
  line(`  ${r.book}-${r.test} ${r.audio_count !== undefined ? "L" : "R"} ok=${r.ok} ans=${r.answer_count}/${r.question_count} nonempty=${r.answer_stats?.nonempty_count ?? "-"} uniq=${r.answer_stats?.unique_count ?? "-"} ms=${r.ms}${r.retried ? " RETRIED" : ""}${r.ok ? "" : " ERR=" + r.error}`);
}
line("");
line(`full raw data: ${OUT_JSON}`);
