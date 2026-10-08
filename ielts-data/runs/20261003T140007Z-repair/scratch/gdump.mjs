import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectQuestionGroups } from "../../../../ielts-api/html-questions.mjs";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const idx = process.argv[2];
const gi = Number(process.argv[3] ?? -1);
const raw = JSON.parse(fs.readFileSync(path.join(RAW_DIR, `raw-${idx}.txt`), "utf8"));
const root = parseHtml(raw[0].content.rendered);
const { groups } = collectQuestionGroups(root, { maxNumber: 45, stopAtHeadings: true });
for (const g of groups) {
  if (gi >= 0 && g.index !== gi) continue;
  console.log(JSON.stringify({ index: g.index, range: g.range, heading: g.heading_text, instruction: (g.instruction||"").slice(0,120), shared: g.shared_prompt, word_limit: g.word_limit, pools: g.pools ? Object.keys(g.pools) : null, span: g.block_span, slots: g.slots.map(s => ({ n: s.number, kind: s.kind, prompt: (s.prompt||"").slice(0,60), opts: s.options ? s.options.length : undefined, input: !!s.input })) }, null, 1));
}
