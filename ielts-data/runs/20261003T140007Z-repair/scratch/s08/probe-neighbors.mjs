// S08：打印指定 book/test 的题组序列与分类结果，用于结构回退/邻居规则的定点核查。
import fs from "node:fs";
import path from "node:path";
import { parsePtePage, expectedFor } from "../../../../../ielts-api/pte.mjs";
import { classifyGroup, deriveStructure } from "../../../../../ielts-api/taxonomy.mjs";

const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const idx = JSON.parse(fs.readFileSync("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json", "utf8"));

const targets = process.argv.slice(2).map((s) => {
  const m = /^b(\d+)t(\d+)([lr])$/.exec(s);
  return m ? { book: Number(m[1]), test: Number(m[2]), skill: m[3] === "l" ? "listening" : "reading" } : null;
}).filter(Boolean);

for (const t of targets) {
  for (const entry of idx) {
    if (entry.book !== t.book || entry.test !== t.test) continue;
    if (t.skill === "listening" && entry.skill !== "listening") continue;
    if (t.skill === "reading" && entry.skill !== "reading") continue;
    const rawFile = path.join(RAW_DIR, `raw-${entry.raw_index}.txt`);
    if (!fs.existsSync(rawFile)) { console.log(`[skip] ${rawFile} missing`); continue; }
    const text = fs.readFileSync(rawFile, "utf8");
    const skill = entry.skill === "reading" ? "academic_reading" : entry.skill === "general" ? "general_reading" : entry.skill;
    const p = parsePtePage(text, { book: entry.book, test: entry.test, skill, slug: entry.slug, page_id: entry.page_id }, expectedFor(entry.book, entry.test, skill));
    console.log(`\n=== b${t.book} t${t.test} ${entry.skill} raw-${entry.raw_index} slug=${entry.slug} groups=${(p.question_groups || []).length}`);
    const baseSkill = skill === "listening" ? "listening" : "reading";
    let prevType = null;
    for (const g of p.question_groups || []) {
      const st = deriveStructure(g);
      const r = classifyGroup({ source_type: null, instruction: g.instruction, shared_prompt: g.shared_prompt, heading_text: g.heading_text, skill: baseSkill, neighbor_type: prevType, structure: st });
      if (r.status === "classified" || r.status === "inferred") prevType = r.type;
      const instr = String(g.instruction || "").replace(/\s+/g, " ").slice(0, 90);
      const head = String(g.heading_text || "").replace(/\s+/g, " ").slice(0, 60);
      console.log(`  [${g.range[0]}-${g.range[1]}] ${r.type}/${r.status} (${r.reason}) kinds=${st.slot_kinds.join(",")} pools=${st.pool_kinds.join(",")} | H:${head} | I:${instr}`);
    }
  }
}
