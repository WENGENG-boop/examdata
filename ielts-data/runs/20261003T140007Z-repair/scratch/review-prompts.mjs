import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectQuestionGroups } from "../../../../ielts-api/html-questions.mjs";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const index = JSON.parse(fs.readFileSync("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json", "utf8"));
const bare = [], stem = [], sec = [], dclass = [];
const paren = (n) => new RegExp("\\(" + n + "\\)");
for (const e of index) {
  if (e.raw_index == null) continue;
  const raw = fs.readFileSync(path.join(RAW_DIR, `raw-${e.raw_index}.txt`), "utf8");
  let html; try { html = JSON.parse(raw)[0].content.rendered; } catch { continue; }
  const root = parseHtml(html);
  const isListening = e.skill !== "reading";
  const g = collectQuestionGroups(root, { maxNumber: 45, stopAtHeadings: !isListening });
  const tag = `raw-${e.raw_index} ${e.book}-${e.test}-${e.skill}`;
  for (const gr of g.groups) {
    for (const s of gr.slots) {
      const p = (s.prompt || "").trim();
      if (s.kind === "gap" && !paren(s.number).test(p)) bare.push(`${tag} G${gr.index} Q${s.number} "${p.slice(0, 110)}"`);
      if (s.kind === "derived" && p.length > 0) stem.push(`${tag} G${gr.index} Q${s.number} "${p.slice(0, 110).replace(/\n/g, "\\n")}"`);
      if (s.kind === "line_section") sec.push(`${tag} G${gr.index} Q${s.number} "${p.slice(0, 110)}"`);
      const dm = /^(\d{1,3})[.\s]/.exec(p);
      if (dm && Number(dm[1]) !== s.number && paren(s.number).test(p) && (s.kind === "gap" || s.kind === "input")) dclass.push(`${tag} G${gr.index} Q${s.number} "${p.slice(0, 110)}"`);
    }
  }
}
fs.writeFileSync("review-prompts.txt",
  `=== BARE-MARKER gaps (kind=gap, prompt without (n)): ${bare.length} ===\n` + bare.join("\n") +
  `\n\n=== DERIVED WITH PROMPT (fill-stage stem/bare): ${stem.length} ===\n` + stem.join("\n") +
  `\n\n=== LINE_SECTION: ${sec.length} ===\n` + sec.join("\n") +
  `\n\n=== D-CLASS candidates (prompt starts other number, has (n)): ${dclass.length} ===\n` + dclass.join("\n") + "\n");
console.log("bare:", bare.length, "derivedFilled:", stem.length, "section:", sec.length, "dclass:", dclass.length);
