// 批量：下载抽样页并检查缺失题号的原始出现方式
import { writeFileSync, readFileSync, existsSync } from "node:fs";
import { bookTests } from 'file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/pte.mjs';
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36";
const API = "https://practicepteonline.com/wp-json/wp/v2/pages";
const sleep = (ms) => new Promise(s => setTimeout(s, ms));

// [book, kind, missing]
const targets = [
  [8, "reading", [9,10,11,12,13]],
  [8, "listening", [16,17,18,19,20,25,26,27]],
  [15, "reading", [23,24,25,26]],
  [15, "listening", [29,30]],
  [17, "reading", [5,23,24,25,26]],
  [17, "listening", [15,16,17,18,19,20]],
  [19, "reading", [20,21,22,23]],
  [19, "listening", [21,22,23,24,38]],
  [21, "listening", [21,22,23,24]],
  [2, "listening", [6,7,8,16,17,18,19,20]],
  [5, "listening", [5,6,24,25]],
  [12, "listening", [15,16]],
  [20, "listening", [19,20,21,22,23,24,25,26]],
];

for (const [b, kind, miss] of targets) {
  const bt = await bookTests(b);
  const slug = bt[kind]?.[1];
  if (!slug) { console.log(`b${b} ${kind}: no slug`); continue; }
  const f = `pg_${b}_${kind}.json`;
  if (!existsSync(f)) {
    const r = await fetch(`${API}?slug=${slug}&_fields=content`, { headers: { "user-agent": UA } });
    const j = await r.json();
    writeFileSync(f, JSON.stringify(j));
    await sleep(400);
  }
  const html = JSON.parse(readFileSync(f, "utf8"))[0].content.rendered;
  console.log(`\n##### b${b} ${kind} (${slug})`);
  for (const n of miss) {
    // 找 ">n" 或 "\nn" 后面跟空白/点/省略号 的所有出现
    const re = new RegExp("(?:>|\\n)" + n + "(?=[\\s.．…）)])", "g");
    let m, hits = [];
    while ((m = re.exec(html)) && hits.length < 2) {
      hits.push(html.slice(m.index, m.index + 100).replace(/<[^>]+>/g, "|").replace(/\s+/g, " "));
    }
    if (hits.length) hits.forEach(h => console.log(`  ${n}: ${h}`));
    else console.log(`  ${n}: (no occurrence)`);
  }
}
