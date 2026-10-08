import { cam21Listening, pdfLfs, pdfLfs as pl, cam21Reading } from 'file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs';
const l = await cam21Listening(1);
console.log('cam21Listening(1).counts:', JSON.stringify(l.counts));
const r = await cam21Reading(1);
console.log('cam21Reading(1).counts:', JSON.stringify(r.counts));
const p1 = await pdfLfs(1);
console.log('pdfLfs(1): bytes=', p1.bytes, 'mb=', p1.mb);
