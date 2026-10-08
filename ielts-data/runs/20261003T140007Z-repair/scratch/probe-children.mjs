import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectBlocks, normalizeWs, nodeText } from "../../../../ielts-api/html-questions.mjs";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const idx = Number(process.argv[2] || 147);
const from = Number(process.argv[3] || 0), to = Number(process.argv[4] || 10);
const raw = JSON.parse(fs.readFileSync(path.join(RAW_DIR, `raw-${idx}.txt`), "utf8"));
const root = parseHtml(raw[0].content.rendered);
const blocks = collectBlocks(root);
for (let i = from; i <= Math.min(to, blocks.length - 1); i++) {
  const el = blocks[i];
  const kids = (el.children || []).map((c) => c.type === "text" ? (c.text.trim() ? `#text(${JSON.stringify(c.text.slice(0,30))})` : null) : `<${c.tag}>`).filter(Boolean);
  console.log(`[${i}] ${el.tag} :: ${kids.join(" ")}`);
  const firstEl = (el.children || []).find((c) => c.type === "element");
  if (firstEl) console.log(`    firstEl=<${firstEl.tag}> text=${JSON.stringify(normalizeWs(nodeText(firstEl, { block: false })).slice(0, 90))}`);
}
