// 收集 S04 测试用例的精确期望值
import fs from 'node:fs';
import path from 'node:path';
import { parsePtePage, expectedFor } from '../../../../ielts-api/pte.mjs';

const RAW_DIR = 'C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003';
const IDX = JSON.parse(fs.readFileSync('C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json', 'utf8'));
const idOf = (raw) => {
  const e = IDX.find(x => x.raw_index === raw);
  return e ? { book: e.book, test: e.test, skill: e.skill } : null;
};
const parse = (raw) => {
  const id = idOf(raw);
  const html = fs.readFileSync(path.join(RAW_DIR, `raw-${raw}.txt`), 'utf8');
  const exp = expectedFor(id.book, id.test, id.skill);
  return { id, exp, out: parsePtePage(html, id, exp) };
};

const list = process.argv[2] ? process.argv[2].split(',').map(Number) : [];
for (const raw of list) {
  const { id, exp, out } = parse(raw);
  console.log(`\n===== raw-${raw} b${id.book}t${id.test} ${id.skill} =====`);
  console.log('expected_total:', exp && exp.expected_total, 'exp_source:', out.expected_source);
  console.log('question_count:', out.question_count, 'questions:', out.questions.length, 'q_missing:', JSON.stringify(out.questions_missing), 'a_missing:', JSON.stringify(out.answer_missing), 'a_missing_detail:', JSON.stringify(out.answer_missing_detail));
  console.log('counts:', JSON.stringify(out.counts));
  for (const g of out.question_groups) {
    const nums = g.slots.map(s => s.number);
    const empty = g.slots.filter(s => !s.prompt).map(s => s.number);
    console.log(`  G${g.index} kind=${g.kind} nums=[${nums.join(',')}]${empty.length ? ' EMPTY=[' + empty.join(',') + ']' : ''}${g.structural ? ' structural' : ''} pools=${(g.pools || []).length}`);
  }
  console.log('warnings:', JSON.stringify(out.warnings.map(w => w.kind)));
}
