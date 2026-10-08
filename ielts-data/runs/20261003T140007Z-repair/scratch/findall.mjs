import fs from "node:fs";
const rawIdx = process.argv[2];
const needle = process.argv[3];
const raw = fs.readFileSync(`C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003/raw-${rawIdx}.txt`, "utf8");
const html = JSON.parse(raw)[0].content.rendered;
let pos = 0, n = 0;
while ((pos = html.indexOf(needle, pos)) >= 0) {
  n++;
  console.log(`--- match ${n} at ${pos} ---`);
  console.log(html.slice(Math.max(0, pos - 80), pos + 200).replace(/\n/g, "\n"));
  pos += needle.length;
}
if (!n) console.log("no match");
