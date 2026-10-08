import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectBlocks, normalizeWs, ownText } from "../../../../ielts-api/html-questions.mjs";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const [rawIdx, ...idxs] = process.argv.slice(2).map(Number);
const raw = fs.readFileSync(path.join(RAW_DIR, `raw-${rawIdx}.txt`), "utf8");
const root = parseHtml(JSON.parse(raw)[0].content.rendered);
const blocks = collectBlocks(root);
for (const i of idxs) {
  const el = blocks[i];
  if (!el) { console.log(`[${i}] <missing>`); continue; }
  console.log(`\n[${i}] <${el.tag}> FULL TEXT:`);
  console.log(normalizeWs(ownText(el)));
}
