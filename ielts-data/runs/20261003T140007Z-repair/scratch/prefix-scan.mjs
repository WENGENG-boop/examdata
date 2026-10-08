import fs from "node:fs";
import { parseHtml, collectBlocks, nodeText, normalizeWs } from "../../../../ielts-api/html-questions.mjs";
const idx = JSON.parse(fs.readFileSync("../evidence/S04-raw-index.json", "utf8"));
const seen = new Map();
const base = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003/";
let n = 0;
for (const e of idx) {
  if (!e.raw_index) continue;
  let raw;
  try { raw = JSON.parse(fs.readFileSync(base + `raw-${e.raw_index}.txt`, "utf8")); } catch { continue; }
  const html = raw[0] && raw[0].content && raw[0].content.rendered;
  if (!html) continue;
  n++;
  const root = parseHtml(html);
  for (const b of collectBlocks(root)) {
    const t = normalizeWs(nodeText(b));
    const m = /^(.{0,40}?)\bQuestions?\s+\d{1,3}\b/.exec(t);
    if (!m) continue;
    const prefix = m[1].trim();
    const key = prefix.replace(/\d+/g, "N").toUpperCase();
    if (!seen.has(key)) seen.set(key, { count: 0, sample: t.slice(0, 90), raw: e.raw_index });
    seen.get(key).count++;
  }
}
console.log("scanned raws:", n);
for (const [k, v] of [...seen.entries()].sort((a, b) => b[1].count - a[1].count)) {
  console.log(`${JSON.stringify(k)} x${v.count}  e.g. [raw-${v.raw}] ${v.sample}`);
}
