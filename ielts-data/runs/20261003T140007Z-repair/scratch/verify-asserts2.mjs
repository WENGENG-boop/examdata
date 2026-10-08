// Part B 断言值精确 dump（生产约定：reading→academic_reading）
import fs from 'node:fs';
import path from 'node:path';
import { parsePtePage, expectedFor } from '../../../../ielts-api/pte.mjs';

const RAW_DIR = 'C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003';
const IDX = JSON.parse(fs.readFileSync('C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json', 'utf8'));
const parse = (raw) => {
  const e = IDX.find(x => x.raw_index === raw);
  const skill = e.skill === 'reading' ? 'academic_reading' : 'listening';
  const id = { book: e.book, test: e.test, skill, slug: e.slug };
  const html = fs.readFileSync(path.join(RAW_DIR, `raw-${raw}.txt`), 'utf8');
  return { id, out: parsePtePage(html, id, expectedFor(id.book, id.test, skill)) };
};
const q = (out, n) => out.questions.find(x => x.number === n);
const g = (out, i) => out.question_groups.find(x => x.index === i);

// raw-143 q35
{ const { out } = parse(143); console.log('143 q34:', JSON.stringify(q(out,34).answer), 'q35:', JSON.stringify(q(out,35).answer), 'am:', JSON.stringify(out.answer_missing), 'detail:', JSON.stringify(out.answer_missing_detail)); }
// raw-35
{ const { out } = parse(35); const g8 = g(out,8); console.log('35 qc:', out.question_count, 'qm:', JSON.stringify(out.questions_missing), 'G8 nums:', JSON.stringify(g8.numbers), 'ext:', JSON.stringify(g8.range_extended), 'oo:', g8.out_of_range.length);
  console.log('35 G8 slots:', JSON.stringify(g8.slots.map(s => [s.number, s.kind, s.prompt])));
  const g11 = g(out,11); console.log('35 G11 slot:', JSON.stringify(g11.slots.map(s => [s.number, s.kind, s.options.length, s.prompt.slice(0,60)])), 'ans:', JSON.stringify(q(out,40).answer));
  console.log('35 passages:', out.counts.passages, JSON.stringify(out.passages.map(p => p.title)));
}
// raw-311
{ const { out } = parse(311); const g2 = g(out,2); console.log('311 G2:', JSON.stringify(g2.slots.map(s => [s.number, s.kind, s.prompt])), 'ans:', JSON.stringify([17,18,19,20].map(n => q(out,n).answer))); }
// raw-122
{ const { out } = parse(122); const g0 = g(out,0); console.log('122 G0:', JSON.stringify(g0.slots.map(s => [s.number, s.kind, s.prompt])), 'ans:', JSON.stringify([2,3,4,5].map(n => q(out,n).answer))); }
// raw-103 pools
{ const { out } = parse(103); console.log('103 pools:', JSON.stringify(out.question_groups.map(x => [x.index, x.numbers.length, x.pools.length, x.pools[0] ? x.pools[0].options.map(o=>o.label) : []]))); }
// raw-299 G1
{ const { out } = parse(299); const g1 = g(out,1); console.log('299 G1 nums:', JSON.stringify(g1.numbers), 'pools:', g1.pools.length, 'slots:', g1.slots.length); }
// raw-152
{ const { out } = parse(152); console.log('152 G6:', JSON.stringify(g(out,6).slots.map(s => [s.number, s.kind, s.options.length, s.prompt.slice(0,70)])), 'q26:', JSON.stringify(q(out,26).answer));
  console.log('152 G7 q27:', JSON.stringify(q(out,27).answer), 'q28:', JSON.stringify(q(out,28).answer)); }
