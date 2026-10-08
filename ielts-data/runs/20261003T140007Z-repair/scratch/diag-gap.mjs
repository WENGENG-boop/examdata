import fs from "node:fs";
import { parseHtml, collectBlocks, nodeText } from "../../../../ielts-api/html-questions.mjs";

const raw = fs.readFileSync(process.argv[2], "utf8");
const arr = JSON.parse(raw);
const html = arr[0].content.rendered;
const root = parseHtml(html);
const blocks = collectBlocks(root);
const needle = process.argv[3] || "20";
const needle2 = process.argv[4] || "27";
const texts = blocks.map((b) => nodeText(b.node).replace(/\s+/g, " ").trim());
let a = -1, b = -1;
for (let i = 0; i < texts.length; i++) {
  if (a < 0 && new RegExp(`(^|[^0-9])${needle}([^0-9]|$)`).test(texts[i])) a = i;
  if (a >= 0 && b < 0 && i > a && new RegExp(`(^|[^0-9])${needle2}([^0-9]|$)`).test(texts[i])) { b = i; break; }
}
console.log("blocks total:", blocks.length, "a=", a, "b=", b);
const lo = Math.max(0, a - 3), hi = Math.min(blocks.length - 1, b + 2);
for (let i = lo; i <= hi; i++) {
  console.log(`[${i}] <${blocks[i].node.tag}> ${JSON.stringify(texts[i].slice(0, 180))}`);
}
