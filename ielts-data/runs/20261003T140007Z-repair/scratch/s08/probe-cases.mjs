// S08：针对具体 book/test/skill/range 的组结构探针（第一批 unknown 精确核对）
import fs from "node:fs";
import path from "node:path";
import { parsePtePage, expectedFor } from "../../../../../ielts-api/pte.mjs";

const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const idx = JSON.parse(fs.readFileSync("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json", "utf8"));

const CASES = [
  [1, 3, "reading", 11, 12],
  [20, 1, "listening", 21, 30],
  [4, 4, "reading", 35, 38],
  [1, 4, "reading", 11, 12],
  [1, 1, "reading", 1, 5],
  [1, 4, "reading", 1, 5],
  [1, 4, "reading", 9, 13],
  [1, 4, "reading", 20, 23],
  [5, 4, "reading", 36, 39],
  [11, 3, "listening", 11, 20],
  [14, 1, "listening", 11, 20],
  [12, 4, "reading", 9, 13],
  [7, 1, "reading", 21, 26],
  [4, 1, "listening", 23, 27],
  [2, 2, "listening", 1, 2],
  [5, 2, "listening", 16, 17],
  [6, 1, "reading", 12, 13],
  [7, 2, "listening", 19, 20],
  [1, 2, "listening", 13, 19],
  [1, 1, "reading", 23, 25],
  [3, 4, "reading", 14, 15],
  [5, 3, "reading", 18, 23],
  [16, 2, "listening", 25, 30],
];

const want = new Set(CASES.map((c) => `${c[0]}|${c[1]}|${c[2]}|${c[3]}|${c[4]}`));

for (const entry of idx) {
  const skill = entry.skill === "reading" ? "academic_reading" : entry.skill === "general" ? "general_reading" : entry.skill;
  const key = `${entry.book}|${entry.test}|${entry.skill}|${null}`;
  // match by book/test/skill then range below
  if (!CASES.some((c) => c[0] === entry.book && c[1] === entry.test && c[2] === entry.skill)) continue;
  const rawFile = path.join(RAW_DIR, `raw-${entry.raw_index}.txt`);
  if (!fs.existsSync(rawFile)) continue;
  const text = fs.readFileSync(rawFile, "utf8");
  const expected = expectedFor(entry.book, entry.test, skill);
  let p;
  try { p = parsePtePage(text, { book: entry.book, test: entry.test, skill, slug: entry.slug, page_id: entry.page_id }, expected); } catch { continue; }
  if (!p.ok) continue;
  for (const g of p.question_groups || []) {
    const caseHit = CASES.find((c) => c[0] === entry.book && c[1] === entry.test && c[2] === entry.skill && g.range[0] <= c[4] && g.range[1] >= c[3]);
    if (!caseHit) continue;
    console.log(`\n#### b${entry.book}t${entry.test} ${entry.skill} ${g.range[0]}-${g.range[1]} (case ${caseHit[3]}-${caseHit[4]}) page=${entry.page_id}`);
    console.log(`INSTR: ${String(g.instruction || "").replace(/\s+/g, " ").slice(0, 220)}`);
    console.log(`SHARED: ${String(g.shared_prompt || "").replace(/\s+/g, " ").slice(0, 220)}`);
    console.log(`HEAD: ${String(g.heading_text || "").replace(/\s+/g, " ").slice(0, 160)}`);
    for (const s of g.slots || []) {
      console.log(`  slot ${s.number} kind=${s.kind} opts=${s.options ? s.options.length : 0} prompt=${String(s.prompt || "").replace(/\s+/g, " ").slice(0, 140)}`);
    }
    for (const pl of g.pools || []) console.log(`  pool kind=${pl.kind} labels=[${(pl.options || []).map((o) => o.label).join(",")}]`);
    console.log(`  assets=${(g.assets || []).length} wl=${g.word_limit || null}`);
  }
}
