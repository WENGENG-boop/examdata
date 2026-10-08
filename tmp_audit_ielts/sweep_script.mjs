import * as api from "file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs";
const out = {};
let total = 0;
for (let b = 1; b <= 20; b++) {
  const r = await api.listeningScript(b);
  let parts = 0, sets = 0, chars = 0;
  if (r.ok) {
    for (const [k, t] of Object.entries(r.tests || {})) {
      const pk = Object.keys(t || {});
      parts += pk.length; sets++;
      for (const p of pk) chars += String(t[p] || "").length;
    }
  }
  out[b] = { ok: r.ok, source: r.source, sets, parts, chars };
  total += parts;
  console.error(b, r.ok, sets, parts, chars);
}
console.log(JSON.stringify({ total_parts: total, books: out }, null, 2));
