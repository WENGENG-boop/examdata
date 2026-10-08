// s05-ito-probe2.mjs — 定位 ITO practice 页真实 slug（search 查询，posts + pages）
import { storeRaw, resolveDataDir } from "file:///C:/Users/weo/Desktop/api/ielts-api/data-store.mjs";
const UA = "Mozilla/5.0";
const root = resolveDataDir();
const tries = [
  ["posts", "https://ieltstrainingonline.com/wp-json/wp/v2/posts?search=practice-cam-10-listening&per_page=20&_fields=id,slug,title,type"],
  ["pages", "https://ieltstrainingonline.com/wp-json/wp/v2/pages?search=practice-cam-10-listening&per_page=20&_fields=id,slug,title,type"],
];
for (const [kind, url] of tries) {
  let r;
  try {
    r = await fetch(url, { headers: { "user-agent": UA, accept: "application/json" }, signal: AbortSignal.timeout(30000) });
  } catch (e) { console.log("FETCH FAIL", kind, String(e && e.message || e)); continue; }
  const text = await r.text();
  console.log("HTTP", r.status, kind, "bytes", text.length);
  const stored = storeRaw({ root, source: "ieltstrainingonline.com", body: text, meta: { url, kind: "search-" + kind, note: "S05 ITO slug locate" } });
  console.log("stored:", stored.sha256.slice(0, 16), stored.deduped);
  try {
    const arr = JSON.parse(text);
    for (const p of arr) console.log(" ", p.id, "|", p.type || "", "|", p.slug, "|", ((p.title || {}).rendered || "").slice(0, 70));
  } catch (e) { console.log("  parse fail:", String(e.message).slice(0, 120)); }
}
