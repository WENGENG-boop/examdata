// S12 shared_prompt 修复 diff：old vs new question-index
import fs from "node:fs";

const oldIdx = JSON.parse(fs.readFileSync("../tmp_s12/question-index.old.json", "utf8"));
const newIdx = JSON.parse(fs.readFileSync("../ielts-data/runs/20261003T140007Z-repair/index/question-index.json", "utf8"));

const byId = (idx) => new Map(idx.groups.map((g) => [g.id, g]));
const og = byId(oldIdx), ng = byId(newIdx);

const bucket = (len) => (len > 4000 ? ">4000" : len > 1200 ? "1200-4000" : len > 400 ? "400-1200" : len > 200 ? "200-400" : "<=200");
const countBuckets = (idx) => {
  const out = {};
  for (const g of idx.groups) {
    const b = bucket((g.shared_prompt || "").length);
    out[b] = (out[b] || 0) + 1;
  }
  return out;
};

console.log("== shared_prompt 长度分桶 ==");
console.log("old:", JSON.stringify(countBuckets(oldIdx)));
console.log("new:", JSON.stringify(countBuckets(newIdx)));

// 逐组比较
let lost = 0, shortened = 0;
const changed = [];
const idMissing = [];
for (const g of oldIdx.groups) {
  const n = ng.get(g.id);
  if (!n) { idMissing.push(g.id); continue; }
  const oSlots = (g.slots || []).length, nSlots = (n.slots || []).length;
  const oOpts = (g.options || []).length, nOpts = (n.options || []).length;
  if (nSlots < oSlots || nOpts < nOpts) { /* noop guard */ }
  if (nSlots < oSlots || nOpts < oOpts) {
    lost++;
    console.log(`LOST ${g.id}: slots ${oSlots}->${nSlots}, options ${oOpts}->${nOpts}`);
  }
  const oLen = (g.shared_prompt || "").length, nLen = (n.shared_prompt || "").length;
  if (oLen - nLen > 200) { shortened++; changed.push({ id: g.id, oLen, nLen }); }
}
console.log(`\n== 结论 ==`);
console.log(`old groups=${oldIdx.groups.length} new groups=${newIdx.groups.length} new-missing-in-old=${newIdx.groups.filter((g) => !og.has(g.id)).length} old-missing-in-new=${idMissing.length}`);
console.log(`slots/options 减少的组: ${lost}`);
console.log(`shared_prompt 缩短>200 的组: ${shortened}`);
changed.sort((a, b) => (b.oLen - b.nLen) - (a.oLen - a.nLen));
for (const c of changed.slice(0, 25)) console.log(`  ${c.id}  ${c.oLen} -> ${c.nLen}`);

console.log(`\nquestions old=${oldIdx.questions.length} new=${newIdx.questions.length}`);

// answers 对比（对象形态：question_id -> entry）
const oa = oldIdx.answers, na = newIdx.answers;
let ansDiff = 0, ansMissing = 0;
for (const k of Object.keys(oa)) {
  const n = na[k];
  if (!n) { ansMissing++; if (ansMissing <= 5) console.log(`ANS-MISSING ${k}`); continue; }
  if (JSON.stringify(oa[k].raw) !== JSON.stringify(n.raw)) { ansDiff++; if (ansDiff <= 10) console.log(`ANS ${k}: ${JSON.stringify(oa[k].raw)} -> ${JSON.stringify(n.raw)}`); }
}
console.log(`答案键 old=${Object.keys(oa).length} new=${Object.keys(na).length} 值变化=${ansDiff} 新缺失=${ansMissing}`);

// 按页分组对比 slot 数
const sumSlots = (idx) => {
  const m = new Map();
  for (const g of idx.groups) m.set(g.page_ref, (m.get(g.page_ref) || 0) + (g.slots || []).length);
  return m;
};
const os = sumSlots(oldIdx), ns = sumSlots(newIdx);
let pageDiff = 0;
for (const [k, v] of os) {
  if (ns.get(k) !== v) { pageDiff++; if (pageDiff <= 15) console.log(`PAGE ${k}: slots ${v} -> ${ns.get(k)}`); }
}
console.log(`页面 slot 总数变化: ${pageDiff}`);

console.log("\nold stats:", JSON.stringify(oldIdx.stats));
console.log("new stats:", JSON.stringify(newIdx.stats));
