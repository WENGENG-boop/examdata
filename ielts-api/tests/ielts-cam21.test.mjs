// ielts-api/tests/ielts-cam21.test.mjs
// S05 acceptance tests for the cam21.mjs adapter rewrite (parseReadingHtml / parseListeningHtml
// + the safe literal scanner that replaced the previous regex/eval-adjacent parsing).
// Part A: inline fixtures via __internals (no network, no local files).
// Part B: assertions against real saved pages in tmp_audit_ielts/cam21/t{n}-{reading,listening}.html
//         (skipped when a file is missing; the directory is read-only evidence).
// Run: node --test ielts-api/tests/ielts-cam21.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseReadingHtml, parseListeningHtml, __internals } from "../cam21.mjs";

const {
  dataScript, literalAuto, jsToJson, sanitize, safeParse,
  parseOptions, divSpan, parseRangeLabel, inputPrompt,
  scanUnsupported, parseLiteral,
} = __internals;

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CAM_DIR = path.resolve(__dirname, "..", "..", "tmp_audit_ielts", "cam21");

const readCam = (name) => {
  const p = path.join(CAM_DIR, name);
  return fs.existsSync(p) ? fs.readFileSync(p, "utf8") : null;
};
const requireCam = (t, name) => {
  const html = readCam(name);
  if (html == null) t.skip(`tmp_audit_ielts/cam21/${name} not available`);
  return html;
};

const scriptPage = (js) => `<!doctype html><html><head><meta charset="utf-8"></head><body><script>\n${js}\n</script></body></html>`;
const countBy = (arr, key) => arr.reduce((m, x) => { const k = x[key]; m[k] = (m[k] || 0) + 1; return m; }, {});

/* ================================ Part A ================================ */

test("A1: literalAuto extracts { } and [ ] forms; brackets inside strings/comments do not break balance", () => {
  const src1 = `const X = { a: "}not a close", b: 'also } here' }; const Y = 1;`;
  const lit1 = literalAuto(src1, "X");
  assert.equal(lit1, `{ a: "}not a close", b: 'also } here' }`);
  const src2 = `let ARR = [1, [2, 3], "x]y"];`;
  assert.equal(literalAuto(src2, "ARR"), `[1, [2, 3], "x]y"]`);
  const src3 = `const Z = { a: /* } */ 1 };`;
  assert.equal(literalAuto(src3, "Z"), `{ a: /* } */ 1 }`);
  assert.equal(literalAuto(`const W = 5;`, "W"), null);
  assert.equal(literalAuto(`const NOPE = {a:1};`, "X"), null);
  // unbalanced: returns the remainder, and safeParse rejects it (no throw)
  assert.equal(safeParse(literalAuto(`const B = {a: 1`, "B")), null);
});

test("A2: jsToJson/safeParse handle quotes, escapes, trailing commas, comments, template strings", () => {
  const lit = `{
    a: 'it\\'s ok',
    b: "double \\"q\\"",
    c: [1, 2, 3,],
    d: { e: { f: [true, false, null] }, },
    g: "\\u0041\\x42\\u{43}",
    h: \`tick \${not-eval}\`,
    'quoted key': 9,
    12: 'numeric key',
    // line comment
    i: 'after line comment',
    /* block comment */
    j: 'after block comment'
  }`;
  const parsed = safeParse(lit);
  assert.ok(parsed);
  assert.equal(parsed.a, "it's ok");
  assert.equal(parsed.b, 'double "q"');
  assert.deepEqual(parsed.c, [1, 2, 3]);
  assert.deepEqual(parsed.d.e.f, [true, false, null]);
  assert.equal(parsed.g, "ABC");
  assert.equal(parsed.h, "tick ${not-eval}");
  assert.equal(parsed["quoted key"], 9);
  assert.equal(parsed["12"], "numeric key");
  assert.equal(parsed.i, "after line comment");
  assert.equal(parsed.j, "after block comment");
});

