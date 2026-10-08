import fs from "node:fs";
import { parsePtePage, expectedFor } from "../../../../ielts-api/pte.mjs";
const [rawIdx, book, test, skillRaw] = process.argv.slice(2);
const raw = fs.readFileSync(`C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003/raw-${rawIdx}.txt`, "utf8");
const skill = skillRaw === "reading" ? "academic_reading" : "listening";
const r = parsePtePage(raw, { book: +book, test: +test, skill }, expectedFor(+book, +test, skill));
console.log("status", r.parse_status, "warnings", JSON.stringify(r.warnings.map(w=>w.kind)));
for (const g of r.question_groups) {
  console.log(`G${g.index} [${g.range}] slots=${g.slots.length} instr="${g.instruction.slice(0,60)}"`);
  console.log("   kinds:", g.slots.map(s=>`${s.number}:${s.kind}`).join(" "));
}
