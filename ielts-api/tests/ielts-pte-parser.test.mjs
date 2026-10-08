// ielts-api/tests/ielts-pte-parser.test.mjs
// S04 acceptance tests for the pte.mjs parser rewrite (parsePtePage / parseHubLinks / expectedFor).
// Part A: inline fixtures (no network, no local files).
// Part B: assertions against real saved pages in tmp_audit_ielts/completeness_20261003/raw-N.txt
//         (skipped when a raw file is missing).
// Run: node --test ielts-api/tests/ielts-pte-parser.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parsePtePage, parseHubLinks, expectedFor } from "../pte.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const RAW_DIR = path.resolve(__dirname, "..", "..", "tmp_audit_ielts", "completeness_20261003");
const IDX_PATH = path.resolve(__dirname, "..", "..", "ielts-data", "runs", "20261003T140007Z-repair", "evidence", "S04-raw-index.json");

const page = (body) => `<!doctype html><html><head><meta charset="utf-8"></head><body>${body}</body></html>`;
const exp = (numbers) => ({ numbers, max: Math.max(...numbers), expected_total: numbers.length, status: "fixture", source: "fixture" });

let RAW_INDEX = null;
try { RAW_INDEX = JSON.parse(fs.readFileSync(IDX_PATH, "utf8")); } catch { RAW_INDEX = null; }

function parseRaw(n) {
  const p = path.join(RAW_DIR, `raw-${n}.txt`);
  if (!fs.existsSync(p)) return null;
  const meta = RAW_INDEX ? RAW_INDEX.find((x) => x.raw_index === n) : null;
  const skill = meta ? (meta.skill === "reading" ? "academic_reading" : meta.skill) : null;
  const id = { book: meta ? meta.book : null, test: meta ? meta.test : null, skill, slug: meta ? meta.slug : null };
  return { id, out: parsePtePage(fs.readFileSync(p, "utf8"), id, expectedFor(id.book, id.test, skill)) };
}
const qOf = (out, n) => out.questions.find((q) => q.number === n);
const gOf = (out, i) => out.question_groups.find((g) => g.index === i);
const requireRaw = (t, n) => {
  const r = parseRaw(n);
  if (!r) t.skip(`raw-${n}.txt not available`);
  return r;
};

/* ================================ Part A ================================ */

test("A1: OL start / LI value / empty middle+tail LI stay positional; empty answers are null", () => {
  const html = page(`
    <div id="bg-showmore-hidden-1">
      <ol start="11">
        <li>eleven</li>
        <li></li>
        <li value="15">fifteen</li>
        <li></li>
      </ol>
    </div>`);
  const out = parsePtePage(html, { book: 1, test: 1, skill: "listening" }, exp([11, 12, 15, 16]));
  assert.equal(out.ok, true);
  assert.deepEqual(out.answer_slots.map((s) => s.number), [11, 12, 15, 16]);
  assert.deepEqual(out.answer_slots.map((s) => s.raw), ["eleven", "", "fifteen", ""]);
  assert.equal(qOf(out, 11).answer, "eleven");
  assert.equal(qOf(out, 12).answer, null);
  assert.equal(qOf(out, 15).answer, "fifteen");
  assert.equal(qOf(out, 16).answer, null);
  assert.deepEqual(out.answer_missing_detail, [{ number: 12, reason: "empty" }, { number: 16, reason: "empty" }]);
  assert.equal(out.counts.empty_slots, 2);
});

test("A2: answer content after a nested closed div is still collected", () => {
  const html = page(`
    <div id="bg-showmore-hidden-1">
      <div class="wrapper"><span>junk</span></div>
      <p>1. first<br/>2. second</p>
    </div>`);
  const out = parsePtePage(html, {}, exp([1, 2]));
  assert.deepEqual(out.answer_slots.map((s) => [s.number, s.raw]), [[1, "first"], [2, "second"]]);
});

test("A3: empty numbered answers (Q2 / Q34) are null and do not shift later answers", () => {
  const html = page(`
    <div id="bg-showmore-hidden-1"><p>1. a<br/>2.<br/>3. c</p></div>
    <div id="bg-showmore-hidden-2"><p>33. A<br/>34.<br/>35. B</p></div>`);
  const out = parsePtePage(html, {}, exp([1, 2, 3, 33, 34, 35]));
  assert.equal(qOf(out, 1).answer, "a");
  assert.equal(qOf(out, 2).answer, null);
  assert.equal(qOf(out, 3).answer, "c");
  assert.equal(qOf(out, 33).answer, "A");
  assert.equal(qOf(out, 34).answer, null);
  assert.equal(qOf(out, 35).answer, "B");
  assert.deepEqual(out.answer_missing_detail, [{ number: 2, reason: "empty" }, { number: 34, reason: "empty" }]);
});