test("A3: __proto__ keys do not pollute prototypes and stay as own data keys", () => {
  const parsed = safeParse(`{ __proto__: { polluted: 1 }, x: 1 }`);
  assert.ok(parsed);
  assert.equal(({}).polluted, undefined);
  assert.equal(Object.getPrototypeOf(parsed), null);
  assert.equal(parsed.x, 1);
  assert.ok(Object.keys(parsed).includes("__proto__"));
  assert.equal(parsed.polluted, undefined);
  // sanitize rebuilds arrays/objects recursively: arrays stay arrays (Array.prototype),
  // object elements become null-prototype
  const s = sanitize({ a: [{ b: 1 }], c: "x" });
  assert.equal(Object.getPrototypeOf(s), null);
  assert.equal(s.c, "x");
  assert.ok(Array.isArray(s.a));
  assert.equal(Object.getPrototypeOf(s.a), Array.prototype);
  assert.equal(Object.getPrototypeOf(s.a[0]), null);
});

test("A4: safeParse returns null (never throws) for bad input", () => {
  assert.equal(safeParse(null), null);
  assert.equal(safeParse(""), null);
  assert.equal(safeParse("{ oops: "), null);
  assert.equal(safeParse("[1, 2"), null);
  assert.equal(safeParse(undefined), null);
});

test("A5: parseRangeLabel understands ranges/pairs and rejects sub-headings", () => {
  assert.deepEqual(parseRangeLabel("Questions 1–6"), { from: 1, to: 6, text: "Questions 1–6" });
  assert.deepEqual(parseRangeLabel("Questions 15-20"), { from: 15, to: 20, text: "Questions 15-20" });
  assert.deepEqual(parseRangeLabel("Questions 21 and 22"), { from: 21, to: 22, text: "Questions 21 and 22" });
  assert.deepEqual(parseRangeLabel("Questions 40 and 41"), { from: 40, to: 41, text: "Questions 40 and 41" });
  assert.deepEqual(parseRangeLabel("Questions 5, 6"), { from: 5, to: 6, text: "Questions 5, 6" });
  assert.deepEqual(parseRangeLabel("Question 7"), { from: 7, to: 7, text: "Question 7" });
  assert.equal(parseRangeLabel("Duties"), null);
  assert.equal(parseRangeLabel("Resources"), null);
  assert.equal(parseRangeLabel("Questions 6–5"), null);
});

test("A6: parseOptions normalizes 'A) x' / 'A. x' / bare letter / plain text", () => {
  assert.deepEqual(parseOptions(["A) alpha", "B) beta"]), [{ label: "A", text: "alpha" }, { label: "B", text: "beta" }]);
  assert.deepEqual(parseOptions(["A. alpha", "B. beta"]), [{ label: "A", text: "alpha" }, { label: "B", text: "beta" }]);
  assert.deepEqual(parseOptions(["A", "B", "C"]), [{ label: "A", text: null }, { label: "B", text: null }, { label: "C", text: null }]);
  assert.deepEqual(parseOptions(["plain text"]), [{ label: null, text: "plain text" }]);
  assert.deepEqual(parseOptions(null), []);
});

test("A7: divSpan balances nested divs", () => {
  const html = `<div class="a"><div class="b">x</div>y</div>tail`;
  assert.equal(divSpan(html, 0), `<div class="a"><div class="b">x</div>y</div>`);
  const html2 = `<p>lead</p><div class="a"><div class="b"><div>c</div></div></div>`;
  assert.equal(divSpan(html2, html2.indexOf(`<div class="a"`)), `<div class="a"><div class="b"><div>c</div></div></div>`);
});

test("A8: inputPrompt turns the qnum badge + input into ' ___ ' (label-before and input-before)", () => {
  const h1 = `<div class="label-item"><span class="qnum-prefix">7</span><label>Bring suitable clothing, a</label><input type="text" class="ans-input" data-q="7" oninput="updateProgress()"></div>`;
  assert.equal(inputPrompt(h1, h1.indexOf(`data-q="7"`)), "Bring suitable clothing, a ___");
  const h2 = `<li><input type="text" class="ans-input" data-q="12"><label>comes first</label></li>`;
  assert.equal(inputPrompt(h2, h2.indexOf(`data-q="12"`)), "___ comes first");
});

