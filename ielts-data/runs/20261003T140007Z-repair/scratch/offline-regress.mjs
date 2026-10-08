import fs from "node:fs";
import path from "node:path";
import { parsePtePage, expectedFor, PARSER_VERSION } from "../../../../ielts-api/pte.mjs";

const ROOT = "C:/Users/weo/Desktop/api";
const RUN = path.join(ROOT, "ielts-data/runs/20261003T140007Z-repair");
const RAW_DIR = path.join(ROOT, "tmp_audit_ielts/completeness_20261003");
const index = JSON.parse(fs.readFileSync(path.join(RUN, "evidence/S04-raw-index.json"), "utf8"));

const results = [];
const errors = [];
let okCount = 0;
let partialCount = 0;
const totals = { questions: 0, answers: 0, q_missing: 0, a_missing: 0, empty_slots: 0 };
const byKey = {};

for (const entry of index) {
  const key = `${entry.book}-${entry.test}-${entry.skill}`;
  if (entry.raw_index == null) {
    results.push({ ...entry, parse: null, reason: "no_raw" });
    continue;
  }
  const rawPath = path.join(RAW_DIR, `raw-${entry.raw_index}.txt`);
  let raw;
  try {
    raw = fs.readFileSync(rawPath, "utf8");
  } catch (e) {
    errors.push({ key, raw_index: entry.raw_index, error: `read: ${e.message}` });
    results.push({ ...entry, parse: null, reason: "read_error" });
    continue;
  }
  const skill = entry.skill === "reading" ? "academic_reading" : "listening";
  let expected = null;
  try {
    expected = expectedFor(entry.book, entry.test, skill);
  } catch (e) {
    errors.push({ key, error: `expectedFor: ${e.message}` });
  }
  let r = null;
  try {
    r = parsePtePage(raw, { book: entry.book, test: entry.test, skill, slug: entry.slug, page_id: entry.page_id }, expected);
  } catch (e) {
    errors.push({ key, raw_index: entry.raw_index, error: `parse: ${e.message}`, stack: e.stack && e.stack.split("\n").slice(0, 4).join(" | ") });
    results.push({ ...entry, parse: null, reason: "parse_error" });
    continue;
  }
  const summary = {
    key,
    book: entry.book,
    test: entry.test,
    skill,
    raw_index: entry.raw_index,
    slug: entry.slug,
    ok: r.ok,
    parse_status: r.parse_status,
    questions: r.question_count,
    answers: r.answer_count,
    expected_total: r.expected_total,
    expected_status: expected && expected.status,
    expected_source: r.expected_source,
    questions_missing: r.questions_missing,
    answer_missing: r.answer_missing,
    empty_slots: r.counts.empty_slots,
    warnings: r.warnings.map((w) => (typeof w === "string" ? w : w.kind)),
    warning_detail: r.warnings,
    passages: r.counts.passages,
    groups: r.counts.question_groups,
    audio_count: r.audio.length,
    assets: r.assets.length,
  };
  results.push(summary);
  if (r.ok) okCount++; else errors.push({ key, error: "parse not ok" });
  if (r.parse_status === "partial") partialCount++;
  totals.questions += r.question_count;
  totals.answers += r.answer_count;
  totals.q_missing += r.questions_missing.length;
  totals.a_missing += r.answer_missing.length;
  totals.empty_slots += r.counts.empty_slots;
  byKey[key] = summary;
}

const out = {
  generated_at: new Date().toISOString(),
  parser_version: PARSER_VERSION,
  total_entries: index.length,
  parsed: results.filter((r) => r.parse_status).length,
  ok: okCount,
  partial: partialCount,
  errors,
  totals,
  results,
};
fs.writeFileSync(path.join(RUN, "evidence/S04-offline-regression.json"), JSON.stringify(out, null, 2));

const lines = [];
lines.push(`S04 offline regression — parser ${PARSER_VERSION}`);
lines.push(`entries=${index.length} parsed=${out.parsed} ok=${okCount} partial=${partialCount} errors=${errors.length}`);
lines.push(`totals: questions=${totals.questions} answers=${totals.answers} q_missing=${totals.q_missing} a_missing=${totals.a_missing} empty_slots=${totals.empty_slots}`);
lines.push("");
lines.push("== per book-test ==");
for (const key of Object.keys(byKey).sort()) {
  const s = byKey[key];
  const w = s.warnings.join(",");
  lines.push(`${key.padEnd(22)} q=${String(s.questions).padStart(3)}/${String(s.expected_total ?? "?").padStart(3)} a=${String(s.answers).padStart(3)} qm=${s.questions_missing.length ? JSON.stringify(s.questions_missing) : "-"} am=${s.answer_missing.length ? JSON.stringify(s.answer_missing) : "-"} st=${s.parse_status} w=[${w}]`);
}
if (errors.length) {
  lines.push("");
  lines.push("== errors ==");
  for (const e of errors) lines.push(`${e.key ?? ""} ${e.raw_index ?? ""} ${e.error}`);
}
fs.writeFileSync(path.join(RUN, "evidence/S04-offline-regression.txt"), lines.join("\n") + "\n");
console.log(lines.slice(0, 8).join("\n"));
console.log("...");
console.log(`wrote evidence/S04-offline-regression.json + .txt (${lines.length} lines)`);
