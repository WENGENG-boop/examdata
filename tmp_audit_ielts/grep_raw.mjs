import { readFileSync } from "node:fs";
const j = JSON.parse(readFileSync(process.argv[2], "utf8"));
const html = j[0].content.rendered;
const n = process.argv[3];
let idx = 0, count = 0;
while (count < 8) {
  const i = html.indexOf(n, idx);
  if (i < 0) break;
  console.log(`--- @${i}: ` + html.slice(Math.max(0, i - 60), i + 80).replace(/<[^>]+>/g, "|").replace(/\s+/g, " "));
  idx = i + 1;
  count++;
}
if (count === 0) console.log("NO OCCURRENCE of", JSON.stringify(n));