test("A9: parseReadingHtml expands multi groups into slots, keeps accept arrays, records missing answers", () => {
  const html = scriptPage(`
const PASSAGES = { "1": {title:"Fixture Passage", qr:"Questions 1-4", html:"<p>Some long enough body text for the passage paragraph filter to keep it. Lorem ipsum dolor sit amet, consectetur adipiscing elit sed do eiusmod tempor.</p>"} };
const GROUPS = {
  g1:{type:"Summary Completion",instr:"Complete the summary. Write <strong>ONE WORD ONLY</strong> for each answer."},
  g2:{type:"Multiple Choice",instr:"Choose <strong>TWO</strong> letters, <strong>A-C</strong>."}
};
const HEADINGS = [];
const ENDINGS = [];
const QUESTIONS = [
  {id:1,p:1,g:'g1',type:'gap',text:"First ___ here."},
  {id:2,p:1,g:'g1',type:'gap',text:"Second ___ here."},
  {id:3,p:1,g:'g2',type:'multi',from:3,to:4,prompt:"Which TWO things?",pick:2,opts:["A) alpha","B) beta","C) gamma"]}
];
const ANSWERS = {1:"alpha", 3:["A","C"], 4:["A","C"]};
`);
  const r = parseReadingHtml(html, { book: 21, test: 9, skill: "reading" });
  assert.equal(r.ok, true);
  assert.equal(r.book, 21);
  assert.deepEqual(r.questions.map((q) => q.number), [1, 2, 3, 4]);
  assert.deepEqual(r.counts.missing_answers, [2]);
  assert.deepEqual(r.counts.duplicate_slots, []);
  assert.equal(r.counts.answers, 3);
  const q3 = r.questions.find((q) => q.number === 3);
  assert.equal(q3.type, "multi");
  assert.equal(q3.slot_kind, "multi_member");
  assert.deepEqual(q3.group_slots, [3, 4]);
  assert.equal(q3.pick, 2);
  assert.equal(q3.options.length, 3);
  assert.deepEqual(q3.options.map((o) => o.label), ["A", "B", "C"]);
  const a3 = r.answer_key.find((e) => e.number === 3);
  assert.equal(a3.kind, "multi_member");
  assert.equal(a3.answer, null);
  assert.deepEqual(a3.accept, ["A", "C"]);
  const a1 = r.answer_key.find((e) => e.number === 1);
  assert.equal(a1.answer, "alpha");
  assert.deepEqual(a1.accept, ["alpha"]);
  assert.equal(r.answer_groups.length, 1);
  assert.deepEqual(r.answer_groups[0].slots, [3, 4]);
  assert.deepEqual(r.answer_groups[0].accept, ["A", "C"]);
  assert.equal(r.answer_groups[0].required_count, 2);
  assert.equal(r.answer_groups[0].source, "questions.multi");
  assert.equal(r.groups.find((g) => g.id === "g1").word_limit, "ONE WORD ONLY");
  assert.equal(r.passages.length, 1);
  assert.deepEqual(r.headings, []);
  assert.deepEqual(r.endings, []);
});

test("A10: parseReadingHtml records duplicate slot numbers instead of shifting", () => {
  const html = scriptPage(`
const PASSAGES = { "1": {title:"T", qr:"", html:"<p>body</p>"} };
const GROUPS = { g1:{type:"gap",instr:"x"} };
const QUESTIONS = [ {id:5,p:1,g:'g1',type:'gap',text:"a"}, {id:5,p:1,g:'g1',type:'gap',text:"b"} ];
const ANSWERS = {5:"a"};
`);
  const r = parseReadingHtml(html, {});
  assert.deepEqual(r.questions.map((q) => q.number), [5]);
  assert.deepEqual(r.counts.duplicate_slots, [5]);
  assert.equal(r.questions[0].prompt, "a");
});

