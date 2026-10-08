// 全量 pte 回归：21 册 × 4 套 × (阅读+听力)，核对答案总数与 questions_missing
import { pteReading, pteListening } from "file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs";
import { writeFileSync } from "node:fs";

const conc = 3;
const jobs = [];
for (let b = 1; b <= 21; b++) for (let t = 1; t <= 4; t++) { jobs.push(["R", b, t]); jobs.push(["L", b, t]); }

const out = { reading: {}, listening: {}, errors: [], startedAt: new Date().toISOString() };
let idx = 0;
async function worker() {
  while (idx < jobs.length) {
    const [kind, b, t] = jobs[idx++];
    const key = `${b}-${t}`;
    const target = kind === "R" ? out.reading : out.listening;
    try {
      const r = kind === "R" ? await pteReading(b, t) : await pteListening(b, t);
      if (r.ok) target[key] = { c: r.answer_count, m: r.questions_missing || [] };
      else { target[key] = { ok: false, e: r.error }; out.errors.push(`${kind} ${key}: ${r.error}`); }
    } catch (e) { out.errors.push(`${kind} ${key}: THROW ${e && e.message}`); }
  }
}
await Promise.all([...Array(conc)].map(worker));

const rTot = Object.values(out.reading).reduce((s, x) => s + (x.c || 0), 0);
const lTot = Object.values(out.listening).reduce((s, x) => s + (x.c || 0), 0);
const rOk = Object.values(out.reading).filter((x) => x.c != null).length;
const lOk = Object.values(out.listening).filter((x) => x.c != null).length;
out.totals = { reading: rTot, listening: lTot, reading_ok: rOk, listening_ok: lOk };
out.finishedAt = new Date().toISOString();
console.log("READING:", rTot, "(expect 3360), ok slots:", rOk, "/84");
console.log("LISTENING:", lTot, "(expect 3239), ok slots:", lOk, "/84");
console.log("ERRORS:", out.errors.length);
for (const e of out.errors) console.log("  ", e);
for (let b = 1; b <= 21; b++) {
  const r = [1, 2, 3, 4].map((t) => out.reading[`${b}-${t}`]?.c ?? "x").join("/");
  const l = [1, 2, 3, 4].map((t) => out.listening[`${b}-${t}`]?.c ?? "x").join("/");
  console.log(`b${b}: R ${r} | L ${l}`);
}
// questions_missing 汇总（阅读缺口为 0 是预期；听力缺口应只在组合题）
const rm = Object.entries(out.reading).filter(([, v]) => v.m && v.m.length).map(([k, v]) => `${k}:${v.m}`);
const lm = Object.entries(out.listening).filter(([, v]) => v.m && v.m.length).map(([k, v]) => `${k}:${v.m}`);
console.log("READING questions_missing slots:", rm.length);
console.log(rm.join(" | "));
console.log("LISTENING questions_missing slots:", lm.length);
console.log(lm.join(" | "));
writeFileSync("regression_after_fixes.json", JSON.stringify(out, null, 1));
console.log("saved regression_after_fixes.json");