test("A4: combined forms '23-24. B D' and '25 and 26. C E' map both numbers to the same raw", () => {
  const html = page(`<div id="bg-showmore-hidden-1"><p>23-24. B D<br/>25 and 26. C E</p></div>`);
  const out = parsePtePage(html, {}, exp([23, 24, 25, 26]));
  assert.equal(qOf(out, 23).answer, "B D");
  assert.equal(qOf(out, 24).answer, "B D");
  assert.equal(qOf(out, 25).answer, "C E");
  assert.equal(qOf(out, 26).answer, "C E");
  assert.equal(qOf(out, 23).answer_form, "numbered_range");
  assert.equal(qOf(out, 25).answer_form, "numbered_pair");
});

test("A5: overlapping groups (11-14 + 13-17) keep both group memberships", () => {
  const html = page(`
    <p>Part 2: Questions 11-14</p>
    <p>11. first<br/>12. second<br/>13. third<br/>14. fourth</p>
    <p>Questions 13-17</p>
    <p>13. a<br/>14. b<br/>15. c<br/>16. d<br/>17. e</p>`);
  const out = parsePtePage(html, { book: 8, test: 4, skill: "academic_reading" }, exp([11, 12, 13, 14, 15, 16, 17]));
  assert.deepEqual(qOf(out, 11).groups, [0]);
  assert.deepEqual(qOf(out, 13).groups, [0, 1]);
  assert.deepEqual(qOf(out, 14).groups, [0, 1]);
  assert.deepEqual(qOf(out, 15).groups, [1]);
  assert.deepEqual(gOf(out, 1).numbers, [13, 14, 15, 16, 17]);
});

test("A6: strong-wrapped letter options on separate lines attach to the preceding question", () => {
  const html = page(`
    <p>Questions 1-2</p>
    <p>Choose the correct letter <strong>A</strong>, <strong>B</strong>, <strong>C</strong> or <strong>D</strong>.</p>
    <p>1. What is X?<br/>
      <strong>A</strong> alpha<br/>
      <strong>B</strong> beta<br/>
      <strong>C</strong> gamma<br/>
      <strong>D</strong> delta<br/>
      2. What is Y?<br/>
      <strong>A</strong> one<br/>
      <strong>B</strong> two<br/>
      <strong>C</strong> three<br/>
      <strong>D</strong> four</p>`);
  const out = parsePtePage(html, {}, exp([1, 2]));
  const g = gOf(out, 0);
  assert.equal(g.slots.length, 2);
  assert.deepEqual(g.slots.map((s) => s.options.length), [4, 4]);
  assert.deepEqual(g.slots[0].options.map((o) => o.label), ["A", "B", "C", "D"]);
  assert.equal(g.slots[0].options[0].text, "alpha");
  assert.equal(g.options.length, 0);
});

test("A7: table cells with (N) markers become cell_gap slots", () => {
  const html = page(`
    <p>Questions 10-12</p>
    <table><tr><td>Alpha</td><td>(10)………………</td></tr>
    <tr><td>Beta</td><td>(11) and (12)</td></tr></table>`);
  const out = parsePtePage(html, {}, exp([10, 11, 12]));
  const g = gOf(out, 0);
  assert.deepEqual(g.slots.map((s) => s.number), [10, 11, 12]);
  assert.ok(g.slots.every((s) => s.kind === "cell_gap"));
  assert.match(g.slots[0].prompt, /\(10\)/);
  assert.match(g.slots[2].prompt, /\(12\)/);
});

