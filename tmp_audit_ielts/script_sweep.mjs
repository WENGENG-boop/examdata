#!/usr/bin/env node
/**
 * script_sweep.mjs — 独立审查：listeningScript(book) 剑1–20 全覆盖复现 + 选源逻辑复核。
 * 只读导入 ielts-api.mjs（绝对 file:/// URL），不修改被测目录任何文件。
 * 并发上限 2；异常（throw 或 ok:false）重试 1 次，间隔 3s。
 * 输出：本目录 script_sweep.json + samples/*.txt
 */
import { listeningScript, listeningSegments } from "file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs";
import { writeFileSync, mkdirSync, readFileSync } from "node:fs";
import { createHash } from "node:crypto";

const OUT = "C:/Users/weo/Desktop/api/tmp_audit_ielts";
const SAMPLES = OUT + "/samples";
const API = "C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs";
const READER = "userheyy/ielts-reader";
const MASLOW = "maslow/EnglishLearning";
mkdirSync(SAMPLES, { recursive: true });

const T0 = Date.now();
const ts = () => ((Date.now() - T0) / 1000).toFixed(1) + "s";
const log = (...a) => console.log("[" + ts() + "]", ...a);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const sha256 = (p) => createHash("sha256").update(readFileSync(p)).digest("hex");

/* ---------------- 全局并发闸门（上限 2） ---------------- */
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

/* 调用包装：throw 或 ok:false 都算异常 → 重试 1 次，间隔 3s */
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

/* ---------------- 汇总对象 ---------------- */
const summary = {
  meta: {
    startedAt: new Date().toISOString(),
    node: process.version,
    entry: "file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs",
    concurrency: LIMIT,
    retryPolicy: "1 retry after 3s on throw or ok:false",
    apiSha256Start: sha256(API),
    apiSha256End: null,
    finishedAt: null,
  },
  taskA: { books: {}, totalParts: null, sourceCounts: {}, anomalies: [] },
  taskB: { samples: [] },
  taskC: { books: {}, conclusion: [] },
  errors: [],
};
function writeJson() {
  summary.meta.updatedAt = new Date().toISOString();
  writeFileSync(OUT + "/script_sweep.json", JSON.stringify(summary, null, 2));
}

/* ---------------- Task A ---------------- */
function partMeta(txt) {
  const s = String(txt ?? "");
  const matches = [...s.matchAll(/\b(?:PART|SECTION)\s*\d+\b/gi)];
  return {
    chars: s.length,
    empty: s.trim().length === 0,
    headingLike: /^\s*(?:PART|SECTION)\s*\d+/im.test(s),
    residueCount: matches.length,
    residueSamples: matches.slice(0, 2).map((m) => s.slice(Math.max(0, m.index - 30), m.index + m[0].length + 30).replace(/\s+/g, " ")),
    head80: s.slice(0, 80),
    tail80: s.slice(-80),
  };
}
function analyze(res, book) {
  const out = {
    book,
    ok: !!(res && res.ok),
    source: res && res.source ? res.source : null,
    format: res && res.format ? res.format : null,
    error: res && res.error ? String(res.error) : null,
    warning: res && res.warning ? String(res.warning) : null,
    note: res && res.note ? String(res.note) : null,
    parts: res && res.parts !== undefined ? res.parts : null,
    bytes: res && res.bytes !== undefined ? res.bytes : null,
    alternatives: res && res.alternatives ? res.alternatives : null,
    readerSkipped: null,
    charsInParts: 0,
    partTotal: 0,
    testsSummary: {},
    tests: {},
  };
  if (res && res.source === MASLOW && res.alternatives && res.alternatives.reader) {
    out.readerSkipped = res.alternatives.reader.parts === 0 && res.alternatives.reader.chars === 0;
  }
  const tests = (res && res.tests) || {};
  for (const [tk, parts] of Object.entries(tests)) {
    const tp = {};
    for (const [pk, txt] of Object.entries(parts)) {
      tp[pk] = partMeta(txt);
      out.partTotal++;
      out.charsInParts += tp[pk].chars;
    }
    out.tests[tk] = tp;
    out.testsSummary[tk] = Object.keys(tp).length;
  }
  return out;
}

const rawA = {}; // book -> 原始 listeningScript 返回（供 B/C 复用）

