import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectQuestionGroups, collectPassages } from "../../../../ielts-api/html-questions.mjs";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const index = JSON.parse(fs.readFileSync("../evidence/S04-raw-index.json", "utf8"));
for (const row of index) {
  if (row.skill !== "reading" || !row.raw_index) continue;
  const raw = JSON.parse(fs.readFileSync(path.join(RAW_DIR, `raw-${row.raw_index}.txt`), "utf8"));
  const root = parseHtml(raw[0].content.rendered);
  const groups = collectQuestionGroups(root, { maxNumber: 45, stopAtHeadings: true }).groups;
  const { passages, notes } = collectPassages(root, { groups, expectedPassages: 3 });
  const n = passages.length;
  if (notes.length || n !== 3) console.log(`${row.book}-${row.test} raw=${row.raw_index} n=${n} notes=${JSON.stringify(notes)}`);
}
console.log("done");
