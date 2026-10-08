// 抽样 12 页（阅读），检查答案块格式：空值 / 点后无空格 / token 数
import { bookTests } from 'file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/pte.mjs';
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36";
const API = "https://practicepteonline.com/wp-json/wp/v2/pages";
const books = [2, 5, 8, 10, 12, 15, 17, 19, 20, 21];
for (const b of books) {
  const bt = await bookTests(b);
  const slug = bt.reading?.[1];
  if (!slug) { console.log(`b${b}: no reading t1`); continue; }
  const r = await fetch(`${API}?slug=${slug}&_fields=content`, { headers: { "user-agent": UA } });
  const j = await r.json();
  const html = j?.[0]?.content?.rendered || "";
  const m = /bg-showmore-hidden-[^'"]*['"][^>]*>([\s\S]*?)<\/div>/i.exec(html);
  const block = m ? m[1] : "";
  const text = block.replace(/<br\s*\/?>/gi, "\n").replace(/<[^>]+>/g, " ").replace(/&nbsp;/g, " ").replace(/\s+/g, " ").trim();
  // 空值：<span...>N.</span> 形态
  const emptySpans = [...block.matchAll(/<span[^>]*>\s*(\d{1,2})\.\s*<\/span>/gi)].map(x => x[1]);
  // 点后直接跟字母数字（无空格）
  const dotNoSpace = [...text.matchAll(/(?:^|\s)(\d{1,2})\.[^\s\d]/g)].map(x => x[0].trim());
  // 宽松 token 数（允许任意后随）
  const loose = [...text.matchAll(/(?:^|\s)(\d{1,2})\s*\.\s*/g)].length;
  // 严格 token 数（点后必须空白或结尾）
  const strict = [...text.matchAll(/(?:^|\s)(\d{1,2})\s*\.(?=\s|$)/g)].length;
  console.log(`b${b} ${slug}: loose=${loose} strict=${strict} emptySpans=[${emptySpans.join(",")}] dotNoSpace=[${dotNoSpace.slice(0,5).join(" | ")}]`);
  await new Promise(s => setTimeout(s, 400));
}
