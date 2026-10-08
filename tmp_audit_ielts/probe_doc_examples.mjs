import * as api from 'file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs';
// 1. aggregate b3t2 降级表现
const p3 = await api.aggregate({ book: 3, test: 2 });
console.log('b3t2 score:', p3.score, '| warnings:', JSON.stringify(p3.warnings));
console.log('b3t2 listening_qa:', JSON.stringify({ok:p3.parts.listening_qa?.ok, source:p3.parts.listening_qa?.source, ak:(p3.parts.listening_qa?.answer_key||[]).length, segs:(p3.parts.listening_qa?.segments||[]).length}));
// 2. 剑21 T1-T4 score
for (const t of [1,2,3,4]) {
  const p = await api.aggregate({ book: 21, test: t });
  console.log(`b21t${t}: score=${p.score} reading_ac=${p.parts.reading?.answer_count} warn=${JSON.stringify(p.warnings)}`);
}
// 3. pteAudio(20,1).all
const a = await api.pteAudio(20, 1);
console.log('pteAudio(20,1):', JSON.stringify({ok:a.ok, url:(a.url||'').slice(-30), all:(a.all||[]).map(u=>u.slice(-25))}));
// 4. reading(20,1,1) ok?
const r20 = await api.reading(20, 1, 1);
console.log('reading(20,1,1):', JSON.stringify({ok:r20.ok, error:r20.error}));
const r21 = await api.reading(21, 1, 1);
console.log('reading(21,1,1):', JSON.stringify({ok:r21.ok, error:r21.error}));
