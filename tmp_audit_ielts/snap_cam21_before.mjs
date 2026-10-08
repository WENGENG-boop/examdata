import * as api from 'file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs';
import fs from 'node:fs';
const out = {};
for (const t of [1,2,3,4]) {
  out["r"+t] = await api.cam21Reading(t);
  out["l"+t] = await api.cam21Listening(t);
}
fs.writeFileSync("C:/Users/weo/Desktop/api/tmp_audit_ielts/cam21_snap_before.json", JSON.stringify(out));
console.log("saved. r counts:", [1,2,3,4].map(t=>out["r"+t].counts.answers).join(","), "l counts:", [1,2,3,4].map(t=>out["l"+t].counts.answers).join(","), "lines:", [1,2,3,4].map(t=>out["l"+t].counts.transcript_lines).join(","));
