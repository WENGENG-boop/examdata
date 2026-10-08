// verify-cam21.mjs — S08: cam21 阅读/听力全组过 taxonomy.classifyGroup
// 阅读组带语义 source_type（"Matching People" 等）→ 期望 source_type+instruction 或 source_type，冲突应极少；
// 听力组 type 为通用 kind（gap/mcq/multi/letter_match）→ 弱提示，期望无 conflict，分类与槽型/指令一致。
import fs from "node:fs";
import { parseReadingHtml, parseListeningHtml } from "../../../../../ielts-api/cam21.mjs";
import { classifyGroup, sourceTypeToCanonical } from "../../../../../ielts-api/taxonomy.mjs";

const DIR = "../../../../../tmp_audit_ielts/cam21";
const tests = [1, 2, 3, 4];
const out = { reading: [], listening: [], summary: {} };

for (const t of tests) {
  const html = fs.readFileSync(`${DIR}/t${t}-reading.html`, "utf8");
  const r = parseReadingHtml(html, { book: 21, test: t, skill: "reading" });
  const qByGroup = new Map();
  for (const q of r.questions) {
    if (!qByGroup.has(q.group)) qByGroup.set(q.group, []);
    qByGroup.get(q.group).push(q);
  }
  for (const g of r.groups) {
    const qs = qByGroup.get(g.id) || [];
    const slots = qs.map((q) => ({ kind: q.slot_kind || "single", prompt: q.prompt || "", options: q.options || [] }));
    const cls = classifyGroup({ source_type: g.type, instruction: g.instruction, skill: "reading", slots, pools: [] });
    const srcCanon = g.type ? sourceTypeToCanonical(g.type) : null;
    out.reading.push({ test: t, group: g.id, src_type: g.type, src_canonical: srcCanon, slots: qs.length, cls });
  }
}

for (const t of tests) {
  const html = fs.readFileSync(`${DIR}/t${t}-listening.html`, "utf8");
  const r = parseListeningHtml(html, { book: 21, test: t, skill: "listening" });
  const qByGroup = new Map();
  for (const q of r.questions) {
    if (!qByGroup.has(q.group)) qByGroup.set(q.group, []);
    qByGroup.get(q.group).push(q);
  }
  for (const g of r.groups) {
    const qs = qByGroup.get(g.index) || [];
    const kindOf = (t) => (t === "multi" ? "multi_select" : t || "unknown");
    const slots = qs.map((q) => ({ kind: kindOf(q.type), prompt: q.prompt || "", options: q.options || [] }));
    const cls = classifyGroup({ source_type: g.type, instruction: g.instruction, skill: "listening", slots, pools: [] });
    out.listening.push({
      test: t, group: g.index, section: g.section, label: g.label, src_type: g.type,
      slot_types: [...new Set(qs.map((q) => q.type))], slots: qs.length, cls,
    });
  }
}

// ---- 汇总 ----
const tally = (arr) => {
  const byStatus = {};
  const byReason = {};
  const byType = {};
  for (const g of arr) {
    byStatus[g.cls.status] = (byStatus[g.cls.status] || 0) + 1;
    byReason[g.cls.reason] = (byReason[g.cls.reason] || 0) + 1;
    byType[g.cls.type] = (byType[g.cls.type] || 0) + 1;
  }
  return { byStatus, byReason, byType };
};
out.summary.reading = tally(out.reading);
out.summary.listening = tally(out.listening);

console.log("===== READING (", out.reading.length, "groups ) =====");
console.log("status:", JSON.stringify(out.summary.reading.byStatus));
console.log("reason:", JSON.stringify(out.summary.reading.byReason));
console.log("type:", JSON.stringify(out.summary.reading.byType));
for (const g of out.reading) {
  const flag = g.cls.status !== "classified" || g.cls.type !== g.src_canonical ? " <<<" : "";
  if (flag || process.env.VERBOSE) {
    console.log(`t${g.test} g${g.group} src=${g.src_type} -> ${g.cls.type}/${g.cls.status}/${g.cls.reason}${flag}`);
  }
}

console.log("===== LISTENING (", out.listening.length, "groups ) =====");
console.log("status:", JSON.stringify(out.summary.listening.byStatus));
console.log("reason:", JSON.stringify(out.summary.listening.byReason));
console.log("type:", JSON.stringify(out.summary.listening.byType));
for (const g of out.listening) {
  const flag = g.cls.status !== "classified" ? " <<<" : "";
  if (flag || process.env.VERBOSE) {
    console.log(`t${g.test} sec${g.section} [${g.label || ""}] src=${g.src_type} slots=${JSON.stringify(g.slot_types)} -> ${g.cls.type}/${g.cls.status}/${g.cls.reason}${flag}`);
  }
}

fs.writeFileSync("verify-cam21-out.json", JSON.stringify(out, null, 2));
console.log("\nwrote verify-cam21-out.json");
