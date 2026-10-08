// ito_sweep.mjs — 独立审查：ieltstrainingonline.com 交叉源覆盖复核
// 不改被测代码；只 import 并调用导出函数。
import fs from "node:fs";
import path from "node:path";

const ENTRY = "file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs";
const OUTDIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts";
const SAMPLEDIR = path.join(OUTDIR, "samples");
const CONCURRENCY = 2;
const SAMPLE_COMBOS = [[10, 1], [15, 2], [21, 1]];

const { itoScript, itoCoverage } = await import(ENTRY);

function ts() {
  return new Date().toISOString().slice(11, 19);
}
function log(...a) {
  console.log("[" + ts() + "]", ...a);
}

function cut(s, n) {
  return String(s == null ? "" : s).slice(0, n);
}
function tail(s, n) {
  const x = String(s == null ? "" : s);
  return x.slice(Math.max(0, x.length - n));
}

/** 对单个 section 做审查用探针 */
function probeSection(text) {
  const t = String(text == null ? "" : text);
  const lines = t.split("\n");
  return {
    chars: t.length,
    head120: cut(t, 120),
    tail120: tail(t, 120),
    has_Advertisements: /Advertisements/i.test(t),
    has_mp3: /\.mp3/i.test(t),
    has_AnswerCam: /Answer\s+Cam/i.test(t),
    // 额外诊断
    line_count: lines.length,
    // 以 "Answer" 开头的行（答案表混入嫌疑）
    answer_lead_lines: lines.filter((l) => /^\s*Answers?\b/i.test(l)).slice(0, 5),
    starts_with_PART: /^\s*(PART|SECTION)\s*[1-4]\b/i.test(t),
    // 首行是否从单词中间截断（首字符不是大写/引号/数字/连字符/括号）
    first_char: t.length ? t[0] : "",
    head300: cut(t, 300),
  };
}

const jobs = [];
for (let b = 10; b <= 21; b++) for (let t = 1; t <= 4; t++) jobs.push({ book: b, test: t });
log("jobs =", jobs.length, "concurrency =", CONCURRENCY);

const results = new Array(jobs.length);
let next = 0;

async function worker(wid) {
  while (true) {
    const i = next++;
    if (i >= jobs.length) return;
    const { book, test } = jobs[i];
    const t0 = Date.now();
    log(`worker${wid} START book=${book} test=${test}`);
    let r;
    try {
      r = await itoScript(book, test);
    } catch (e) {
      r = { ok: false, error: "THREW: " + String((e && e.stack) || e) };
    }
    const ms = Date.now() - t0;
    const rec = {
      book,
      test,
      ok: !!r.ok,
      error: r.ok ? null : (r.error ?? null),
      slug: r.slug ?? null,
      title: r.title ?? null,
      section_count: r.section_count ?? 0,
      bytes: r.bytes ?? 0,
      ms,
      section_keys: r.sections ? Object.keys(r.sections) : [],
    };
    if (r.ok && r.sections) {
      rec.sections = {};
      for (const k of Object.keys(r.sections)) rec.sections[k] = probeSection(r.sections[k]);
      rec.text_chars = (r.text || "").length;
      rec.text = r.text || "";
      rec.sections_full = r.sections;
    }
    results[i] = rec;
    log(
      `worker${wid} DONE  book=${book} test=${test} ok=${rec.ok} slug=${rec.slug} secs=${rec.section_count} bytes=${rec.bytes} (${ms}ms)` +
        (rec.ok ? "" : " err=" + JSON.stringify(rec.error))
    );
  }
}

await Promise.all(Array.from({ length: CONCURRENCY }, (_, k) => worker(k + 1)));

/* ---------------- 汇总 ---------------- */
const okCount = results.filter((r) => r.ok).length;
const dist = {};
for (const r of results) dist[r.section_count] = (dist[r.section_count] || 0) + 1;

