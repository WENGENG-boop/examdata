import { itoScript } from "file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs";
const s = await itoScript(20, 2);
console.log("ok=", s.ok, "slug=", s.slug, "sections=", s.section_count);
const secs = s.sections || {};
for (const [k, v] of Object.entries(secs)) {
  console.log(`--- ${k}: ${v.length} chars ---`);
  console.log("HEAD:", JSON.stringify(v.slice(0, 150)));
  console.log("TAIL:", JSON.stringify(v.slice(-200)));
  console.log("has Advertisements:", /Advertisements/i.test(v), " has …:", /…/.test(v));
}
// 打印 section4 里 'Advertisements' 出现的上下文
const s4 = secs.section4 || "";
let i = s4.search(/Advertisements/i);
if (i >= 0) console.log("ADV CONTEXT:", JSON.stringify(s4.slice(Math.max(0,i-300), i+200)));
