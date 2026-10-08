// S08：结构探针 — 对给定指令正则，打印组结构（slot kinds、pool kinds/labels、options 情况）
import fs from "node:fs";
import path from "node:path";
import { parsePtePage, expectedFor } from "../../../../../ielts-api/pte.mjs";

const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const idx = JSON.parse(fs.readFileSync("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json", "utf8"));

const PROBES = [
  ["mcq_multi_circle", /circle\s+(two|three|four|five|\d)\s+letters?/i, 3],
  ["mcq_multi_choose", /choose\s+(two|three|four|five|\d)\s+letters?/i, 3],
  ["sentence_completion", /complete\s+the\s+sentences?\s+below/i, 3],
  ["flow_chart", /complete\s+the\s+(steps|flow[\s-]?chart)/i, 3],
  ["notes", /complete\s+the\s+notes/i, 2],
  ["form", /complete\s+the\s+(form|application)/i, 2],
  ["summary_choose", /choose\s+no\s+more\s+than\s+two\s+words\s+from\s+the\s+passage\s+for\s+each\s+answer/i, 3],
  ["circle_letters_plain", /circle\s+the\s+correct\s+letters\.?\s*$/i, 3],
  ["choose_letters_boxes", /choose\s+the\s+appropriate\s+letters\s+a[-–—]?\s*d/i, 3],
  ["short_answer_questions", /write\s+no\s+more\s+than\s+three\s+words\s+and\/or\s+a\s+number/i, 2],
  ["headings", /headings?\s+below|list\s+of\s+headings/i, 2],
];

const seen = new Map(); // probeName -> [{book,test,skill,range,slotKinds,poolKinds,poolLabels,hasSlotOptions,slotCount,instruction}]
for (const entry of idx) {
  const skill = entry.skill === "reading" ? "academic_reading" : entry.skill === "general" ? "general_reading" : entry.skill;
  const rawFile = path.join(RAW_DIR, `raw-${entry.raw_index}.txt`);
  if (!fs.existsSync(rawFile)) continue;
  const text = fs.readFileSync(rawFile, "utf8");
  const expected = expectedFor(entry.book, entry.test, skill);
  let p;
  try { p = parsePtePage(text, { book: entry.book, test: entry.test, skill, slug: entry.slug, page_id: entry.page_id }, expected); } catch { continue; }
  if (!p.ok) continue;
  for (const g of p.question_groups || []) {
    const all = [g.instruction, g.shared_prompt, g.heading_text].filter(Boolean).join("\n");
    for (const [name, re] of PROBES) {
      if (!re.test(all)) continue;
      const list = seen.get(name) || [];
      if (list.length >= 8) continue;
      list.push({
        book: entry.book, test: entry.test, skill: entry.skill, range: `${g.range[0]}-${g.range[1]}`,
        slotKinds: [...new Set((g.slots || []).map((s) => s.kind))],
        slotCount: (g.slots || []).length,
        hasSlotOptions: (g.slots || []).some((s) => s.options && s.options.length),
        poolKinds: (g.pools || []).map((pl) => pl.kind),
        poolLabels: (g.pools || []).map((pl) => (pl.options || []).map((o) => o.label).join(",")),
        wordLimit: g.word_limit || null,
        instr: String(g.instruction || "").replace(/\s+/g, " ").slice(0, 150),
      });
      seen.set(name, list);
    }
  }
}

for (const [name] of PROBES) {
  const list = seen.get(name) || [];
  console.log(`\n===== ${name} (${list.length}) =====`);
  for (const x of list) {
    console.log(`b${x.book}t${x.test} ${x.skill} ${x.range} slots=${x.slotCount} kinds=[${x.slotKinds}] slotOpts=${x.hasSlotOptions} pools=[${x.poolKinds}] labels=[${x.poolLabels}] wl=${x.wordLimit}`);
    console.log(`   instr: ${x.instr}`);
  }
}
