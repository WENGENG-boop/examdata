import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectBlocks, collectQuestionGroups, normalizeWs, ownText, nodeText } from "../../../../ielts-api/html-questions.mjs";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const index = JSON.parse(fs.readFileSync("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json", "utf8"));
const byRaw = new Map();
for (const e of index) if (e.raw_index != null) byRaw.set(e.raw_index, e);
const pairs = process.argv.slice(2).map((s) => { const [r, g] = s.split(":"); return { raw: Number(r), gi: Number(g) }; });
for (const p of pairs) {
  const e = byRaw.get(p.raw);
  const raw = fs.readFileSync(path.join(RAW_DIR, `raw-${p.raw}.txt`), "utf8");
  const root = parseHtml(JSON.parse(raw)[0].content.rendered);
  const isListening = e.skill !== "reading";
  const blocks = collectBlocks(root);
  const { groups } = collectQuestionGroups(root, { maxNumber: 45, stopAtHeadings: !isListening });
  const g = groups.find((x) => x.index === p.gi);
  if (!g) { console.log(`raw-${p.raw} G${p.gi}: MISSING`); continue; }
  const [k, endK] = g.block_span;
  console.log(`\n### raw-${p.raw} (${e.book}-${e.test}-${e.skill}) G${g.index} span=[${k},${endK})`);
  for (let i = k; i < Math.min(endK, blocks.length); i++) {
    const el = blocks[i];
    const t = normalizeWs(ownText(el)).replace(/\n/g, "\\n");
    const kids = (el.children || []).filter((c) => c.type === "element");
    const strongOnly = el.tag === "p" && kids.length === 1 && (kids[0].tag === "strong" || kids[0].tag === "b") && !(el.children || []).some((c) => c.type === "text" && c.text.trim());
    console.log(`  ${String(i).padStart(3)} ${el.tag.padEnd(6)} len=${String(t.length).padStart(5)} strongOnly=${strongOnly ? "Y" : "-"} :: ${t.slice(0, 110)}`);
  }
}
