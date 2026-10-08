// S08 calibration probe: cam21 multi question shape + PTE matching/choice/visual pool&asset shape
import fs from "node:fs";
import { parseListeningHtml, parseReadingHtml } from "../../../../../ielts-api/cam21.mjs";
import { parsePtePage, expectedFor } from "../../../../../ielts-api/pte.mjs";
import { classifyGroup, deriveStructure } from "../../../../../ielts-api/taxonomy.mjs";

const CAM = "../../../../../tmp_audit_ielts/cam21";
console.log("=== cam21 t1 listening: first multi question + its answer_group ===");
const l = parseListeningHtml(fs.readFileSync(`${CAM}/t1-listening.html`, "utf8"), { book: 21, test: 1, skill: "listening" });
const multiQ = l.questions.find((q) => q.type === "multi");
console.log("multi q:", JSON.stringify(multiQ, null, 1).slice(0, 1500));
const ag = (l.answer_groups || []).find((g) => g.slots && multiQ && g.slots.includes(multiQ.number));
console.log("answer_group:", JSON.stringify(ag, null, 1).slice(0, 1200));
console.log("multi questions total:", l.questions.filter((q) => q.type === "multi").length);
console.log("=== cam21 t1 reading: first matching group question ===");
const r = parseReadingHtml(fs.readFileSync(`${CAM}/t1-reading.html`, "utf8"), { book: 21, test: 1, skill: "reading" });
for (const g of r.groups) {
  const qs = r.questions.filter((q) => q.group === g.id);
  if (/matching/i.test(g.type)) {
    console.log("group:", g.id, g.type, "| instr:", String(g.instruction || "").slice(0, 120));
    console.log("q0:", JSON.stringify(qs[0], null, 1).slice(0, 800));
    break;
  }
}
console.log("=== PTE calibration: matching/choice/visual/table groups from sample pages ===");
const RAW = "../../../../../tmp_audit_ielts/completeness_20261003";
const samples = [[9,1,"academic_reading"],[1,4,"listening"],[10,2,"academic_reading"],[15,1,"academic_reading"]];
for (const [b,t,sk] of samples) {
  const idx = JSON.parse(fs.readFileSync("../../evidence/S04-raw-index.json","utf8"));
  const entry = idx.find((e) => e.book===b && e.test===t && (e.skill===(sk==="listening"?"listening":"reading")) && e.raw_index!=null);
  if (!entry) { console.log(`b${b}t${t} ${sk}: no entry`); continue; }
  const text = fs.readFileSync(`${RAW}/raw-${entry.raw_index}.txt`, "utf8");
  const p = parsePtePage(text, { book: b, test: t, skill: sk, slug: entry.slug, page_id: entry.page_id }, expectedFor(b,t,sk));
  for (const g of p.question_groups || []) {
    const st = deriveStructure(g);
    const cls = classifyGroup({ instruction: g.instruction, shared_prompt: g.shared_prompt, heading_text: g.heading_text, skill: sk==="listening"?"listening":"reading", structure: st });
    if (["matching","choice","visual","short_answer"].includes((cls.type && {"matching_headings":"matching","matching_information":"matching","matching_features":"matching","matching_sentence_endings":"matching"}[cls.type]) || cls.type)) {
      const fam = ["multiple_choice_single","multiple_choice_multiple"].includes(cls.type) ? "choice" : ["matching_headings","matching_information","matching_features","matching_sentence_endings"].includes(cls.type) ? "matching" : ["diagram_labeling","map_plan_labeling"].includes(cls.type) ? "visual" : "other";
      console.log(`b${b}t${t} ${g.range} type=${cls.type}(${cls.status}) fam=${fam} pools=${JSON.stringify((g.pools||[]).map(x=>({k:x.kind,n:(x.options||[]).length,l:(x.options||[]).slice(0,3).map(o=>o.label)})))} assets=${JSON.stringify((g.assets||[]).map(a=>a.kind))} slots=${(g.slots||[]).length} slotOpts=${(g.slots||[]).filter(s=>s.options&&s.options.length).length} instr=${String(g.instruction||"").replace(/\s+/g," ").slice(0,90)}`);
    }
  }
}
