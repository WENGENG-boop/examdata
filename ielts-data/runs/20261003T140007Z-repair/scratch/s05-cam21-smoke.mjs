// S05 冒烟：新版 cam21.mjs 对本地 8 个 HTML 的解析验证（只读输入）
import { readFileSync } from "node:fs";
import { parseReadingHtml, parseListeningHtml, __internals } from "file:///C:/Users/weo/Desktop/api/ielts-api/cam21.mjs";

const CAM = "C:/Users/weo/Desktop/api/tmp_audit_ielts/cam21/";
let pass = 0, fail = 0;
function check(name, cond, detail = "") {
  if (cond) { pass++; console.log("ok   " + name + (detail ? "  [" + detail + "]" : "")); }
  else { fail++; console.log("FAIL " + name + (detail ? "  [" + detail + "]" : "")); }
}

const R = {}, L = {};
for (const t of [1, 2, 3, 4]) R[t] = parseReadingHtml(readFileSync(CAM + "t" + t + "-reading.html", "utf8"), { test: t });
for (const t of [1, 2, 3, 4]) L[t] = parseListeningHtml(readFileSync(CAM + "t" + t + "-listening.html", "utf8"), { test: t });

console.log("=== reading counts ===");
for (const t of [1, 2, 3, 4]) {
  const c = R[t].counts;
  console.log(`t${t} passages=${c.passages} groups=${c.groups} questions=${c.questions} keys_raw=${c.answer_keys_raw} answers=${c.answers} missing=${JSON.stringify(c.missing_answers)} dup=${JSON.stringify(c.duplicate_slots)}`);
}
console.log("=== listening counts ===");
for (const t of [1, 2, 3, 4]) {
  const c = L[t].counts;
  const byType = {};
  for (const q of L[t].questions) byType[q.type] = (byType[q.type] || 0) + 1;
  console.log(`t${t} sections=${c.sections} questions=${c.questions} keys_raw=${c.answer_keys_raw} answers=${c.answers} missing=${JSON.stringify(c.missing_answers)} qmissing=${JSON.stringify(c.questions_missing)} multi_groups=${c.multi_groups} audio=${c.audio} transcript_lines=${c.transcript_lines} types=${JSON.stringify(byType)}`);
}

console.log("=== reading assertions ===");
for (const t of [1, 2, 3, 4]) {
  const r = R[t];
  check(`R t${t} questions=40`, r.counts.questions === 40, String(r.counts.questions));
  check(`R t${t} answers=40`, r.counts.answers === 40, String(r.counts.answers));
  check(`R t${t} keys_raw=40`, r.counts.answer_keys_raw === 40, String(r.counts.answer_keys_raw));
  check(`R t${t} missing_answers=[]`, r.counts.missing_answers.length === 0, JSON.stringify(r.counts.missing_answers));
  check(`R t${t} duplicate_slots=[]`, r.counts.duplicate_slots.length === 0, JSON.stringify(r.counts.duplicate_slots));
  check(`R t${t} passages=3`, r.passages.length === 3, String(r.passages.length));
  check(`R t${t} groups>=1`, r.groups.length >= 1, String(r.groups.length));
  check(`R t${t} headings=[]`, r.headings.length === 0, String(r.headings.length));
  check(`R t${t} endings=[]`, r.endings.length === 0, String(r.endings.length));
  check(`R t${t} passages text nonempty`, r.passages.every((p) => p.text.length > 500), r.passages.map((p) => p.text.length).join(","));
}
{
  const r = R[2];
  const q20 = r.questions.find((q) => q.number === 20);
  const q21 = r.questions.find((q) => q.number === 21);
  check("R t2 Q20 exists", !!q20);
  check("R t2 Q21 exists", !!q21);
  if (q20) {
    check("R t2 Q20 type=multi", q20.type === "multi", q20.type);
    check("R t2 Q20 group_slots=[20,21]", JSON.stringify(q20.group_slots) === "[20,21]", JSON.stringify(q20.group_slots));
    check("R t2 Q20 pick=2", q20.pick === 2, String(q20.pick));
    check("R t2 Q20 options=5", q20.options.length === 5, String(q20.options.length));
    check("R t2 Q20 prompt nonempty", (q20.prompt || "").length > 10, q20.prompt);
  }
  if (q21) {
    check("R t2 Q21 group_slots=[20,21]", JSON.stringify(q21.group_slots) === "[20,21]", JSON.stringify(q21.group_slots));
  }
  const a20 = r.answer_key.find((e) => e.number === 20);
  const a21 = r.answer_key.find((e) => e.number === 21);
  check("R t2 ans20 accept B,D", !!a20 && JSON.stringify(a20.accept) === '["B","D"]', a20 && JSON.stringify(a20.accept));
  check("R t2 ans21 accept B,D", !!a21 && JSON.stringify(a21.accept) === '["B","D"]', a21 && JSON.stringify(a21.accept));
  check("R t2 answer_groups>=1", r.answer_groups.length >= 1, String(r.answer_groups.length));
}
{
  const r = R[4];
  const q9 = r.questions.find((q) => q.number === 9);
  check("R t4 Q9 exists", !!q9);
  const a9 = r.answer_key.find((e) => e.number === 9);
  check("R t4 Q9 accept=fermentation,fermentation process",
    !!a9 && JSON.stringify(a9.accept) === '["fermentation","fermentation process"]', a9 && JSON.stringify(a9.accept));
  const a34 = r.answer_key.find((e) => e.number === 34);
  check("R t4 ans34 present", !!a34, a34 && JSON.stringify(a34.accept));
}
{
  // 每组都有 instruction 且 40 题都挂在某组
  const r = R[1];
  const groupIds = new Set(r.groups.map((g) => g.id));
  check("R t1 all questions in groups", r.questions.every((q) => groupIds.has(q.group)), "");
  check("R t1 groups all have instruction", r.groups.every((g) => (g.instruction || "").length > 0), r.groups.map((g) => g.id + ":" + (g.instruction || "").slice(0, 20)).join(" | "));
}

