import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectBlocks, normalizeWs, ownText, collectQuestionGroups, __internals } from "../../../../ielts-api/html-questions.mjs";
const { parseHeadingText, isQuestionLineLike } = __internals;

const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const RAW_IDX = JSON.parse(fs.readFileSync("../evidence/S04-raw-index.json", "utf8"));

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

const dist = {};
const lines = [];
for (const e of RAW_IDX) {
  if (e.skill !== "reading" || !e.raw_index) continue;
  const raw = JSON.parse(fs.readFileSync(path.join(RAW_DIR, `raw-${e.raw_index}.txt`), "utf8"));
  const html = raw[0].content.rendered;
  const root = parseHtml(html);
  const blocks = collectBlocks(root);
  const groups = collectQuestionGroups(root, { maxNumber: 45, stopAtHeadings: true });
  const spans = groups.groups.map((g) => g.block_span).filter((s) => Array.isArray(s));
  const inSpan = (i) => spans.some(([a, b]) => i >= a && i < b);
  const cands = [];
  for (let i = 0; i < blocks.length; i++) {
    const el = blocks[i];
    let t = null;
    if (isHeadingElement(el)) t = headingText(el);
    else t = strongTitleText(el);
    if (!t || !isTitleLike(t)) continue;
    cands.push({ i, t, inSpan: inSpan(i) });
  }
  const n = cands.length;
  dist[n] = (dist[n] || 0) + 1;
  const key = `${e.book}-${e.test}`;
  if (n !== 3) {
    lines.push(`## ${key} raw=${e.raw_index} n=${n}`);
    for (const c of cands) lines.push(`   ${String(c.i).padStart(3)} span=${c.inSpan ? "Y" : "n"} ${JSON.stringify(c.t.slice(0, 90))}`);
  }
}
lines.unshift(`distribution: ${JSON.stringify(dist)}`);
fs.writeFileSync("cand-scan-out.txt", lines.join("\n") + "\n");
console.log(lines.slice(0, 400).join("\n"));
