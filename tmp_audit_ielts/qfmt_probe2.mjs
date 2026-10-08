import { readFileSync } from "node:fs";
// 用法: node qfmt_probe2.mjs <jsonfile> <nums...>
const [file, ...nums] = process.argv.slice(2);
const j = JSON.parse(readFileSync(file, "utf8"));
const html = j[0].content.rendered;
for (const n of nums.map(Number)) {
  const re = new RegExp("(?:>|\\n)" + n + "(?=\\s|[.．)])", "g");
  let m, hits = [];
  while ((m = re.exec(html)) && hits.length < 2) {
    const ctx = html.slice(m.index, m.index + 120).replace(/<[^>]+>/g, "|").replace(/\s+/g, " ");
    hits.push(ctx);
  }
  console.log("Q" + n + ":");
  hits.forEach(h => console.log("   ", h));
}
