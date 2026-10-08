import fs from "node:fs";
import { parseHtml, collectBlocks, nodeText } from "../../../../ielts-api/html-questions.mjs";
const raw = fs.readFileSync(process.argv[2], "utf8");
const arr = JSON.parse(raw);
const html = arr[0].content.rendered;
const root = parseHtml(html);
const blocks = collectBlocks(root);
const texts = blocks.map((b) => nodeText(b).replace(/\s+/g, " ").trim());
for (let i = 0; i < blocks.length; i++) {
  console.log(`[${i}] <${blocks[i].tag}> ${JSON.stringify(texts[i].slice(0, 150))}`);
}
