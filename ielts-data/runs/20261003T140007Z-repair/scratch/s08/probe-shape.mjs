// S08: dump exact group/question/passage shapes from pte parse for index design.
import fs from "node:fs";
import { parsePtePage, expectedFor } from "../../../../../ielts-api/pte.mjs";
const raw = fs.readFileSync("C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003/raw-5.txt", "utf8");
const expected = expectedFor(1, 2, "academic_reading");
const p = parsePtePage(raw, { book: 1, test: 2, skill: "academic_reading", slug: "x" }, expected);
console.log("ok", p.ok, "groups", p.question_groups.length, "q", p.questions.length);
const g = p.question_groups.find(g => (g.slots||[]).length > 0);
console.log(JSON.stringify(g, null, 1).slice(0, 3000));
console.log("=== passages[0] keys:", Object.keys(p.passages[0] || {}));
console.log("=== passage[0] sample:", JSON.stringify(p.passages[0]).slice(0, 400));
console.log("=== assets:", JSON.stringify((p.assets || []).slice(0, 2)));
console.log("=== audio:", JSON.stringify(p.audio));
