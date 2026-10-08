import fs from "node:fs";
import path from "node:path";
import { parseHtml, collectBlocks, collectQuestionGroups, normalizeWs, ownText } from "../../../../ielts-api/html-questions.mjs";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const index = JSON.parse(fs.readFileSync("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S04-raw-index.json", "utf8"));
// scan: lines ending with bare in-range number (possible marker), grouped
const out = [];
for (const e of index) {
  if (e.raw_index == null) continue;
  const raw = fs.readFileSync(path.join(RAW_DIR, `raw-${e.raw_index}.txt`), "utf8");
  let html; try { html = JSON.parse(raw)[0].content.rendered; } catch { continue; }
  const root = parseHtml(html);
  const isListening = e.skill !== "reading";
  const { groups } = collectQuestionGroups(root, { maxNumber: 45, stopAtHeadings: !isListening });
  const blocks = collectBlocks(root);
  for (const g of groups) {
    const [k, endK] = g.block_span || [0, 0];
    const covered = new Set(g.slots.map((s) => s.number));
    for (let i = k + 1; i < Math.min(endK, blocks.length); i++) {
      const lines = normalizeWs(ownText(blocks[i])).split("\n");
      for (const line of lines) {
        const m = /(?:^|[\s(])(\d{1,3})[ \t]*$/.exec(line);
        if (!m) continue;
        const n = Number(m[1]);
        if (!g.numbers.includes(n)) continue;
        // skip if line itself looks like a question line (e.g. "23 xxx")
        const isQLine = /^\d{1,3}[ \t]*[.\uFF0E)\uFF09]?[ \t]*\S/.test(line) && !/^\d{1,3}[ \t]*$/.test(line) === false ? true : false;
        out.push(`raw-${e.raw_index} G${g.index} n=${n} covered=${covered.has(n) ? "Y" : "N"} line="${line.replace(/\s+/g, " ").slice(0, 120)}"`);
      }
    }
  }
}
const uniq = [...new Set(out)];
fs.writeFileSync("C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/scratch/bare-number-scan.txt", uniq.join("\n") + "\n");
console.log("total lines:", uniq.length);
console.log(uniq.slice(0, 120).join("\n"));
