import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectBlocks, normalizeWs, ownText, collectQuestionGroups, __internals } from "../../../../ielts-api/html-questions.mjs";
const { parseHeadingText, isQuestionLineLike } = __internals;

const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const idxs = process.argv.slice(2).map(Number);
const RAW_IDX = JSON.parse(fs.readFileSync("../evidence/S04-raw-index.json", "utf8"));
const byRaw = new Map();
for (const e of RAW_IDX) if (e.raw_index) byRaw.set(e.raw_index, e);

const isHeadingElement = (n) => /^h[1-6]$/.test(n.tag);
const headingText = (el) => normalizeWs(ownText(el));
const isQuestionHeadingText = (t) => !!parseHeadingText(t.replace(/\n/g, " ")) || /^(?:part|section)\s+\d+/i.test(t);
const strongTitleText = (el) => {
  if (el.tag !== "p") return null;
  const kids = (el.children || []).filter((c) => c.type === "element");
  const texts = (el.children || []).filter((c) => c.type === "text" && c.text.trim());
  if (texts.length || kids.length !== 1) return null;
  const k = kids[0];
  if (k.tag !== "strong" && k.tag !== "b") return null;
  const t = normalizeWs(ownText(k));
  return t || null;
};
const isTitleLike = (t) => {
  if (t.length < 3 || t.length > 120) return false;
  if (isQuestionLineLike(t)) return false;
  if (isQuestionHeadingText(t)) return false;
  if (/^(?:list of|type of|notes?|table|diagram|summary|example)s?\b/i.test(t)) return false;
  if (/cambridge ielts|ielts test|practice pte/i.test(t)) return false;
  return true;
};

for (const idx of idxs) {
  const raw = JSON.parse(fs.readFileSync(path.join(RAW_DIR, `raw-${idx}.txt`), "utf8"));
  const html = raw[0].content.rendered;
  const root = parseHtml(html);
  const blocks = collectBlocks(root);
  const groups = collectQuestionGroups(root, { maxNumber: 45, stopAtHeadings: true });
  const spans = groups.groups.map((g) => g.block_span).filter((s) => Array.isArray(s));
  const inSpan = (i) => spans.some(([a, b]) => i >= a && i < b);
  const e = byRaw.get(idx);
  console.log(`\n===== raw-${idx} (${e ? e.book + "-" + e.test : "?"}) blocks=${blocks.length} =====`);
  for (let i = 0; i < blocks.length; i++) {
    const el = blocks[i];
    let t = null;
    if (isHeadingElement(el)) t = headingText(el);
    else t = strongTitleText(el);
    if (!t || !isTitleLike(t)) continue;
    const next = blocks[i + 1];
    const nt = next ? normalizeWs(ownText(next)).replace(/\n/g, " ").slice(0, 70) : "(none)";
    console.log(`  ${String(i).padStart(3)} span=${inSpan(i) ? "Y" : "n"} tag=${el.tag.padEnd(7)} "${t.slice(0, 60)}"\n      next: ${nt}`);
  }
}
