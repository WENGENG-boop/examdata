import { pteReading, pteListening } from 'file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs';
for (const [b,t] of [[8,2],[20,1],[1,1]]) {
  const r = await pteReading(b,t);
  const qs = r.questions||[];
  const withText = qs.filter(q=>q.text && q.text.trim()).length;
  console.log(`R ${b}-${t}: questions=${qs.length}, withText=${withText}, missing=${JSON.stringify(r.questions_missing)}`);
  console.log('  sample with text:', JSON.stringify(qs.filter(q=>q.text&&q.text.trim()).slice(0,2)));
}
const l = await pteListening(10,1);
console.log('L 10-1: questions='+(l.questions||[]).length, 'withText='+(l.questions||[]).filter(q=>q.text&&q.text.trim()).length, 'missing='+JSON.stringify(l.questions_missing));
