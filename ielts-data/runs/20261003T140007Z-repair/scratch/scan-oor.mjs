// 扫描全部 raw 页面：列出含 out_of_range 题行的组及其指令/box 范围
import fs from 'node:fs';
import path from 'node:path';
import { parsePtePage, expectedFor } from '../../../../ielts-api/pte.mjs';

const RAW_DIR = 'C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003';
const IDX = JSON.parse(fs.readFileSync('C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json', 'utf8'));
const files = fs.readdirSync(RAW_DIR).filter(f => /^raw-\d+\.txt$/.test(f)).sort((a, b) => parseInt(a.match(/\d+/)) - parseInt(b.match(/\d+/)));

const RE_BOX = /boxes?\s+(\d{1,3})\s*(?:[-\u2013\u2014]\s*(\d{1,3})|(?:and|&|,|\/)\s*(\d{1,3}))?/gi;
let nGroups = 0, nAffected = 0;
for (const f of files) {
  const raw = parseInt(f.match(/\d+/)[0]);
  const e = IDX.find(x => x.raw_index === raw);
  if (!e) continue;
  const id = { book: e.book, test: e.test, skill: e.skill };
  const html = fs.readFileSync(path.join(RAW_DIR, f), 'utf8');
  let out;
  try { out = parsePtePage(html, id, expectedFor(id.book, id.test, id.skill)); } catch (err) { console.log(raw, 'ERROR', err.message); continue; }
  for (const g of out.question_groups) {
    if (!g.out_of_range || !g.out_of_range.length) continue;
    nGroups++;
    // box range from instruction+shared
    const text = (g.instruction || '') + '\n' + (g.shared_prompt || '');
    const boxes = [];
    RE_BOX.lastIndex = 0; let m;
    while ((m = RE_BOX.exec(text))) {
      const a = Number(m[1]); const b = m[2] ? Number(m[2]) : m[3] ? Number(m[3]) : a;
      boxes.push([a, b]);
    }
    const oors = g.out_of_range.map(o => o.number);
    // only report when oo numbers are covered by a declared box range
    const covered = oors.filter(n => boxes.some(([a, b]) => n >= a && n <= b));
    if (!covered.length) continue;
    nAffected++;
    console.log(`raw-${raw} b${id.book}t${id.test} ${id.skill} G${g.index} heading=[${g.numbers[0]}..${g.numbers[g.numbers.length-1]}] boxes=${JSON.stringify(boxes)} oo=[${oors.join(',')}] covered=[${covered.join(',')}]`);
    for (const o of g.out_of_range) {
      if (covered.includes(o.number)) console.log(`    ${o.number}: ${JSON.stringify(o.line.slice(0, 90))}`);
    }
  }
}
console.log(`\n总计: 有 out_of_range 且被 box 范围覆盖的组 = ${nAffected} / 含 out_of_range 的组 = ${nGroups}`);
