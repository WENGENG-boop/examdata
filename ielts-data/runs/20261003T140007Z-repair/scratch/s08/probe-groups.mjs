// S08：解析真实 pte raw，打印组签名，用于分类器/索引构建器设计。
import fs from "node:fs";
import path from "node:path";
import { parsePtePage, expectedFor } from "../../../../../ielts-api/pte.mjs";

const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const idx = JSON.parse(fs.readFileSync("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json", "utf8"));

const want = process.argv[2]
  ? [process.argv[2]]
  : ["10-1-reading", "10-1-listening", "1-2-listening", "20-1-general", "21-1-reading", "5-1-reading", "3-1-listening"];

for (const key of want) {
  const [b, t, kind] = key.split("-");
  const skill = kind === "reading" ? "academic_reading" : kind === "general" ? "general_reading" : "listening";
  const entry = idx.find((x) => x.book === +b && x.test === +t && (x.skill === skill || x.skill === kind));
  if (!entry) { console.log(key, "NO RAW ENTRY"); continue; }
  const rawFile = path.join(RAW_DIR, `raw-${entry.raw_index}.txt`);
  const text = fs.readFileSync(rawFile, "utf8");
  const expected = expectedFor(+b, +t, skill);
  const p = parsePtePage(text, { book: +b, test: +t, skill, slug: entry.slug, page_id: entry.page_id }, expected);
  console.log(`\n===== ${key} (${entry.slug}) ok=${p.ok} q=${p.question_count}/${p.expected_total} a=${p.answer_count} parts=${JSON.stringify(expected?.parts?.map(x=>[x.part,x.ranges]))}`);
  console.log("passages:", (p.passages || []).map((x) => `${x.passage}:${x.title || ""}(${(x.text || "").length}ch)`).join(" | "));
  for (const g of p.question_groups || []) {
    const poolKinds = (g.pools || []).map((pl) => `${pl.kind}:${pl.options?.length ?? 0}`).join(",");
    const slotKinds = [...new Set((g.slots || []).map((s) => s.kind))].join(",");
    const opts = g.options ? `${Array.isArray(g.options) ? g.options.length : typeof g.options}` : "-";
    console.log(`  g${g.index} [${g.range?.[0]}-${g.range?.[1]}] struct=${!!g.structural} pools=[${poolKinds}] slots=[${slotKinds}] options=${opts} shared=${g.shared_prompt ? JSON.stringify(String(g.shared_prompt).slice(0, 60)) : "-"} assets=${(g.assets || []).length} instr=${JSON.stringify(String(g.instruction || "").replace(/\s+/g, " ").slice(0, 130))}`);
  }
  if (p.audio?.length) console.log("audio:", JSON.stringify(p.audio.slice(0, 2)));
  if (p.assets?.length) console.log("page assets:", JSON.stringify(p.assets.slice(0, 3)).slice(0, 300));
}
