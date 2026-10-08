import * as api from 'file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs';
import fs from 'node:fs';
const out = {};
for (const t of [1,2,3,4]) {
  out["r"+t] = await api.cam21Reading(t);
  out["l"+t] = await api.cam21Listening(t);
}
fs.writeFileSync("C:/Users/weo/Desktop/api/tmp_audit_ielts/cam21_snap_after.json", JSON.stringify(out));
console.log("saved. r counts:", [1,2,3,4].map(t=>out["r"+t].counts.answers).join(","), "l counts:", [1,2,3,4].map(t=>out["l"+t].counts.answers).join(","), "lines:", [1,2,3,4].map(t=>out["l"+t].counts.transcript_lines).join(","));
const before = JSON.parse(fs.readFileSync("C:/Users/weo/Desktop/api/tmp_audit_ielts/cam21_snap_before.json","utf8"));
let diffs = [];
for (const k of Object.keys(out)) {
  const a = JSON.stringify(before[k]), b = JSON.stringify(out[k]);
  if (a !== b) diffs.push(k);
}
console.log("keys:", Object.keys(out).join(","));
console.log(diffs.length ? "BYTE-DIFF: " + diffs.join(",") : "IDENTICAL to before (all 8 payloads)");
// deep detail if diff
for (const k of diffs) {
  const a = before[k], b = out[k];
  for (const f of Object.keys(b)) {
    const ja = JSON.stringify(a[f]), jb = JSON.stringify(b[f]);
    if (ja !== jb) console.log("  field diff", k, f, "len", ja.length, "->", jb.length);
  }
}
