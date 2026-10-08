import { pteReading, pteListening } from 'file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs';
for (const [b,t] of [[8,2],[20,1],[1,1],[3,2]]) {
  const r = await pteReading(b,t);
  const qs = r.questions||[];
  const withPrompt = qs.filter(q=>q.prompt && q.prompt.trim()).length;
  console.log(`R ${b}-${t}: questions=${qs.length}, withPrompt=${withPrompt}, missing=${JSON.stringify(r.questions_missing)}`);
}
for (const [b,t] of [[10,1],[20,1],[21,1]]) {
  const l = await pteListening(b,t);
  const qs = l.questions||[];
  const withPrompt = qs.filter(q=>q.prompt && q.prompt.trim()).length;
  console.log(`L ${b}-${t}: questions=${qs.length}, withPrompt=${withPrompt}, missing=${JSON.stringify(l.questions_missing)}`);
}
