import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectQuestionGroups, collectPassages } from "../../../../ielts-api/html-questions.mjs";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const index = JSON.parse(fs.readFileSync("../evidence/S04-raw-index.json", "utf8"));
const rows = Array.isArray(index) ? index : (index.rows || index.entries || []);
for (const row of rows) {
  const idx = row.raw_index ?? row.rawIndex ?? row.idx;
  let raw;
  try { raw = JSON.parse(fs.readFileSync(path.join(RAW_DIR, `raw-${idx}.txt`), "utf8")); } catch { continue; }
  const root = parseHtml(raw[0].content.rendered);
  const groups = collectQuestionGroups(root, { maxNumber: 45, stopAtHeadings: true }).groups;
  const { passages, notes } = collectPassages(root, { groups, expectedPassages: 3 });
  const interesting = notes.filter((n) => n.kind !== "passage_count_mismatch" || passages.length !== 3);
  if (interesting.length) console.log(`${row.book}-${row.test} raw=${idx} n=${passages.length} notes=${JSON.stringify(interesting)}`);
}
