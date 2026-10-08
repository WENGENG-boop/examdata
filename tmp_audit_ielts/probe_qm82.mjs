import { pteReading } from 'file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs';
const r = await pteReading(8, 2);
console.log('missing:', JSON.stringify(r.questions_missing));
console.log('answers 1-10:', JSON.stringify(r.answer_key.filter(a=>a.number<=10).map(a=>a.number+':'+a.answer)));
console.log('questions 1-10:', JSON.stringify((r.questions||[]).filter(q=>q.number<=10).map(q=>({n:q.number,t:(q.text||'').slice(0,60)}))));
// raw page text check
const res = await fetch('https://practicepteonline.com/ielts-reading-test-67/');
console.log('status', res.status);
