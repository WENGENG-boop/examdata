import { pteReading } from 'file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs';
const r = await pteReading(8, 2);
console.log('ok:', r.ok, 'answer_count:', r.answer_count);
console.log('answer_key sample:', JSON.stringify(r.answer_key.slice(0,12)));
console.log('questions sample:', JSON.stringify((r.questions||[]).slice(0,12).map(q=>({n:q.number,text:(q.text||'').slice(0,40)}))));
