import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectBlocks, normalizeWs, nodeText, attr } from "../../../../ielts-api/html-questions.mjs";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const index = JSON.parse(fs.readFileSync("../evidence/S04-raw-index.json", "utf8"));
const rows = Array.isArray(index) ? index : (index.rows || index.entries || []);
let total = 0;
for (const row of rows) {
  const idx = row.raw_index ?? row.rawIndex ?? row.idx;
  const file = path.join(RAW_DIR, `raw-${idx}.txt`);
  let raw;
  try { raw = JSON.parse(fs.readFileSync(file, "utf8")); } catch { continue; }
  const root = parseHtml(raw[0].content.rendered);
  const blocks = collectBlocks(root);
  for (let i = 0; i < blocks.length; i++) {
    const el = blocks[i];
    if (el.tag !== "p") continue;
    const style = (attr(el, "style") || "").toLowerCase();
    if (!/text-align\s*:\s*center/.test(style)) continue;
    const children = el.children || [];
    const first = children.find((c) => (c.type === "text" && c.text.trim()) || c.type === "element");
    if (!first || first.type !== "element" || (first.tag !== "strong" && first.tag !== "b")) continue;
    const after = children.slice(children.indexOf(first) + 1);
    const next = after.find((c) => (c.type === "text" && c.text.trim()) || c.type === "element");
    if (!next || next.type !== "element" || next.tag !== "br") continue;
    const title = normalizeWs(nodeText(first, { block: false }));
    const restParts = [];
    for (const c of children.slice(children.indexOf(next) + 1)) {
      if (c.type === "text") { if (c.text.trim()) restParts.push(c.text); }
      else restParts.push(nodeText(c, { block: false }));
    }
    const rest = normalizeWs(restParts.join(" "));
    console.log(`${row.book}-${row.test} raw=${idx} b${i} title=${JSON.stringify(title)} rest=${JSON.stringify(rest.slice(0, 70))}`);
    total++;
  }
}
console.log("total centered merged detections:", total);
