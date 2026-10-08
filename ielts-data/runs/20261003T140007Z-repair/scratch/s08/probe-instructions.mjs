import fs from "node:fs";
import path from "node:path";
import { parsePtePage, expectedFor } from "../../../../../ielts-api/pte.mjs";
const ROOT = "C:/Users/weo/Desktop/api";
const RAW = path.join(ROOT, "tmp_audit_ielts/completeness_20261003");
const idx = JSON.parse(fs.readFileSync(path.join(ROOT, "ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json"), "utf8"));
const seen = new Map();
let n = 0;
for (const e of idx) {
  if (e.raw_index == null) continue;
  if (![1,3,10,20,21].includes(e.book)) continue;
  const raw = fs.readFileSync(path.join(RAW, `raw-${e.raw_index}.txt`), "utf8");
  const skill = e.skill === "reading" ? "academic_reading" : "listening";
  let expected = null;
  try { expected = expectedFor(e.book, e.test, skill); } catch {}
  const r = parsePtePage(raw, { book: e.book, test: e.test, skill, slug: e.slug, page_id: e.page_id }, expected);
  if (!r.ok) continue;
  n++;
  for (const g of r.question_groups) {
    if (g.structural) continue;
    const kinds = [...new Set(g.slots.map(s => s.kind))].join("+");
    const poolKinds = g.pools.map(p => p.kind + ":" + p.options.length).join(",");
    const key = kinds + " | " + poolKinds + " | " + (g.instruction||"").replace(/\s+/g," ").slice(0,110);
    if (!seen.has(key)) seen.set(key, { book: e.book, test: e.test, skill: e.skill, example: g.instruction, wl: g.word_limit, pools: g.pools.map(p=>({kind:p.kind, n:p.options.length, first:p.options[0]})), nums: g.numbers.slice(0,3) });
  }
}
console.log("parsed pages:", n, "distinct group signatures:", seen.size);
let i = 0;
for (const [k, v] of seen) {
  i++;
  console.log(`--- [${i}] b${v.book}t${v.test} ${v.skill} wl=${v.wl} pools=${JSON.stringify(v.pools)} nums=${JSON.stringify(v.nums)}`);
  console.log("   ", JSON.stringify(v.example));
  if (i >= 60) break;
}
