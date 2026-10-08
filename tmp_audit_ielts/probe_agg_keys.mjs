import { aggregate } from 'file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs';
const p = await aggregate({ book: 20, test: 1 });
console.log('reading keys:', JSON.stringify(Object.keys(p.parts.reading)));
console.log('reading question_count:', p.parts.reading.question_count, '| q len:', (p.parts.reading.questions||[]).length);
console.log('listening_qa keys:', JSON.stringify(Object.keys(p.parts.listening_qa)));
console.log('listening_qa question_count:', p.parts.listening_qa.question_count, '| q len:', (p.parts.listening_qa.questions||[]).length);
console.log('listening_qa instructions:', (p.parts.listening_qa.instructions||[]).length);
