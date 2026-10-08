import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectBlocks, collectQuestionGroups, ownTextLines, normalizeWs } from "../../../../ielts-api/html-questions.mjs";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const index = JSON.parse(fs.readFileSync("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json", "utf8"));
const RE_OPT = /^([A-H])(?:[ \t]*[.):]|[ \t]+)[ \t]*(\S[\s\S]*)$/;
const longOpt = [], optWithGap = [];
for (const e of index) {
  if (e.raw_index == null) continue;
  const raw = fs.readFileSync(path.join(RAW_DIR, `raw-${e.raw_index}.txt`), "utf8");
  let html; try { html = JSON.parse(raw)[0].content.rendered; } catch { continue; }
  const root = parseHtml(html);
  const isListening = e.skill !== "reading";
  const g = collectQuestionGroups(root, { maxNumber: 45, stopAtHeadings: !isListening });
  const tag = `raw-${e.raw_index} ${e.book}-${e.test}-${e.skill}`;
  for (const bl of collectBlocks(root)) {
    for (const line of ownTextLines(bl, { preserveSpaces: false })) {
      const m = RE_OPT.exec(line);
      if (!m) continue;
      const text = m[2];
      if (text.length > 160) longOpt.push(`${tag} [${m[1]}] len=${text.length} "${text.slice(0, 90)}"`);
      // 含本页组范围内 (N)
      let gm; const re = /\((\d{1,3})\)/g;
      while ((gm = re.exec(line))) {
        const n = Number(gm[1]);
        if (g.groups.some((gr) => gr.range[0] <= n && n <= gr.range[1] && gr.range[1] <= 45)) {
          optWithGap.push(`${tag} [${m[1]}] (${n}) "${line.slice(0, 100)}"`);
          break;
        }
      }
    }
  }
}
fs.writeFileSync("review3.txt",
  `=== option-like lines with text > 160 (would be dropped by G-class rule): ${longOpt.length} ===\n` + longOpt.join("\n") +
  `\n\n=== option-like lines containing in-range (N) (become gap slots now): ${optWithGap.length} ===\n` + optWithGap.join("\n") + "\n");
console.log("longOpt:", longOpt.length, "optWithGap:", optWithGap.length);
