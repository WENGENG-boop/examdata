// S08 复核：dump 指定 book/test/skill 的全部题组完整结构（含 slot/pool/asset 原文），
// 用法: node probe-group-detail.mjs b1t4r [lo] [hi]   例如 node probe-group-detail.mjs b1t4r 32 35
import fs from "node:fs";
import path from "node:path";
import { parsePtePage, expectedFor } from "../../../../../ielts-api/pte.mjs";
import { classifyGroup, deriveStructure } from "../../../../../ielts-api/taxonomy.mjs";

const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const idx = JSON.parse(fs.readFileSync("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json", "utf8"));

const arg = process.argv[2] || "b1t4r";
const lo = process.argv[3] ? Number(process.argv[3]) : null;
const hi = process.argv[4] ? Number(process.argv[4]) : null;
const m = arg.match(/^b(\d+)t(\d+)([rl])$/);
if (!m) { console.error("usage: node probe-group-detail.mjs b1t4r [lo] [hi]"); process.exit(2); }
const book = Number(m[1]), test = Number(m[2]);
const skillKey = m[3] === "l" ? "listening" : "reading";
const entry = idx.find((e) => e.book === book && e.test === test && e.skill === skillKey);
if (!entry) { console.error("no index entry for", arg); process.exit(2); }
const skill = entry.skill === "reading" ? "academic_reading" : entry.skill === "general" ? "general_reading" : entry.skill;
const text = fs.readFileSync(path.join(RAW_DIR, `raw-${entry.raw_index}.txt`), "utf8");
const p = parsePtePage(text, { book, test, skill, slug: entry.slug, page_id: entry.page_id }, expectedFor(book, test, skill));
if (!p.ok) { console.error("parse failed"); process.exit(2); }
const baseSkill = skill === "listening" ? "listening" : "reading";
let prevType = null;
for (const g of p.question_groups || []) {
  const inRange = lo == null || (g.numbers && g.numbers.some((n) => n >= lo && n <= (hi ?? lo)) && g.numbers.some((n) => n <= (hi ?? lo) && n >= lo));
  const r = classifyGroup({ source_type: null, instruction: g.instruction, shared_prompt: g.shared_prompt, heading_text: g.heading_text, skill: baseSkill, neighbor_type: prevType, structure: deriveStructure(g) });
  if (inRange) {
    console.log(`\n===== group [${g.range?.[0]}-${g.range?.[1]}] numbers=${JSON.stringify(g.numbers)} => ${r.status}/${r.type} reason=${r.reason} notes=${r.notes || ""}`);
    console.log("HEADING:", JSON.stringify(g.heading_text));
    console.log("INSTRUCTION:", JSON.stringify(g.instruction));
    console.log("SHARED:", JSON.stringify(g.shared_prompt));
    console.log("WORD_LIMIT:", JSON.stringify(g.word_limit));
    console.log("SLOTS:", JSON.stringify((g.slots || []).map((s) => ({ n: s.number, kind: s.kind, prompt: s.prompt, options: s.options })), null, 1));
    console.log("POOLS:", JSON.stringify((g.pools || []).map((pl) => ({ kind: pl.kind, options: pl.options })), null, 1));
    console.log("ASSETS:", JSON.stringify((g.assets || []).map((a) => ({ kind: a.kind, label: a.label, src: a.src || a.url || null })), null, 1));
    console.log("OUT_OF_RANGE:", JSON.stringify(g.out_of_range || []));
  }
  if (r.status === "classified" || r.status === "inferred") prevType = r.type;
}
