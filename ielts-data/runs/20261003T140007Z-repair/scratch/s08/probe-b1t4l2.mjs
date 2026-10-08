import fs from "node:fs";
import { parsePtePage, expectedFor } from "../../../../../ielts-api/pte.mjs";
const RAW = "../../../../../tmp_audit_ielts/completeness_20261003";
const idx = JSON.parse(fs.readFileSync("../../evidence/S04-raw-index.json","utf8"));
const e1 = expectedFor(1,4,"listening");
console.log("expectedFor(1,4,listening):", JSON.stringify({status:e1.status,total:e1.expected_total,n:e1.numbers.length,parts:e1.parts.map(p=>p.part+":"+p.ranges.map(r=>r.join("-")).join(","))}));
const e2 = expectedFor(1,2,"listening");
console.log("expectedFor(1,2,listening):", JSON.stringify({status:e2.status,total:e2.expected_total,n:e2.numbers.length}));
const entry = idx.find((x) => x.book===1 && x.test===4 && x.skill==="listening");
const text = fs.readFileSync(`${RAW}/raw-${entry.raw_index}.txt`, "utf8");
// context around '26' and '41'
for (const pat of [/Q?26/i, /\b41\b/, /\b42\b/]) {
  const m = pat.exec(text);
  console.log("=== pattern", pat, "at", m && m.index);
  if (m) console.log(JSON.stringify(text.slice(Math.max(0,m.index-200), m.index+300)));
}