test("A11: parseListeningHtml classifies gap/mcq/multi/letter_match and expands multiCorrect", () => {
  const sec1 = [
    '<p class="q-label">Questions 1-2</p>',
    '<p class="instruction">Complete the notes below.<br><strong>Write ONE WORD ONLY for each answer.</strong></p>',
    '<div class="notes-card"><ul><li>First <span class="qnum-prefix">1</span><input type="text" data-q="1"> done.</li><li>Second <span class="qnum-prefix">2</span><input type="text" data-q="2"> done.</li></ul></div>',
    '<p class="q-label">Questions 3-4</p>',
    '<p class="instruction">Choose the correct letter, <strong>A, B</strong> or <strong>C</strong>.</p>',
    '<div class="mcq-group"><div class="mcq-question"><span class="qnum">3</span> What is X?</div><label class="mcq-option"><span class="opt-letter">A</span> alpha</label><label class="mcq-option"><span class="opt-letter">B</span> beta</label><label class="mcq-option"><span class="opt-letter">C</span> gamma</label></div>',
    '<div class="mcq-group"><div class="mcq-question"><span class="qnum">4</span> What is Y?</div><label class="mcq-option"><span class="opt-letter">A</span> one</label><label class="mcq-option"><span class="opt-letter">B</span> two</label></div>',
    '<p class="q-label">Questions 5 and 6</p>',
    '<p class="instruction">Choose <strong>TWO</strong> letters, <strong>A-C</strong>.</p>',
    '<div class="check-group" data-questions="5,6" data-max="2"><label class="check-option"><span class="opt-letter">A</span> first</label><label class="check-option"><span class="opt-letter">B</span> second</label><label class="check-option"><span class="opt-letter">C</span> third</label></div>',
    '<p class="q-label">Questions 7-8</p>',
    '<p class="instruction">Write the correct letter, <strong>A</strong> or <strong>B</strong>, next to questions 7-8.</p>',
    '<div class="letter-bank"><div class="row"><strong>A</strong> alpha</div><div class="row"><strong>B</strong> beta</div></div>',
    '<p class="q-label">Duties</p>',
    '<div class="label-row"><div class="label-item"><span class="qnum-prefix">7</span><label>First item</label><input type="text" data-q="7"></div><div class="label-item"><span class="qnum-prefix">8</span><label>Second item</label><input type="text" data-q="8"></div></div>',
  ].join("");
  const html = scriptPage(`
const PARTS = { "1": ${JSON.stringify(sec1)} };
const TITLES = { "1": "Fixture Section" };
const audioTracks = { "1": "audio/C21T1_Section_1.mp3" };
const correctAnswers = {"1":"one","3":"B","7":"A","8":"B"};
const multiCorrect = {"5":{"inputs":["5","6"],"accept":["A","C"]}};
const TRANSCRIPTS = {"1":[{"sp":"MAN","h":"Hello there.","t":1.5},{"sp":"","h":"And more.","t":3.25}]};
`);
  const r = parseListeningHtml(html, { book: 21, test: 9, skill: "listening" });
  assert.equal(r.ok, true);
  assert.deepEqual(r.questions.map((q) => q.number), [1, 2, 3, 4, 5, 6, 7, 8]);
  assert.deepEqual(r.counts.missing_answers, [2, 4]);
  assert.equal(r.counts.answer_keys_raw, 5);
  assert.equal(r.counts.answers, 6);
  assert.equal(r.counts.questions_missing.length, 32);
  assert.equal(r.counts.questions_missing[0], 9);
  assert.equal(r.counts.questions_missing[31], 40);
  const q = (n) => r.questions.find((x) => x.number === n);
  assert.equal(q(1).type, "gap");
  assert.ok(q(1).prompt.includes("___"));
  assert.equal(q(3).type, "mcq");
  assert.equal(q(3).prompt, "What is X?");
  assert.deepEqual(q(3).options.map((o) => o.label), ["A", "B", "C"]);
  assert.equal(q(5).type, "multi");
  assert.deepEqual(q(5).group_slots, [5, 6]);
  assert.equal(q(5).required_count, 2);
  assert.deepEqual(q(5).accept, ["A", "C"]);
  assert.deepEqual(q(6).accept, ["A", "C"]);
  assert.equal(q(7).type, "letter_match");
  assert.deepEqual(q(7).options.map((o) => o.label), ["A", "B"]);
  assert.equal(q(7).sublabel, "Duties");
  const a5 = r.answer_key.find((e) => e.number === 5);
  assert.equal(a5.kind, "multi_member");
  assert.equal(a5.answer, null);
  assert.deepEqual(a5.accept, ["A", "C"]);
  const a1 = r.answer_key.find((e) => e.number === 1);
  assert.equal(a1.answer, "one");
  assert.equal(r.answer_groups.length, 1);
  assert.deepEqual(r.answer_groups[0].inputs_raw, ["5", "6"]);
  assert.deepEqual(r.answer_groups[0].slots, [5, 6]);
  assert.equal(r.audio.length, 1);
  assert.equal(r.audio[0].url, "https://raw.githubusercontent.com/maqsudjon-cell/cambridge-21/main/audio/C21T1_Section_1.mp3");
  assert.equal(r.transcript.length, 1);
  assert.equal(r.transcript[0].lines.length, 2);
  assert.equal(r.transcript[0].has_speakers, true);
  assert.equal(r.transcript[0].lines[0].speaker, "MAN");
  assert.equal(r.transcript[0].lines[1].speaker, null);
  assert.equal(r.transcript[0].time_unit, null);
});

