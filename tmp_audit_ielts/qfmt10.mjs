import { readFileSync } from "node:fs";
const j = JSON.parse(readFileSync("pte10_1_raw.json", "utf8"));
const html = j[0].content.rendered;
for (const n of [17, 18, 19, 27, 28, 29, 30, 31]) {
  const re = new RegExp("(?:>|\\n)" + n + "(?=\\s|[.．)])", "g");
  let m, hits = [];
  while ((m = re.exec(html)) && hits.length < 3) {
    const ctx = html.slice(m.index, m.index + 130).replace(/<[^>]+>/g, "|").replace(/\s+/g, " ");
    hits.push(ctx);
  }
  console.log("Q" + n + ":");
  hits.forEach(h => console.log("   ", h));
}
