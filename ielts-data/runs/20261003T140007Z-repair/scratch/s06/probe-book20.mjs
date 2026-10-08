// probe-book20.mjs — 剑20 分册 T2/T3/T4 真实性探测（只探测，不下载）
import fs from "node:fs";
import { BOOK20_TESTS, probe } from "../../../../../ielts-api/lfs.mjs";

const OUT = "C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/evidence/S06-book20-probe.json";
const out = { source: "BaBaLiBoo/IELTS-Resources", probed_at: new Date().toISOString(), tests: {} };

for (const [k, p] of Object.entries(BOOK20_TESTS)) {
  if (k === "test1") continue; // 本地已有 book_20.pdf
  const r = await probe(p, { via: "media", retries: 3 });
  out.tests[k] = {
    path: p, ok: r.ok, status: r.status ?? null, isPdf: r.isPdf ?? false,
    isLfsPointer: r.isLfsPointer ?? false, bytes: r.bytes ?? null, mb: r.mb ?? null,
    contentType: r.contentType ?? null, error: r.error ?? null, url: r.url,
  };
  console.log(k, JSON.stringify(out.tests[k]));
}
out.all_ok = Object.values(out.tests).every((t) => t.ok);
fs.writeFileSync(OUT, JSON.stringify(out, null, 2));
console.log("ALL_OK=", out.all_ok, "->", OUT);
