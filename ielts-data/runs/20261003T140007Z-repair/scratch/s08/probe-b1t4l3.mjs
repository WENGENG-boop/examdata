import fs from "node:fs";
import { parsePtePage, expectedFor } from "../../../../../ielts-api/pte.mjs";
const RAW = "../../../../../tmp_audit_ielts/completeness_20261003";
const idx = JSON.parse(fs.readFileSync("../../evidence/S04-raw-index.json","utf8"));
const entry = idx.find((x) => x.book===1 && x.test===4 && x.skill==="listening");
const text = fs.readFileSync(`${RAW}/raw-${entry.raw_index}.txt`, "utf8");
const p = parsePtePage(text, { book: 1, test: 4, skill: "listening", slug: entry.slug, page_id: entry.page_id }, expectedFor(1,4,"listening"));
console.log("groups:", JSON.stringify((p.question_groups||[]).map(g=>[g.range[0],g.range[1]])));
console.log("questions numbers:", JSON.stringify((p.questions||[]).map(q=>q.number)));
// search raw for 41/42 as question markers
for (const pat of [/\(41\)/g, /\(42\)/g, /<strong>41<\/strong>/g, /<strong>42<\/strong>/g]) {
  let m, count=0;
  while ((m = pat.exec(text)) && count<3) { count++; console.log("pat", pat, "at", m.index, JSON.stringify(text.slice(m.index-100,m.index+150))); }
  if (!count) console.log("pat", pat, "no match");
}
