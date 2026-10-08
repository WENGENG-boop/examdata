import fs from "node:fs";
import { parseHtml, collectBlocks, ownTextLines, nodePath } from "../../../../ielts-api/html-questions.mjs";
const raw = fs.readFileSync("C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003/raw-23.txt", "utf8");
const html = JSON.parse(raw)[0].content.rendered;
const root = parseHtml(html);
const blocks = collectBlocks(root);
for (let i = 33; i < 46; i++) {
  const b = blocks[i];
  if (!b) continue;
  const lines = ownTextLines(b);
  console.log(`--- block[${i}] <${b.tag}> ${nodePath(b)} lines=${lines.length}`);
  for (const l of lines.slice(0, 8)) console.log("    ", JSON.stringify(l.slice(0, 90)));
}