test("A8: image map page yields gap slots with bare numbers and absolute asset URLs", () => {
  const html = page(`
    <p>Questions 17-20</p>
    <p>Label the map below. Write the correct letter A-G next to questions 17-20.</p>
    <figure><img src="/wp-content/uploads/2024/09/test-78-min-1.png" /></figure>
    <p>17<br/>18<br/>19<br/>20</p>`);
  const out = parsePtePage(html, {}, exp([17, 18, 19, 20]));
  const g = gOf(out, 0);
  assert.deepEqual(g.slots.map((s) => [s.number, s.kind]), [[17, "gap"], [18, "gap"], [19, "gap"], [20, "gap"]]);
  assert.equal(g.slots[0].prompt, "17");
  const img = out.assets.find((a) => a.kind === "image");
  assert.equal(img.url, "https://practicepteonline.com/wp-content/uploads/2024/09/test-78-min-1.png");
});

test("A9: three-passage reading page yields 3 passages with titles and full question coverage", () => {
  const title = (t) => `<p style="text-align: center;"><strong>${t}</strong></p>`;
  const html = page(`
    ${title("THE FIRST TITLE")}
    <p>Body text of the first passage.</p>
    <p>Questions 1-2</p>
    <p>1. q one<br/>2. q two</p>
    ${title("THE SECOND TITLE")}
    <p>Body text of the second passage.</p>
    <p>Questions 3-4</p>
    <p>3. q three<br/>4. q four</p>
    ${title("THE THIRD TITLE")}
    <p>Body text of the third passage.</p>
    <p>Questions 5-6</p>
    <p>5. q five<br/>6. q six</p>`);
  const out = parsePtePage(html, { book: 1, test: 1, skill: "academic_reading" }, exp([1, 2, 3, 4, 5, 6]));
  assert.equal(out.counts.passages, 3);
  assert.deepEqual(out.passages.map((p) => p.title), ["THE FIRST TITLE", "THE SECOND TITLE", "THE THIRD TITLE"]);
  assert.deepEqual(out.questions_missing, []);
  assert.deepEqual(out.passages[0].question_groups, [0]);
  assert.deepEqual(out.passages[2].question_groups, [2]);
});

test("A10: long prompts are not truncated at 400 chars", () => {
  const long = "A 3,000-year-old burial ground of a seafaring people called the Lapita has been found on an abandoned (1) " + "x".repeat(450) + " end";
  const html = page(`<p>Questions 1-2</p><p>${long}</p>`);
  const out = parsePtePage(html, {}, exp([1, 2]));
  const s1 = gOf(out, 0).slots.find((s) => s.number === 1);
  assert.ok(s1.prompt.length > 500);
  assert.ok(s1.prompt.includes("end"));
});

test("A11: a year-like number ('850 AD') does not become an out-of-range question", () => {
  const html = page(`<p>Questions 1-2</p><p>1. first<br/>2. second</p><p>850 AD saw the founding of the city.</p>`);
  const out = parsePtePage(html, {}, exp([1, 2]));
  assert.equal(gOf(out, 0).out_of_range.length, 0);
  assert.ok(!out.warnings.some((w) => w.kind === "out_of_range_question_lines"));
});

test("A12: 41-question listening page keeps Q41 answer", () => {
  const html = page(`
    <p>Questions 40 and 41</p>
    <p>40. first<br/>41. second</p>
    <div id="bg-showmore-hidden-1"><p>40. a<br/>41. b</p></div>`);
  const out = parsePtePage(html, { book: 1, test: 2, skill: "listening" }, exp([40, 41]));
  assert.equal(qOf(out, 41).answer, "b");
  assert.equal(qOf(out, 40).answer, "a");
  assert.equal(out.question_count, 2);
  assert.deepEqual(out.questions_missing, []);
});

