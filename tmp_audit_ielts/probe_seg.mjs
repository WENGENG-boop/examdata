import { listeningSegments } from 'file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs';
const s = await listeningSegments(19, 1, 1);
console.log('ok:', s.ok, '| segments:', (s.segments||[]).length);
const f = (s.segments||[])[0];
console.log('seg[0] keys:', JSON.stringify(Object.keys(f||{})));
console.log('seg[0]:', JSON.stringify({id:f.id, start:f.start, speaker:f.speaker, en:(f.en||'').slice(0,50), zh:f.zh, words:(f.words||[]).slice(0,2)}));