async function taskA() {
  let total = 0;
  for (let b = 1; b <= 20; b++) {
    const r = await run(`listeningScript(${b})`, () => listeningScript(b));
    const a = analyze(r.v, b);
    a.callMs = r.totalMs;
    a.attempts = r.attempts;
    if (r.thrown) { a.ok = false; a.scriptError = r.thrown; }
    if (r.v) rawA[b] = r.v;
    summary.taskA.books[b] = a;
    total += a.partTotal;
    log(`A b=${String(b).padStart(2, "0")} source=${a.source} parts=${a.partTotal} bytes=${a.bytes} readerSkipped=${a.readerSkipped} alt=${JSON.stringify(a.alternatives)} ms=${r.totalMs}${a.scriptError ? " ERR=" + a.scriptError : ""}`);
    writeJson();
  }
  summary.taskA.totalParts = total;
  const sc = {};
  for (const a of Object.values(summary.taskA.books)) sc[a.source] = (sc[a.source] || 0) + 1;
  summary.taskA.sourceCounts = sc;
  const anomalies = [];
  for (const [b, a] of Object.entries(summary.taskA.books)) {
    if (!a.ok) anomalies.push(`b${b}: not ok (${a.error || a.scriptError})`);
    if (a.partTotal === 0) anomalies.push(`b${b}: 0 parts`);
    for (const [tk, tp] of Object.entries(a.tests)) {
      for (const [pk, m] of Object.entries(tp)) {
        if (m.empty) anomalies.push(`b${b} ${tk} ${pk}: empty text`);
        if (m.headingLike) anomalies.push(`b${b} ${tk} ${pk}: heading-like residue (${m.residueSamples[0] || ""})`);
      }
    }
  }
  summary.taskA.anomalies = anomalies;
  log(`A TOTAL parts(1..20)=${total} sources=${JSON.stringify(sc)} anomalies=${anomalies.length}`);
  writeJson();
}

/* ---------------- Task B ---------------- */
const SAMPLE_REQ = [
  { b: 1, t: 1, p: 1, docSource: "reader" },
  { b: 3, t: 1, p: 1, docSource: null },
  { b: 5, t: 2, p: 1, docSource: "reader" },
  { b: 12, t: 1, p: 1, docSource: "maslow" },
  { b: 17, t: 2, p: 3, docSource: "maslow" },
  { b: 20, t: 4, p: 4, docSource: "maslow" },
];

function taskB() {
  for (const req of SAMPLE_REQ) {
    const res = rawA[req.b];
    const file = `b${String(req.b).padStart(2, "0")}_t${req.t}_p${req.p}.txt`;
    const path = SAMPLES + "/" + file;
    const source = res ? (res.source ?? null) : null;
    const txt = res && res.tests && res.tests["test" + req.t] ? res.tests["test" + req.t]["part" + req.p] : undefined;
    let missing = null;
    let chars = null;
    let head400 = null;
    if (!res) missing = "no listeningScript result (call failed)";
    else if (typeof txt !== "string") missing = "part missing in returned tests";
    if (typeof txt === "string") {
      chars = txt.length;
      head400 = txt.slice(0, 400);
      writeFileSync(path, `# book ${req.b} test ${req.t} part ${req.p} source=${source}\n` + txt);
    } else {
      writeFileSync(path, `# book ${req.b} test ${req.t} part ${req.p} source=${source ?? "N/A"} MISSING: ${missing}\n`);
    }
    summary.taskB.samples.push({
      file, book: req.b, test: req.t, part: req.p, docClaimedSource: req.docSource,
      actualSource: source, chars, missing, head400,
    });
    log(`B ${file} source=${source} chars=${chars}${missing ? " MISSING:" + missing : ""}`);
    if (head400) console.log(`----- head400 ${file} (source=${source}) -----\n${head400}\n----- end ${file} -----`);
  }
  writeJson();
}

/* ---------------- Task C ---------------- */
async function fetchReaderParts(book) {
  const calls = [];
  const parts = {};
  for (let t = 1; t <= 4; t++) {
    for (let p = 1; p <= 4; p++) {
      const r = await run(`listeningSegments(${book},${t},${p})`, () => listeningSegments(book, t, p));
      const res = r.v;
      const rec = { t, p, ok: !!(res && res.ok), segments: 0, chars: 0, included: false, error: null, ms: r.totalMs, attempts: r.attempts.length };
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
        if (txt.length > 200) {
          rec.included = true;
          parts["test" + t] = parts["test" + t] || {};
          parts["test" + t]["part" + p] = txt;
        }
      }
      calls.push(rec);
      log(`C b=${book} t=${t} p=${p} ok=${rec.ok} segs=${rec.segments} chars=${rec.chars} incl=${rec.included}${rec.error ? " ERR=" + rec.error : ""}`);
    }
  }
  let partsCount = 0, chars = 0;
  for (const tp of Object.values(parts)) for (const txt of Object.values(tp)) { partsCount++; chars += txt.length; }
  const rawChars = calls.reduce((n, c) => n + c.chars, 0);
  return { calls, partsCount, chars, rawChars };
}

function sumPartChars(res) {
  let n = 0;
  for (const parts of Object.values((res && res.tests) || {})) for (const t of Object.values(parts)) n += String(t).length;
  return n;
}

