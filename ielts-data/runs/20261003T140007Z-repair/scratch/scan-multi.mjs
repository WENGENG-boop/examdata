// 扫描全部 raw 页面的 multi-select 组及其空 prompt 槽位
import fs from 'node:fs';
import path from 'node:path';
import { parsePtePage, expectedFor } from '../../../../ielts-api/pte.mjs';

const RAW_DIR = 'C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003';
const IDX = JSON.parse(fs.readFileSync('C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json', 'utf8'));
const files = fs.readdirSync(RAW_DIR).filter(f => /^raw-\d+\.txt$/.test(f)).sort((a, b) => parseInt(a.match(/\d+/)) - parseInt(b.match(/\d+/)));

let nMulti = 0, nEmpty = 0;
const rows = [];
for (const f of files) {
  const raw = parseInt(f.match(/\d+/)[0]);
  const e = IDX.find(x => x.raw_index === raw);
  if (!e) continue;
  const id = { book: e.book, test: e.test, skill: e.skill };
  const html = fs.readFileSync(path.join(RAW_DIR, f), 'utf8');
  let out;
  try { out = parsePtePage(html, id, expectedFor(id.book, id.test, id.skill)); } catch (err) { rows.push([raw, 'ERROR', err.message]); continue; }
  for (const g of out.question_groups) {
    const inst = (g.instruction || '') + '\n' + (g.shared_prompt || '');
    if (!/TWO|THREE|FOUR|TWO correct|correct options/i.test(inst)) continue;
    if (g.structural) continue;
    nMulti++;
    const empty = g.slots.filter(s => !s.prompt).map(s => s.number);
    if (empty.length) {
      nEmpty++;
      rows.push([raw, `b${id.book}t${id.test} ${id.skill}`, `G${g.index}`, JSON.stringify(g.numbers), 'EMPTY=' + JSON.stringify(empty), 'inst=' + JSON.stringify((g.instruction || '').slice(0, 70)), 'shared=' + JSON.stringify((g.shared_prompt || '').slice(0, 90))]);
    }
  }
}
console.log(`multi-ish groups: ${nMulti}, with empty prompts: ${nEmpty}`);
for (const r of rows) console.log(r.join(' | '));
