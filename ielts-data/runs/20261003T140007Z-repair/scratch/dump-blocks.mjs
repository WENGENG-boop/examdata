import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectBlocks, normalizeWs, ownText, collectQuestionGroups } from "../../../../ielts-api/html-questions.mjs";

const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const idx = Number(process.argv[2] || 147);
const from = Number(process.argv[3] || 0);
const to = Number(process.argv[4] || 70);
const raw = JSON.parse(fs.readFileSync(path.join(RAW_DIR, `raw-${idx}.txt`), "utf8"));
const html = raw[0].content.rendered;
const root = parseHtml(html);
const blocks = collectBlocks(root);
const groups = collectQuestionGroups(root, { maxNumber: 45, stopAtHeadings: true });
const spans = groups.groups.map((g) => [g.index, g.block_span]).filter(([, s]) => Array.isArray(s));
const inSpanOf = (i) => spans.filter(([, [a, b]]) => i >= a && i < b).map(([gi]) => gi);

for (let i = from; i < Math.min(to, blocks.length); i++) {
  const el = blocks[i];
  const t = normalizeWs(ownText(el)).replace(/\n/g, " ").slice(0, 110);
  const kids = (el.children || []).filter((c) => c.type === "element").map((c) => c.tag).join(",");
  console.log(`${String(i).padStart(3)} ${el.tag.padEnd(7)} kids=[${kids.slice(0, 30)}] span=${JSON.stringify(inSpanOf(i))} :: ${t}`);
}
console.log(`total blocks: ${blocks.length}`);