test("A13: hub links separate Academic/General and record label conflicts without cross-fill", () => {
  const hub = `
    <a href="https://practicepteonline.com/ielts-reading-test-100/">Academic Reading Test 1</a>
    <a href="/ielts-reading-test-101/">Academic Reading Test 2</a>
    <a href="/ielts-general-reading-test-200/">General Reading Test 1</a>
    <a href="/ielts-reading-test-102/">General Reading Test 3</a>
    <a href="/ielts-listening-test-300/">Listening Test 1</a>
    <a href="/ielts-listening-test-301/">Listening</a>
    <a href="/ielts-reading-test-103/">Test 5</a>
    <a href="/ielts-reading-test-104/">Reading Test 9.2</a>
    <a href="/ielts-writing-test-400/">Writing Test 1</a>
    <a href="/ielts-speaking-test-500/">Speaking Test 1</a>`;
  const r = parseHubLinks(hub, 10);
  assert.equal(r.slots.academic_reading[1], "ielts-reading-test-100");
  assert.equal(r.slots.academic_reading[2], "ielts-reading-test-101");
  assert.equal(r.slots.general_reading[1], "ielts-general-reading-test-200");
  assert.equal(r.slots.listening[1], "ielts-listening-test-300");
  assert.equal(r.slots.writing[1], "ielts-writing-test-400");
  assert.equal(r.slots.speaking[1], "ielts-speaking-test-500");
  assert.deepEqual(Object.keys(r.slots.academic_reading).sort(), ["1", "2"]);
  assert.ok(r.conflicts.some((c) => c.slug === "ielts-reading-test-102" && c.reason === "kind_mismatch"));
  assert.ok(r.unassigned.some((u) => u.slug === "ielts-reading-test-103" && u.reason === "index_out_of_range" && u.index === 5));
  assert.ok(r.conflicts.some((c) => c.slug === "ielts-reading-test-104" && c.reason === "book_mismatch"));
  assert.ok(r.conflicts.some((c) => c.slug === "ielts-listening-test-301" && c.reason === "duplicate_index"));
});

test("A14: instruction 'boxes 29-33' promotes out-of-range lines to slots with provenance", () => {
  const html = page(`
    <p>Questions 29-30</p>
    <p>Complete the notes below. Write your answers in boxes 29-33 on your answer sheet.</p>
    <p>29. Paragraph C<br/>30. Paragraph D<br/>31. Paragraph E<br/>32. Paragraph F<br/>33. Paragraph G</p>`);
  const out = parsePtePage(html, {}, exp([29, 30, 31, 32, 33]));
  const g = gOf(out, 0);
  assert.deepEqual(g.numbers, [29, 30, 31, 32, 33]);
  assert.deepEqual(g.range_extended, { from: [29, 30], to: [29, 33], source: "instruction_boxes" });
  assert.deepEqual(g.out_of_range, []);
  assert.deepEqual(out.questions_missing, []);
  assert.equal(out.question_count, 5);
  const s31 = g.slots.find((s) => s.number === 31);
  assert.equal(s31.kind, "line");
  assert.equal(s31.prompt, "Paragraph E");
});

/* ================================ Part B ================================ */

test("B1: expectedFor carries per-book-test totals from the manifest (no default-40 assumption)", () => {
  const b1l = expectedFor(1, 2, "listening");
  assert.equal(b1l.expected_total, 41);
  assert.equal(b1l.max, 41);
  assert.equal(b1l.numbers.length, 41);
  assert.equal(b1l.status, "verified");
  assert.equal(expectedFor(1, 2, "academic_reading").expected_total, 41);
  assert.equal(expectedFor(1, 1, "listening").expected_total, 41);
  assert.equal(expectedFor(3, 2, "listening").expected_total, 40);
  assert.equal(expectedFor(21, 4, "listening").status, "unverified");
});

test("B2: raw-8 (b1t2 listening) — 41 expected, 39 answered, Q40/41 missing, multi_select group", (t) => {
  const r = requireRaw(t, 8);
  if (!r) return;
  const { out } = r;
  assert.equal(out.question_count, 39);
  assert.equal(out.questions.length, 41);
  assert.deepEqual(out.questions_missing, [40, 41]);
  assert.deepEqual(out.answer_missing, [40, 41]);
  const g4 = gOf(out, 4);
  assert.deepEqual(g4.numbers, [31, 32]);
  assert.deepEqual(g4.slots.map((s) => [s.number, s.kind, s.options.length]), [[31, "multi_select", 5], [32, "multi_select", 5]]);
  assert.match(g4.shared_prompt, /Consumption of Australian bananas/);
  assert.deepEqual(g4.pools[0].options.map((o) => o.label), ["A", "B", "C", "D", "E"]);
  assert.equal(qOf(out, 40).answer, null);
});

test("B3: raw-143 (b10t1 reading) — Q34 empty answer stays null, Q35 keeps its own value", (t) => {
  const r = requireRaw(t, 143);
  if (!r) return;
  const { out } = r;
  assert.equal(out.question_count, 40);
  assert.deepEqual(out.questions_missing, []);
  assert.deepEqual(out.answer_missing, [34]);
  assert.deepEqual(out.answer_missing_detail, [{ number: 34, reason: "empty" }]);
  assert.equal(qOf(out, 34).answer, null);
  assert.equal(qOf(out, 35).answer, "B");
});

