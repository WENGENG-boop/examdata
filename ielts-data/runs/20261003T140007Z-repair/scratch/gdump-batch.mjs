import fs from "node:fs";
import path from "node:path";
import { parsePtePage, expectedFor } from "../../../../ielts-api/pte.mjs";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const index = JSON.parse(fs.readFileSync("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json", "utf8"));
const byRaw = new Map();
for (const e of index) if (e.raw_index != null) byRaw.set(e.raw_index, e);

const pairs = process.argv.slice(2).map((s) => {
  const [r, g] = s.split(":");
  return { raw: Number(r), gi: Number(g) };
});
for (const p of pairs) {
  const e = byRaw.get(p.raw);
  if (!e) { console.log(`raw-${p.raw}: NOT FOUND`); continue; }
  const raw = fs.readFileSync(path.join(RAW_DIR, `raw-${p.raw}.txt`), "utf8");
  const skill = e.skill === "reading" ? "academic_reading" : "listening";
  const r = parsePtePage(raw, { book: e.book, test: e.test, skill, slug: e.slug }, expectedFor(e.book, e.test, skill));
  const g = r.question_groups[p.gi];
  if (!g) { console.log(`raw-${p.raw} G${p.gi}: NO GROUP (n=${r.question_groups.length})`); continue; }
  console.log(`\n### raw-${p.raw} (${e.book}-${e.test}-${e.skill}) G${g.index} [${g.range[0]}-${g.range[1]}]`);
  console.log(`heading: ${(g.heading_text || "").replace(/\s+/g, " ").slice(0, 150)}`);
  console.log(`instr:   ${(g.instruction || "").replace(/\s+/g, " ").slice(0, 150)}`);
  console.log(`shared:  ${(g.shared_prompt || "").replace(/\s+/g, " ").slice(0, 220)}`);
  console.log(`pools: ${g.pools.length} opts: ${g.pools.map((p2) => p2.options.length).join(",")} assets: ${g.assets.map((a) => a.kind).join(",") || "-"} word_limit: ${g.word_limit}`);
  for (const s of g.slots) {
    const flags = [];
    if (s.kind === "derived") flags.push("DERIVED");
    console.log(`  ${s.number} [${s.kind}] opts=${s.options.length}${flags.length ? " " + flags.join(",") : ""} :: ${String(s.prompt || "").replace(/\s+/g, " ").slice(0, 130)}`);
  }
}
