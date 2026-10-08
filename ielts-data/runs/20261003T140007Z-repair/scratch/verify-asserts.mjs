// 写测试前核对若干断言值：raw-163 assets、raw-35 全组、raw-8 G4、raw-110 组信息
import fs from 'node:fs';
import path from 'node:path';
import { parsePtePage, expectedFor } from '../../../../ielts-api/pte.mjs';

const RAW_DIR = 'C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003';
const IDX = JSON.parse(fs.readFileSync('C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json', 'utf8'));
const parse = (raw) => {
  const e = IDX.find(x => x.raw_index === raw);
  const id = { book: e.book, test: e.test, skill: e.skill };
  const html = fs.readFileSync(path.join(RAW_DIR, `raw-${raw}.txt`), 'utf8');
  return { id, out: parsePtePage(html, id, expectedFor(id.book, id.test, id.skill)) };
};

// raw-163 assets
{
  const { out } = parse(163);
  console.log('raw-163 assets:', JSON.stringify(out.assets, null, 1).slice(0, 1500));
  console.log('raw-163 assets count:', out.assets.length);
}
// raw-35 全组
{
  const { out } = parse(35);
  console.log('\nraw-35 question_count:', out.question_count, 'q_missing:', JSON.stringify(out.questions_missing));
  for (const g of out.question_groups) {
    console.log(`G${g.index} nums=[${g.numbers.join(',')}] slots=${g.slots.length} oo=${g.out_of_range ? g.out_of_range.length : 0} ext=${JSON.stringify(g.range_extended || null)}`);
  }
}
// raw-8 G4 细节
{
  const { out } = parse(8);
  const g4 = out.question_groups.find(g => g.index === 4);
  console.log('\nraw-8 G4 numbers:', JSON.stringify(g4.numbers), 'range:', JSON.stringify(g4.range));
  console.log('raw-8 G4 slots:', JSON.stringify(g4.slots.map(s => ({ n: s.number, kind: s.kind, opts: s.options.length }))));
  console.log('raw-8 G4 pool0 opts:', JSON.stringify(g4.pools[0].options.map(o => o.label)));
  const q40 = out.questions.find(q => q.number === 40);
  const q39 = out.questions.find(q => q.number === 39);
  console.log('raw-8 q39:', JSON.stringify({ answer: q39.answer, kind: q39.kind, groups: q39.groups }), 'q40:', JSON.stringify({ answer: q40.answer, kind: q40.kind }));
}
// raw-110 组
{
  const { out } = parse(110);
  const g6 = out.question_groups.find(g => g.index === 6);
  console.log('\nraw-110 G6 nums:', JSON.stringify(g6.numbers), 'slots:', g6.slots.length, 'kinds:', JSON.stringify([...new Set(g6.slots.map(s => s.kind))]));
}
// raw-192 q26 groups 索引
{
  const { out } = parse(192);
  const q26 = out.questions.find(q => q.number === 26);
  console.log('\nraw-192 q26 group:', q26.group, 'kind:', q26.kind, 'answer:', JSON.stringify(q26.answer));
}
// raw-303 q18
{
  const { out } = parse(303);
  const q18 = out.questions.find(q => q.number === 18);
  console.log('raw-303 q18 kind:', q18.kind, 'answer:', JSON.stringify(q18.answer), 'group:', q18.group);
}
// expectedFor 剑1 听力2
{
  const e = expectedFor(1, 2, 'listening');
  console.log('\nexpectedFor(1,2,listening):', JSON.stringify(e && { status: e.status, expected_total: e.expected_total, max: e.max, numbers_len: e.numbers.length, first: e.numbers.slice(0, 5), last: e.numbers.slice(-3) }));
}
// raw-8 identity 确认
{
  const e = IDX.find(x => x.raw_index === 8);
  console.log('\nraw-8 identity:', JSON.stringify({ book: e.book, test: e.test, skill: e.skill, slug: e.slug }));
}
