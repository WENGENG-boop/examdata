// S12 shared_prompt 修复 diff v2：修正 answers 对比 + 细查 7 组 options 减少 + 400-1200 桶抽样
import fs from "node:fs";

const oldIdx = JSON.parse(fs.readFileSync("../tmp_s12/question-index.old.json", "utf8"));
const newIdx = JSON.parse(fs.readFileSync("../ielts-data/runs/20261003T140007Z-repair/index/question-index.json", "utf8"));

const byId = (idx) => new Map(idx.groups.map((g) => [g.id, g]));
const og = byId(oldIdx), ng = byId(newIdx);

const TARGETS = [
  "cambridge:1:academic:reading:3:P2:G1",
  "cambridge:1:academic:reading:4:P1:G2",
  "cambridge:17:academic:reading:2:P1:G1",
  "cambridge:19:academic:reading:4:P2:G2",
  "cambridge:20:academic:reading:2:P1:G1",
  "cambridge:20:academic:reading:4:P2:G2",
  "cambridge:9:academic:reading:2:P2:G2",
];
console.log("== 7 组 options 减少详情 ==");
for (const id of TARGETS) {
  const o = og.get(id), n = ng.get(id);
  const oOpts = (o.options || []).map((x) => `${x.label}:${(x.text || "").slice(0, 40)}`);
  const nOpts = (n.options || []).map((x) => `${x.label}:${(x.text || "").slice(0, 40)}`);
  console.log(`\n${id}`);
  console.log(`  old sp_len=${(o.shared_prompt || "").length} instr=${JSON.stringify((o.instruction || "").slice(0, 90))}`);
  console.log(`  new sp_len=${(n.shared_prompt || "").length} instr=${JSON.stringify((n.instruction || "").slice(0, 90))}`);
  console.log(`  old options(${oOpts.length}): ${JSON.stringify(oOpts)}`);
  console.log(`  new options(${nOpts.length}): ${JSON.stringify(nOpts)}`);
  // slots 内 options 是否有变化
  const oSlotOpts = (o.slots || []).map((s) => `${s.number}:${(s.options || []).length}`);
  const nSlotOpts = (n.slots || []).map((s) => `${s.number}:${(s.options || []).length}`);
  console.log(`  old slot opt counts: ${oSlotOpts.join(",")}`);
  console.log(`  new slot opt counts: ${nSlotOpts.join(",")}`);
  console.log(`  old slot kinds: ${(o.slots || []).map((s) => s.kind).join(",")}`);
  console.log(`  new slot kinds: ${(n.slots || []).map((s) => s.kind).join(",")}`);
}

console.log("\n== answers 对比 ==");
const oa = oldIdx.answers, na = newIdx.answers;
let ansDiff = 0, ansMissing = 0;
for (const k of Object.keys(oa)) {
  const n = na[k];
  if (!n) { ansMissing++; if (ansMissing <= 5) console.log(`ANS-MISSING ${k}`); continue; }
  if (JSON.stringify(oa[k].raw) !== JSON.stringify(n.raw)) { ansDiff++; if (ansDiff <= 10) console.log(`ANS ${k}: ${JSON.stringify(oa[k].raw)} -> ${JSON.stringify(n.raw)}`); }
}
console.log(`答案键 old=${Object.keys(oa).length} new=${Object.keys(na).length} 值变化=${ansDiff} 新缺失=${ansMissing}`);

console.log("\n== 400-1200 桶抽样（new，按长度降序前 20）==");
const mid = newIdx.groups.filter((g) => { const l = (g.shared_prompt || "").length; return l > 400 && l <= 1200; });
mid.sort((a, b) => (b.shared_prompt || "").length - (a.shared_prompt || "").length);
for (const g of mid.slice(0, 20)) {
  console.log(`  ${g.id} len=${g.shared_prompt.length} type=${g.type} head=${JSON.stringify(g.shared_prompt.slice(0, 100))}`);
}
