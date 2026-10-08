// jsToJson 精确攻击测试 v2：用 fromCharCode 构造输入，排除转义歧义
// 从 cam21.mjs 源文件精确提取 jsToJson（不改动被测代码）
import fs from "node:fs";
const src = fs.readFileSync("C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/cam21.mjs", "utf8");
const m = src.match(/function jsToJson\(src\) \{[\s\S]*?\n\}/);
if (!m) { console.log("EXTRACT FAIL"); process.exit(1); }
const jsToJson = new Function("TICK", m[0] + "\nreturn jsToJson;")(String.fromCharCode(96));

const BS = String.fromCharCode(92);   // \
const SQ = String.fromCharCode(39);   // '
const DQ = String.fromCharCode(34);   // "
const TK = String.fromCharCode(96);   // `
const NL = String.fromCharCode(10);   // newline
const LBR = "{", RBR = "}";

function show(s) { return JSON.stringify(s); }

const cases = [
  ["A. sq + escaped apostrophe", LBR + "a:" + SQ + "it" + BS + SQ + "s ok" + SQ + RBR, "it's ok"],
  ["B. sq + double-backslash", LBR + "a:" + SQ + "c:" + BS + BS + "path" + SQ + RBR, "c:" + BS + "path"],
  ["C. sq + newline escape", LBR + "a:" + SQ + "L1" + BS + "nL2" + SQ + RBR, "L1" + NL + "L2"],
  ["D. dq + newline escape", LBR + 'a:"L1' + BS + 'nL2"' + RBR, "L1" + NL + "L2"],
  ["E. template literal plain", LBR + "a:" + TK + "hello" + TK + RBR, "hello"],
  ["F. template with apostrophe", LBR + "a:" + TK + "it" + SQ + "s" + TK + RBR, "it's"],
  ["G. template with newline escape", LBR + "a:" + TK + "L1" + BS + "nL2" + TK + RBR, "L1" + NL + "L2"],
  ["H. mixed (doc claim)", LBR + "g:" + SQ + "g1" + SQ + ", text:" + DQ + "grandfather" + SQ + "s wealth" + DQ + RBR, "grandfather's wealth"],
  ["I. dq + escaped dq", LBR + "a:" + DQ + "say " + BS + DQ + "hi" + BS + DQ + DQ + RBR, 'say "hi"'],
];

for (const [name, input, expect] of cases) {
  let out, parsed, err = null;
  try { out = jsToJson(input); } catch (e) { err = "THROW: " + e.message; }
  if (out !== undefined) { try { parsed = JSON.parse(out); } catch (e) { parsed = undefined; } }
  const got = parsed !== undefined ? parsed.a ?? parsed.text : undefined;
  const pass = parsed !== undefined && got === expect;
  console.log((pass ? "PASS " : "FAIL ") + name);
  if (!pass) {
    console.log("   input : " + show(input));
    console.log("   out   : " + show(out));
    console.log("   parsed: " + (parsed !== undefined ? show(JSON.stringify(parsed)) : "PARSE-FAIL"));
    console.log("   expect: " + show(expect));
  }
}
