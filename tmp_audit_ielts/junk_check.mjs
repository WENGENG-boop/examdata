// 全册 maslow/reader 解析后：垃圾残留检测（Search / LISTENING KEYS / **Cam / Answer Cam / 编号答案表）
const m = await import('file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs');

const junkRes = [
  [/LISTENING KEYS/i, 'LISTENING KEYS'],
  [/\bSearch\b/, 'Search'],
  [/\*{2,3}\s*(?:Answer\s+)?Cam\s*\d+\s+Listening\s+Test/i, '**Cam N Listening Test'],
  [/\bAnswer Cam\b/i, 'Answer Cam'],
  [/^\s*Answers?\s*$/im, 'Answers line'],
];

let totalJunk = 0;
const summary = [];
for (let b = 1; b <= 21; b++) {
  const s = await m.listeningScript(b);
  if (!s.ok) { summary.push(`b${b} FAIL ${s.error}`); continue; }
  const tests = s.tests || {};
  let parts = 0, junkHits = [];
  for (const [tn, pm] of Object.entries(tests)) {
    for (const [pn, txt] of Object.entries(pm)) {
      parts++;
      for (const [re, name] of junkRes) {
        const mm = re.exec(txt);
        if (mm) junkHits.push(`${tn}.${pn}: ${name} @${mm.index}`);
      }
    }
  }
  totalJunk += junkHits.length;
  summary.push(`b${b} src=${s.source} tests=${Object.keys(tests).length} parts=${parts} junk=${junkHits.length}${junkHits.length ? ' :: ' + junkHits.slice(0, 6).join(' | ') : ''}`);
}
console.log(summary.join('\n'));
console.log('TOTAL JUNK HITS:', totalJunk);
