// 攻击点：尾逗号正则 /,(\s*[}\]])/g 是否误伤字符串内的 ",}" 或 ",]"
import fs from "node:fs";
const src = fs.readFileSync("C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/cam21.mjs", "utf8");
const m = src.match(/function jsToJson\(src\) \{[\s\S]*?\n\}/);
const jsToJson = new Function("TICK", m[0] + "\nreturn jsToJson;")(String.fromCharCode(96));
const DQ = String.fromCharCode(34);
const cases = [
  ["string containing ,}", "{" + "a:" + DQ + "x,}" + DQ + "}"],
  ["string containing , ]", "{" + "a:" + DQ + "x,] y" + DQ + "}"],
  ["string containing , } spaced", "{" + "a:" + DQ + "x,  }y" + DQ + "}"],
  ["normal trailing comma", "{a:1,b:2,}"],
  ["array trailing comma", "{a:[1,2,],b:3}"],
];
for (const [name, input] of cases) {
  const out = jsToJson(input);
  let parsed = undefined; try { parsed = JSON.parse(out); } catch {}
  console.log(name);
  console.log("  in :", JSON.stringify(input));
  console.log("  out:", JSON.stringify(out));
  console.log("  parsed:", parsed !== undefined ? JSON.stringify(parsed) : "PARSE-FAIL");
}
