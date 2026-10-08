import fs from "node:fs";
import path from "node:path";
import { parsePtePage, expectedFor } from "../../../../ielts-api/pte.mjs";

const ROOT = "C:/Users/weo/Desktop/api";
const RUN = path.join(ROOT, "ielts-data/runs/20261003T140007Z-repair");
const RAW_DIR = path.join(ROOT, "tmp_audit_ielts/completeness_20261003");
const index = JSON.parse(fs.readFileSync(path.join(RUN, "evidence/S04-raw-index.json"), "utf8"));

const dist = {};
const rows = [];
for (const entry of index) {
  if (entry.skill !== "reading" || !entry.raw_index) continue;
  const raw = fs.readFileSync(path.join(RAW_DIR, `raw-${entry.raw_index}.txt`), "utf8");
  const expected = (() => { try { return expectedFor(entry.book, entry.test, "academic_reading"); } catch { return null; } })();
  let r;
  try {
    r = parsePtePage(raw, { book: entry.book, test: entry.test, skill: "academic_reading", slug: entry.slug, page_id: entry.page_id }, expected);
  } catch (e) {
    rows.push({ key: `${entry.book}-${entry.test}`, err: e.message });
    continue;
  }
  if (!r || !r.ok) { rows.push({ key: `${entry.book}-${entry.test}`, err: "not ok" }); continue; }
  const n = r.counts.passages;
  dist[n] = (dist[n] || 0) + 1;
  rows.push({
    key: `${entry.book}-${entry.test}`,
    raw: entry.raw_index,
    n,
    exp: expected && expected.parts ? expected.parts.length : null,
    titles: r.passages.map((p) => (p.title || "?") + (p.range ? ` [${p.range}]` : "")).join(" || "),
  });
}
rows.sort((a, b) => String(a.key).localeCompare(String(b.key), undefined, { numeric: true }));
for (const r of rows) console.log(`${String(r.key).padEnd(6)} raw=${String(r.raw).padEnd(4)} n=${r.n}${r.exp ? "/" + r.exp : ""} ${r.err || ""}\n      ${(r.titles || "").slice(0, 260)}`);
console.log("distribution:", JSON.stringify(dist));
