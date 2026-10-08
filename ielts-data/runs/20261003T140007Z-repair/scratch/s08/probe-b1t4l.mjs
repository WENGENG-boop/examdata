import fs from "node:fs";
import { parsePtePage, expectedFor } from "../../../../../ielts-api/pte.mjs";
const RAW = "../../../../../tmp_audit_ielts/completeness_20261003";
const idx = JSON.parse(fs.readFileSync("../../evidence/S04-raw-index.json","utf8"));
const entry = idx.find((e) => e.book===1 && e.test===4 && e.skill==="listening");
const text = fs.readFileSync(`${RAW}/raw-${entry.raw_index}.txt`, "utf8");
const p = parsePtePage(text, { book: 1, test: 4, skill: "listening", slug: entry.slug, page_id: entry.page_id }, expectedFor(1,4,"listening"));
for (const g of p.question_groups || []) {
  if (g.range[0] <= 12) {
    console.log("== group", g.range, "heading:", JSON.stringify(String(g.heading_text||"").slice(0,100)));
    console.log("   instruction:", JSON.stringify(String(g.instruction||"").slice(0,200)));
    console.log("   shared:", JSON.stringify(String(g.shared_prompt||"").slice(0,300)));
    console.log("   word_limit:", g.word_limit, "pools:", JSON.stringify((g.pools||[]).map(x=>({k:x.kind,n:x.options.length}))));
    for (const s of g.slots||[]) console.log("   slot", s.number, s.kind, "| prompt:", JSON.stringify(String(s.prompt||"").slice(0,120)), "| opts:", JSON.stringify((s.options||[]).map(o=>o.label)));
  }
}
// Q1-4 answers
console.log("answers 1-5:", JSON.stringify(p.questions.filter(q=>q.number<=5).map(q=>({n:q.number,a:q.answer,form:q.answer_form}))));
console.log("missing:", JSON.stringify(p.questions_missing), "answer_missing:", JSON.stringify(p.answer_missing_detail||p.answer_missing));
