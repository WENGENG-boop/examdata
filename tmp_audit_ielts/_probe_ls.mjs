const api = await import('file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs');
const orig = globalThis.fetch;
let count = 0; const hosts = {};
globalThis.fetch = async (u, o) => { count++; try { const h = new URL(typeof u === "string" ? u : u.url).host; hosts[h] = (hosts[h]||0)+1; } catch {} return orig(u, o); };
for (const b of [17, 11, 20]) {
  count = 0; for (const k in hosts) delete hosts[k];
  const t0 = Date.now();
  const s = await api.listeningScript(b);
  console.log(`listeningScript(${b}): ${Date.now()-t0}ms, requests=${count}, ok=${s.ok}, source=${s.source}, parts=${s.parts}, hosts=${JSON.stringify(hosts)}`);
}
