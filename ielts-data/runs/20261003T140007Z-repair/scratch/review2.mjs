import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectBlocks, collectQuestionGroups, ownTextLines } from "../../../../ielts-api/html-questions.mjs";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const index = JSON.parse(fs.readFileSync("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json", "utf8"));
const newDot = [], droppedOpt = [], optWithGap = [];
const RE_NEW_DOT = /^(\d{1,3})[ \t]*[.\uFF0E]((?![ \t\d])[^\n]*)$/;
for (const e of index) {
  if (e.raw_index == null) continue;
  const raw = fs.readFileSync(path.join(RAW_DIR, `raw-${e.raw_index}.txt`), "utf8");
  let html; try { html = JSON.parse(raw)[0].content.rendered; } catch { continue; }
  const root = parseHtml(html);
  const isListening = e.skill !== "reading";
  const g = collectQuestionGroups(root, { maxNumber: 45, stopAtHeadings: !isListening });
  const tag = `raw-${e.raw_index} ${e.book}-${e.test}-${e.skill}`;
  // new-DOT candidate lines: dot immediately followed by non-space non-digit
  for (const bl of collectBlocks(root)) {
    for (const line of ownTextLines(bl, { preserveSpaces: false })) {
      const m = RE_NEW_DOT.exec(line);
      if (m) {
        const num = Number(m[1]);
        const inRange = g.groups.some((gr) => gr.range[0] <= num && num <= gr.range[1]);
        if (inRange && num <= 45) newDot.push(`${tag} "${line.slice(0, 100)}"`);
      }
    }
  }
  // dropped options 160-200
  for (const gr of g.groups) {
    for (const p of gr.pools) {
      for (const o of p.options) {
        if (o.text && o.text.length > 160 && o.text.length <= 200) droppedOpt.push(`${tag} G${gr.index} opt ${o.label} len=${o.text.length} "${o.text.slice(0, 80)}"`);
      }
    }
  }
}
fs.writeFileSync("review2.txt",
  `=== NEW-DOT candidate lines in-range: ${newDot.length} ===\n` + newDot.join("\n") +
  `\n\n=== options with text len 160-200 (kept; would be dropped if >160): ${droppedOpt.length} ===\n` + droppedOpt.join("\n") + "\n");
console.log("newDot:", newDot.length, "droppedOpt(160-200 kept):", droppedOpt.length);
