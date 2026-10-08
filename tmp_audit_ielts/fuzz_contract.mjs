// 契约 fuzz：永不抛异常、不挂起
import * as api from 'file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs';
const cases = [0, -1, 999, null, undefined, "abc", 3.7, 1e9, NaN, Infinity, "", "3", [], {}];
let failures = [];
const timeout = (p, ms, label) => Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error("HANG >" + ms + "ms")), ms))]);
async function tryCall(label, fn, ms=60000) {
  const t0 = Date.now();
  try {
    const r = await timeout(fn(), ms, label);
    const okField = r && typeof r === "object" && ("ok" in r) ? String(r.ok) : "(no ok)";
    console.log(`PASS ${label} -> ok=${okField} ${Date.now()-t0}ms`);
    return null;
  } catch (e) {
    console.log(`FAIL ${label} -> ${String(e.message||e).slice(0,120)}`);
    failures.push(label + " :: " + String(e.message||e).slice(0,120));
    return e;
  }
}
// 包装器 fuzz（选代表性集合，避免海量请求）
for (const b of [0, -1, 999, null, undefined, "abc", 3.7]) {
  await tryCall(`pteReading(${JSON.stringify(b)},1)`, () => api.pteReading(b, 1));
}
for (const t of [0, -1, 999, null, undefined, "abc", 3.7]) {
  await tryCall(`pteReading(20,${JSON.stringify(t)})`, () => api.pteReading(20, t));
}
await tryCall(`pteBook(null)`, () => api.pteBook(null));
await tryCall(`pteBook(1e9)`, () => api.pteBook(1e9));
await tryCall(`cam21Reading(0)`, () => api.cam21Reading(0));
await tryCall(`cam21Reading(999)`, () => api.cam21Reading(999));
await tryCall(`cam21Listening("x")`, () => api.cam21Listening("x"));
await tryCall(`cam21Audio(1,999)`, () => api.cam21Audio(1, 999));
await tryCall(`reading(19,1,999)`, () => api.reading(19, 1, 999));
await tryCall(`listeningScript(999)`, () => api.listeningScript(999));
await tryCall(`listeningSegments(19,1,999)`, () => api.listeningSegments(19, 1, 999));
await tryCall(`itoScript(999,1)`, () => api.itoScript(999, 1));
await tryCall(`pdfLfs(999)`, () => api.pdfLfs(999));
await tryCall(`aggregate({book:null,test:null})`, () => api.aggregate({ book: null, test: null }), 120000);
await tryCall(`aggregate({book:999,test:-1})`, () => api.aggregate({ book: 999, test: -1 }), 120000);
await tryCall(`aggregate({book:"abc",test:3.7})`, () => api.aggregate({ book: "abc", test: 3.7 }), 120000);
await tryCall(`aggregate({})`, () => api.aggregate({}), 120000);
await tryCall(`aggregate()`, () => api.aggregate(), 120000);
console.log("\n=== FAILURES:", failures.length, "===");
failures.forEach(f => console.log(" -", f));
