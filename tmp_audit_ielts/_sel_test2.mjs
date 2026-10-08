import { listeningScript } from './ielts-api.mjs';
for (const b of [5, 18, 20]) {
  const t0 = Date.now();
  const r = await listeningScript(b);
  const dt = Date.now() - t0;
  console.log(`book ${b}: ok=${r.ok} source=${r.source} parts=${r.parts ?? '-'} bytes=${r.bytes ?? '-'} ${dt}ms`);
  if (r.alternatives) console.log('   alternatives:', JSON.stringify(r.alternatives));
  if (r.error) console.log('   error:', r.error);
}