const summary = {
  generated_at: new Date().toISOString(),
  source: "ieltstrainingonline.com",
  entry: ENTRY,
  concurrency: CONCURRENCY,
  combos_total: results.length,
  ok_count: okCount,
  section_count_4: results.filter((r) => r.ok && r.section_count === 4).length,
  section_count_distribution: dist,
  bad: results
    .filter((r) => !r.ok || r.section_count !== 4)
    .map((r) => ({ book: r.book, test: r.test, ok: r.ok, error: r.error, slug: r.slug, section_count: r.section_count })),
  slug_used: results.map((r) => `${r.book}-${r.test} ${r.slug}`),
  per_combo: results.map((r) => ({
    book: r.book, test: r.test, ok: r.ok, error: r.error, slug: r.slug, title: r.title,
    section_count: r.section_count, bytes: r.bytes, ms: r.ms, text_chars: r.text_chars ?? 0,
    sections: r.sections ? Object.fromEntries(Object.entries(r.sections).map(([k, v]) => [k, {
      chars: v.chars, head120: v.head120, tail120: v.tail120,
      has_Advertisements: v.has_Advertisements, has_mp3: v.has_mp3, has_AnswerCam: v.has_AnswerCam,
      line_count: v.line_count, answer_lead_lines: v.answer_lead_lines, starts_with_PART: v.starts_with_PART, first_char: v.first_char,
    }])) : null,
  })),
};

/* ---------------- 任务 C：切分边界样本 ---------------- */
fs.mkdirSync(SAMPLEDIR, { recursive: true });
const samples = [];
for (const [b, t] of SAMPLE_COMBOS) {
  const r = results.find((x) => x.book === b && x.test === t);
  if (!r || !r.ok || !r.sections) {
    samples.push({ book: b, test: t, error: "no data", ok: r ? r.ok : false });
    log(`SAMPLE MISS book=${b} test=${t}`);
    continue;
  }
  const entry = { book: b, test: t, slug: r.slug, section_count: r.section_count, sections: {} };
  for (let n = 1; n <= 4; n++) {
    const key = "section" + n;
    const txt = r.sections_full[key];
    if (txt === undefined) {
      entry.sections[key] = null;
      continue;
    }
    const p300 = cut(txt, 300);
    const file = path.join(SAMPLEDIR, `ito_${b}_${t}_s${n}.txt`);
    fs.writeFileSync(file, p300, "utf8");
    entry.sections[key] = { file, chars_total: txt.length, first300: p300 };
  }
  samples.push(entry);
}

const full = { summary, samples, results };
fs.writeFileSync(path.join(OUTDIR, "ito_sweep.json"), JSON.stringify(full, null, 2), "utf8");

/* ---------------- stdout 报告 ---------------- */
console.log("\n================ TASK A SUMMARY ================");
console.log("combos_total      =", summary.combos_total);
console.log("ok_count          =", summary.ok_count);
console.log("section_count==4  =", summary.section_count_4);
console.log("section_count dist=", JSON.stringify(dist));
console.log("\n--- ok=false or section_count<4 ---");
if (!summary.bad.length) console.log("(none)");
for (const r of summary.bad) console.log(JSON.stringify(r));
console.log("\n--- per-combo table ---");
console.log("book-test | ok | sections | bytes | ms | slug");
for (const r of results) {
  console.log(
    `${r.book}-${r.test}`.padEnd(9), "|", String(r.ok).padEnd(5), "|", String(r.section_count).padEnd(8), "|",
    String(r.bytes).padEnd(7), "|", String(r.ms).padEnd(6), "|", r.slug, r.ok ? "" : "  ERR=" + r.error
  );
}

console.log("\n================ TASK C SAMPLES (first 300 chars) ================");
for (const s of samples) {
  console.log(`\n##### book=${s.book} test=${s.test} slug=${s.slug} section_count=${s.section_count}`);
  if (s.error) { console.log("  ERROR:", s.error); continue; }
  for (const k of Object.keys(s.sections)) {
    const v = s.sections[k];
    if (!v) { console.log(`\n--- ${k}: MISSING ---`); continue; }
    console.log(`\n--- ${k} (total ${v.chars_total} chars) file=${v.file} ---`);
    console.log(JSON.stringify(v.first300));
  }
}

console.log("\nJSON written to:", path.join(OUTDIR, "ito_sweep.json"));
