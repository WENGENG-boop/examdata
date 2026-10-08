import fs from "node:fs";
import path from "node:path";
const RAW_DIR = "C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003";
const files = fs.readdirSync(RAW_DIR).filter((f) => /^raw-\d+\.txt$/.test(f));
for (const f of files) {
  let raw;
  try { raw = JSON.parse(fs.readFileSync(path.join(RAW_DIR, f), "utf8")); } catch { console.log(`${f} :: NOT JSON`); continue; }
  const html = (raw[0] && raw[0].content && raw[0].content.rendered) || "";
  const ms = [...html.matchAll(/Passage\s+\d+\s*(?:[–—\-:.]\s*)?Questions?[^<]{0,50}/gi)].slice(0, 4);
  for (const m of ms) console.log(`${f} :: ${JSON.stringify(m[0].slice(0, 90))}`);
}
console.log("done");
