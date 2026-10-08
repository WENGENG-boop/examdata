import fs from "node:fs";
import path from "node:path";
import { parsePtePage, expectedFor } from "../../../../ielts-api/pte.mjs";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const index = JSON.parse(fs.readFileSync("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json", "utf8"));
const rows = [];
const summary = { pages: 0, groups: 0, asset_groups: 0, diagram_groups: 0, other_groups: 0 };
for (const e of index) {
  if (e.raw_index == null) continue;
  const raw = fs.readFileSync(path.join(RAW_DIR, `raw-${e.raw_index}.txt`), "utf8");
  const skill = e.skill === "reading" ? "academic_reading" : "listening";
  const r = parsePtePage(raw, { book: e.book, test: e.test, skill, slug: e.slug }, expectedFor(e.book, e.test, skill));
  let any = false;
  for (const g of r.question_groups) {
    const derived = g.slots.filter((s) => s.kind === "derived");
    if (!derived.length) continue;
    if (!any) { rows.push(`\n=== ${e.book}-${e.test}-${e.skill} raw-${e.raw_index} (${e.slug}) ===`); summary.pages++; any = true; }
    const instr = (g.heading_text || "").replace(/\s+/g, " ").slice(0, 130);
    const kinds = [...new Set(g.slots.map((s) => s.kind))].join("+");
    const nums = derived.map((s) => s.number);
    const assets = g.assets.map((a) => a.kind).join(",");
    const diag = /diagram|table|label|map|chart|figure|picture|choose.*from|box/i.test(g.heading_text || "");
    if (assets) summary.asset_groups++;
    if (diag) summary.diagram_groups++; else summary.other_groups++;
    summary.groups++;
    rows.push(`G${g.index} [${g.range[0]}-${g.range[1]}] derived=${nums.join(",")} kinds=${kinds} assets=[${assets}] kw=${diag ? "DIAG" : "-"} :: ${instr}`);
  }
}
rows.push(`\nsummary ${JSON.stringify(summary)}`);
fs.writeFileSync("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-derived-triage.txt", rows.join("\n"));
console.log(rows.join("\n"));
