import fs from "node:fs";
import { parseHtml, collectBlocks, nodeText, normalizeWs } from "../../../../ielts-api/html-questions.mjs";
const idx = JSON.parse(fs.readFileSync("../evidence/S04-raw-index.json", "utf8"));
const base = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003/";
let total = 0, with3 = 0, withH = 0;
const samples = [];
for (const e of idx) {
  if (e.skill !== "reading" || !e.raw_index) continue;
  let raw;
  try { raw = JSON.parse(fs.readFileSync(base + `raw-${e.raw_index}.txt`, "utf8")); } catch { continue; }
  const html = raw[0] && raw[0].content && raw[0].content.rendered;
  if (!html) continue;
  total++;
  const root = parseHtml(html);
  const blocks = collectBlocks(root);
  const hs = blocks.filter((b) => /^h[1-6]$/.test(b.tag));
  if (hs.length >= 2) withH++;
  const cands = [];
  for (const b of blocks) {
    if (b.tag !== "p") continue;
    const kids = (b.children || []).filter((c) => c.type === "element");
    const texts = (b.children || []).filter((c) => c.type === "text" && c.text.trim());
    if (kids.length === 1 && texts.length === 0 && (kids[0].tag === "strong" || kids[0].tag === "b")) {
      const t = normalizeWs(nodeText(kids[0], { block: false }));
      if (t.length >= 3 && t.length <= 120 && !/^questions?\b/i.test(t) && !/^part\s+\d/i.test(t)) cands.push(t);
    }
  }
  if (cands.length >= 2) with3++;
  if (e.book <= 2 && e.test === 1) samples.push(`[${e.book}-${e.test}] h=${hs.length} strong=${cands.length} :: ${cands.slice(0, 5).join(" | ").slice(0, 200)}`);
}
console.log(`reading pages: ${total}, h-tag>=2: ${withH}, strong-title>=2: ${with3}`);
for (const s of samples) console.log(s);
