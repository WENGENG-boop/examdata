// 从 cam21.mjs 源文件精确提取 jsToJson + looseParse（不改动被测代码）
import fs from "node:fs";
const src = fs.readFileSync("C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/cam21.mjs", "utf8");
const m = src.match(/function jsToJson\(src\) \{[\s\S]*?\n\}/);
const TICK_M = src.match(/const TICK = .*/);
if (!m) { console.log("EXTRACT FAIL"); process.exit(1); }
const fn = m[0];
console.log("extracted bytes:", fn.length, "| TICK line:", TICK_M ? TICK_M[0].trim() : "?");
const jsToJson = new Function("TICK", fn + "\nreturn jsToJson;")(`"` + "`" + `"`);

const cases = [
  ["mixed quotes (doc claim)", `{g:'g1', text:"grandfather's wealth"}`, true],
  ["escaped quote in dq", `{a:"say \\"hi\\" now"}`, true],
  ["escaped quote in sq", `{a:'it\'s ok'}`, true],
  ["template literal", "{a:`hello ${1+1}`}", false],
  ["template with tick", "{a:`it's fine`}", true],
  ["comment //", `{a:1 // note\n, b:2}`, true],
  ["comment /* */", `{a:1 /* c */, b:2}`, true],
  ["unicode escape", `{a:"\u0041"}`, true],
  ["newline escape in dq", `{a:"line1\nline2"}`, true],
  ["newline escape in sq", `{a:'line1\nline2'}`, false],
  ["backslash in sq", `{a:'c:\\path'}`, false],
  ["nested obj+arr", `{a:{b:[1,2,{c:'x'}]}}`, true],
  ["trailing comma", `{a:1,b:2,}`, true],
  ["__proto__ key", `{"__proto__":{"polluted":1}, b:2}`, true],
  ["__proto__ bare", `{__proto__:{polluted:1}}`, true],
  ["constructor key", `{constructor:{prototype:{x:1}}}`, true],
  ["number key", `{1:'a', 2:'b'}`, true],
  ["regex literal", `{a:/foo+/gi, b:2}`, false],
  ["unterminated string", `{a:"never closed`, false],
  ["deep nesting 500", `{a:` + "[".repeat(500) + "]".repeat(500) + "}", true],
];
let bad = 0;
for (const [name, input, expectParse] of cases) {
  let out, parsed, err = null;
  try { out = jsToJson(input); } catch (e) { err = "THROW: " + e.message; }
  if (out !== undefined) { try { parsed = JSON.parse(out); } catch (e) { parsed = undefined; err = err || ("PARSE FAIL"); } }
  const status = err ? "ERR(" + err + ")" : (parsed !== undefined ? "OK" : "?");
  const flag = (err && expectParse) || (!err && !expectParse) ? "  <<< UNEXPECTED" : "";
  if (flag) bad++;
  console.log(`${name}: ${status}${flag}`);
  if (out !== undefined && out.length < 200) console.log(`   out: ${out}`);
  if (parsed !== undefined) console.log(`   parsed: ${JSON.stringify(parsed)}`);
}
// prototype pollution check
delete Object.prototype.polluted;
const o1 = JSON.parse(jsToJson(`{"__proto__":{"polluted":1}, b:2}`));
console.log("\npollution via JSON.parse:", ({}).polluted === undefined ? "SAFE (no global pollution)" : "POLLUTED!");
console.log("o1 own keys:", JSON.stringify(Object.keys(o1)), "| o1.__proto__ type:", typeof o1.__proto__);
// ReDoS timing
const t0 = Date.now();
jsToJson("{a:1,".repeat(20000) + "b:2}");
console.log("ReDoS 20k keys:", Date.now() - t0, "ms");
const t1 = Date.now();
jsToJson('{a:"' + "x".repeat(200000));
console.log("unterminated 200k chars:", Date.now() - t1, "ms");
console.log("\nUNEXPECTED count:", bad);
