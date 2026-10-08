// 交叉核验 v2：看原始 HTML 与 hub 页真实响应
const API = "https://practicepteonline.com/wp-json/wp/v2/pages";
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36";
const raw = async (u) => {
  const r = await fetch(u, { headers: { "user-agent": UA, accept: "application/json" }, signal: AbortSignal.timeout(30000) });
  return { status: r.status, text: await r.text() };
};
const bySlug = (s) => raw(`${API}?slug=${encodeURIComponent(s)}&_fields=id,slug,title,content`);
const block = (html) => { const m = /bg-showmore-hidden-[^'"]*['"][^>]*>([\s\S]*?)<\/div>/i.exec(html); return m ? m[1] : null; };
const plain = (h) => h.replace(/<br\s*\/?>/gi, "\n").replace(/<\/(p|div|li|tr|h[1-6]|td)>/gi, "\n").replace(/<[^>]+>/g, " ").replace(/&nbsp;/g, " ").replace(/[ \t]+/g, " ").replace(/\n{2,}/g, "\n").trim();

/* 1. hub 21 数字 ID 是否有效 */
for (const u of [`${API}/12724?_fields=id,slug,title`, `${API}?slug=official-ielts-tests-book-21&_fields=id,slug,title,content`]) {
  const r = await raw(u);
  console.log(`\n=== GET ${u.replace(API, "/pages")} ===\n  status=${r.status} body[0..400]=${JSON.stringify(r.text.slice(0, 400))}`);
}

/* 2. hub 21 页面里的链接（判断是否真的缺 Academic Reading） */
const h21 = JSON.parse((await bySlug("official-ielts-tests-book-21")).text);
if (h21[0]) {
  const links = [...h21[0].content.rendered.matchAll(/href=["']([^"']+)["'][^>]*>([\s\S]{0,80}?)<\/a>/gi)]
    .map((m) => [m[1], m[2].replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim()]);
  console.log(`\n=== hub21 by slug: id=${h21[0].id} title=${JSON.stringify(h21[0].title.rendered)} links=${links.length} ===`);
  console.log("  reading:", JSON.stringify(links.filter(([u, l]) => /reading/i.test(u + l))));
  console.log("  listening:", JSON.stringify(links.filter(([u, l]) => /listening/i.test(u + l))));
} else console.log("\nhub21 by slug: EMPTY", JSON.stringify(h21).slice(0, 300));

/* 3. reading-test-36 答案块原始 HTML */
const r36 = JSON.parse((await bySlug("ielts-reading-test-36")).text)[0];
const b36 = block(r36.content.rendered);
console.log(`\n=== reading-test-36 (id=${r36.id}) answer block raw (${b36.length} chars) ===`);
console.log(JSON.stringify(b36.slice(0, 700)));
const p36 = plain(b36).replace(/\s+/g, " ");
console.log("  plain (first 500):", JSON.stringify(p36.slice(0, 500)));
const pairs36 = [...p36.matchAll(/(?:^|\s)(\d{1,2})\s*[.]\s*(.*?)(?=\s+\d{1,2}\s*[.]\s|$)/g)].map((m) => [m[1], m[2]]);
console.log(`  独立正则(贪婪)解析出 ${pairs36.length} 对; 34/35/36 =`, JSON.stringify(pairs36.filter(([n]) => ["34", "35", "36"].includes(n))));

/* 4. listening 172 / 59 答案块：数一数站点自己的编号条目 */
for (const slug of ["ielts-listening-test-172", "ielts-listening-test-59", "ielts-listening-test-171"]) {
  const p = JSON.parse((await bySlug(slug)).text)[0];
  const b = block(p.content.rendered);
  const t = plain(b).replace(/\s+/g, " ");
  const nums = [...t.matchAll(/(?:^|\s)(\d{1,2})\s*[.]\s/g)].map((m) => Number(m[1]));
  const uniq = [...new Set(nums)].sort((a, b) => a - b);
  console.log(`\n=== ${slug} (id=${p.id}) ===\n  block=${b.length} chars, 出现的题号数=${uniq.length}, 最大=${Math.max(...uniq)}, 缺号=${JSON.stringify(Array.from({ length: Math.max(...uniq) }, (_, i) => i + 1).filter((n) => !uniq.includes(n)))}`);
  console.log(`  plain head: ${JSON.stringify(t.slice(0, 220))}`);
  console.log(`  plain tail: ${JSON.stringify(t.slice(-160))}`);
}

/* 5. 音频真实性 */
for (const mp3 of ["https://practicepteonline.com/wp-content/uploads/audio/172_we.mp3", "https://practicepteonline.com/wp-content/uploads/audio//59_deep.mp3"]) {
  const hr = await fetch(mp3, { method: "HEAD", headers: { "user-agent": UA }, signal: AbortSignal.timeout(30000) });
  console.log(`\naudio HEAD ${mp3}\n  status=${hr.status} type=${hr.headers.get("content-type")} len=${hr.headers.get("content-length")}`);
}
