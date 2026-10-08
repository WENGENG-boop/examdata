import fs from "node:fs";
import path from "node:path";
import { parsePtePage, expectedFor } from "../../../../ielts-api/pte.mjs";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const index = JSON.parse(fs.readFileSync("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json", "utf8"));
const targets = process.argv.slice(2).map(Number);
for (const ri of targets) {
  const entry = index.find((e) => e.raw_index === ri);
  if (!entry) { console.log(`raw-${ri}: no index entry`); continue; }
  const raw = fs.readFileSync(path.join(RAW_DIR, `raw-${ri}.txt`), "utf8");
  const skill = entry.skill === "reading" ? "academic_reading" : "listening";
  const expected = expectedFor(entry.book, entry.test, skill);
  const r = parsePtePage(raw, { book: entry.book, test: entry.test, skill, slug: entry.slug, page_id: entry.page_id }, expected);
  console.log(`raw-${ri} ${entry.book}-${entry.test}-${entry.skill}: q=${r.question_count} exp=${r.expected_total} missing=[${r.questions_missing}] status=${r.parse_status}`);
}
