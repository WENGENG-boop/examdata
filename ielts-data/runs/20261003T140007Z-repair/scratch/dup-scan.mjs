// 扫描全库：同一题号出现在多个组的情况（组合题/重复编号）
import fs from 'node:fs';
import path from 'node:path';
import { parsePtePage, expectedFor } from '../../../../ielts-api/pte.mjs';

const RAW_DIR = 'C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003';
const IDX = JSON.parse(fs.readFileSync('C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json', 'utf8'));
const files = fs.readdirSync(RAW_DIR).filter(f => /^raw-\d+\.txt$/.test(f)).sort((a, b) => parseInt(a.match(/\d+/)) - parseInt(b.match(/\d+/)));

let hits = 0;
for (const f of files) {
  const raw = parseInt(f.match(/\d+/)[0]);
  const e = IDX.find(x => x.raw_index === raw);
  if (!e) continue;
  const id = { book: e.book, test: e.test, skill: e.skill };
  const html = fs.readFileSync(path.join(RAW_DIR, f), 'utf8');
  let out;
  try { out = parsePtePage(html, id, expectedFor(id.book, id.test, id.skill)); } catch { continue; }
  const byNum = new Map();
  for (const g of out.question_groups) {
    for (const s of g.slots) {
      if (!byNum.has(s.number)) byNum.set(s.number, []);
      byNum.get(s.number).push(g.index);
    }
  }
  const dup = [...byNum.entries()].filter(([, gs]) => gs.length > 1).sort((a, b) => a[0] - b[0]);
  if (dup.length) {
    hits++;
    console.log(`raw-${raw} b${e.book}t${e.test} ${e.skill}: ` + dup.map(([n, gs]) => `${n}→G${gs.join('/')}`).join(' '));
  }
}
console.log(`\n含跨组重复编号的页面 = ${hits}`);