async function taskC() {
  for (const b of [12, 17, 18, 19]) {
    const a = summary.taskA.books[b];
    const res = rawA[b];
    const mParts = a.alternatives && a.alternatives.maslow ? a.alternatives.maslow.parts : (a.source === MASLOW ? a.parts : null);
    const mChars = a.alternatives && a.alternatives.maslow ? a.alternatives.maslow.chars : (a.source === MASLOW ? sumPartChars(res) : null);
    const maslowGood = mParts != null && mChars != null ? (mParts >= 16 && mChars >= 40000) : null;
    const readerAlt = a.alternatives ? a.alternatives.reader ?? null : null;
    const readerSkipped = !!(readerAlt && readerAlt.parts === 0 && readerAlt.chars === 0);
    log(`C b=${b} START actualSource=${a.source} mParts=${mParts} mChars=${mChars} maslowGood=${maslowGood} readerSkipped=${readerSkipped} reportedReaderAlt=${JSON.stringify(readerAlt)}`);
    const rd = await fetchReaderParts(b);
    const rParts = rd.partsCount, rChars = rd.chars;
    const useReaderRule = mParts != null && mChars != null ? (rParts > mParts || (rParts === mParts && rChars > mChars * 1.3)) : null;
    const actualReader = a.source === READER;
    const bug = readerSkipped && maslowGood === true && useReaderRule === true && !actualReader;
    summary.taskC.books[b] = {
      actualSource: a.source,
      actualFormat: a.format,
      maslowParts: mParts,
      maslowChars: mChars,
      maslowMdBytes: a.source === MASLOW ? a.bytes : null,
      maslowGood16and40k: maslowGood,
      readerSkippedByOptimization: readerSkipped,
      reportedReaderAlt: readerAlt,
      readerPartsGt200: rParts,
      readerCharsGt200: rChars,
      readerRawCharsAll16: rd.rawChars,
      readerRawCalls: rd.calls,
      ratio_readerChars_over_maslowChars: mChars ? +(rChars / mChars).toFixed(4) : null,
      threshold_maslow_x1_3: mChars ? Math.round(mChars * 1.3) : null,
      rule_wouldUseReader: useReaderRule,
      actualUsedReader: actualReader,
      verdict_skipButShouldBeReader: bug,
      consistent: useReaderRule === actualReader || readerSkipped,
    };
    log(`C b=${b} RESULT rParts=${rParts} rChars=${rChars} (rawAll=${rd.rawChars}) mParts=${mParts} mChars=${mChars} ratio=${summary.taskC.books[b].ratio_readerChars_over_maslowChars} ruleWouldUseReader=${useReaderRule} actualReader=${actualReader} SKIP_BUG=${bug}`);
    writeJson();
  }
}

/* ---------------- main ---------------- */
(async () => {
  try {
    log(`START node=${process.version} apiSha=${summary.meta.apiSha256Start.slice(0, 16)}`);
    await taskA();
    log("Task A done");
    taskB();
    log("Task B done");
    await taskC();
    log("Task C done");
  } catch (e) {
    summary.errors.push(String((e && e.stack) || e));
    log("FATAL " + ((e && e.stack) || e));
  }
  summary.meta.apiSha256End = sha256(API);
  summary.meta.finishedAt = new Date().toISOString();
  summary.meta.durationMs = Date.now() - T0;
  summary.taskC.conclusion = Object.entries(summary.taskC.books).map(([b, c]) =>
    `b${b}: actual=${c.actualSource} maslow(${c.maslowParts}p/${c.maslowChars}c) reader(${c.readerPartsGt200}p/${c.readerCharsGt200}c) ratio=${c.ratio_readerChars_over_maslowChars} skip=${c.readerSkippedByOptimization} ruleWouldUseReader=${c.rule_wouldUseReader} bug=${c.verdict_skipButShouldBeReader}`);
  writeJson();
  log("================ FINAL ================");
  log(`apiSha256 start=${summary.meta.apiSha256Start}`);
  log(`apiSha256 end  =${summary.meta.apiSha256End} unchanged=${summary.meta.apiSha256Start === summary.meta.apiSha256End}`);
  log(`duration=${(summary.meta.durationMs / 1000).toFixed(1)}s`);
  log(`TASK A totalParts(1..20)=${summary.taskA.totalParts} sourceCounts=${JSON.stringify(summary.taskA.sourceCounts)} anomalies=${summary.taskA.anomalies.length}`);
  for (const [b, a] of Object.entries(summary.taskA.books)) log(`A book ${String(b).padStart(2, "0")}: source=${a.source} parts=${a.partTotal} bytes=${a.bytes} charsInParts=${a.charsInParts} readerSkipped=${a.readerSkipped}`);
  for (const s of summary.taskB.samples) log(`B ${s.file}: source=${s.actualSource} chars=${s.chars}${s.missing ? " MISSING:" + s.missing : ""}`);
  for (const c of summary.taskC.conclusion) log("C " + c);
  log(`json=${OUT}/script_sweep.json`);
})();
