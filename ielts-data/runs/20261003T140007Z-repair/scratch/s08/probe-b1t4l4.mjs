import fs from "node:fs";
import { parsePtePage, expectedFor } from "../../../../../ielts-api/pte.mjs";
const RAW = "../../../../../tmp_audit_ielts/completeness_20261003";
const idx = JSON.parse(fs.readFileSync("../../evidence/S04-raw-index.json","utf8"));
const entry = idx.find((x) => x.book===1 && x.test===4 && x.skill==="listening");
const text = fs.readFileSync(`${RAW}/raw-${entry.raw_index}.txt`, "utf8");
const p = parsePtePage(text, { book: 1, test: 4, skill: "listening", slug: entry.slug, page_id: entry.page_id }, expectedFor(1,4,"listening"));
for (const n of [26,31,41,42]) {
  const q = p.questions.find(x=>x.number===n);
  console.log("Q"+n+":", JSON.stringify(q).slice(0,400));
}
console.log("questions_missing:", JSON.stringify(p.questions_missing));
console.log("counts:", JSON.stringify(p.counts));
console.log("warnings:", JSON.stringify(p.warnings).slice(0,500));
