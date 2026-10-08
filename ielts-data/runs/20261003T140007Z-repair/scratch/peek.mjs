import fs from "node:fs";

const [, , file, needle, before = "300", after = "900"] = process.argv;
if (!file || !needle) {
  console.error("usage: node peek.mjs <file> <needle> [before] [after]");
  process.exit(2);
}
const s = fs.readFileSync(file, "utf8");
let idx = -1;
let count = 0;
while ((idx = s.indexOf(needle, idx + 1)) !== -1 && count < 5) {
  console.log(`--- match ${count} at ${idx} ---`);
  console.log(s.slice(Math.max(0, idx - Number(before)), idx + Number(after)));
  count++;
}
if (count === 0) console.log("no match");
