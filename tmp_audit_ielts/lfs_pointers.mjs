// 独立审查：抓取全部 20 本 PDF 的 Git LFS 指针（raw 通道），提取 oid/size
// 同时打印被测代码 lfs.mjs 生成的 media URL，供后续下载使用
import fs from "node:fs";

const MOD = "file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/lfs.mjs";
const mod = await import(MOD);

const OUT = "C:/Users/weo/Desktop/api/tmp_audit_ielts/lfs_pointers.json";
const enc = (p) => p.split("/").map(encodeURIComponent).join("/");
const RAW = "https://raw.githubusercontent.com/BaBaLiBoo/IELTS-Resources/main/";

const results = [];
for (const [b, path] of Object.entries(mod.BOOK_PDF)) {
  const rawUrl = RAW + enc(path);
  const mediaUrl = mod.url(path); // 被测代码的 URL 构造
  const info = { book: Number(b), path, rawUrl, mediaUrlFromCode: mediaUrl };
  try {
    const r = await fetch(rawUrl, { headers: { "user-agent": "Mozilla/5.0" }, redirect: "follow", signal: AbortSignal.timeout(30000) });
    const buf = Buffer.from(await r.arrayBuffer());
    const text = buf.toString("utf8");
    const oid = (text.match(/oid sha256:([0-9a-f]{64})/) || [])[1] || null;
    const size = Number((text.match(/size (\d+)/) || [])[1] || 0);
    Object.assign(info, {
      status: r.status, ptrBytes: buf.length, oid, size,
      firstLine: text.split("\n")[0],
    });
  } catch (e) { info.error = String((e && e.message) || e); }
  results.push(info);
  console.log(JSON.stringify(info));
}
fs.writeFileSync(OUT, JSON.stringify(results, null, 2));
const total = results.reduce((s, x) => s + (x.size || 0), 0);
console.log("TOTAL_LFS_BYTES", total, "=", (total / 1048576).toFixed(1), "MB");
console.log("OK_COUNT", results.filter(x => x.oid).length, "/", results.length);
