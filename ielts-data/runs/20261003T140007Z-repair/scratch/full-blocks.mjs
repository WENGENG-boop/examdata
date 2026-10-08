import fs from "node:fs";
import path from "node:path";
import { parseHtml, nodeText } from "../../../../ielts-api/html-questions.mjs";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const [rawIdx, ...idxs] = process.argv.slice(2).map(Number);
const raw = fs.readFileSync(path.join(RAW_DIR, `raw-${rawIdx}.txt`), "utf8");
const parsed = JSON.parse(raw);
const html = parsed[0].content.rendered;
const doc = parseHtml(html);
// find top-level blocks the same way dump-blocks does: walk body children
const out = [];
const walk = (n) => {
  if (n.type === "element") {
    const tag = n.tag;
    out.push({ tag, node: n });
    if (["p", "h1", "h2", "h3", "h4", "figure", "table", "ul", "ol", "div"].includes(tag)) return;
  }
  for (const c of n.children || []) walk(c);
};
for (const c of doc.children || []) walk(c);
for (const i of idxs) {
  const b = out[i];
  if (!b) { console.log(`[${i}] <missing>`); continue; }
  console.log(`\n[${i}] <${b.tag}> FULL:`);
  console.log(nodeText(b.node, { block: true }));
}