test("B4: raw-163 (b11t2 reading) — table group cell_gap slots, missing 20-26, absolute image asset", (t) => {
  const r = requireRaw(t, 163);
  if (!r) return;
  const { out } = r;
  assert.equal(out.question_count, 33);
  assert.deepEqual(out.questions_missing, [20, 21, 22, 23, 24, 25, 26]);
  const g4 = gOf(out, 4);
  assert.deepEqual(g4.numbers, [30, 31, 32, 33, 34, 35, 36]);
  assert.ok(g4.slots.every((s) => s.kind === "cell_gap"));
  assert.match(g4.slots[0].prompt, /to create a \(30\)/);
  assert.equal(qOf(out, 30).answer, "sunshade");
  assert.equal(qOf(out, 36).answer, "rivers");
  assert.equal(out.assets.length, 4);
  assert.equal(out.assets.find((a) => a.kind === "image").url, "https://practicepteonline.com/wp-content/uploads/2024/09/test-78-min-1.png");
});

test("B5: raw-236/267/75/110 — table cell prompts keep inline gaps and answers", (t) => {
  for (const [raw, gi, nums, checks] of [
    [236, 1, [6, 7, 8], [[7, "leaves (and) bark", "(7)……………………and………………….."]]],
    [267, 1, [7, 8, 9, 10, 11, 12, 13], [[9, "Mosquitoes", null], [13, "Houses", null]]],
    [75, 2, [10, 11, 12, 13], [[10, "cheese", null], [13, "jewellery", null]]],
    [110, 6, [31, 32, 33, 34, 35, 36, 37, 38, 39, 40], [[31, "sender", null], [40, "big/ large enough", null]]],
  ]) {
    const r = requireRaw(t, raw);
    if (!r) continue;
    const g = gOf(r.out, gi);
    assert.deepEqual(g.numbers, nums, `raw-${raw} G${gi} numbers`);
    assert.ok(g.slots.every((s) => s.kind === "cell_gap"), `raw-${raw} G${gi} all cell_gap`);
    for (const [n, answer, prompt] of checks) {
      assert.equal(qOf(r.out, n).answer, answer, `raw-${raw} q${n} answer`);
      if (prompt != null) assert.equal(g.slots.find((s) => s.number === n).prompt, prompt, `raw-${raw} q${n} prompt`);
    }
  }
});

test("B6: raw-303/307/315 — reading line-slot kinds, prompts and answers", (t) => {
  {
    const r = requireRaw(t, 303);
    if (r) {
      const s18 = gOf(r.out, 2).slots.find((s) => s.number === 18);
      assert.equal(s18.kind, "line");
      assert.equal(s18.prompt, "reference to the stage at which young elms become vulnerable to Dutch elm disease");
      assert.equal(qOf(r.out, 18).answer, "C");
    }
  }
  {
    const r = requireRaw(t, 307);
    if (r) {
      const s32 = gOf(r.out, 6).slots.find((s) => s.number === 32);
      assert.equal(s32.prompt, "ABSmakes changes to the shape of the strike zone feasible.");
      assert.equal(qOf(r.out, 32).answer, "Yes");
    }
  }
  {
    const r = requireRaw(t, 315);
    if (r) {
      assert.equal(qOf(r.out, 28).answer, "G");
      assert.equal(qOf(r.out, 29).answer, "B");
      assert.deepEqual(gOf(r.out, 5).numbers, [27, 28, 29, 30, 31]);
    }
  }
});