// raw-315
{ const { out } = parse(315); console.log('315 q28:', JSON.stringify(q(out,28).answer), 'q29:', JSON.stringify(q(out,29).answer), 'G5 nums:', JSON.stringify(g(out,5).numbers)); }
// raw-307
{ const { out } = parse(307); console.log('307 q32:', JSON.stringify(q(out,32).answer), 'prompt:', JSON.stringify(g(out,6).slots.find(s=>s.number===32).prompt), 'G6 nums:', JSON.stringify(g(out,6).numbers)); }
// raw-303
{ const { out } = parse(303); console.log('303 q18:', JSON.stringify(q(out,18).answer), 'prompt:', JSON.stringify(g(out,2).slots.find(s=>s.number===18).prompt)); }
// F 类 11 组
for (const [raw, gi, n] of [[152,6,26],[35,11,40],[37,8,40],[43,7,27],[48,8,40],[56,3,13],[91,8,40],[99,9,40],[127,8,40],[131,3,13],[135,2,13]]) {
  const { out } = parse(raw); const grp = g(out,gi); const s = grp.slots.find(x => x.number === n);
  console.log(`F raw-${raw} G${gi} q${n}: nums=${JSON.stringify(grp.numbers)} kind=${s.kind} opts=${s.options.length} ans=${JSON.stringify(q(out,n).answer)} prompt=${JSON.stringify(s.prompt.slice(0,80))}`);
}
// 裸数字 5 页
for (const [raw, gi, n] of [[192,4,26],[219,7,36],[256,0,5],[287,6,38]]) {
  const { out } = parse(raw); const s = g(out,gi).slots.find(x => x.number === n);
  console.log(`bare raw-${raw} G${gi} q${n}: kind=${s.kind} ans=${JSON.stringify(q(out,n).answer)} prompt=${JSON.stringify(s.prompt)}`);
}
// raw-110 / 267 / 75 / 236
{ const { out } = parse(110); const g6 = g(out,6); console.log('110 G6 nums:', JSON.stringify(g6.numbers), 'kinds:', JSON.stringify([...new Set(g6.slots.map(s=>s.kind))]), 'q31:', JSON.stringify(q(out,31).answer), 'q40:', JSON.stringify(q(out,40).answer)); }
{ const { out } = parse(267); const g1 = g(out,1); console.log('267 G1 nums:', JSON.stringify(g1.numbers), 'kinds:', JSON.stringify([...new Set(g1.slots.map(s=>s.kind))]), 'q9:', JSON.stringify(q(out,9).answer), 'q13:', JSON.stringify(q(out,13).answer)); }
{ const { out } = parse(75); const g2 = g(out,2); console.log('75 G2 nums:', JSON.stringify(g2.numbers), 'q10:', JSON.stringify(q(out,10).answer), 'q13:', JSON.stringify(q(out,13).answer)); }
{ const { out } = parse(236); const g1 = g(out,1); console.log('236 G1 nums:', JSON.stringify(g1.numbers), 'slot7:', JSON.stringify(g1.slots.find(s=>s.number===7).prompt), 'q7:', JSON.stringify(q(out,7).answer)); }
// raw-163
{ const { out } = parse(163); const g4 = g(out,4); console.log('163 qc:', out.question_count, 'qm:', JSON.stringify(out.questions_missing), 'G4 nums:', JSON.stringify(g4.numbers), 'q30:', JSON.stringify(q(out,30).answer), 'q36:', JSON.stringify(q(out,36).answer), 'assets:', out.assets.length, 'img:', JSON.stringify(out.assets.find(a=>a.kind==='image')?.url)); }
// raw-243
{ const { out } = parse(243); const s = g(out,0).slots.find(x => x.number === 10); console.log('243 q10:', JSON.stringify(q(out,10).answer), 'prompt:', JSON.stringify(s.prompt)); }
// raw-180
{ const { out } = parse(180); const s = g(out,5).slots.find(x => x.number === 38); console.log('180 q38:', JSON.stringify(q(out,38).answer), 'kind:', s.kind, 'prompt:', JSON.stringify(s.prompt)); }
// raw-280
{ const { out } = parse(280); const s = g(out,8).slots.find(x => x.number === 39); console.log('280 q39:', JSON.stringify(q(out,39).answer), 'prompt:', JSON.stringify(s.prompt), 'G8 nums:', JSON.stringify(g(out,8).numbers)); }
// raw-8 详细
{ const { out } = parse(8); const g4 = g(out,4); console.log('8 qc:', out.question_count, 'questions:', out.questions.length, 'qm:', JSON.stringify(out.questions_missing), 'am:', JSON.stringify(out.answer_missing));
  console.log('8 G4:', JSON.stringify(g4.slots.map(s => [s.number, s.kind, s.options.length])), 'shared:', JSON.stringify(g4.shared_prompt.slice(0,80)), 'pool:', JSON.stringify(g4.pools[0].options.map(o=>o.label)));
  console.log('8 q40:', JSON.stringify(q(out,40).answer), 'kind:', q(out,40).kind); }
