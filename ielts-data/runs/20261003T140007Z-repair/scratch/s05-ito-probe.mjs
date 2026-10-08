// s05-ito-probe.mjs — 抓取 1 个真实 ITO practice 页（剑10 T1），存 raw + 打印答案区格式
// 预算：≤2 请求；失败即停（不重试风暴）。
import { storeRaw, resolveDataDir } from "file:///C:/Users/weo/Desktop/api/ielts-api/data-store.mjs";

const WP = "https://ieltstrainingonline.com/wp-json/wp/v2/posts";
const UA = "Mozilla/5.0";
const slugs = [
  "practice-cam-10-listening-test-01-with-answer-and-audioscripts",
  "practice-cam-10-listening-test-01",
];
const root = resolveDataDir();
let done = false;
for (const slug of slugs) {
  const url = WP + "?slug=" + encodeURIComponent(slug) + "&_fields=id,title,slug,content";
  let r;
  try {
    r = await fetch(url, { headers: { "user-agent": UA, accept: "application/json" }, signal: AbortSignal.timeout(30000) });
  } catch (e) { console.log("FETCH FAIL", slug, String(e && e.message || e)); continue; }
  console.log("HTTP", r.status, slug);
  if (!r.ok) continue;
  const text = await r.text();
  const stored = storeRaw({
    root, source: "ieltstrainingonline.com", body: text,
    meta: { url, slug, book: 10, test: 1, kind: "practice-page", note: "S05 ITO answer-table format probe" },
  });
  console.log("stored:", stored.bodyPath, stored.bytes, "bytes", "deduped=" + stored.deduped);
  const arr = JSON.parse(text);
  const p = Array.isArray(arr) ? arr[0] : arr;
  if (!p || !p.id) { console.log("no post found for slug"); continue; }
  const html = (p.content && p.content.rendered) || "";
  console.log("title:", (p.title && p.title.rendered) || "", "| content len:", html.length);
  // 找到 "Answer Cam" 附近（原始 HTML），打印前后片段
  const i = html.search(/Answers?\s+(?:Cam|Cambridge|IELTS)/i);
  console.log("answer heading at:", i);
  if (i >= 0) {
    console.log("---- RAW HTML around answer area (first 1800 chars) ----");
    console.log(JSON.stringify(html.slice(i, i + 1800)));
  }
  done = true;
  break;
}
if (!done) { console.log("PROBE INCOMPLETE: no page fetched"); process.exit(2); }
console.log("PROBE OK");
