// 独立交叉核验：直接打 WP REST API，绕开被测适配器的解析逻辑
const API = "https://practicepteonline.com/wp-json/wp/v2/pages";
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36";
const get = async (u) => (await fetch(u, { headers: { "user-agent": UA, accept: "application/json" }, signal: AbortSignal.timeout(30000) })).json();
const bySlug = (s) => get(`${API}?slug=${encodeURIComponent(s)}&_fields=id,slug,title,content`);
const byId = (i) => get(`${API}/${i}?_fields=id,slug,title,content`);

const block = (html) => {
  const m = /bg-showmore-hidden-[^'"]*['"][^>]*>([\s\S]*?)<\/div>/i.exec(html);
  return m ? m[1] : null;
};
const liOf = (html) => {
  const b = block(html);
  if (!b) return null;
  return [...b.matchAll(/<li[^>]*>([\s\S]*?)<\/li>/gi)].map((x) => x[1].replace(/<[^>]+>/g, " ").replace(/&nbsp;/g, " ").replace(/\s+/g, " ").trim()).filter(Boolean);
};

for (const slug of ["ielts-reading-test-36", "ielts-listening-test-172", "ielts-listening-test-59"]) {
  const arr = await bySlug(slug);
  const p = arr[0];
  const lis = liOf(p.content.rendered);
  console.log(`\n=== ${slug} (id=${p.id}, title=${JSON.stringify(p.title.rendered)}) ===`);
  console.log(`  raw <li> count = ${lis.length}`);
  console.log(`  first3 = ${JSON.stringify(lis.slice(0, 3))}`);
  console.log(`  last3  = ${JSON.stringify(lis.slice(-3))}`);
  console.log(`  block html has <ol>? ${/<ol/i.test(block(p.content.rendered))}  <li>? ${/<li/i.test(block(p.content.rendered))}`);
  if (slug === "ielts-reading-test-36") {
    const txt = block(p.content.rendered).replace(/<[^>]+>/g, "|").replace(/\|+/g, "|");
    const i = txt.indexOf("35");
    console.log(`  RAW around "35": ${JSON.stringify(txt.slice(Math.max(0, i - 160), i + 120))}`);
    console.log(`  full <li> list = ${JSON.stringify(lis)}`);
  }
}

// 剑21 hub：站点是否真的没有 Academic Reading 链接（适配器 FALLBACK 的前提）
const h21 = await byId(12724);
const c21 = h21[0].content.rendered;
const links21 = [...c21.matchAll(/href=["']([^"']+)["'][^>]*>([\s\S]{0,80}?)<\/a>/gi)].map((m) => [m[1], m[2].replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim()]);
console.log(`\n=== hub 21 (id=12724) title=${JSON.stringify(h21[0].title.rendered)} ===`);
console.log(`  total links=${links21.length}`);
console.log("  reading-ish links:", JSON.stringify(links21.filter(([u, l]) => /reading/i.test(u) || /reading/i.test(l))));
console.log("  listening-ish links:", JSON.stringify(links21.filter(([u, l]) => /listening/i.test(u) || /listening/i.test(l))));

// 剑3 hub：listening 是否真的只有 1 套
const h3 = await byId(9341);
const links3 = [...h3[0].content.rendered.matchAll(/href=["']([^"']+)["'][^>]*>([\s\S]{0,80}?)<\/a>/gi)].map((m) => [m[1], m[2].replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim()]);
console.log(`\n=== hub 3 (id=9341) title=${JSON.stringify(h3[0].title.rendered)} ===`);
console.log("  listening-ish links:", JSON.stringify(links3.filter(([u, l]) => /listening/i.test(u) || /listening/i.test(l))));

// 音频真实性：HEAD 一条 mp3
const mp3 = "https://practicepteonline.com/wp-content/uploads/audio/172_we.mp3";
const hr = await fetch(mp3, { method: "HEAD", headers: { "user-agent": UA }, signal: AbortSignal.timeout(30000) });
console.log(`\n=== audio HEAD ${mp3} ===`);
console.log(`  status=${hr.status} content-type=${hr.headers.get("content-type")} content-length=${hr.headers.get("content-length")}`);
