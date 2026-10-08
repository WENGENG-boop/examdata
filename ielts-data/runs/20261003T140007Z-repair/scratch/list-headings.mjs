import fs from "node:fs";
import { parseHtml, findAll, isElement, rawText } from "../../../../ielts-api/html-questions.mjs";

const file = process.argv[2];
const root = parseHtml(fs.readFileSync(file, "utf8"));
const hs = findAll(root, (n) => isElement(n) && /^h[1-6]$/.test(n.tag));
for (const h of hs) {
  const t = rawText(h).replace(/\s+/g, " ").trim();
  console.log(h.tag, JSON.stringify(t.slice(0, 90)));
}
console.log("total headings:", hs.length);
