import { reading, listening } from "file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/cam21.mjs";
for (const t of [1,2,3,4]) {
  const r = await reading(t);
  const q = r.questions ? Object.keys(r.questions).length : 0;
  const a = r.answer_key ? Object.keys(r.answer_key).length : 0;
  const nulls = r.answer_key ? Object.values(r.answer_key).filter(v => v === null || v === "" || v === undefined).length : 0;
  console.log(`t${t}-reading: ok=${r.ok} questions=${q} answers=${a} nullAnswers=${nulls}`);
}
for (const t of [1,2,3,4]) {
  const l = await listening(t);
  const a = l.answer_key ? Object.keys(l.answer_key).length : 0;
  const nulls = l.answer_key ? Object.values(l.answer_key).filter(v => v === null || v === "" || v === undefined).length : 0;
  let segs = 0;
  if (l.transcript) for (const arr of Object.values(l.transcript)) if (Array.isArray(arr)) segs += arr.length;
  console.log(`t${t}-listening: ok=${l.ok} answers=${a} nullAnswers=${nulls} segs=${segs} keys=${l.transcript?Object.keys(l.transcript).join(','):'none'}`);
}
