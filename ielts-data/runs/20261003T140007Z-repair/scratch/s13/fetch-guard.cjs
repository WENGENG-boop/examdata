// S13 fetch=0 证明：拦截 globalThis.fetch，逐次把 URL 追加到 FETCH_GUARD_LOG（JSONL）。
// 通过 NODE_OPTIONS=--require <本文件> 注入到每个 node 子进程（含 FastAPI 网关起的子进程）。
// 只记录，不改变行为；日志缺失时静默。
const fs = require("fs");
const log = process.env.FETCH_GUARD_LOG;
if (log) {
  const orig = globalThis.fetch;
  globalThis.fetch = function (input, init) {
    try {
      const url = typeof input === "string" ? input : (input && input.url) || "";
      fs.appendFileSync(log, JSON.stringify({ pid: process.pid, url: String(url).slice(0, 300) }) + "\n");
    } catch {}
    return orig.apply(this, arguments);
  };
}
