import fs from "node:fs";
import { parsePtePage, expectedFor } from "../../../../ielts-api/pte.mjs";
const [rawIdx, book, test, skillRaw, groupSpec] = process.argv.slice(2);
const raw = fs.readFileSync(`C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003/raw-${rawIdx}.txt`, "utf8");
const skill = skillRaw === "reading" ? "academic_reading" : "listening";
const r = parsePtePage(raw, { book: +book, test: +test, skill }, expectedFor(+book, +test, skill));
const want = groupSpec ? new Set(groupSpec.split(",").map(Number)) : null;
for (const g of r.question_groups) {
  if (want && !want.has(g.index)) continue;
  console.log(`== G${g.index} [${g.range}] multi=${!!g.multi_select} slots=${g.slots.length}`);
  console.log(`   instr="${g.instruction.replace(/\s+/g, " ").slice(0, 120)}"`);
  if (g.options) {
    console.log(`   options(${g.options.length}):`);
    for (const o of g.options) console.log(`     ${o.label}: ${String(o.text ?? "").slice(0, 90)}`);
  }
  if (g.headings) {
    console.log(`   headings(${g.headings.length}):`);
    for (const h of g.headings) console.log(`     ${h.label}: ${String(h.text ?? "").slice(0, 90)}`);
  }
  for (const s of g.slots) {
    const so = s.options ? ` slotOpts(${s.options.length})=${JSON.stringify(s.options.map(o=>o.label))}` : "";
    const sp = s.shared_prompt ? ` prompt="${String(s.shared_prompt).slice(0,60)}"` : "";
    console.log(`   #${s.number} kind=${s.kind}${so}${sp} text="${String(s.text ?? "").slice(0, 70)}"`);
  }
  if (g.shared_prompt) console.log(`   group prompt="${g.shared_prompt.slice(0, 100)}"`);
}
