// 请求计数 + 计时：listeningScript 优化路径 / reader 全量路径 / aggregate
const api = await import('file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs');
const orig = globalThis.fetch;
let count = 0; const hosts = {};
globalThis.fetch = async (u, o) => {
  count++;
  try { const h = new URL(typeof u === "string" ? u : u.url).host; hosts[h] = (hosts[h]||0)+1; } catch {}
  return orig(u, o);
};
const t0 = Date.now();
const s16 = await api.listeningScript(16);
console.log("listeningScript(16):", Date.now()-t0, "ms, requests:", count, "ok:", s16.ok, "source:", s16.source, "parts:", s16.parts);
console.log("  hosts:", JSON.stringify(hosts));
count = 0; for (const k in hosts) delete hosts[k];
// 模拟未优化路径的 reader 全量开销（16 个 slot）
const t1 = Date.now();
let segReq0 = count;
for (let t = 1; t <= 4; t++) for (let p = 1; p <= 4; p++) await api.listeningSegments(16, t, p);
console.log("reader 全量 16 slot:", Date.now()-t1, "ms, requests:", count - segReq0);
console.log("  => 未优化合计约:", (Date.now()-t0), "ms (script+reader)");
// aggregate(20,1) 请求数
count = 0; for (const k in hosts) delete hosts[k];
const t2 = Date.now();
const agg = await api.aggregate({book:20, test:1});
console.log("aggregate(20,1):", Date.now()-t2, "ms, requests:", count);
console.log("  hosts:", JSON.stringify(hosts));
console.log("  ok(no top-level):", agg.ok, "parts keys:", Object.keys(agg.parts||{}).join(","), "score:", JSON.stringify(agg.score));
