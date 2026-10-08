import fs from "node:fs";
import { parseHtml, collectQuestionGroups } from "../../../../ielts-api/html-questions.mjs";
const raw = fs.readFileSync("C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003/raw-23.txt", "utf8");
const html = JSON.parse(raw)[0].content.rendered;
const root = parseHtml(html);
const { groups } = collectQuestionGroups(root, { maxNumber: 40, stopAtHeadings: false });
const g2 = groups.find((g) => g.range[0] === 7);
console.log("G2 slots:", JSON.stringify(g2.slots, null, 1).slice(0, 1200));
console.log("G2 span:", g2.block_span);
