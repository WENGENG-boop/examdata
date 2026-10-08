// 交叉核验 v5：hub 权威映射（宽松正则） vs 适配器实际返回的 84 个 slug
import { readFileSync } from "node:fs";
const API = "https://practicepteonline.com/wp-json/wp/v2/pages";
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36";
const j = async (u) => (await fetch(u, { headers: { "user-agent": UA, accept: "application/json" }, signal: AbortSignal.timeout(30000) })).json();
const toText = (h) => h.replace(/<[^>]+>/g, " ").replace(/&nbsp;/g, " ").replace(/\s+/g, " ").trim();

const HUBS = { 1: 9322, 2: 9330, 3: 9341, 4: 9349, 5: 9357, 6: 9365, 7: 9374, 8: 9382, 9: 9390, 10: 9404, 11: 9452, 12: 9463, 13: 7025, 14: 7051, 15: 9314, 16: 9291, 17: 9277, 18: 9263, 19: 9255, 20: 12381, 21: 12724 };

// 与适配器同样的标签解析逻辑，但链接正则放宽（inner HTML 不限长）
function hubMap(c) {
  const reading = {}, listening = {}, general = {};
  let aIdx = 0, gIdx = 0, lIdx = 0;
  for (const m of c.matchAll(/<a[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi)) {
    const url = m[1].replace(/^https?:\/\/practicepteonline\.com/, "").replace(/\/$/, "");
    const label = toText(m[2]);
    const rl = /(?:ielts-)?reading-test-([\w-]+)/i.exec(url);
    const ll = /(?:ielts-)?listening-(?:test-)?(\d+)/i.exec(url);
    const dotted = label.match(/(\d+)\.(\d+)\s*$/);
    const plain = label.match(/(\d+)\s*$/);
    const tail = dotted ? Number(dotted[2]) : plain ? Number(plain[1]) : NaN;
    const idx = Number.isFinite(tail) && tail >= 1 && tail <= 4 ? tail : null;
    const slug = url.replace(/^\/+/, "");
    if (rl && /reading/i.test(label)) {
      if (/general/i.test(label)) general[idx ?? ++gIdx] = slug;
      else reading[idx ?? ++aIdx] = slug;
    } else if (ll && /listening/i.test(label)) {
      listening[idx ?? ++lIdx] = slug;
    }
  }
  return { reading, listening, general };
}

const sweep = JSON.parse(readFileSync("C:/Users/weo/Desktop/api/tmp_audit_ielts/pte_sweep.json", "utf8"));
const adapterBook = Object.fromEntries(sweep.books.map((b) => [b.book, b]));

let mismatches = 0;
console.log("book | test | 适配器 slug | hub 权威 slug | 判定");
for (const book of Object.keys(HUBS).map(Number)) {
  const p = await j(`${API}/${HUBS[book]}?_fields=id,content`);
  const hm = hubMap(p.content.rendered);
  const ab = adapterBook[book];
  for (const t of [1, 2, 3, 4]) {
    const got = ab.reading_map?.[t] ?? null;
    const want = hm.reading[t] ?? null;
    const okMark = got === want ? "OK" : "*** MISMATCH ***";
    if (got !== want) mismatches++;
    console.log(`R ${book} | ${t} | ${got} | ${want} | ${okMark}`);
  }
  for (const t of [1, 2, 3, 4]) {
    const got = ab.listening_map?.[t] ?? null;
    const want = hm.listening[t] ?? null;
    const okMark = got === want ? "OK" : "*** MISMATCH ***";
    if (got !== want) mismatches++;
    console.log(`L ${book} | ${t} | ${got} | ${want} | ${okMark}`);
  }
}
console.log(`\n总 mismatches = ${mismatches} / 168 槽位`);

// hub21 标签内 HTML 长度（解释适配器 80 字符窗口为何漏掉）
const p21 = await j(`${API}/12724?_fields=content`);
console.log("\n=== hub21 各链接 <a> 内 HTML 长度（适配器窗口上限 80） ===");
for (const m of p21.content.rendered.matchAll(/<a[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi)) {
  const inner = m[2];
  console.log(`  ${m[1]}  inner=${inner.length}  ${inner.length > 80 ? "<== 超出 80，适配器正则必然漏掉" : ""}`);
}
