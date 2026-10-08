#!/usr/bin/env node
/**
 * taskC_extra.mjs — 补测：对同样被 maslowGood 优化跳过 reader 的 b2/b11/b13 复算 reader 侧字符数，
 * 与 script_sweep.json 中的 maslow 数字比对，判定跳过是否掩盖了"本应选 reader"的情况。
 * 只读导入 API；结果合并回 script_sweep.json（先备份）。
 */
import { listeningSegments } from "file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs";
import { writeFileSync, readFileSync, copyFileSync } from "node:fs";

const OUT = "C:/Users/weo/Desktop/api/tmp_audit_ielts";
const T0 = Date.now();
const ts = () => ((Date.now() - T0) / 1000).toFixed(1) + "s";
const log = (...a) => console.log("[" + ts() + "]", ...a);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const LIMIT = 2;
let active = 0;
const queue = [];
function acquire() {
  return new Promise((resolve) => {
    if (active < LIMIT) { active++; resolve(); }
    else queue.push(resolve);
  });
}
function release() {
  active--;
  if (queue.length && active < LIMIT) { active++; queue.shift()(); }
}
async function limited(fn) {
  await acquire();
  try { return await fn(); } finally { release(); }
}
async function run(label, fn) {
  const start = Date.now();
  const attempts = [];
  for (let i = 0; i < 2; i++) {
    const t = Date.now();
    let v = null, thrown = null;
    try { v = await limited(fn); } catch (e) { thrown = String((e && e.message) || e); }
    attempts.push({ ms: Date.now() - t, thrown, ok: v ? v.ok : null, error: v && v.error ? String(v.error) : null });
    const bad = !!thrown || (v && v.ok === false);
    if (!bad) return { v, thrown: null, attempts, totalMs: Date.now() - start };
    if (i === 0) { log(`RETRY ${label}: ${thrown || "ok=false " + (v && v.error)} (wait 3s)`); await sleep(3000); }
  }
  const last = attempts[attempts.length - 1];
  log(`STILL-BAD ${label}: ${last.thrown || last.error}`);
  return { v: null, thrown: last.thrown || "ok=false:" + last.error, attempts, totalMs: Date.now() - start };
}

const summary = JSON.parse(readFileSync(OUT + "/script_sweep.json", "utf8"));
copyFileSync(OUT + "/script_sweep.json", OUT + "/script_sweep.json.bak");
summary.taskC.extraRun = { startedAt: new Date().toISOString(), books: [2, 11, 13] };

for (const b of [2, 11, 13]) {
  const a = summary.taskA.books[b];
  const mParts = a.parts;
  const mChars = a.charsInParts;
  log(`EXTRA b=${b} START actualSource=${a.source} mParts=${mParts} mChars=${mChars} readerAlt=${JSON.stringify(a.alternatives && a.alternatives.reader)}`);
  const calls = [];
  let rParts = 0, rChars = 0;
  for (let t = 1; t <= 4; t++) {
    for (let p = 1; p <= 4; p++) {
      const r = await run(`listeningSegments(${b},${t},${p})`, () => listeningSegments(b, t, p));
      const res = r.v;
      const rec = { t, p, ok: !!(res && res.ok), segments: 0, chars: 0, included: false, error: null };
      if (r.thrown) rec.error = r.thrown;
      else if (!res.ok) rec.error = res.error || "not ok";
      else {
        const segs = res.segments || [];
        rec.segments = segs.length;
        const lines = [];
        for (const g of segs) {
          const who = g.speaker ? g.speaker + ": " : "";
          const en = String(g.en || "").trim();
          if (en) lines.push(who + en);
        }
        const txt = lines.join("\n");
        rec.chars = txt.length;
        if (txt.length > 200) { rec.included = true; rParts++; rChars += txt.length; }
      }
      calls.push(rec);
      log(`EXTRA b=${b} t=${t} p=${p} ok=${rec.ok} segs=${rec.segments} chars=${rec.chars} incl=${rec.included}${rec.error ? " ERR=" + rec.error : ""}`);
    }
  }
  const useReaderRule = rParts > mParts || (rParts === mParts && rChars > mChars * 1.3);
  const entry = {
    actualSource: a.source,
    maslowParts: mParts,
    maslowChars: mChars,
    maslowGood16and40k: mParts >= 16 && mChars >= 40000,
    readerSkippedByOptimization: true,
    readerPartsGt200: rParts,
    readerCharsGt200: rChars,
    ratio_readerChars_over_maslowChars: +(rChars / mChars).toFixed(4),
    threshold_maslow_x1_3: Math.round(mChars * 1.3),
    rule_wouldUseReader: useReaderRule,
    actualUsedReader: a.source === "userheyy/ielts-reader",
    verdict_skipButShouldBeReader: useReaderRule === true,
    readerRawCalls: calls,
  };
  summary.taskC.books[b] = entry;
  log(`EXTRA b=${b} RESULT rParts=${rParts} rChars=${rChars} mParts=${mParts} mChars=${mChars} ratio=${entry.ratio_readerChars_over_maslowChars} ruleWouldUseReader=${useReaderRule} SKIP_MASKED_READER=${entry.verdict_skipButShouldBeReader}`);
  writeFileSync(OUT + "/script_sweep.json", JSON.stringify(summary, null, 2));
}

summary.taskC.conclusion = Object.entries(summary.taskC.books).map(([b, c]) =>
  `b${b}: actual=${c.actualSource} maslow(${c.maslowParts}p/${c.maslowChars}c) reader(${c.readerPartsGt200}p/${c.readerCharsGt200}c) ratio=${c.ratio_readerChars_over_maslowChars} skip=${c.readerSkippedByOptimization} ruleWouldUseReader=${c.rule_wouldUseReader} bug=${c.verdict_skipButShouldBeReader}`);
summary.taskC.extraRun.finishedAt = new Date().toISOString();
writeFileSync(OUT + "/script_sweep.json", JSON.stringify(summary, null, 2));
log("EXTRA DONE");
for (const c of summary.taskC.conclusion) log("C " + c);
