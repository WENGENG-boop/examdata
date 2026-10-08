import { listeningScript, listeningSegments } from "file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs";
// b8 用 reader 源
const s = await listeningScript(8);
console.log("b8 ok=", s.ok, "source=", s.source);
const t4p2 = (s.tests||{}).test4?.part2 || "";
console.log("--- b8 t4 p2 first 200 chars ---");
console.log(JSON.stringify(t4p2.slice(0, 200)));
const headingLike = /^\s*(?:PART|SECTION)\s*\d+/im.test(t4p2);
console.log("headingLike at line start =", headingLike);
// 也检查所有 part 无行首标题
let bad = 0;
for (const [tn, pm] of Object.entries(s.tests||{})) for (const [pn, txt] of Object.entries(pm)) {
  if (/^\s*(?:PART|SECTION)\s*\d+/im.test(txt)) { bad++; console.log("STILL BAD:", tn, pn); }
}
console.log("bad parts:", bad);
