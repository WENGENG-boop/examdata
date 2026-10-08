import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectQuestionGroups } from "../../../../ielts-api/html-questions.mjs";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const idx = process.argv[2];
const gi = Number(process.argv[3] ?? -1);
const nums = process.argv[4] ? process.argv[4].split(",").map(Number) : null;
const raw = JSON.parse(fs.readFileSync(path.join(RAW_DIR, `raw-${idx}.txt`), "utf8"));
const root = parseHtml(raw[0].content.rendered);
const { groups } = collectQuestionGroups(root, { maxNumber: 45, stopAtHeadings: true });
for (const g of groups) {
  if (gi >= 0 && g.index !== gi) continue;
  for (const s of g.slots) {
    if (nums && !nums.includes(s.number)) continue;
    console.log(`Q${s.number} [${s.kind}] len=${(s.prompt||"").length} prompt=${JSON.stringify(s.prompt)}`);
  }
}
