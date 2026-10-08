import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectBlocks, collectQuestionGroups, nodeText, ownText, normalizeWs } from "../../../../ielts-api/html-questions.mjs";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const index = JSON.parse(fs.readFileSync("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json", "utf8"));

const real = [], covered = [], inPage = [];
for (const e of index) {
  if (e.raw_index == null) continue;
  const raw = fs.readFileSync(path.join(RAW_DIR, `raw-${e.raw_index}.txt`), "utf8");
  let html; try { html = JSON.parse(raw)[0].content.rendered; } catch { continue; }
  const root = parseHtml(html);
  const isListening = e.skill !== "reading";
  const g = collectQuestionGroups(root, { maxNumber: 45, stopAtHeadings: !isListening });
  const pageText = nodeText(root, { block: true });
  for (const gr of g.groups) {
    const derived = gr.slots.filter((s) => s.kind === "derived").map((s) => s.number);
    if (!derived.length) continue;
    for (const n of derived) {
      // other group same page with explicit slot
      let other = null;
      for (const g2 of g.groups) {
        if (g2 === gr) continue;
        if (g2.slots.some((s) => s.number === n && s.kind !== "derived")) { other = g2.index; break; }
      }
      const tag = `raw-${e.raw_index} G${gr.index} Q${n} [${gr.range[0]}-${gr.range[1]}] "${(gr.heading_text||"").replace(/\s+/g," ").slice(0,70)}"`;
      if (other != null) { covered.push(`${tag} coveredBy=G${other}`); continue; }
      // does the page contain the marker (N) anywhere?
      const hasParen = new RegExp(`\\(${n}\\s*\\)`).test(pageText) || new RegExp(`\\(${n}[^\\d]{0,2}\\)`).test(pageText);
      const hasDot = new RegExp(`(^|\\s)${n}\\s*[.．]`).test(pageText);
      real.push(tag);
      inPage.push(`${tag} parenMarker=${hasParen} dotNum=${hasDot}`);
    }
  }
}
fs.writeFileSync("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/scratch/gap-refined.txt",
  "=== COVERED BY OTHER GROUP ===\n" + covered.join("\n") + "\n\n=== REAL (no other group) ===\n" + real.join("\n") + "\n\n=== REAL + page marker check ===\n" + inPage.join("\n") + "\n");
console.log("covered:", covered.length, "real:", real.length);
console.log(inPage.join("\n"));
