// S08：用全量本地 raw 语料回归分类器；对 unknown 组导出完整结构（slots/pools/answers）供校准。
import fs from "node:fs";
import path from "node:path";
import { parsePtePage, expectedFor } from "../../../../../ielts-api/pte.mjs";
import { classifyGroup, deriveStructure } from "../../../../../ielts-api/taxonomy.mjs";

const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const idx = JSON.parse(fs.readFileSync("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json", "utf8"));

const byStatus = new Map();
const byType = new Map();
const byReason = new Map();
const unknownDetail = [];
const conflicts = [];
let groupsTotal = 0;
let parseFails = 0;
let emptyGroups = 0;

for (const entry of idx) {
  const skill = entry.skill === "reading" ? "academic_reading" : entry.skill === "general" ? "general_reading" : entry.skill;
  const rawFile = path.join(RAW_DIR, `raw-${entry.raw_index}.txt`);
  if (!fs.existsSync(rawFile)) continue;
  const text = fs.readFileSync(rawFile, "utf8");
  const expected = expectedFor(entry.book, entry.test, skill);
  let p;
  try {
    p = parsePtePage(text, { book: entry.book, test: entry.test, skill, slug: entry.slug, page_id: entry.page_id }, expected);
  } catch (e) { parseFails++; continue; }
  if (!p.ok) { parseFails++; continue; }
  const baseSkill = skill === "listening" ? "listening" : "reading";
  const answerByNumber = new Map();
  (p.questions || []).forEach((q) => answerByNumber.set(q.number, q.answer));
  let prevType = null;
  for (const g of p.question_groups || []) {
    groupsTotal++;
    const r = classifyGroup({
      source_type: null,
      instruction: g.instruction,
      shared_prompt: g.shared_prompt,
      heading_text: g.heading_text,
      skill: baseSkill,
      neighbor_type: prevType,
      structure: deriveStructure(g),
    });
    byStatus.set(r.status, (byStatus.get(r.status) || 0) + 1);
    byType.set(r.type, (byType.get(r.type) || 0) + 1);
    byReason.set(r.reason, (byReason.get(r.reason) || 0) + 1);
    if (r.reason === "empty_group_no_content") emptyGroups++;
    if (r.status === "unknown") {
      unknownDetail.push({
        book: entry.book, test: entry.test, skill: baseSkill,
        range: g.range, numbers: g.numbers,
        reason: r.reason,
        heading_text: g.heading_text,
        instruction: g.instruction,
        shared_prompt: g.shared_prompt,
        word_limit: g.word_limit,
        slots: (g.slots || []).map((s) => ({ n: s.number, kind: s.kind, hasOptions: !!(s.options && s.options.length), prompt: String(s.prompt || "").slice(0, 200) })),
        pools: (g.pools || []).map((pl) => ({ kind: pl.kind, labels: (pl.options || []).map((o) => o.label), texts: (pl.options || []).map((o) => String(o.text || "").slice(0, 60)) })),
        assets: (g.assets || []).length,
        answers: g.numbers.map((n) => ({ n, a: answerByNumber.get(n) ?? null })),
      });
    }
    if (r.status === "conflict") conflicts.push({ book: entry.book, test: entry.test, skill: baseSkill, range: g.range, reason: r.reason });
    if (r.status === "classified" || r.status === "inferred") prevType = r.type;
  }
}

console.log("groups total:", groupsTotal, "parse fails:", parseFails, "empty groups:", emptyGroups);
console.log("status:", JSON.stringify([...byStatus].sort((a, b) => b[1] - a[1])));
console.log("types:", JSON.stringify([...byType].sort((a, b) => b[1] - a[1])));
console.log("reasons:", JSON.stringify([...byReason].sort((a, b) => b[1] - a[1])));
console.log("conflicts:", conflicts.length, JSON.stringify(conflicts.slice(0, 10)));
console.log("unknown groups:", unknownDetail.length);

const outDir = "C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/scratch/s08";
fs.writeFileSync(path.join(outDir, "classify-unmatched.json"), JSON.stringify({ byStatus: [...byStatus], byType: [...byType], byReason: [...byReason], conflicts, unknownDetail }, null, 2));

// 可读文本：每条 unknown 完整结构
const lines = [];
lines.push(`unknown groups: ${unknownDetail.length}`);
const seen = new Map();
for (const u of unknownDetail) {
  const key = `${u.reason}::${u.skill}::${String(u.instruction || "").replace(/\s+/g, " ").slice(0, 300)}::${String(u.shared_prompt || "").replace(/\s+/g, " ").slice(0, 300)}`;
  if (!seen.has(key)) seen.set(key, []);
  seen.get(key).push(u);
}
let i = 0;
for (const [key, list] of [...seen].sort((a, b) => b[1].length - a[1].length)) {
  i++;
  const u = list[0];
  lines.push(`\n######## [${list.length}x] #${i} ${u.reason} ${u.skill} book${u.book} t${u.test} range ${u.range[0]}-${u.range[1]}`);
  lines.push(`HEADING: ${String(u.heading_text || "").slice(0, 300)}`);
  lines.push(`INSTRUCTION: ${u.instruction}`);
  lines.push(`SHARED: ${u.shared_prompt}`);
  lines.push(`SLOTS: ${JSON.stringify(u.slots)}`);
  lines.push(`POOLS: ${JSON.stringify(u.pools)}`);
  lines.push(`ASSETS: ${u.assets} ANSWERS: ${JSON.stringify(u.answers)}`);
  lines.push(`OTHER: ${list.slice(1, 4).map((x) => `book${x.book}t${x.test} ${x.range[0]}-${x.range[1]}`).join(" | ")}`);
}
fs.writeFileSync(path.join(outDir, "unknown-detail.txt"), lines.join("\n"));
console.log("wrote classify-unmatched.json + unknown-detail.txt");
