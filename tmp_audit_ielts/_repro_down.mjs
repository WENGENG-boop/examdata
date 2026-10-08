// 网络完全不可达：全部 fetch 直接拒绝 → 应优雅 ok:false，不抛异常
globalThis.fetch = async () => { throw new TypeError("fetch failed"); };
const { listeningScript } = await import('./ielts-api.mjs');
const t0 = Date.now();
const r = await listeningScript(5);
console.log("NO-THROW:", JSON.stringify(r).slice(0, 160), (Date.now()-t0)+"ms");
