// 交叉核验 v4：剑21 映射真伪 + 全 21 本 hub 链接 vs 适配器正则
const API = "https://practicepteonline.com/wp-json/wp/v2/pages";
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36";
const j = async (u) => (await fetch(u, { headers: { "user-agent": UA, accept: "application/json" }, signal: AbortSignal.timeout(30000) })).json();
const plain = (h) => h.replace(/<br\s*\/?>/gi, "\n").replace(/<\/(p|div|li|tr|h[1-6]|td)>/gi, "\n").replace(/<[^>]+>/g, " ").replace(/&nbsp;/g, " ").replace(/&#8217;/g, "'").replace(/[ \t]+/g, " ").trim();

/* A. 剑21 阅读：hub 标注 vs FALLBACK 给的 slug */
const h21 = await j(`${API}/12724?_fields=id,content`);
const links21 = [...h21.content.rendered.matchAll(/<a[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi)]
  .map((m) => [m[1], plain(m[2]).replace(/\s+/g, " ").trim()]);
console.log("=== hub21 全部链接（宽松正则） ===");
for (const [u, l] of links21) console.log(`   ${u}  ::  ${JSON.stringify(l)}`);

console.log("\n=== 剑21 阅读相关 slug 逐个体检 ===");
for (const s of ["ielts-reading-test-314", "ielts-reading-test-315", "ielts-reading-test-316", "ielts-reading-test-317", "ielts-reading-test-318", "ielts-reading-test-319"]) {
  const a = await j(`${API}?slug=${s}&_fields=id,slug,title,content`);
  const p = a[0];
  if (!p) { console.log(`  ${s}: NOT FOUND`); continue; }
  const html = p.content.rendered;
  const cut = html.search(/Questions?\s+1\s*[-–]/i);
  const paras = [...(cut > 0 ? html.slice(0, cut) : html).matchAll(/<p[^>]*>([\s\S]*?)<\/p>/gi)]
    .map((m) => plain(m[1]).replace(/\s+/g, " ").trim()).filter((t) => t.length > 80 && !/cookie|advertisement|subscribe|share this/i.test(t));
  const bm = /bg-showmore-hidden-[^'"]*['"][^>]*>([\s\S]*?)<\/div>/i.exec(html);
  const ans = bm ? [...plain(bm[1]).replace(/\s+/g, " ").matchAll(/(?:^|\s)(\d{1,2})\s*\.\s/g)].map((m) => Number(m[1])) : [];
  console.log(`  ${s} id=${p.id} title=${JSON.stringify(p.title.rendered)} paras=${paras.length} ansTokens=${ans.length}`);
  console.log(`      passage[0] = ${JSON.stringify((paras[0] || "").slice(0, 150))}`);
  console.log(`      passage[1] = ${JSON.stringify((paras[1] || "").slice(0, 100))}`);
}

/* B. 全部 21 本 hub：适配器正则命中数 vs 页面真实 href 数 */
const HUB = { 1: 9322, 2: 9330, 3: 9341, 4: 9349, 5: 9357, 6: 9365, 7: 9374, 8: 9382, 9: 9390, 10: 9404, 11: 9452, 12: 9463, 13: 7025, 14: 7051, 15: 9314, 16: 9291, 17: 9277, 18: 9263, 19: 9255, 20: 12381, 21: 12724 };
console.log("\n=== 各 hub：适配器链接正则命中 vs 真实 href（reading/listening） ===");
for (const [b, id] of Object.entries(HUB)) {
  const p = await j(`${API}/${id}?_fields=id,content`);
  if (!p.content) { console.log(`  book ${b} id=${id}: 无 content（${JSON.stringify(p).slice(0, 80)}）`); continue; }
  const c = p.content.rendered;
  const matched = [...c.matchAll(/href=["']([^"']+)["'][^>]*>([\s\S]{0,80}?)<\/a>/gi)].map((m) => m[1]);
  const all = [...new Set([...c.matchAll(/href=["']([^"']+)["']/gi)].map((m) => m[1]))];
  const realR = all.filter((u) => /reading/i.test(u));
  const realL = all.filter((u) => /listening/i.test(u));
  const hitR = matched.filter((u) => /reading/i.test(u));
  const hitL = matched.filter((u) => /listening/i.test(u));
  const flag = (hitR.length !== realR.length || hitL.length !== realL.length) ? "  <== 漏" : "";
  console.log(`  book ${b}: 正则命中 R=${hitR.length}/真实${realR.length}  L=${hitL.length}/真实${realL.length}${flag}`);
  if (flag) {
    console.log(`     真实 R=${JSON.stringify(realR)}`);
    console.log(`     命中 R=${JSON.stringify(hitR)}`);
    console.log(`     真实 L=${JSON.stringify(realL)}`);
    console.log(`     命中 L=${JSON.stringify(hitL)}`);
  }
}
