import { reading } from 'file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs';
const d = await reading(19, 1, 1);
console.log('ok:', d.ok);
console.log('top-level keys:', Object.keys(d));
console.log('has segments:', !!d.segments, 'has sentences:', !!d.sentences);
if (d.sentences) console.log('sentences[0]:', JSON.stringify(d.sentences[0]));
console.log('sentence count:', (d.sentences||[]).length);