test("A12: dataScript picks the largest <script> block", () => {
  const html = `<script>const A = 1;</script><script>const B = "xxxxxxxxxxxxxxxxxxxxxxxxxxxx";</script>`;
  assert.equal(dataScript(html), `const B = "xxxxxxxxxxxxxxxxxxxxxxxxxxxx";`);
  assert.equal(dataScript("<p>no script</p>"), "");
});

test("A13: unsupported literals (template/function/arrow/regex) flagged with raw, never evaluated", () => {
  assert.deepEqual(scanUnsupported("{a: `${x}`}"), ["template_expression"]);
  assert.deepEqual(scanUnsupported("{a: function () { return 1; }}"), ["function_expression"]);
  assert.deepEqual(scanUnsupported("{a: () => 1}"), ["arrow_function"]);
  assert.deepEqual(scanUnsupported("{a: /re/g}"), ["regex_or_division"]);
  assert.deepEqual(scanUnsupported("{a: 1/2}"), ["regex_or_division"]);
  // no false positives: keys named function/functions, strings, comments, escaped ${
  assert.deepEqual(scanUnsupported("{function: 1, functions: [1], functionName: 2}"), []);
  assert.deepEqual(scanUnsupported('{a: "has ${x} and / slash"}'), []);
  assert.deepEqual(scanUnsupported("{a: '\\${esc}'}"), []);
  assert.deepEqual(scanUnsupported("{a: 1 /* / c */, b: 2}"), []);
  assert.deepEqual(scanUnsupported("{a: 1 // / line\n}"), []);
  assert.deepEqual(scanUnsupported("{a: 'function () => {}'}"), []);

  // parseLiteral: keeps raw, returns null, records warning (does not throw)
  const w = [];
  const v = parseLiteral("const X = {a: (() => 1)()};", "X", w);
  assert.equal(v, null);
  assert.equal(w.length, 1);
  assert.equal(w[0].kind, "unsupported_literal");
  assert.equal(w[0].name, "X");
  assert.deepEqual(w[0].problems, ["arrow_function"]);
  assert.ok(w[0].raw.includes("=>"));

  // end-to-end: ANSWERS uses an arrow IIFE → flagged, ok stays true, answer treated as missing
  const page = scriptPage([
    `const PASSAGES = { "1": {title:"T", qr:"", html:"<p>long enough body text to survive the paragraph filter lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor.</p>"} };`,
    `const GROUPS = { g1:{type:"gap",instr:"Write ONE WORD."} };`,
    `const QUESTIONS = [ {id:1,p:1,g:'g1',type:'gap',text:"a"} ];`,
    `const ANSWERS = { 1: (() => "x")() };`,
  ].join("\n"));
  const r = parseReadingHtml(page, { test: 9 });
  assert.equal(r.ok, true);
  assert.equal(r.warnings.length, 1);
  assert.equal(r.warnings[0].kind, "unsupported_literal");
  assert.equal(r.warnings[0].name, "ANSWERS");
  assert.deepEqual(r.counts.missing_answers, [1]);
  assert.equal(r.answer_key.length, 0);
});

