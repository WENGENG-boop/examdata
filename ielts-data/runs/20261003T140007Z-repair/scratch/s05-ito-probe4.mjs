// s05-ito-probe4.mjs — 枚举 practice slug 命名规律（1 请求）
import { storeRaw, resolveDataDir } from "file:///C:/Users/weo/Desktop/api/ielts-api/data-store.mjs";
const root = resolveDataDir();
const url = "https://ieltstrainingonline.com/wp-json/wp/v2/posts?search=Practice%20Cam&per_page=100&_fields=id,slug,title";
const r = await fetch(url, { headers: { "user-agent": "Mozilla/5.0", accept: "application/json" }, signal: AbortSignal.timeout(30000) });
const text = await r.text();
console.log("HTTP", r.status, "bytes", text.length);
const stored = storeRaw({ root, source: "ieltstrainingonline.com", body: text, meta: { url, kind: "search-practice-slugs", note: "S05 ITO practice slug patterns" } });
console.log("stored:", stored.sha256.slice(0, 16));
const arr = JSON.parse(text);
const slugs = arr.map(p => p.slug).sort();
// 归纳模式
const pats = {};
for (const s of slugs) {
  const p = s.replace(/\d+/g, "N");
  pats[p] = (pats[p] || 0) + 1;
}
console.log("patterns:");
for (const [p, n] of Object.entries(pats)) console.log(" ", n, p);
console.log("total:", slugs.length);
console.log("sample:", slugs.slice(0, 12).join("\n "));
