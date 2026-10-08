// download-book20.mjs — 下载剑20 T2/T3/T4 分册到 ielts-data/raw/pdf-source/（守字节预算）
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { BOOK20_TESTS, url } from "../../../../../ielts-api/lfs.mjs";

const DEST = "C:/Users/weo/Desktop/api/ielts-data/raw/pdf-source";
const OUT = "C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S06-book20-download.json";
fs.mkdirSync(DEST, { recursive: true });

const sha = (b) => crypto.createHash("sha256").update(b).digest("hex");
const out = { source: "BaBaLiBoo/IELTS-Resources", downloaded_at: new Date().toISOString(), files: {} };
let budgetBytes = 0;

for (const k of ["test2", "test3", "test4"]) {
  const p = BOOK20_TESTS[k];
  const u = url(p);
  const dest = path.join(DEST, `book20-${k}.pdf`);
  const r = await fetch(u, { headers: { "user-agent": "Mozilla/5.0" }, redirect: "follow", signal: AbortSignal.timeout(180000) });
  if (!r.ok) { out.files[k] = { ok: false, status: r.status, url: u }; continue; }
  const buf = Buffer.from(await r.arrayBuffer());
  budgetBytes += buf.length;
  const magic = buf.slice(0, 5).toString("latin1");
  if (!magic.startsWith("%PDF")) { out.files[k] = { ok: false, error: "not pdf", magic, bytes: buf.length, url: u }; continue; }
  fs.writeFileSync(dest, buf);
  out.files[k] = { ok: true, path: dest, bytes: buf.length, mb: +(buf.length / 1048576).toFixed(2), sha256: sha(buf), url: u, source_path: p };
  console.log(k, "->", dest, buf.length, "bytes", sha(buf).slice(0, 16));
}
out.budget_bytes = budgetBytes;
out.all_ok = Object.values(out.files).every((f) => f.ok);
fs.writeFileSync(OUT, JSON.stringify(out, null, 2));
console.log("ALL_OK=", out.all_ok, "TOTAL_MB=", (budgetBytes / 1048576).toFixed(1), "->", OUT);