/* ================================ Part B ================================ */

test("B1: t1-reading — 40 slots/answers, 3 passages, group/type composition", (t) => {
  const html = requireCam(t, "t1-reading.html");
  if (!html) return;
  const r = parseReadingHtml(html, { test: 1 });
  assert.equal(r.counts.questions, 40);
  assert.equal(r.counts.answers, 40);
  assert.equal(r.counts.answer_keys_raw, 40);
  assert.deepEqual(r.counts.missing_answers, []);
  assert.deepEqual(r.counts.duplicate_slots, []);
  assert.deepEqual(r.passages.map((p) => p.title), ["The Davies Sisters", "Why we need silence", "Book review: The World of Sugar by Ulbe Bosma"]);
  assert.ok(r.passages.every((p) => p.text.length > 500));
  assert.equal(r.groups.length, 8);
  assert.ok(r.groups.every((g) => (g.instruction || "").length > 0));
  assert.deepEqual(countBy(r.questions, "type"), { gap: 11, tfng: 6, info: 15, mcq: 4, ynng: 4 });
  assert.deepEqual(r.headings, []);
  assert.deepEqual(r.endings, []);
  const a9 = r.answer_key.find((e) => e.number === 9);
  assert.deepEqual(a9.accept, ["Not Given"]);
  const a34 = r.answer_key.find((e) => e.number === 34);
  assert.deepEqual(a34.accept, ["A"]);
});

test("B2: t2-reading — multi group Q20/Q21 expanded, accept sets kept unjoined", (t) => {
  const html = requireCam(t, "t2-reading.html");
  if (!html) return;
  const r = parseReadingHtml(html, { test: 2 });
  assert.equal(r.counts.questions, 40);
  assert.equal(r.counts.answers, 40);
  assert.deepEqual(r.counts.missing_answers, []);
  assert.deepEqual(r.counts.duplicate_slots, []);
  assert.equal(r.passages.length, 3);
  assert.equal(r.groups.length, 9);
  assert.deepEqual(countBy(r.questions, "type"), { gap: 10, tfng: 8, info: 12, multi: 2, mcq: 4, ynng: 4 });
  const q20 = r.questions.find((q) => q.number === 20);
  const q21 = r.questions.find((q) => q.number === 21);
  assert.equal(q20.type, "multi");
  assert.equal(q20.slot_kind, "multi_member");
  assert.deepEqual(q20.group_slots, [20, 21]);
  assert.equal(q20.pick, 2);
  assert.equal(q20.options.length, 5);
  assert.deepEqual(q20.options.map((o) => o.label), ["A", "B", "C", "D", "E"]);
  assert.match(q20.prompt, /Which TWO/);
  assert.deepEqual(q21.group_slots, [20, 21]);
  const a20 = r.answer_key.find((e) => e.number === 20);
  const a21 = r.answer_key.find((e) => e.number === 21);
  assert.deepEqual(a20.accept, ["B", "D"]);
  assert.deepEqual(a21.accept, ["B", "D"]);
  assert.equal(a20.answer, null);
  const g = r.answer_groups.find((x) => Array.isArray(x.slots) && x.slots[0] === 20);
  assert.ok(g);
  assert.deepEqual(g.slots, [20, 21]);
  assert.deepEqual(g.accept, ["B", "D"]);
  assert.equal(g.required_count, 2);
  assert.equal(g.source, "questions.multi");
});

test("B3: t3-reading — 40 slots/answers, type composition", (t) => {
  const html = requireCam(t, "t3-reading.html");
  if (!html) return;
  const r = parseReadingHtml(html, { test: 3 });
  assert.equal(r.counts.questions, 40);
  assert.equal(r.counts.answers, 40);
  assert.deepEqual(r.counts.missing_answers, []);
  assert.deepEqual(r.counts.duplicate_slots, []);
  assert.equal(r.passages.length, 3);
  assert.equal(r.groups.length, 7);
  assert.deepEqual(countBy(r.questions, "type"), { gap: 15, tfng: 11, mcq: 4, info: 4, ynng: 6 });
});

