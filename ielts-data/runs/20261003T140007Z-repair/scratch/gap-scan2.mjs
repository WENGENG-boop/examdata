import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectBlocks, collectQuestionGroups, nodeText, ownText, normalizeWs } from "../../../../ielts-api/html-questions.mjs";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const index = JSON.parse(fs.readFileSync("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json", "utf8"));

let trunc = 0, proseOpts = 0, noSpaceDot = 0, proseSlots = 0;
const lines = [];
for (const e of index) {
  if (e.raw_index == null) continue;
  const raw = fs.readFileSync(path.join(RAW_DIR, `raw-${e.raw_index}.txt`), "utf8");
  let html;
  try { html = JSON.parse(raw)[0].content.rendered; } catch { continue; }
  const root = parseHtml(html);
  const maxN = 45;
  const isListening = e.skill !== "reading";
  const g = collectQuestionGroups(root, { maxNumber: maxN, stopAtHeadings: !isListening });
  const blocks = collectBlocks(root);
  // (1) truncation: blocks after group end before next group start containing in-range markers
  for (let gi = 0; gi < g.groups.length; gi++) {
    const gr = g.groups[gi];
    const derived = gr.slots.filter((s) => s.kind === "derived").map((s) => s.number);
    if (!derived.length) continue;
    const nextStart = gi + 1 < g.groups.length ? g.groups[gi + 1].block_span[0] : blocks.length;
    const from = gr.block_span[1];
    const inRange = new Set(gr.numbers);
    const hits = [];
    for (let k = from; k < nextStart; k++) {
      const t = nodeText(blocks[k], { block: true });
      const re = /\((\d{1,3})\)/g; let m;
      while ((m = re.exec(t))) { const n = Number(m[1]); if (inRange.has(n) && derived.includes(n)) hits.push(`${n}@b${k}`); }
    }
    if (hits.length) { trunc++; lines.push(`TRUNC raw-${e.raw_index} G${gr.index} [${gr.range}] derived=[${derived}] afterSpan=[${hits.join(",")}]`); }
  }
  // (2) prose-like options
  for (const gr of g.groups) {
    const allOpts = [...gr.pools.flatMap((p) => p.options), ...gr.slots.flatMap((s) => s.options)];
    for (const o of allOpts) {
      const t = o.text || "";
      if (t.length > 110 || /…{3,}/.test(t) || /\(\d{1,3}\)/.test(t)) {
        proseOpts++;
        if (proseOpts <= 40) lines.push(`PROSEOPT raw-${e.raw_index} G${gr.index} label=${o.label} len=${t.length} :: ${t.slice(0, 90)}`);
      }
    }
  }
  // (3) no-space dot lines in shared_prompt
  for (const gr of g.groups) {
    for (const ln of String(gr.shared_prompt || "").split("\n")) {
      if (/^\d{1,3}\.[A-Za-z(“"']/.test(ln.trim())) {
        noSpaceDot++;
        if (noSpaceDot <= 60) lines.push(`NOSPACE raw-${e.raw_index} G${gr.index} :: ${ln.trim().slice(0, 90)}`);
      }
    }
    // (3b) slots with prompt matching no-space dot
    for (const s of gr.slots) {
      if (/^\d{1,3}\.[A-Za-z(“"']/.test(String(s.prompt || "").trim())) proseSlots++;
    }
  }
}
console.log(lines.join("\n"));
console.log(`\nsummary trunc=${trunc} proseOpts=${proseOpts} noSpaceDot=${noSpaceDot} proseSlots=${proseSlots}`);
