// M3 复验：模拟 raw.githubusercontent.com 全面故障，确认代码真实回落到 jsDelivr CDN
const RAW_HOST = "raw.githubusercontent.com";
let calls = { raw: 0, cdn: 0, other: 0 };
const orig = globalThis.fetch;
globalThis.fetch = async (url, opts) => {
  const s = String(url);
  if (s.includes(RAW_HOST)) { calls.raw++; throw new Error("simulated RAW outage"); }
  if (s.includes("cdn.jsdelivr.net")) calls.cdn++;
  else calls.other++;
  return orig(url, opts);
};

const BASE = "file:///C:/Users/weo/Desktop/api/ielts-api/";

// --- cam21.mjs: get() 的 [RAW, CDN] 循环 ---
const cam21 = await import(BASE + "cam21.mjs");
calls = { raw: 0, cdn: 0, other: 0 };
const r1 = await cam21.reading(1);
console.log("[cam21.reading(1)]", JSON.stringify({ ok: r1.ok, via: r1.via, answers: r1.counts?.answers, error: r1.error }));
console.log("[cam21 fetch calls]", JSON.stringify(calls));

// --- ielts-api.mjs: gh() 的 base→cdn 回落 ---
const ielts = await import(BASE + "ielts-api.mjs");
calls = { raw: 0, cdn: 0, other: 0 };
const r2 = await ielts.reading(1, 1, 1);
console.log("[ielts.reading(1,1,1)]", JSON.stringify({ ok: r2.ok, questions: r2.question_count, error: r2.error }));
console.log("[ielts fetch calls]", JSON.stringify(calls));
