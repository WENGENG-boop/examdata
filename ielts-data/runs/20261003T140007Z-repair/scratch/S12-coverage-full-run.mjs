// tmp: S12 全量 coverage 跑批 — 21 册 → JSON + Markdown
import fs from "node:fs";
import path from "node:path";
import { buildCoverage } from "./coverage.mjs";

const evidenceDir = "C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence";
fs.mkdirSync(evidenceDir, { recursive: true });

const t0 = Date.now();
const cov = buildCoverage();
const elapsed = Date.now() - t0;

const jsonPath = path.join(evidenceDir, "S12-coverage-full.json");
fs.writeFileSync(jsonPath, JSON.stringify(cov, null, 1));

const s = cov.summary;
let md = `# S12 全量 coverage 汇总\n\n`;
md += `- schema: \`${cov.schema}\` version: \`${cov.version}\` resolver: \`${cov.resolver}\`\n`;
md += `- run_id: ${cov.run_id}\n- data_dir: ${cov.data_dir}\n- generated_at_utc: ${cov.generated_at_utc}\n- elapsed: ${elapsed} ms\n`;
md += `- warnings: ${JSON.stringify(cov.warnings)}\n\n`;
md += `## 单元状态\n\n| status | count |\n|---|---|\n`;
for (const [k, v] of Object.entries(s.unit_status)) md += `| ${k} | ${v} |\n`;
md += `\n- units: ${s.units}\n- fully_complete_units: ${s.fully_complete_units}\n- units_with_audio_verified: ${s.units_with_audio_verified}\n- units_with_alignment_complete: ${s.units_with_alignment_complete}\n- books_pdf_complete: ${s.books_pdf_complete.join(", ")}\n\n`;
md += `## by skill/variant\n\n| key | units | fully | audio_verified | alignment_complete |\n|---|---|---|---|---|\n`;
for (const [k, v] of Object.entries(s.by_skill))
  md += `| ${k} | ${v.units} | ${v.fully_complete} | ${v.audio_verified_units} | ${v.alignment_complete_units} |\n`;
md += `\n## by book\n\n| book | units | fully | pdf_complete |\n|---|---|---|---|\n`;
for (const b of s.by_book) md += `| ${b.book} | ${b.units} | ${b.fully_complete} | ${b.pdf_complete} |\n`;
const mdPath = path.join(evidenceDir, "S12-coverage-summary.md");
fs.writeFileSync(mdPath, md);

console.log("json:", jsonPath);
console.log("md:", mdPath);
console.log("elapsed", elapsed, "ms");
console.log("units", s.units, "status:", JSON.stringify(s.unit_status));
console.log("fully", s.fully_complete_units, "audio_verified_units", s.units_with_audio_verified, "align_complete", s.units_with_alignment_complete);
console.log("by_skill", JSON.stringify(s.by_skill));
console.log("pdf_complete_books", s.books_pdf_complete.join(","));

// 关键单元抽查
for (const [b, t] of [[3, "2"], [3, "3"], [3, "4"], [20, "1"], [12, "5"], [21, "1"]]) {
  const bk = cov.books.find((x) => x.book === b);
  if (!bk) continue;
  const us = bk.units.filter((u) => u.test === t);
  for (const u of us) {
    console.log(
      `check b${b} t${t} ${u.skill}/${u.variant}: status=${u.status} n=${u.numbers.observed.length}/${u.numbers.expected.length} reasons=${u.status_reasons.slice(0, 4).join(",")}`,
    );
  }
}
