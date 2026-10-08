import fs from "node:fs";
const [rawIdx, needle, win] = process.argv.slice(2);
const raw = JSON.parse(fs.readFileSync(`C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003/raw-${rawIdx}.txt`, "utf8"));
const html = raw[0].content.rendered;
const w = Number(win || 260);
let from = 0, count = 0;
while (count < 4) {
  const pos = html.indexOf(needle, from);
  if (pos < 0) break;
  console.log(`--- match at ${pos} ---`);
  console.log(html.slice(Math.max(0, pos - w), pos + needle.length + w).replace(/\n/g, "\n"));
  from = pos + needle.length;
  count++;
}
if (count === 0) console.log("NOT FOUND");
