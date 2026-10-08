// S04 测试期望值批量 dump：为 ielts-pte-parser.test.mjs 提供精确断言值
import fs from 'node:fs';
import path from 'node:path';
import { parsePtePage, expectedFor } from '../../../../ielts-api/pte.mjs';

const RAW_DIR = 'C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003';
const IDX = JSON.parse(fs.readFileSync('C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json', 'utf8'));
const cache = new Map();
const parse = (raw) => {
  if (cache.has(raw)) return cache.get(raw);
  const e = IDX.find(x => x.raw_index === raw);
  const id = { book: e.book, test: e.test, skill: e.skill };
  const html = fs.readFileSync(path.join(RAW_DIR, `raw-${raw}.txt`), 'utf8');
  const out = parsePtePage(html, id, expectedFor(id.book, id.test, id.skill));
  cache.set(raw, { id, out });
  return cache.get(raw);
};
const show = (raw, gi, nums) => {
  const { id, out } = parse(raw);
  const g = out.question_groups[gi];
  console.log(`\n## raw-${raw} b${id.book}t${id.test} ${id.skill} G${gi} nums=[${g.numbers.join(',')}] kind=${g.kind} shared=${JSON.stringify((g.shared_prompt || '').slice(0, 120))}`);
  for (const s of g.slots) {
    if (nums && !nums.includes(s.number)) continue;
    console.log(`  ${s.number} kind=${s.kind} opts=${s.options.length} prompt=${JSON.stringify(s.prompt)}`);
  }
  const q = (n) => out.questions.find(x => x.number === n);
  if (nums) for (const n of nums) {
    const x = q(n);
    console.log(`  [q${n}] kind=${x.kind} answer=${JSON.stringify(x.answer)} prompt=${JSON.stringify((x.prompt || '').slice(0, 200))}`);
  }
};

// 1. raw-8 multi-select G4 + q40/41
{
  const { out } = parse(8);
  console.log('## raw-8 summary');
  console.log('question_count:', out.question_count, 'questions:', out.questions.length, 'q_missing:', JSON.stringify(out.questions_missing), 'a_missing:', JSON.stringify(out.answer_missing));
  console.log('counts:', JSON.stringify(out.counts));
  const g4 = out.question_groups.find(g => g.index === 4);
  console.log('G4 slots:', JSON.stringify(g4.slots.map(s => ({ n: s.number, kind: s.kind, prompt: s.prompt, opts: s.options.length }))));
  console.log('G4 shared_prompt:', JSON.stringify(g4.shared_prompt));
  console.log('G4 pools:', JSON.stringify(g4.pools.map(p => ({ kind: p.kind, options: p.options.map(o => o.label) }))));
}
// 2. raw-143
{
  const { out } = parse(143);
  console.log('\n## raw-143 summary');
  console.log('question_count:', out.question_count, 'q_missing:', JSON.stringify(out.questions_missing), 'a_missing:', JSON.stringify(out.answer_missing), 'detail:', JSON.stringify(out.answer_missing_detail));
}
// 3. raw-163
show(163, 4, [30, 31, 32, 33, 34, 35, 36]);
{
  const { out } = parse(163);
  console.log('raw-163 question_count:', out.question_count, 'q_missing:', JSON.stringify(out.questions_missing));
}
// 4. raw-236/267/75/110 prompts
show(236, 1, [6, 7, 8]);
show(267, 1, [7, 8, 9, 10, 11, 12, 13]);
show(75, 2, [10, 11, 12, 13]);
show(110, 6, [31, 32, 39, 40]);
// 5. raw-303 G2 q18
show(303, 2, [18]);
// 6. raw-307 G6 q32
show(307, 6, [32]);
// 7. raw-315 G5 q28/29 ; raw-152 G7 q27/28 ; raw-180 G5 q38 ; raw-280 G8 q39 ; raw-243 G0 q10
show(315, 5, [28, 29]);
show(152, 7, [27, 28]);
show(180, 5, [38]);
show(280, 8, [39]);
show(243, 0, [10]);
// 8. F-class
show(152, 6, [26]);
show(35, 11, [40]);
show(37, 8, [40]);
show(43, 7, [27]);
show(48, 8, [40]);
show(56, 3, [13]);
show(91, 8, [40]);
show(99, 9, [40]);
show(127, 8, [40]);
show(131, 3, [13]);
show(135, 2, [13]);
// 9. bare numbers
show(192, 4, [26]);
show(219, 7, [36]);
show(256, 0, [5]);
show(287, 6, [38]);
show(311, 2, [17, 18, 19, 20]);
// 10. raw-122 G0 q2-5 ; raw-103 headings ; raw-299 G1
show(122, 0, [2, 3, 4, 5]);
{
  const { out } = parse(103);
  console.log('\n## raw-103 groups');
  for (const g of out.question_groups) console.log(`  G${g.index} nums=[${g.numbers.join(',')}] pools=${g.pools.length} poolOpts=${JSON.stringify(g.pools.map(p => p.options.map(o => o.label)))}`);
}
{
  const { out } = parse(299);
  console.log('\n## raw-299 groups');
  for (const g of out.question_groups) console.log(`  G${g.index} nums=[${g.numbers.join(',')}] pools=${g.pools.length}`);
}
// 11. raw-35 Edit F
{
  const { out } = parse(35);
  console.log('\n## raw-35 summary');
  console.log('question_count:', out.question_count, 'q_missing:', JSON.stringify(out.questions_missing));
  const g8 = out.question_groups[8];
  console.log('G8 nums:', JSON.stringify(g8.numbers), 'range_extended:', JSON.stringify(g8.range_extended), 'oo:', JSON.stringify(g8.out_of_range));
  console.log('G8 slots 29-33:', JSON.stringify(g8.slots.filter(s => s.number >= 29 && s.number <= 33).map(s => ({ n: s.number, kind: s.kind, prompt: s.prompt }))));
}
