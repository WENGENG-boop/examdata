// 全路由实测：起服务，逐条请求，记录 status/ok/耗时
import { spawn } from "node:child_process";
const PORT = 8795;
const srv = spawn("node", ["ielts-cli.mjs", "serve", String(PORT)], {
  cwd: "C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api",
  stdio: ["ignore", "pipe", "pipe"],
});
srv.stdout.on("data", d => process.stdout.write("[srv] " + d));
srv.stderr.on("data", d => process.stdout.write("[srv-err] " + d));
await new Promise(r => setTimeout(r, 2500));

const routes = [
  ["/api/aggregate/20/1", 120000],
  ["/api/pte-book/20", 60000],
  ["/api/pte-reading/20/1", 60000],
  ["/api/pte-listening/20/1", 60000],
  ["/api/pte-audio/20/1", 60000],
  ["/api/reading/19/1/1", 60000],
  ["/api/reading-index", 60000],
  ["/api/listening-index", 60000],
  ["/api/listening-qa/20/1", 60000],
  ["/api/listening-script/20", 60000],
  ["/api/listening-audio/20/1/1", 30000],
  ["/api/listening-segments/19/1/1", 60000],
  ["/api/pdf/18", 90000],
  ["/api/pdf-lfs/20", 90000],
  ["/api/book20-set", 120000],
  ["/api/explain-pdf/20", 90000],
  ["/api/lfs-coverage", 240000],
  ["/api/ito-script/21/1", 90000],
  ["/api/ito-listening/21/1", 90000],
  ["/api/ito-coverage", 300000],
  ["/api/cam21-reading/1", 60000],
  ["/api/cam21-listening/1", 60000],
  ["/api/cam21-audio/1/1", 30000],
  ["/api/cam21-full/1", 90000],
  ["/api/cam21-index", 30000],
  ["/api/cam21-coverage", 120000],
  ["/api/mini-list/1", 60000],
  ["/api/mini-solution/1518/australian-artist-margaret-preston", 60000],
  ["/api/coverage", 120000],
];
const results = [];
for (const [path, tmo] of routes) {
  const t0 = Date.now();
  try {
    const ctrl = AbortSignal.timeout(tmo);
    const r = await fetch(`http://127.0.0.1:${PORT}${path}`, { signal: ctrl });
    const txt = await r.text();
    let ok = null, err = null;
    try { const o = JSON.parse(txt); ok = o.ok ?? null; err = o.error || null; } catch {}
    results.push({ path, status: r.status, ok, err, ms: Date.now() - t0, bytes: txt.length });
    console.log(`${r.status} ok=${ok} ${Date.now()-t0}ms ${txt.length}B ${path}${err ? " ERR="+err : ""}`);
  } catch (e) {
    results.push({ path, status: "FAIL", err: String(e.message).slice(0,100), ms: Date.now() - t0 });
    console.log(`FAIL ${Date.now()-t0}ms ${path} :: ${String(e.message).slice(0,100)}`);
  }
}
srv.kill();
import fs from "node:fs";
fs.writeFileSync("route_sweep_results.json", JSON.stringify(results, null, 1));
console.log("DONE, saved route_sweep_results.json");
process.exit(0);
