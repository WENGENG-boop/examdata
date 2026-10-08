// pte_audio_scan.mjs — 枚举 practicepteonline 剑1–21 全部听力音频 URL 并 HEAD 求和
import { bookTests, audio } from '../../../Documents/deepseek-harness/default-workspace/ielts-api/pte.mjs';
import fs from 'node:fs';

const out = { books: {}, head: {}, generated: new Date().toISOString() };
const allUrls = new Set();

for (let b = 1; b <= 21; b++) {
  let bt;
  try { bt = await bookTests(b); } catch (e) { out.books[b] = { error: String(e.message) }; console.error(`book ${b} bookTests FAIL: ${e.message}`); continue; }
  const tests = Object.keys(bt.listening || {}).filter(k => /^\d+$/.test(k));
  out.books[b] = { hub_ok: bt.ok, slugs: bt.listening || {}, tests: {} };
  // 4 套并发
  await Promise.all(tests.map(async t => {
    try {
      const r = await audio(b, +t);
      out.books[b].tests[t] = { ok: r.ok, urls: r.all || [], error: r.error || null };
      for (const u of (r.all || [])) allUrls.add(u);
    } catch (e) { out.books[b].tests[t] = { error: String(e.message) }; }
  }));
  const okCount = Object.values(out.books[b].tests).filter(x => x.ok).length;
  const uCount = Object.values(out.books[b].tests).reduce((n, x) => n + (x.urls?.length || 0), 0);
  console.error(`[book ${b}] tests=${tests.length} ok=${okCount} urls=${uCount}`);
}

console.error(`unique urls total: ${allUrls.size}`);
const list = [...allUrls];
const CONC = 4;
let totalBytes = 0, headOk = 0, headFail = 0;
async function worker(chunk, wi) {
  for (const u of chunk) {
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const r = await fetch(u, { method: 'HEAD', signal: AbortSignal.timeout(30000), headers: { 'user-agent': 'Mozilla/5.0' } });
        const len = +(r.headers.get('content-length') || 0);
        out.head[u] = { status: r.status, len, type: r.headers.get('content-type') || null };
        if (r.ok && len > 0) { totalBytes += len; headOk++; } else headFail++;
        break;
      } catch (e) {
        if (attempt === 1) { out.head[u] = { error: String(e.message) }; headFail++; }
        else await new Promise(s => setTimeout(s, 800));
      }
    }
    if ((headOk + headFail) % 10 === 0) console.error(`  head progress ${headOk + headFail}/${list.length} total=${(totalBytes / 1048576).toFixed(1)}MB`);
  }
}
const chunks = Array.from({ length: CONC }, (_, i) => list.filter((_, j) => j % CONC === i));
await Promise.all(chunks.map((c, i) => worker(c, i)));

out.summary = { unique_urls: list.length, head_ok: headOk, head_fail: headFail, total_bytes: totalBytes, total_MB: +(totalBytes / 1048576).toFixed(1) };
fs.writeFileSync('pte_audio_scan.json', JSON.stringify(out, null, 2));
console.log('SUMMARY ' + JSON.stringify(out.summary));
console.error('SCAN_DONE');
