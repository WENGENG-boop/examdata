import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectBlocks, ownTextLines } from "../../../../ielts-api/html-questions.mjs";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const index = JSON.parse(fs.readFileSync("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json", "utf8"));

// 找一行内出现 >=2 个连续字母标签（A B C D…）的行
function inlineRuns(line) {
  const re = /(?:^|[\s\u2013\u2014(])([A-H])(?:[.):]|\s)/g;
  const labels = [];
  let m;
  while ((m = re.exec(line))) labels.push({ label: m[1], idx: m.index, end: re.lastIndex });
  // 找连续段：起始标签 + 后续按字母表顺序递增
  const runs = [];
  for (let i = 0; i < labels.length; i++) {
    const run = [labels[i]];
    let expect = labels[i].label.charCodeAt(0) + 1;
    for (let j = i + 1; j < labels.length; j++) {
      if (labels[j].label.charCodeAt(0) === expect) { run.push(labels[j]); expect++; }
    }
    if (run.length >= 3) runs.push(run);
  }
  return runs;
}

let pagesA = 0, linesA = 0, pagesB = 0, linesB = 0;
const samples = [];
for (const e of index) {
  if (e.raw_index == null) continue;
  const raw = fs.readFileSync(path.join(RAW_DIR, `raw-${e.raw_index}.txt`), "utf8");
  let arr;
  try { arr = JSON.parse(raw); } catch { continue; }
  const html = arr[0]?.content?.rendered || arr[0]?.html;
  if (!html) continue;
  const root = parseHtml(html);
  const blocks = collectBlocks(root);
  let hitA = 0, hitB = 0;
  for (const b of blocks) {
    for (const line of ownTextLines(b)) {
      const runs = inlineRuns(line);
      if (!runs.length) continue;
      const isQ = /^\d{1,3}[. )]/.test(line);
      const isOpt = /^[A-H][ \t.:]/.test(line);
      if (isQ) { hitA++; if (samples.length < 40) samples.push(`Q ${e.book}-${e.test}-${e.skill} raw-${e.raw_index}: ${line.slice(0, 130)}`); }
      else if (isOpt) { hitB++; if (samples.length < 40) samples.push(`O ${e.book}-${e.test}-${e.skill} raw-${e.raw_index}: ${line.slice(0, 130)}`); }
    }
  }
  if (hitA) { pagesA++; linesA += hitA; }
  if (hitB) { pagesB++; linesB += hitB; }
}
console.log("pattern A (question line with inline options): pages", pagesA, "lines", linesA);
console.log("pattern B (option block line with inline options): pages", pagesB, "lines", linesB);
console.log("--- samples ---");
console.log(samples.join("\n"));
