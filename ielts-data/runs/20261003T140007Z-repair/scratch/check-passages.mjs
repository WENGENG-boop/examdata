import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectQuestionGroups, collectPassages } from "../../../../ielts-api/html-questions.mjs";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
for (const idx of process.argv.slice(2)) {
  const raw = JSON.parse(fs.readFileSync(path.join(RAW_DIR, `raw-${idx}.txt`), "utf8"));
  const root = parseHtml(raw[0].content.rendered);
  const groups = collectQuestionGroups(root, { maxNumber: 45, stopAtHeadings: true }).groups;
  const { passages } = collectPassages(root, { groups, expectedPassages: 3 });
  console.log(`===== raw-${idx}`);
  for (const p of passages) {
    console.log(`  P${p.index + 1} "${p.title}" label=${p.title_is_label} range=${JSON.stringify(p.range)} paras=${p.paragraphs.length} tbl=${p.tables.length} fig=${p.figures.length} img=${p.images.length} gids=${JSON.stringify(p.question_groups)}`);
    if (p.paragraphs.length) console.log(`      first: ${JSON.stringify(p.paragraphs[0].text.slice(0, 90))}`);
    if (p.paragraphs.length > 1) console.log(`      second: ${JSON.stringify(p.paragraphs[1].text.slice(0, 90))}`);
  }
}
