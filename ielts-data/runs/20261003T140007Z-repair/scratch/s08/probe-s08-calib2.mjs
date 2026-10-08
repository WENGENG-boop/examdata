// MCQ pools + visual/table assets across listening pages of a few books
import fs from "node:fs";
import { parsePtePage, expectedFor } from "../../../../../ielts-api/pte.mjs";
import { classifyGroup, deriveStructure } from "../../../../../ielts-api/taxonomy.mjs";

const RAW = "../../../../../tmp_audit_ielts/completeness_20261003";
const idx = JSON.parse(fs.readFileSync("../../evidence/S04-raw-index.json","utf8"));
const want = [[1,4,"listening"],[3,1,"listening"],[6,1,"listening"],[9,2,"listening"],[11,4,"listening"]];
const found = new Map();
for (const [b,t,sk] of want) {
  const entry = idx.find((e) => e.book===b && e.test===t && e.skill===sk && e.raw_index!=null);
  if (!entry) { console.log(`b${b}t${t} ${sk}: no entry`); continue; }
  const text = fs.readFileSync(`${RAW}/raw-${entry.raw_index}.txt`, "utf8");
  const p = parsePtePage(text, { book: b, test: t, skill: sk, slug: entry.slug, page_id: entry.page_id }, expectedFor(b,t,sk));
  for (const g of p.question_groups || []) {
    const st = deriveStructure(g);
    const cls = classifyGroup({ instruction: g.instruction, shared_prompt: g.shared_prompt, heading_text: g.heading_text, skill: "listening", structure: st });
    const pools = (g.pools||[]).map(x=>({k:x.kind,n:(x.options||[]).length,l:(x.options||[]).slice(0,4).map(o=>o.label+":"+String(o.text||"").slice(0,25))}));
    const assets = (g.assets||[]).map(a=>a.kind+" "+String(a.source_ref||"").slice(0,50));
    const slotOpts = (g.slots||[]).map(s=>({n:s.number,k:s.kind,o:(s.options||[]).map(x=>x.label)}));
    console.log(`b${b}t${t}l ${g.range} ${cls.type}(${cls.status}) pools=${JSON.stringify(pools)} assets=${JSON.stringify(assets)} slotOpts=${JSON.stringify(slotOpts.filter(x=>x.o.length))} slots=${(g.slots||[]).length}`);
  }
}
