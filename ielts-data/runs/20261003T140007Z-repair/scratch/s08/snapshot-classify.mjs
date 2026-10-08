// S08：全量分类快照（用于改动前后 diff 校准）
import fs from "node:fs";
import path from "node:path";
import { parsePtePage, expectedFor } from "../../../../../ielts-api/pte.mjs";
import { classifyGroup, deriveStructure } from "../../../../../ielts-api/taxonomy.mjs";

const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const idx = JSON.parse(fs.readFileSync("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json", "utf8"));
const out = [];
for (const entry of idx) {
  const skill = entry.skill === "reading" ? "academic_reading" : entry.skill === "general" ? "general_reading" : entry.skill;
  const rawFile = path.join(RAW_DIR, `raw-${entry.raw_index}.txt`);
  if (!fs.existsSync(rawFile)) continue;
  let p;
  try { p = parsePtePage(fs.readFileSync(rawFile, "utf8"), { book: entry.book, test: entry.test, skill, slug: entry.slug, page_id: entry.page_id }, expectedFor(entry.book, entry.test, skill)); } catch { continue; }
  if (!p.ok) continue;
  const baseSkill = skill === "listening" ? "listening" : "reading";
  let prevType = null;
  for (const g of p.question_groups || []) {
    const r = classifyGroup({ source_type: null, instruction: g.instruction, shared_prompt: g.shared_prompt, heading_text: g.heading_text, skill: baseSkill, neighbor_type: prevType, structure: deriveStructure(g) });
    out.push({ b: entry.book, t: entry.test, s: baseSkill, r: g.range, type: r.type, status: r.status, reason: r.reason });
    if (r.status === "classified" || r.status === "inferred") prevType = r.type;
  }
}
fs.writeFileSync(process.argv[2] || "snapshot.json", JSON.stringify(out, null, 0));
console.log("snapshot groups:", out.length, "->", process.argv[2] || "snapshot.json");