test("B7: derived single-question groups (11 pages) keep A-D options, prompts and answers", (t) => {
  const cases = [
    { raw: 152, group: 6, number: 26, keyword: "offer an explanation", answer: "B" },
    { raw: 35, group: 11, number: 40, keyword: "main purpose", answer: "D" },
    { raw: 37, group: 8, number: 40, keyword: "taken from", answer: "C" },
    { raw: 43, group: 7, number: 27, keyword: "exhibition", answer: "D" },
    { raw: 48, group: 8, number: 40, keyword: "general conclusion", answer: "B" },
    { raw: 56, group: 3, number: 13, keyword: "street children", answer: "A" },
    { raw: 91, group: 8, number: 40, keyword: "suitable title", answer: "D" },
    { raw: 99, group: 9, number: 40, keyword: "main aim", answer: "B" },
    { raw: 127, group: 8, number: 40, keyword: "tortoises", answer: "D" },
    { raw: 131, group: 3, number: 13, keyword: "overall purpose", answer: "C" },
    { raw: 135, group: 2, number: 13, keyword: "purpose in Reading Passage", answer: "B" },
  ];
  for (const c of cases) {
    const r = requireRaw(t, c.raw);
    if (!r) continue;
    const g = gOf(r.out, c.group);
    const s = g.slots.find((x) => x.number === c.number);
    assert.deepEqual(g.numbers, [c.number], `raw-${c.raw} G${c.group} numbers`);
    assert.equal(s.kind, "derived", `raw-${c.raw} q${c.number} kind`);
    assert.equal(s.options.length, 4, `raw-${c.raw} q${c.number} options`);
    assert.ok(s.prompt.includes(c.keyword), `raw-${c.raw} q${c.number} prompt`);
    assert.equal(qOf(r.out, c.number).answer, c.answer, `raw-${c.raw} q${c.number} answer`);
  }
});

test("B8: bare-number gap pages keep prompts and answers", (t) => {
  const cases = [
    { raw: 192, group: 4, number: 26, answer: "curiosity", promptHas: "26" },
    { raw: 219, group: 7, number: 36, answer: "populations", promptHas: "not entire 36" },
    { raw: 256, group: 0, number: 5, answer: "Press", promptHas: "in the 5" },
    { raw: 287, group: 6, number: 38, answer: "Winter", promptHas: "during 38" },
  ];
  for (const c of cases) {
    const r = requireRaw(t, c.raw);
    if (!r) continue;
    const s = gOf(r.out, c.group).slots.find((x) => x.number === c.number);
    assert.equal(s.kind, "gap", `raw-${c.raw} q${c.number} kind`);
    assert.ok(s.prompt.includes(c.promptHas), `raw-${c.raw} q${c.number} prompt`);
    assert.equal(qOf(r.out, c.number).answer, c.answer, `raw-${c.raw} q${c.number} answer`);
  }
});

test("B9: raw-311 (b20t3 listening) — map labels keep 17-20 as gap slots with letter answers", (t) => {
  const r = requireRaw(t, 311);
  if (!r) return;
  const g2 = gOf(r.out, 2);
  assert.deepEqual(g2.slots.map((s) => [s.number, s.kind, s.prompt]), [[17, "gap", "17"], [18, "gap", "18"], [19, "gap", "19"], [20, "gap", "20"]]);
  assert.deepEqual([17, 18, 19, 20].map((n) => qOf(r.out, n).answer), ["B", "A", "G", "E"]);
});

test("B10: raw-122 (b8t4 reading) — interleaved 'B 2 Section' lines keep line_section slots and roman answers", (t) => {
  const r = requireRaw(t, 122);
  if (!r) return;
  const g0 = gOf(r.out, 0);
  assert.deepEqual(g0.slots.map((s) => s.number), [1, 2, 3, 4, 5]);
  assert.deepEqual(g0.slots.slice(1).map((s) => s.kind), ["line_section", "line_section", "line_section", "line_section"]);
  assert.deepEqual(g0.slots.slice(1).map((s) => s.prompt), ["B 2 Section", "C 3 Section", "D 4 Section", "E 5 Section F"]);
  assert.deepEqual([2, 3, 4, 5].map((n) => qOf(r.out, n).answer), ["i", "v", "ii", "viii"]);
});

test("B11: raw-103 pools — 12 single-letter pools, roman pool, A-J pool, TRUE/FALSE/NOT GIVEN", (t) => {
  const r = requireRaw(t, 103);
  if (!r) return;
  const gs = r.out.question_groups;
  assert.deepEqual(gs[0].pools[0].options.map((o) => o.label), ["TRUE", "FALSE", "NOT GIVEN"]);
  assert.equal(gs[1].pools.length, 12);
  assert.deepEqual(gs[1].pools.map((p) => p.options[0].label), ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]);
  assert.deepEqual(gs[2].pools[0].options.map((o) => o.label), ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"]);
  assert.deepEqual(gs[7].pools[0].options.map((o) => o.label), ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]);
});

test("B12: raw-299 (b19t4 reading) — group without letter pool stays pool-less", (t) => {
  const r = requireRaw(t, 299);
  if (!r) return;
  const g1 = gOf(r.out, 1);
  assert.deepEqual(g1.numbers, [7, 8, 9, 10, 11, 12, 13]);
  assert.equal(g1.pools.length, 0);
  assert.equal(g1.slots.length, 7);
});

