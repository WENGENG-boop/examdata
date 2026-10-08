import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectQuestionGroups } from "../../../../ielts-api/html-questions.mjs";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const idx = Number(process.argv[2]);
const gi = Number(process.argv[3]);
const raw = JSON.parse(fs.readFileSync(path.join(RAW_DIR, `raw-${idx}.txt`), "utf8"));
const root = parseHtml(raw[0].content.rendered);
const { groups } = collectQuestionGroups(root, { maxNumber: 45, stopAtHeadings: true });
for (const g of groups) {
  if (gi >= 0 && g.index !== gi) continue;
  console.log(`G${g.index} range=[${g.range}] span=[${g.block_span}] pools=${g.pools.length}`);
  for (const p of g.pools) {
    console.log(`  pool(${p.kind}) n=${p.options.length}`);
    for (const o of p.options) console.log(`    [${o.label}] len=${(o.text||"").length} "${(o.text||"").slice(0, 70)}"`);
  }
}
