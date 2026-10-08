import fs from "node:fs";
import { parsePtePage, expectedFor } from "../../../../../ielts-api/pte.mjs";
const base = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
// find a group with assets and a reading passage shape
const files = ["raw-5.txt","raw-8.txt","raw-17.txt"];
for (const f of files) {
  const raw = fs.readFileSync(`${base}/${f}`, "utf8");
  const idx = { "raw-5.txt": [1,2], "raw-8.txt": [1,3], "raw-17.txt": [1,4] }[f];
  const p = parsePtePage(raw, { book: idx[0], test: idx[1], skill: "academic_reading" }, expectedFor(idx[0], idx[1], "academic_reading"));
  console.log(`== ${f} b${idx[0]}t${idx[1]} ok=${p.ok}`);
  const g = (p.question_groups||[]).find(g => (g.assets||[]).length);
  if (g) console.log("group assets:", JSON.stringify(g.assets).slice(0, 500), "range", g.range);
  const pas = (p.passages||[])[0];
  if (pas) console.log("passage keys:", Object.keys(pas), "| range:", pas.range, "| text len:", (pas.text||"").length);
}