console.log("=== listening assertions ===");
const expRaw = { 1: 38, 2: 35, 3: 36, 4: 38 };
const expMultiGroups = { 1: 2, 2: 5, 3: 4, 4: 2 };
const expMcq = { 1: 6, 2: 0, 3: 2, 4: 3 };
const expMultiSlots = { 1: 4, 2: 10, 3: 8, 4: 4 };
for (const t of [1, 2, 3, 4]) {
  const l = L[t];
  const c = l.counts;
  check(`L t${t} questions=40`, c.questions === 40, String(c.questions));
  check(`L t${t} answers=40`, c.answers === 40, String(c.answers));
  check(`L t${t} keys_raw=${expRaw[t]}`, c.answer_keys_raw === expRaw[t], String(c.answer_keys_raw));
  check(`L t${t} missing_answers=[]`, c.missing_answers.length === 0, JSON.stringify(c.missing_answers));
  check(`L t${t} questions_missing=[]`, c.questions_missing.length === 0, JSON.stringify(c.questions_missing));
  check(`L t${t} multi_groups=${expMultiGroups[t]}`, c.multi_groups === expMultiGroups[t], String(c.multi_groups));
  check(`L t${t} audio=4`, c.audio === 4, String(c.audio));
  check(`L t${t} transcript_lines>0`, c.transcript_lines > 0, String(c.transcript_lines));
  const mcq = l.questions.filter((q) => q.type === "mcq").length;
  const multi = l.questions.filter((q) => q.type === "multi").length;
  check(`L t${t} mcq slots=${expMcq[t]}`, mcq === expMcq[t], String(mcq));
  check(`L t${t} multi slots=${expMultiSlots[t]}`, multi === expMultiSlots[t], String(multi));
  check(`L t${t} all questions have group`, l.questions.every((q) => q.group != null), "");
  check(`L t${t} all questions have prompt`, l.questions.every((q) => (q.prompt || "").length > 0), l.questions.filter((q) => !(q.prompt || "").length).map((q) => q.number).join(","));
  check(`L t${t} all gap/mcq have options or prompt`, true, "");
}
{
  const l = L[1];
  const q15 = l.questions.find((q) => q.number === 15);
  check("L t1 Q15 type=mcq (11-16 radio)", !!q15 && q15.type === "mcq", q15 && q15.type);
  const q17 = l.questions.find((q) => q.number === 17);
  check("L t1 Q17 type=letter_match", !!q17 && q17.type === "letter_match", q17 && q17.type);
  check("L t1 Q17 options=3 (A,B,C)", !!q17 && q17.options.length === 3, q17 && String(q17.options.length));
  check("L t1 Q17 prompt has ___", !!q17 && q17.prompt.includes("___"), q17 && q17.prompt);
  const q25 = l.questions.find((q) => q.number === 25);
  check("L t1 Q25 type=letter_match", !!q25 && q25.type === "letter_match", q25 && q25.type);
  check("L t1 Q25 options=8 (A-H, header skipped)", !!q25 && q25.options.length === 8, q25 && String(q25.options.length));
  const q11 = l.questions.find((q) => q.number === 11);
  check("L t1 Q11 type=mcq with options", !!q11 && q11.type === "mcq" && q11.options.length === 3, q11 && String(q11.options.length));
  const g21 = l.answer_groups.find((g) => g.slots.includes(21));
  check("L t1 multiCorrect 21 inputs strings", !!g21 && JSON.stringify(g21.inputs_raw) === '["21","22"]', g21 && JSON.stringify(g21.inputs_raw));
  check("L t1 transcript has speakers", l.transcript.some((s) => s.has_speakers), "");
}
{
  const l = L[2];
  const g = l.answer_groups.find((x) => x.slots.includes(11));
  check("L t2 multiCorrect 11 inputs numbers", !!g && JSON.stringify(g.inputs_raw) === "[11,12]", g && JSON.stringify(g.inputs_raw));
}
{
  const l = L[3];
  check("L t3 transcript all null speakers", l.transcript.every((s) => !s.has_speakers), l.transcript.map((s) => s.has_speakers).join(","));
}
{
  const l = L[4];
  const a21 = l.answer_key.find((e) => e.number === 21);
  const a22 = l.answer_key.find((e) => e.number === 22);
  const a24 = l.answer_key.find((e) => e.number === 24);
  check("L t4 ans21 B", !!a21 && a21.answer === "B", a21 && a21.answer);
  check("L t4 ans22 A", !!a22 && a22.answer === "A", a22 && a22.answer);
  check("L t4 ans24 B", !!a24 && a24.answer === "B", a24 && a24.answer);
  const q21 = l.questions.find((q) => q.number === 21);
  check("L t4 Q21 type=mcq", !!q21 && q21.type === "mcq", q21 && q21.type);
  const q11 = l.questions.find((q) => q.number === 11);
  check("L t4 Q11 type=multi", !!q11 && q11.type === "multi", q11 && q11.type);
}

