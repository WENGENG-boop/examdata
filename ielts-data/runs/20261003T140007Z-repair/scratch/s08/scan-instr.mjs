// S08 复核：全量扫描 instruction/shared/heading 中匹配给定正则的组（辅助校准规则，不落库）
// 用法: node scan-instr.mjs "正则" [字段=instr|shared|heading|any]
import fs from "node:fs";
import path from "node:path";
import { parsePtePage, expectedFor } from "../../../../../ielts-api/pte.mjs";
import { classifyGroup, deriveStructure } from "../../../../../ielts-api/taxonomy.mjs";

const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const idx = JSON.parse(fs.readFileSync("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json", "utf8"));
const re = new RegExp(process.argv[2], "i");
const field = process.argv[3] || "any";

for (const entry of idx) {
  const skill = entry.skill === "reading" ? "academic_reading" : entry.skill === "general" ? "general_reading" : entry.skill;
  const rawFile = path.join(RAW_DIR, `raw-${entry.raw_index}.txt`);
  if (!fs.existsSync(rawFile)) continue;
  const text = fs.readFileSync(rawFile, "utf8");
  let p;
  try { p = parsePtePage(text, { book: entry.book, test: entry.test, skill, slug: entry.slug, page_id: entry.page_id }, expectedFor(entry.book, entry.test, skill)); } catch { continue; }
  if (!p.ok) continue;
  const baseSkill = skill === "listening" ? "listening" : "reading";
  for (const g of p.question_groups || []) {
    const candidates = { instr: String(g.instruction || ""), shared: String(g.shared_prompt || ""), heading: String(g.heading_text || "") };
    const fields = field === "any" ? ["instr", "shared", "heading"] : [field];
    const hit = fields.some((f) => re.test(candidates[f]));
    if (hit) {
      const r = classifyGroup({ source_type: null, instruction: g.instruction, shared_prompt: g.shared_prompt, heading_text: g.heading_text, skill: baseSkill, neighbor_type: null, structure: deriveStructure(g) });
      const txt = (candidates.instr || candidates.shared || candidates.heading).replace(/\s+/g, " ").slice(0, 180);
      console.log(`b${entry.book}t${entry.test}${baseSkill === "listening" ? "l" : "r"} [${g.range?.[0]}-${g.range?.[1]}] ${r.status}/${r.type} | ${txt}`);
    }
  }
}
