import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectBlocks, nodeText, normalizeWs, ownText, collectQuestionGroups, __internals } from "../../../../ielts-api/html-questions.mjs";
const { parseHeadingText, isQuestionLineLike } = __internals;

const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const idx = Number(process.argv[2] || 147);
const raw = JSON.parse(fs.readFileSync(path.join(RAW_DIR, `raw-${idx}.txt`), "utf8"));
const html = raw[0].content.rendered;
const root = parseHtml(html);
const blocks = collectBlocks(root);
const groups = collectQuestionGroups(root, { maxNumber: 45, stopAtHeadings: true });
const spans = groups.groups.map((g) => g.block_span).filter((s) => Array.isArray(s) && s.length === 2);
const inQuestionSpan = (i) => spans.some(([a, b]) => i >= a && i < b);

console.log("groups:", groups.groups.map((g) => `G${g.index} span=${JSON.stringify(g.block_span)} nums=[${g.numbers[0]}-${g.numbers[g.numbers.length - 1]}]`).join("\n        "));

const needles = ["Gifted Children", "Museum of Fine Art", "Tea and the Industrial"];
for (let i = 0; i < blocks.length; i++) {
  const el = blocks[i];
  const t = normalizeWs(ownText(el)).slice(0, 90);
  if (!needles.some((n) => t.includes(n))) continue;
  const kids = (el.children || []).filter((c) => c.type === "element").map((c) => c.tag);
  const texts = (el.children || []).filter((c) => c.type === "text" && c.text.trim()).length;
  console.log(`\nblock ${i} tag=${el.tag} inSpan=${inQuestionSpan(i)} kids=${JSON.stringify(kids)} textKids=${texts}`);
  console.log("  ownText:", JSON.stringify(t));
  console.log("  html:", el.toString ? el.toString().slice(0, 300) : "(no toString)");
}
