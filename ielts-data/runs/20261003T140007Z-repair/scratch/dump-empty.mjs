// 对指定页面，打印所有含空 prompt 槽位的组的 instruction/shared_prompt/kind 摘要
import fs from 'node:fs';
import path from 'node:path';
import { parsePtePage, expectedFor } from '../../../../ielts-api/pte.mjs';

const RAW_DIR = 'C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003';
const IDX = JSON.parse(fs.readFileSync('C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json', 'utf8'));
const raws = process.argv[2].split(',').map(Number);
for (const raw of raws) {
  const e = IDX.find(x => x.raw_index === raw);
  const id = { book: e.book, test: e.test, skill: e.skill };
  const html = fs.readFileSync(path.join(RAW_DIR, `raw-${raw}.txt`), 'utf8');
  const out = parsePtePage(html, id, expectedFor(id.book, id.test, id.skill));
  console.log(`\n##### raw-${raw} b${id.book}t${id.test} ${id.skill} qmiss=${JSON.stringify(out.questions_missing)}`);
  for (const g of out.question_groups) {
    const empty = g.slots.filter(s => !s.prompt);
    if (!empty.length) continue;
    const kinds = [...new Set(g.slots.map(s => s.kind))];
    console.log(`G${g.index} nums=[${g.numbers.join(',')}] kinds=[${kinds}] empty=[${empty.map(s => s.number + ':' + s.kind).join(',')}]`);
    console.log(`   inst: ${JSON.stringify((g.instruction || '').slice(0, 110))}`);
    console.log(`   shared: ${JSON.stringify((g.shared_prompt || '').slice(0, 130))}`);
    console.log(`   pools: ${(g.pools || []).map(p => p.options.length).join('/')} assets: ${(g.assets || []).length}`);
  }
}
