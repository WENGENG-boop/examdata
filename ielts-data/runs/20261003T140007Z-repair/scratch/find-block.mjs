import fs from "node:fs";
import { parseHtml, collectBlocks, nodeText } from "../../../../ielts-api/html-questions.mjs";
const [rawIdx, needle] = process.argv.slice(2);
const raw = JSON.parse(fs.readFileSync(`C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003/raw-${rawIdx}.txt`, "utf8"));
const html = raw[0].content.rendered;
const root = parseHtml(html);
const blocks = collectBlocks(root);
console.log("blocks:", blocks.length);
for (let i = 0; i < blocks.length; i++) {
  const t = nodeText(blocks[i]).replace(/\s+/g, " ").trim();
  if (t.includes(needle)) {
    console.log(`[${i}] <${blocks[i].tag}> ${JSON.stringify(t.slice(0, 180))}`);
  }
}
