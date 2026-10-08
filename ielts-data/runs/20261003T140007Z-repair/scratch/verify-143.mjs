import fs from "node:fs";
import { parsePtePage, expectedFor } from "../../../../ielts-api/pte.mjs";

const raw = fs.readFileSync("C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003/raw-143.txt", "utf8");
const expected = expectedFor(10, 1, "academic_reading");
const r = parsePtePage(raw, { book: 10, test: 1, skill: "academic_reading", slug: "ielts-reading-test-36", page_id: 5040 }, expected);
console.log("ok:", r.ok, "status:", r.parse_status);
console.log("warnings:", JSON.stringify(r.warnings));
console.log("partial_reasons:", JSON.stringify(r.partial_reasons));
console.log("questions:", r.question_count, "answers:", r.answer_count);
console.log("answer_missing:", JSON.stringify(r.answer_missing));
console.log("questions_missing:", JSON.stringify(r.questions_missing));
// dump out_of_range across groups
for (const g of r.question_groups) {
  if (g.out_of_range && g.out_of_range.length) console.log(`G${g.index} out_of_range:`, JSON.stringify(g.out_of_range));
}
// dump Q34 detail
const q34 = r.questions.find((q) => q.number === 34);
console.log("Q34:", JSON.stringify(q34));
const q35 = r.questions.find((q) => q.number === 35);
console.log("Q35:", JSON.stringify(q35));