test("B4: t4-reading — Q9 accept array (two spellings), Q34 answer present", (t) => {
  const html = requireCam(t, "t4-reading.html");
  if (!html) return;
  const r = parseReadingHtml(html, { test: 4 });
  assert.equal(r.counts.questions, 40);
  assert.equal(r.counts.answers, 40);
  assert.deepEqual(r.counts.missing_answers, []);
  assert.equal(r.groups.length, 9);
  assert.deepEqual(countBy(r.questions, "type"), { tfng: 7, gap: 6, info: 12, ynng: 8, mcq: 7 });
  const a9 = r.answer_key.find((e) => e.number === 9);
  assert.deepEqual(a9.accept, ["fermentation", "fermentation process"]);
  assert.equal(a9.answer, "fermentation");
  const a34 = r.answer_key.find((e) => e.number === 34);
  assert.deepEqual(a34.accept, ["Not Given"]);
});

test("B5: t1-listening — 8 groups, letter banks, multiCorrect strings, speakers present", (t) => {
  const html = requireCam(t, "t1-listening.html");
  if (!html) return;
  const r = parseListeningHtml(html, { test: 1 });
  assert.equal(r.counts.questions, 40);
  assert.equal(r.counts.answers, 40);
  assert.equal(r.counts.answer_keys_raw, 38);
  assert.deepEqual(r.counts.missing_answers, []);
  assert.deepEqual(r.counts.questions_missing, []);
  assert.equal(r.counts.multi_groups, 2);
  assert.equal(r.counts.audio, 4);
  assert.equal(r.counts.transcript_lines, 89);
  assert.deepEqual(countBy(r.questions, "type"), { gap: 20, mcq: 6, multi: 4, letter_match: 10 });
  assert.deepEqual(r.groups.map((g) => [g.from, g.to, g.type]), [
    [1, 6, "gap"], [7, 10, "gap"], [11, 16, "mcq"], [17, 20, "letter_match"],
    [21, 22, "multi"], [23, 24, "multi"], [25, 30, "letter_match"], [31, 40, "gap"],
  ]);
  assert.ok(r.questions.every((q) => q.group != null && (q.prompt || "").length > 0));
  const q17 = r.questions.find((q) => q.number === 17);
  assert.equal(q17.type, "letter_match");
  assert.deepEqual(q17.options.map((o) => o.label), ["A", "B", "C"]);
  assert.ok(q17.prompt.includes("___"));
  const q25 = r.questions.find((q) => q.number === 25);
  assert.equal(q25.type, "letter_match");
  assert.deepEqual(q25.options.map((o) => o.label), ["A", "B", "C", "D", "E", "F", "G", "H"]);
  const g21 = r.answer_groups.find((g) => g.slots.includes(21));
  assert.deepEqual(g21.inputs_raw, ["21", "22"]);
  assert.deepEqual(g21.accept, ["B", "D"]);
  const a21 = r.answer_key.find((e) => e.number === 21);
  assert.equal(a21.kind, "multi_member");
  assert.equal(a21.answer, null);
  assert.deepEqual(a21.accept, ["B", "D"]);
  assert.equal(r.transcript.some((s) => s.has_speakers), true);
  assert.equal(r.audio[0].url, "https://raw.githubusercontent.com/maqsudjon-cell/cambridge-21/main/audio/C21T1_Section_1.mp3");
});

test("B6: t2-listening — 5 multi groups, multiCorrect numeric inputs", (t) => {
  const html = requireCam(t, "t2-listening.html");
  if (!html) return;
  const r = parseListeningHtml(html, { test: 2 });
  assert.equal(r.counts.questions, 40);
  assert.equal(r.counts.answers, 40);
  assert.equal(r.counts.answer_keys_raw, 35);
  assert.deepEqual(r.counts.missing_answers, []);
  assert.deepEqual(r.counts.questions_missing, []);
  assert.equal(r.counts.multi_groups, 5);
  assert.equal(r.counts.transcript_lines, 204);
  assert.deepEqual(countBy(r.questions, "type"), { gap: 26, multi: 10, letter_match: 4 });
  assert.deepEqual(r.questions.filter((q) => q.type === "letter_match").map((q) => q.number), [27, 28, 29, 30]);
  const g11 = r.answer_groups.find((g) => g.slots.includes(11));
  assert.deepEqual(g11.inputs_raw, [11, 12]);
  assert.deepEqual(g11.accept, ["B", "E"]);
  const q15 = r.questions.find((q) => q.number === 15);
  assert.equal(q15.type, "gap");
  assert.ok(q15.prompt.includes("___"));
});

