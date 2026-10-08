// s05-warnings-check.mjs — 验证 scanUnsupported/parseLiteral 对 8 个真实 HTML 零误报
import { readFileSync } from "node:fs";
import { parseReadingHtml, parseListeningHtml, __internals } from "file:///C:/Users/weo/Desktop/api/ielts-api/cam21.mjs";

const CAM = "C:/Users/weo/Desktop/api/tmp_audit_ielts/cam21/";
let bad = 0;
for (const t of [1, 2, 3, 4]) {
  const r = parseReadingHtml(readFileSync(CAM + "t" + t + "-reading.html", "utf8"), { test: t });
  const l = parseListeningHtml(readFileSync(CAM + "t" + t + "-listening.html", "utf8"), { test: t });
  const rw = r.warnings || [], lw = l.warnings || [];
  console.log(`t${t} reading warnings=${rw.length} listening warnings=${lw.length}`);
  if (rw.length) { bad++; console.log("  reading:", JSON.stringify(rw).slice(0, 400)); }
  if (lw.length) { bad++; console.log("  listening:", JSON.stringify(lw).slice(0, 400)); }
}

// 合成用例：确认各类非数据表达式都能命中，且字符串/注释内不误报
const { scanUnsupported } = __internals;
const cases = [
  ["{a: `${x}`}", ["template_expression"]],
  ["{a: function () {}}", ["function_expression"]],
  ["{a: () => 1}", ["arrow_function"]],
  ["{a: /re/g}", ["regex_or_division"]],
  ["{a: 1/2}", ["regex_or_division"]],
  ["{function: 1, functions: [1], functionName: 2}", []],
  ['{a: "has ${x} and / slash"}', []],
  ["{a: '\\${esc}'}", []],
  ["{a: 1 /* / in comment */ , b: 2}", []],
  ["{a: 1 // / line comment\n}", []],
  ["{a: 'function () => {}'} ", []],
];
let fail = 0;
for (const [lit, want] of cases) {
  const got = scanUnsupported(lit);
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) { fail++; console.log("MISMATCH", JSON.stringify(lit), "got", JSON.stringify(got), "want", JSON.stringify(want)); }
}
// parseLiteral: 有问题时不解析且保留 raw
const w = [];
const v = __internals.parseLiteral("const X = {a: (() => 1)()};", "X", w);
if (v !== null || w.length !== 1 || w[0].kind !== "unsupported_literal" || !w[0].raw.includes("=>")) { fail++; console.log("parseLiteral fail", v, JSON.stringify(w)); }

console.log(bad === 0 && fail === 0 ? "ALL OK" : `PROBLEMS: fileWarn=${bad} caseFail=${fail}`);
process.exit(bad === 0 && fail === 0 ? 0 : 1);
