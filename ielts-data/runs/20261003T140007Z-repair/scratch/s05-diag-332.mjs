import fs from "node:fs";
import { parsePtePage, expectedFor } from "../../../../ielts-api/pte.mjs";

const raw = fs.readFileSync("C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003/raw-332.txt", "utf8");
const r = parsePtePage(raw, { book: 21, test: 4, skill: "listening", slug: "ielts-listening-test-208", page_id: 12718 }, expectedFor(21, 4, "listening"));
console.log("ok", r.ok, "status", r.parse_status, "qc", r.question_count, "ac", r.answer_count, "expected", r.expected_total);
for (const g of r.question_groups) {
  console.log(`G${g.index} [${g.range}] slots=${g.slots.length} wl=${g.word_limit}`);
  console.log("  instr:", (g.instruction || "").slice(0, 140).replace(/\n/g, " | "));
  console.log("  nums:", g.slots.map((s) => s.number).join(","));
  if (g.out_of_range?.length) console.log("  oor:", JSON.stringify(g.out_of_range.map(o => o.number)));
}
console.log("questions_missing", JSON.stringify(r.questions_missing));
console.log("answer_missing", JSON.stringify(r.answer_missing));
