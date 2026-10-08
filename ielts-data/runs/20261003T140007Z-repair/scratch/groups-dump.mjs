import fs from "node:fs";
import { parseHtml, collectQuestionGroups } from "../../../../ielts-api/html-questions.mjs";
const [rawIdx] = process.argv.slice(2);
const raw = JSON.parse(fs.readFileSync(`C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003/raw-${rawIdx}.txt`, "utf8"));
const html = raw[0].content.rendered;
const root = parseHtml(html);
const groups = collectQuestionGroups(root, { maxNumber: 45, stopAtHeadings: false });
console.log("groups:", groups.groups.length, "notes:", JSON.stringify(groups.notes));
for (const g of groups.groups) {
  console.log(`G${g.index} [${g.range}] slots=${g.slots.length} structural=${!!g.structural} heading="${g.heading_text.slice(0, 50)}"`);
}
