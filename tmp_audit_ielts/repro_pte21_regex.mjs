// 最小复现：pte.mjs:221 的 hub 链接正则对剑21 hub 的行为
// 用法: node repro_pte21_regex.mjs
import fs from 'node:fs';

const page = JSON.parse(fs.readFileSync('hub12724.json', 'utf8'));
const c = page.content.rendered;

// 与 pte.mjs 完全相同的正则
const matches = [...c.matchAll(/href=["']([^"']+)["'][^>]*>([\s\S]{0,80}?)<\/a>/gi)];
console.log('匹配到的链接数:', matches.length);
for (const m of matches) {
  const url = m[1].replace(/^https?:\/\/practicepteonline\.com/, '').replace(/\/$/, '');
  if (/reading|listening/i.test(url)) {
    console.log('  captured:', url, ':: inner_len=', m[2].length);
  }
}

// 对比：放宽到 200 字符
const matches2 = [...c.matchAll(/href=["']([^"']+)["'][^>]*>([\s\S]{0,200}?)<\/a>/gi)];
let n = 0;
for (const m of matches2) {
  const url = m[1].replace(/^https?:\/\/practicepteonline\.com/, '').replace(/\/$/, '');
  if (/reading|listening/i.test(url)) {
    n++;
    if (n <= 16) console.log('  relaxed:', url, ':: inner_len=', m[2].length);
  }
}
console.log('放宽后匹配到 reading/listening 链接数:', n);
