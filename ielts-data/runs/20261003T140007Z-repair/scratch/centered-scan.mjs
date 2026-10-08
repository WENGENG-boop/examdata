import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectBlocks, normalizeWs, ownText, attr, collectQuestionGroups, __internals } from "../../../../ielts-api/html-questions.mjs";
const { parseHeadingText, isQuestionLineLike } = __internals;

const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const RAW_IDX = JSON.parse(fs.readFileSync("../evidence/S04-raw-index.json", "utf8"));

const isQuestionHeadingText = (t) => !!parseHeadingText(t.replace(/\n/g, " ")) || /^(?:part|section)\s+\d+/i.test(t);
const strongTitleText = (el) => {
  if (el.tag !== "p") return null;
  const kids = (el.children || []).filter((c) => c.type === "element");
  const texts = (el.children || []).filter((c) => c.type === "text" && c.text.trim());
  if (texts.length || kids.length !== 1) return null;
  let k = kids[0];
  let guard = 0;
  while (k.tag === "span" && guard++ < 3) {
    const kk = (k.children || []).filter((c) => c.type === "element");
    const kt = (k.children || []).filter((c) => c.type === "text" && c.text.trim());
    if (kt.length || kk.length !== 1) return null;
    k = kk[0];
  }
  if (k.tag !== "strong" && k.tag !== "b") return null;
  return normalizeWs(ownText(k)) || null;
};
const isTitleLike = (t) => {
  if (t.length < 3 || t.length > 120) return false;
  if (isQuestionLineLike(t)) return false;
  if (isQuestionHeadingText(t)) return false;
  if (/^(?:list of|type of|notes?|table|diagram|summary|example)s?\b/i.test(t)) return false;
  if (/cambridge ielts|ielts test|practice pte/i.test(t)) return false;
  return true;
};

let centeredPlain = 0;
for (const e of RAW_IDX) {
  if (e.skill !== "reading" || !e.raw_index) continue;
  const raw = JSON.parse(fs.readFileSync(path.join(RAW_DIR, `raw-${e.raw_index}.txt`), "utf8"));
  const html = raw[0].content.rendered;
  const root = parseHtml(html);
  const blocks = collectBlocks(root);
  for (let i = 0; i < blocks.length; i++) {
    const el = blocks[i];
    if (el.tag !== "p") continue;
    const style = attr(el, "style") || "";
    if (!/text-align\s*:\s*center/i.test(style)) continue;
    if (strongTitleText(el)) continue; // already case 2
    const t = normalizeWs(ownText(el)).replace(/\n/g, " ");
    if (!t || t.length < 3 || t.length > 120) continue;
    centeredPlain++;
    console.log(`${e.book}-${e.test} r${String(e.raw_index).padStart(3)} b${String(i).padStart(3)} titleLike=${isTitleLike(t) ? "Y" : "n"} style="${style.slice(0, 60)}" :: ${t.slice(0, 100)}`);
  }
}
console.log("total centered-plain blocks:", centeredPlain);
