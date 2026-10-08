import fs from "node:fs";
import { parsePtePage, expectedFor } from "../../../../ielts-api/pte.mjs";
const raw = fs.readFileSync("C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003/raw-208.txt", "utf8");
const r = parsePtePage(raw, { book: 14, test: 1, skill: "listening", slug: "ielts-listening-test-175", page_id: 2444 }, expectedFor(14, 1, "listening"));
console.log("ok", r.ok, "status", r.parse_status);
console.log("warnings", JSON.stringify(r.warnings));
for (const g of r.question_groups) {
  console.log(`G${g.index} [${g.range}] slots=${g.slots.length} kind=${g.slots[0]?.kind} wl=${g.word_limit}`);
  console.log("  instr:", g.instruction.slice(0, 100));
  console.log("  nums:", g.slots.map((s) => s.number).join(","));
  if (g.out_of_range?.length) console.log("  oor:", JSON.stringify(g.out_of_range.slice(0, 8)));
}
console.log("answer_missing", JSON.stringify(r.answer_missing));
