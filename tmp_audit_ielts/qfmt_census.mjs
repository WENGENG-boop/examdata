// 格式普查：抽样页面题干区（首个 "Questions N" 到 Show Answers 按钮）的编号格式分布
import { bookTests } from 'file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/pte.mjs';
import { writeFileSync } from 'node:fs';
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36";
const API = "https://practicepteonline.com/wp-json/wp/v2/pages";
const books = [2, 5, 8, 10, 12, 15, 17, 19, 20, 21];
const out = [];
const sleep = (ms) => new Promise(s => setTimeout(s, ms));

function census(html) {
  const cutIdx = html.search(/bg-showmore-action|Show Answers/i);
  const h = cutIdx > 0 ? html.slice(0, cutIdx) : html;
  const text = h.replace(/<script[\s\S]*?<\/script>/gi, " ").replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<br\s*\/?>/gi, "\n").replace(/<\/(p|div|li|tr|h[1-6]|td)>/gi, "\n")
    .replace(/<[^>]+>/g, " ").replace(/&nbsp;/g, " ").replace(/&#8217;|&rsquo;|&#39;/g, "'")
    .replace(/&#8211;|&ndash;/g, "-").replace(/&quot;/g, '"')
    .replace(/[ \t\u00a0]+/g, " ").replace(/\n{2,}/g, "\n").trim();
  const lines = text.split("\n");
  const dot = new Set(), nodot = new Set(), paren = new Set();
  for (const ln of lines) {
    let m;
    if ((m = /^\s*(\d{1,2})\s*[.．)]\s*([^\n]{2,})/.exec(ln))) { const n = +m[1]; if (n >= 1 && n <= 40) dot.add(n); }
    if ((m = /^\s*(\d{1,2})[ \t]+([^\n]{2,})/.exec(ln))) { const n = +m[1]; if (n >= 1 && n <= 40) nodot.add(n); }
    for (const pm of ln.matchAll(/\((\d{1,2})\)/g)) { const n = +pm[1]; if (n >= 1 && n <= 40) paren.add(n); }
  }
  const all = new Set([...dot, ...nodot, ...paren]);
  const miss = []; for (let i = 1; i <= 40; i++) if (!all.has(i)) miss.push(i);
  return { dot: [...dot].sort((a,b)=>a-b), nodot: [...nodot].sort((a,b)=>a-b), paren: [...paren].sort((a,b)=>a-b), missing: miss };
}

for (const b of books) {
  for (const kind of ["reading", "listening"]) {
    const bt = await bookTests(b);
    const slug = bt[kind]?.[1];
    if (!slug) { out.push({ b, kind, slug: null }); continue; }
    const r = await fetch(`${API}?slug=${slug}&_fields=content`, { headers: { "user-agent": UA } });
    const j = await r.json();
    const html = j?.[0]?.content?.rendered || "";
    const c = census(html);
    out.push({ b, kind, slug, ...c, sizes: { dot: c.dot.length, nodot: c.nodot.length, paren: c.paren.length } });
    console.log(`b${b} ${kind} ${slug}: dot=${c.dot.length} nodot=${c.nodot.length} paren=${c.paren.length} missing=[${c.missing.join(",")}]`);
    await sleep(400);
  }
}
writeFileSync("qfmt_census.json", JSON.stringify(out, null, 1));
console.log("saved qfmt_census.json");
