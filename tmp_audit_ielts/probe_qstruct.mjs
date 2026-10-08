import { pteReading } from 'file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs';
const r = await pteReading(20,1);
const qs = r.questions||[];
console.log('total:', qs.length);
console.log('first 3 full:', JSON.stringify(qs.slice(0,3), null, 1));
console.log('keys:', Object.keys(qs[0]||{}));
