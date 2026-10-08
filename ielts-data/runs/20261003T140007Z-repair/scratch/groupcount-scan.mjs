import fs from "node:fs";
import path from "node:path";
import { parsePtePage, expectedFor } from "../../../../ielts-api/pte.mjs";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const index = JSON.parse(fs.readFileSync("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json", "utf8"));
const rows = [];
for (const e of index) {
  if (e.raw_index == null) continue;
  const raw = fs.readFileSync(path.join(RAW_DIR, `raw-${e.raw_index}.txt`), "utf8");
  const skill = e.skill === "reading" ? "academic_reading" : "listening";
  const r = parsePtePage(raw, { book: e.book, test: e.test, skill, slug: e.slug }, expectedFor(e.book, e.test, skill));
  if (r.question_groups.length > 12) rows.push(`${e.book}-${e.test}-${e.skill} raw-${e.raw_index} groups=${r.question_groups.length}`);
}
console.log(rows.join("\n") || "(none)");
