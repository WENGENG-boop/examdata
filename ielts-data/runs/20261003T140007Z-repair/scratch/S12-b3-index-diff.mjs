// tmp_s12_b3_diff.mjs — S12 b3 融合 diff：旧索引 vs 新索引（组分类/内容状态/答案状态）
// 用法: node tmp_s12_b3_diff.mjs
import fs from "node:fs";
const OLD = "C:/Users/weo/Desktop/api/ielts-api/tmp_qindex_old.json";
const NEW = "C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/index/question-index.json";
const oldI = JSON.parse(fs.readFileSync(OLD, "utf8"));
const newI = JSON.parse(fs.readFileSync(NEW, "utf8"));

const keyOf = (g) => g.id || `${g.book}|${g.variant}|${g.skill}|${g.test}|${g.range ? g.range.join("-") : "?"}`;
const om = new Map(oldI.groups.map((g) => [keyOf(g), g]));
const nm = new Map(newI.groups.map((g) => [keyOf(g), g]));

const added = [];
const removed = [];
const changed = [];
for (const [k, g] of nm) {
  if (!om.has(k)) { added.push(g); continue; }
  const o = om.get(k);
  if ((o.type || null) !== (g.type || null) || (o.classification_status || null) !== (g.classification_status || null)) {
    changed.push({ k, from: o.type, to: g.type, fromS: o.classification_status, toS: g.classification_status, book: g.book, test: g.test, range: g.range });
  }
}
for (const [k, g] of om) if (!nm.has(k)) removed.push(g);

console.log(`groups: old=${oldI.groups.length} new=${newI.groups.length} added=${added.length} removed=${removed.length} changed=${changed.length}`);
console.log("--- changed ---");
for (const c of changed) console.log(`${c.k} b${c.book}t${c.test} ${JSON.stringify(c.range)}: ${c.from}/${c.fromS} -> ${c.to}/${c.toS}`);
console.log("--- added (new group ids) ---");
for (const g of added) console.log(`${keyOf(g)} b${g.book}t${g.test} ${JSON.stringify(g.range)} type=${g.type} status=${g.classification_status}`);
console.log("--- removed ---");
for (const g of removed) console.log(`${keyOf(g)} b${g.book}t${g.test} ${JSON.stringify(g.range)} type=${g.type}`);

// b3 内容/答案状态
const b3q = newI.questions.filter((q) => q.book === 3 && q.skill === "listening");
const b3qa = newI.answers ? Object.values(newI.answers).filter((a) => a && a.raw != null) : [];
const byStatus = {};
for (const q of b3q) { const k = `${q.content_status}`; byStatus[k] = (byStatus[k] || 0) + 1; }
console.log("--- b3 listening questions:", b3q.length, "content_status:", JSON.stringify(byStatus));
const partial = b3q.filter((q) => q.content_status !== "complete");
for (const q of partial) console.log(`  partial q${q.number} (${q.test}) status=${q.content_status} notes=${JSON.stringify(q.content_notes)}`);
const fully = b3q.filter((q) => q.fully_complete === false);
console.log("  b3 not fully_complete:", fully.length);
for (const q of fully.slice(0, 20)) console.log(`   notfull q${q.number} t${q.test} content=${q.content_status} answer=${q.answer_status}`);

// answer_groups 对比
const agOf = (i) => (i.answer_groups || []).map((g) => g.key || g.id).sort();
console.log("answer_groups old:", agOf(oldI).length, "new:", agOf(newI).length);
const oldSet = new Set(agOf(oldI));
for (const k of agOf(newI)) if (!oldSet.has(k)) console.log("  new answer_group:", k);
