// s05-ito-probe3.mjs — 抓取真实 practice 帖（id 9736, 剑10 T1），存 raw + 打印答案区原始 HTML
import { storeRaw, resolveDataDir } from "file:///C:/Users/weo/Desktop/api/ielts-api/data-store.mjs";
const root = resolveDataDir();
const url = "https://ieltstrainingonline.com/wp-json/wp/v2/posts/9736?_fields=id,title,slug,content";
const r = await fetch(url, { headers: { "user-agent": "Mozilla/5.0", accept: "application/json" }, signal: AbortSignal.timeout(30000) });
const text = await r.text();
console.log("HTTP", r.status, "bytes", text.length);
const stored = storeRaw({ root, source: "ieltstrainingonline.com", body: text, meta: { url, post_id: 9736, slug: "practice-cam-10-listening-test-01-with-answer", book: 10, test: 1, kind: "practice-page", note: "S05 ITO answer-table format" } });
console.log("stored:", stored.bodyPath, stored.deduped);
const p = JSON.parse(text);
const html = (p.content && p.content.rendered) || "";
console.log("title:", (p.title && p.title.rendered) || "", "| len:", html.length);
const i = html.search(/Answers?\s+(?:Cam|Cambridge|IELTS)/i);
console.log("answer heading at:", i);
if (i >= 0) {
  console.log("---- RAW HTML around answer area ----");
  console.log(JSON.stringify(html.slice(i, i + 3000)));
}
// also: 数据属性/输入框统计（题目区结构）
for (const pat of ["data-q", "<input", "wp-block-table", "<table", "<td", "checkbox", "radio"]) {
  console.log("count", pat, (html.match(new RegExp(pat.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "g")) || []).length);
}
