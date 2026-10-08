import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectQuestionGroups } from "../../../../ielts-api/html-questions.mjs";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const idx = Number(process.argv[2]);
const bi = Number(process.argv[3]);
const raw = JSON.parse(fs.readFileSync(path.join(RAW_DIR, `raw-${idx}.txt`), "utf8"));
const root = parseHtml(raw[0].content.rendered);
const { groups } = collectQuestionGroups(root, { maxNumber: 45, stopAtHeadings: true });
for (const g of groups) {
  const [a, b] = g.block_span || [];
  if (a != null && bi >= a && bi < b) {
    console.log(`block ${bi} is in G${g.index} span=[${a},${b}) range=[${g.range}]`);
    for (const s of g.slots) console.log(`  Q${s.number} [${s.kind}] ${JSON.stringify((s.prompt||"").slice(0,100))}`);
  }
}
