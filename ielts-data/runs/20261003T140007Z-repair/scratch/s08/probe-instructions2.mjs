import fs from "node:fs";
import path from "node:path";
import { parsePtePage, expectedFor } from "../../../../../ielts-api/pte.mjs";
const ROOT = "C:/Users/weo/Desktop/api";
const RAW = path.join(ROOT, "tmp_audit_ielts/completeness_20261003");
const idx = JSON.parse(fs.readFileSync(path.join(ROOT, "ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json"), "utf8"));
const seen = new Set();
let i = 0;
for (const e of idx) {
  if (e.raw_index == null) continue;
  if (![20,21].includes(e.book)) continue;
  const raw = fs.readFileSync(path.join(RAW, `raw-${e.raw_index}.txt`), "utf8");
  const skill = e.skill === "reading" ? "academic_reading" : "listening";
  let expected = null;
  try { expected = expectedFor(e.book, e.test, skill); } catch {}
  const r = parsePtePage(raw, { book: e.book, test: e.test, skill, slug: e.slug, page_id: e.page_id }, expected);
  if (!r.ok) continue;
  for (const g of r.question_groups) {
    if (g.structural) continue;
    const kinds = [...new Set(g.slots.map(s => s.kind))].join("+");
    const poolKinds = g.pools.map(p => p.kind + ":" + p.options.length).join(",");
    const inst = (g.instruction||"").replace(/\s+/g," ").slice(0,160);
    const key = `${e.book}-${e.test}-${e.skill} ${kinds} ${poolKinds} ${inst}`;
    if (seen.has(key)) continue;
    seen.add(key);
    i++;
    console.log(`[${i}] b${e.book}t${e.test} ${e.skill} kinds=${kinds} pools=${poolKinds} wl=${g.word_limit}`);
    console.log("   ", JSON.stringify(inst));
    if (i >= 70) { console.log("TRUNCATED"); process.exit(0); }
  }
}
