// ito_analyze.mjs — 对 ito_sweep.json 做切分边界与污染审查（只读，不发网络请求）
import fs from "node:fs";
const P = "C:/Users/weo/Desktop/api/tmp_audit_ielts/ito_sweep.json";
const d = JSON.parse(fs.readFileSync(P, "utf8"));
const results = d.results;

function show(s, n = 90) { return JSON.stringify(String(s).slice(0, n)); }
function tail(s, n = 90) { const x = String(s); return JSON.stringify(x.slice(Math.max(0, x.length - n))); }

console.log("### 1) 每个 section 首 90 字符 / 末 90 字符（全部 48 组合）");
let anomalies = [];
for (const r of results) {
  if (!r.ok || !r.sections) { anomalies.push(`${r.book}-${r.test}: NOT OK`); continue; }
  const line = [];
  for (let n = 1; n <= 4; n++) {
    const k = "section" + n;
    const t = r.sections_full[k];
    if (!t) { line.push(`s${n}=MISSING`); anomalies.push(`${r.book}-${r.test}: ${k} missing`); continue; }
    line.push(`s${n}[${t.length}]`);
  }
  console.log(`${r.book}-${r.test} ${line.join(" ")}`);
}

console.log("\n### 2) 各 section 是否以 'PART N'/'SECTION N' 标题开头，首字符是否可疑");
for (const r of results) {
  if (!r.ok || !r.sections) continue;
  const flags = [];
  for (let n = 1; n <= 4; n++) {
    const t = r.sections_full["section" + n];
    if (!t) continue;
    const head = t.slice(0, 20).replace(/\n/g, "\\n");
    const startsHeading = /^\s*(PART|SECTION)\s*[1-4]\b/i.test(t);
    if (startsHeading) flags.push(`s${n}:HAS_HEADING(${JSON.stringify(head)})`);
  }
  if (flags.length) console.log(`${r.book}-${r.test} ${flags.join(" ")}`);
}

console.log("\n### 3) section 末尾是否在单词中间截断（末字符非 [.!?\"')\\]] 且非空行）");
for (const r of results) {
  if (!r.ok || !r.sections) continue;
  const flags = [];
  for (let n = 1; n <= 4; n++) {
    const t = r.sections_full["section" + n];
    if (!t) continue;
    const last = t.trim().slice(-1);
    if (!/[.!?"')\]:\]]/.test(last)) flags.push(`s${n}:tail=${JSON.stringify(t.trim().slice(-60))}`);
  }
  if (flags.length) console.log(`${r.book}-${r.test} ${flags.join(" | ")}`);
}

console.log("\n### 4) 污染检查汇总");
const pol = { Advertisements: 0, mp3: 0, AnswerCam: 0, answerLead: 0 };
const polDetail = [];
for (const r of results) {
  if (!r.ok || !r.sections) continue;
  for (let n = 1; n <= 4; n++) {
    const t = r.sections_full["section" + n];
    if (!t) continue;
    if (/Advertisements/i.test(t)) { pol.Advertisements++; polDetail.push(`${r.book}-${r.test} s${n} Advertisements`); }
    if (/\.mp3/i.test(t)) { pol.mp3++; polDetail.push(`${r.book}-${r.test} s${n} .mp3`); }
    if (/Answer\s+Cam/i.test(t)) { pol.AnswerCam++; polDetail.push(`${r.book}-${r.test} s${n} AnswerCam`); }
    const al = t.split("\n").filter((l) => /^\s*Answers?\b/i.test(l));
    if (al.length) { pol.answerLead++; polDetail.push(`${r.book}-${r.test} s${n} answerLead=${JSON.stringify(al[0].slice(0, 80))}`); }
  }
}
console.log("counts:", JSON.stringify(pol));
console.log(polDetail.length ? polDetail.join("\n") : "(no pollution found)");

console.log("\n### 5) 串行/漏段检查：section N 末尾 60 字符 是否出现在 section N+1 前 400 字符中（重叠）");
for (const r of results) {
  if (!r.ok || !r.sections) continue;
  for (let n = 1; n <= 3; n++) {
    const a = r.sections_full["section" + n], b = r.sections_full["section" + (n + 1)];
    if (!a || !b) continue;
    const seg = a.trim().slice(-60);
    if (b.slice(0, 400).includes(seg)) console.log(`OVERLAP ${r.book}-${r.test} s${n}->s${n+1}: ${JSON.stringify(seg)}`);
  }
}
console.log("(overlap scan done)");

console.log("\n### 6) 内容连续性：section N 末尾 + section N+1 开头 拼接样本（抽查 10-1 / 15-2 / 21-1）");
for (const [b, t] of [[10, 1], [15, 2], [21, 1]]) {
  const r = results.find((x) => x.book === b && x.test === t);
  if (!r || !r.ok) { console.log(`${b}-${t}: no data`); continue; }
  console.log(`\n===== ${b}-${t} (slug=${r.slug}) =====`);
  for (let n = 1; n <= 3; n++) {
    const a = r.sections_full["section" + n], c = r.sections_full["section" + (n + 1)];
    if (!a || !c) continue;
    console.log(`  -- s${n} TAIL: ${tail(a.trim(), 140)}`);
    console.log(`  -- s${n + 1} HEAD: ${show(c.trim(), 140)}`);
  }
  console.log(`  -- s4 TAIL: ${tail(r.sections_full.section4.trim(), 140)}`);
}

console.log("\n### 7) 总文本 vs 4 段之和（判断是否丢内容）");
for (const r of results) {
  if (!r.ok || !r.sections) continue;
  const sum = [1, 2, 3, 4].reduce((n, i) => n + (r.sections_full["section" + i]?.length || 0), 0);
  const diff = r.text_chars - sum;
  console.log(`${r.book}-${r.test} text=${r.text_chars} sum4=${sum} diff=${diff}`);
}
