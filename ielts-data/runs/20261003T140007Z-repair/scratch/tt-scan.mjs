import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectBlocks, normalizeWs, ownText, attr } from "../../../../ielts-api/html-questions.mjs";

const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const RAW_IDX = JSON.parse(fs.readFileSync("../evidence/S04-raw-index.json", "utf8"));
let n = 0;
for (const e of RAW_IDX) {
  if (!e.raw_index) continue;
  const raw = JSON.parse(fs.readFileSync(path.join(RAW_DIR, `raw-${e.raw_index}.txt`), "utf8"));
  const html = raw[0].content.rendered;
  const root = parseHtml(html);
  const blocks = collectBlocks(root);
  for (let i = 0; i < blocks.length; i++) {
    const el = blocks[i];
    const style = attr(el, "style") || "";
    if (!/text-transform\s*:\s*capitalize/i.test(style)) continue;
    n++;
    const t = normalizeWs(ownText(el)).replace(/\n/g, " ").slice(0, 90);
    console.log(`${e.book}-${e.test} ${e.skill} r${e.raw_index} b${i} tag=${el.tag} :: ${t}`);
  }
}
console.log("total text-transform:capitalize blocks:", n);
