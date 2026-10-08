import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectQuestionGroups, nodeText } from "../../../../ielts-api/html-questions.mjs";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const index = JSON.parse(fs.readFileSync("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json", "utf8"));
const filled = [], empty = [], covered = [];
for (const e of index) {
  if (e.raw_index == null) continue;
  const raw = fs.readFileSync(path.join(RAW_DIR, `raw-${e.raw_index}.txt`), "utf8");
  let html; try { html = JSON.parse(raw)[0].content.rendered; } catch { continue; }
  const root = parseHtml(html);
  const isListening = e.skill !== "reading";
  const g = collectQuestionGroups(root, { maxNumber: 45, stopAtHeadings: !isListening });
  for (const gr of g.groups) {
    for (const s of gr.slots.filter((x) => x.kind === "derived")) {
      const tag = `raw-${e.raw_index} ${e.book}-${e.test}-${e.skill} G${gr.index} Q${s.number} [${gr.range[0]}-${gr.range[1]}]`;
      if ((s.prompt || "").trim().length > 0) { filled.push(`${tag} prompt="${s.prompt.slice(0, 70).replace(/\n/g, "\n")}"`); continue; }
      let other = null;
      for (const g2 of g.groups) {
        if (g2 === gr) continue;
        if (g2.slots.some((x) => x.number === s.number && x.kind !== "derived")) { other = g2.index; break; }
      }
      if (other != null) { covered.push(`${tag} coveredBy=G${other}`); continue; }
      empty.push(`${tag} "${(gr.heading_text || "").replace(/\s+/g, " ").slice(0, 60)}"`);
    }
  }
}
fs.writeFileSync("gap-refined2.txt",
  `=== DERIVED WITH PROMPT (filled): ${filled.length} ===\n` + filled.join("\n") +
  `\n\n=== EMPTY DERIVED (no other group): ${empty.length} ===\n` + empty.join("\n") +
  `\n\n=== COVERED BY OTHER GROUP: ${covered.length} ===\n` + covered.join("\n") + "\n");
console.log("filled:", filled.length, "empty:", empty.length, "covered:", covered.length);