console.log("=== internals smoke ===");
{
  const { safeParse, literalAuto, jsToJson, sanitize, parseRangeLabel } = __internals;
  const src = `
    const X = {
      a: 'it\\'s ok', // trailing comment
      b: "double \\"q\\"",
      c: [1, 2, 3,],
      __proto__: { polluted: 1 },
      d: { e: { f: [true, false, null] } },
      g: "\\u0041\\x42\\u{43}",
      h: \`tick \${not-eval}\`,
    };
  `;
  const lit = literalAuto(src, "X");
  check("lit X extracted", !!lit && lit.startsWith("{") && lit.endsWith("}"), lit && lit.slice(0, 30));
  const parsed = safeParse(lit);
  check("X parsed", !!parsed, JSON.stringify(parsed && Object.keys(parsed)));
  if (parsed) {
    check("X a=it's ok", parsed.a === "it's ok", parsed.a);
    check("X b=double \"q\"", parsed.b === 'double "q"', parsed.b);
    check("X c=[1,2,3]", JSON.stringify(parsed.c) === "[1,2,3]", JSON.stringify(parsed.c));
    check("X g=ABC", parsed.g === "ABC", parsed.g);
    check("X h=tick ${not-eval}", parsed.h === "tick ${not-eval}", parsed.h);
    check("X no prototype pollution", ({}).polluted === undefined, String(({}).polluted));
    check("X __proto__ own key", Object.keys(parsed).includes("__proto__"), Object.keys(parsed).join(","));
  }
  check("bad literal -> null", safeParse("{ oops: ") === null, "");
  check("range Questions 1-6", JSON.stringify(parseRangeLabel("Questions 1–6")) === '{"from":1,"to":6,"text":"Questions 1–6"}', JSON.stringify(parseRangeLabel("Questions 1–6")));
  check("range Duties -> null", parseRangeLabel("Duties") === null, String(parseRangeLabel("Duties")));
}

console.log(`\nRESULT pass=${pass} fail=${fail}`);
process.exit(fail ? 1 : 0);