test("B13: raw-35 (b3t1 reading) — 3 passages; Edit F range extension to boxes 29-33", (t) => {
  const r = requireRaw(t, 35);
  if (!r) return;
  const { out } = r;
  assert.equal(out.question_count, 40);
  assert.deepEqual(out.questions_missing, []);
  assert.equal(out.counts.passages, 3);
  assert.deepEqual(out.passages.map((p) => p.title), ["THE ROCKET \u2013 FROM EAST TO WEST", "The Risks of Cigarette Smoke", "THE SCIENTIFIC METHOD"]);
  const g8 = gOf(out, 8);
  assert.deepEqual(g8.numbers, [29, 30, 31, 32, 33]);
  assert.deepEqual(g8.range_extended, { from: [29, 30], to: [29, 33], source: "instruction_boxes" });
  assert.equal(g8.out_of_range.length, 0);
  assert.deepEqual(g8.slots.map((s) => [s.number, s.kind, s.prompt]), [
    [29, "line_plain", "Paragraph C"],
    [30, "line_plain", "Paragraph D"],
    [31, "line_plain", "Paragraph E"],
    [32, "line_plain", "Paragraph F"],
    [33, "line_plain", "Paragraph G"],
  ]);
});

test("B14: raw-243/180/280 — listening input gaps keep prompts (incl. 'not 10' split) and answers", (t) => {
  {
    const r = requireRaw(t, 243);
    if (r) {
      const s = gOf(r.out, 0).slots.find((x) => x.number === 10);
      assert.equal(s.prompt, "• Send the photos in a box (not 10 )");
      assert.equal(qOf(r.out, 10).answer, "Plastic");
    }
  }
  {
    const r = requireRaw(t, 180);
    if (r) {
      const s = gOf(r.out, 5).slots.find((x) => x.number === 38);
      assert.equal(s.kind, "input");
      assert.equal(s.prompt, "A structure that is more (38) may create a feeling of uncertainty about who staff should report to");
      assert.equal(qOf(r.out, 38).answer, "democratic");
    }
  }
  {
    const r = requireRaw(t, 280);
    if (r) {
      const s = gOf(r.out, 8).slots.find((x) => x.number === 39);
      assert.equal(s.prompt, "2. The information should be combined in one (39)");
      assert.equal(qOf(r.out, 39).answer, "Database");
      assert.deepEqual(gOf(r.out, 8).numbers, [31, 32, 33, 34, 35, 36, 37, 38, 39, 40]);
    }
  }
});

test("B15: shared_prompt 截断 — 阅读组正文不再吞掉下一篇文章/分隔链接（raw-41/raw-127）", (t) => {
  {
    const r = requireRaw(t, 41);
    if (r) {
      const g = gOf(r.out, 4);
      assert.deepEqual(g.numbers, [22, 23, 24, 25]);
      assert.ok(!/HIGHS and LOWS/.test(g.shared_prompt), `raw-41 G4 不应含下一篇文章标题`);
      assert.ok(!/Hormone levels/.test(g.shared_prompt), `raw-41 G4 不应含下一篇文章正文`);
      assert.ok(g.shared_prompt.length < 200, `raw-41 G4 shared_prompt=${g.shared_prompt.length}`);
      assert.equal(r.out.counts.passages, 3);
      assert.equal(r.out.question_count, 40);
      assert.equal(qOf(r.out, 22).answer, "C");
      assert.equal(qOf(r.out, 25).answer, "C");
    }
  }
  {
    const r = requireRaw(t, 127);
    if (r) {
      const g = gOf(r.out, 4);
      assert.deepEqual(g.numbers, [21, 22, 23, 24, 25, 26]);
      assert.ok(!/driest of deserts/.test(g.shared_prompt), `raw-127 G4 不应含下一篇文章正文尾`);
      assert.ok(g.shared_prompt.length < 300, `raw-127 G4 shared_prompt=${g.shared_prompt.length}`);
      assert.deepEqual(g.slots.map((s) => s.number), [21, 22, 23, 24, 25, 26]);
      assert.equal(r.out.counts.passages, 3);
      assert.deepEqual([21, 22, 26].map((n) => qOf(r.out, n).answer), ["true", "true", "false"]);
    }
  }
});
