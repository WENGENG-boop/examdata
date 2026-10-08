import fs from "node:fs";
import { parsePtePage, expectedFor } from "../../../../ielts-api/pte.mjs";
const [rawIdx, book, test, skillRaw] = process.argv.slice(2);
const raw = fs.readFileSync(`C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003/raw-${rawIdx}.txt`, "utf8");
const skill = skillRaw === "reading" ? "academic_reading" : "listening";
const r = parsePtePage(raw, { book: +book, test: +test, skill }, expectedFor(+book, +test, skill));
console.log(JSON.stringify({ status: r.parse_status, warnings: r.warnings.map((w) => w.kind), q_missing: r.questions_missing, a_missing: r.answer_missing_detail, counts: r.counts }));
console.log("KEY", r.answer_key.map((a, i) => `${i + 1}:${a}`).join(" "));