test("B7: t3-listening — transcript speakers all null (source side empty), mcq at 15-16", (t) => {
  const html = requireCam(t, "t3-listening.html");
  if (!html) return;
  const r = parseListeningHtml(html, { test: 3 });
  assert.equal(r.counts.questions, 40);
  assert.equal(r.counts.answers, 40);
  assert.equal(r.counts.answer_keys_raw, 36);
  assert.deepEqual(r.counts.questions_missing, []);
  assert.equal(r.counts.multi_groups, 4);
  assert.equal(r.counts.transcript_lines, 230);
  assert.deepEqual(countBy(r.questions, "type"), { gap: 20, mcq: 2, multi: 8, letter_match: 10 });
  assert.ok(r.transcript.every((s) => s.has_speakers === false));
  assert.ok(r.transcript.every((s) => s.lines.every((l) => l.speaker === null)));
  assert.deepEqual(r.questions.filter((q) => q.type === "mcq").map((q) => q.number), [15, 16]);
});

test("B8: t4-listening — mcq 21-23 + letter bank 15-20/24-30, single-letter answers", (t) => {
  const html = requireCam(t, "t4-listening.html");
  if (!html) return;
  const r = parseListeningHtml(html, { test: 4 });
  assert.equal(r.counts.questions, 40);
  assert.equal(r.counts.answers, 40);
  assert.equal(r.counts.answer_keys_raw, 38);
  assert.deepEqual(r.counts.questions_missing, []);
  assert.equal(r.counts.multi_groups, 2);
  assert.equal(r.counts.transcript_lines, 215);
  assert.deepEqual(countBy(r.questions, "type"), { gap: 20, mcq: 3, multi: 4, letter_match: 13 });
  assert.deepEqual(r.questions.filter((q) => q.type === "letter_match").map((q) => q.number), [15, 16, 17, 18, 19, 20, 24, 25, 26, 27, 28, 29, 30]);
  assert.equal(r.questions.find((q) => q.number === 21).type, "mcq");
  assert.equal(r.questions.find((q) => q.number === 11).type, "multi");
  const ans = (n) => r.answer_key.find((e) => e.number === n).answer;
  assert.equal(ans(21), "B");
  assert.equal(ans(22), "A");
  assert.equal(ans(23), "B");
  assert.equal(ans(24), "B");
});

test("B9: listening transcripts total 738 lines across the four tests", (t) => {
  const totals = [];
  for (const n of [1, 2, 3, 4]) {
    const html = requireCam(t, `t${n}-listening.html`);
    if (!html) return;
    totals.push(parseListeningHtml(html, { test: n }).counts.transcript_lines);
  }
  assert.deepEqual(totals, [89, 204, 230, 215]);
  assert.equal(totals.reduce((a, b) => a + b, 0), 738);
});

test("B10: all 8 real pages carry zero unsupported_literal warnings", (t) => {
  const names = [
    "t1-reading.html", "t2-reading.html", "t3-reading.html", "t4-reading.html",
    "t1-listening.html", "t2-listening.html", "t3-listening.html", "t4-listening.html",
  ];
  let checked = 0;
  for (const name of names) {
    const html = readCam(name);
    if (html == null) continue;
    const r = name.includes("reading") ? parseReadingHtml(html, {}) : parseListeningHtml(html, {});
    assert.deepEqual(r.warnings, [], name + " should have no unsupported literals");
    checked++;
  }
  if (!checked) t.skip("no cam21 HTML available");
  else assert.equal(checked, 8);
});
