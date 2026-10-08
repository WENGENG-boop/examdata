import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectQuestionGroups } from "../../../../ielts-api/html-questions.mjs";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const idx = Number(process.argv[2]);
const raw = JSON.parse(fs.readFileSync(path.join(RAW_DIR, `raw-${idx}.txt`), "utf8"));
const root = parseHtml(raw[0].content.rendered);
for (const stop of [true, false]) {
  const { groups } = collectQuestionGroups(root, { maxNumber: 45, stopAtHeadings: stop });
  for (const g of groups) {
    for (const s of g.slots) {
      if (s.kind === "gap") console.log(`stop=${stop} G${g.index} Q${s.number} kind=gap prompt=${JSON.stringify((s.prompt||"").slice(0,80))}`);
    }
  }
}
