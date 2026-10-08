// S08：列出所有「非 instruction 直判」的组分类（结构回退/pool 覆盖/推断），供逐条核查。
import fs from "node:fs";
import path from "node:path";
import { parsePtePage, expectedFor } from "../../../../../ielts-api/pte.mjs";
import { classifyGroup, deriveStructure } from "../../../../../ielts-api/taxonomy.mjs";

const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const idx = JSON.parse(fs.readFileSync("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json", "utf8"));

for (const entry of idx) {
  const rawFile = path.join(RAW_DIR, `raw-${entry.raw_index}.txt`);
  if (!fs.existsSync(rawFile)) continue;
  const text = fs.readFileSync(rawFile, "utf8");
  const skill = entry.skill === "reading" ? "academic_reading" : entry.skill === "general" ? "general_reading" : entry.skill;
  const p = parsePtePage(text, { book: entry.book, test: entry.test, skill, slug: entry.slug, page_id: entry.page_id }, expectedFor(entry.book, entry.test, skill));
  if (!p.ok) continue;
  const baseSkill = skill === "listening" ? "listening" : "reading";
  let prevType = null;
  for (const g of p.question_groups || []) {
    const st = deriveStructure(g);
    const r = classifyGroup({ source_type: null, instruction: g.instruction, shared_prompt: g.shared_prompt, heading_text: g.heading_text, skill: baseSkill, neighbor_type: prevType, structure: st });
    if (r.status === "classified" || r.status === "inferred") prevType = r.type;
    if (r.reason === "instruction" || r.reason === "empty_group_no_content") continue;
    const instr = String(g.instruction || "").replace(/\s+/g, " ").slice(0, 110);
    const shared = String(g.shared_prompt || "").replace(/\s+/g, " ").slice(0, 80);
    const pools = st.pools.map((pl) => `${pl.kind}[${pl.labels.slice(0, 5).join(",")}]`).join(" ");
    console.log(`${r.reason} -> ${r.type} | b${entry.book}t${entry.test} ${entry.skill} [${g.range[0]}-${g.range[1]}] kinds=${st.slot_kinds.join(",")} pools=${pools} notes=${(r.notes || []).join(";")}`);
    console.log(`    I: ${instr}`);
    console.log(`    S: ${shared}`);
  }
}
