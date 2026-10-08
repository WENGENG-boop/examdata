// 交叉核验 v3：适配器自带的正则 vs 原始 HTML
const API = "https://practicepteonline.com/wp-json/wp/v2/pages";
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36";
const j = async (u) => (await fetch(u, { headers: { "user-agent": UA, accept: "application/json" }, signal: AbortSignal.timeout(30000) })).json();

/* --- A. reading-test-36 原始 HTML 中 34/35 的精确形态 --- */
const r36 = (await j(`${API}?slug=ielts-reading-test-36&_fields=id,content`))[0];
const m = /bg-showmore-hidden-[^'"]*['"][^>]*>([\s\S]*?)<\/div>/i.exec(r36.content.rendered);
const rawBlock = m[1];
const i = rawBlock.indexOf("33. A");
console.log("=== reading-test-36 RAW HTML slice [33. A .. 37] ===");
console.log(JSON.stringify(rawBlock.slice(i, i + 420)));
const cnt34 = (rawBlock.match(/34\./g) || []).length;
console.log(`  raw block 中 "34." 出现 ${cnt34} 次;  "35." 出现 ${(rawBlock.match(/35\./g) || []).length} 次`);

/* --- B. 适配器自带的 hub 链接正则，跑在 hub 3 / 20 / 21 上 --- */
const HUB = { 3: 9341, 20: 12381, 21: 12724 };
for (const [book, id] of Object.entries(HUB)) {
  const p = await j(`${API}/${id}?_fields=id,slug,title,content`);
  const c = p.content.rendered;
  const rows = [];
  for (const mm of c.matchAll(/href=["']([^"']+)["'][^>]*>([\s\S]{0,80}?)<\/a>/gi)) rows.push([mm[1], mm[2]]);
  const readingish = rows.filter(([u, l]) => /reading/i.test(u + l));
  const listeningish = rows.filter(([u, l]) => /listening/i.test(u + l));
  console.log(`\n=== hub ${book} (id=${id}, ${p.title.rendered}) 用适配器正则 ===`);
  console.log(`  总匹配 ${rows.length}; reading 相关 ${readingish.length}; listening 相关 ${listeningish.length}`);
  console.log(`  reading 命中: ${JSON.stringify(readingish.map(([u]) => u))}`);
  console.log(`  listening 命中: ${JSON.stringify(listeningish.map(([u]) => u))}`);
  const allHrefs = [...c.matchAll(/href=["']([^"']+)["']/gi)].map((x) => x[1]);
  console.log(`  页面真实 href 总数 ${allHrefs.length}; 其中 reading=${allHrefs.filter((u) => /reading/i.test(u)).length} listening=${allHrefs.filter((u) => /listening/i.test(u)).length}`);
  console.log(`  真实 reading hrefs: ${JSON.stringify(allHrefs.filter((u) => /reading/i.test(u)))}`);
  console.log(`  真实 listening hrefs: ${JSON.stringify(allHrefs.filter((u) => /listening/i.test(u)))}`);
}
