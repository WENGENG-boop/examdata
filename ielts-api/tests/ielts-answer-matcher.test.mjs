// ielts-api/tests/ielts-answer-matcher.test.mjs
// S07 acceptance tests for answer-matcher.mjs + adjudications.mjs.
// Covers the 12 required acceptance cases from the repair plan plus the
// 45-adjudication migration integrity checks (ids/identity/pdf.sha256/verifier).
// Run: node --test ielts-api/tests/ielts-answer-matcher.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import {
  matchAnswers, compareAnswers, compareGroupAnswer, normalizeAnswer, normalizeChoice,
  expandVariants, numberWordForm, dateForm, choiceFamilyOf, RULES,
} from "../answer-matcher.mjs";
import { DECISIONS, decisionsFor, decisionById, correctionsFor } from "../adjudications.mjs";

// 真实选项表：book 4 test 1 listening p16（来自官方答案页视觉核验 book4_p16_options.txt）
const B4_OPTIONS = [
  { label: "A", text: "must read" },
  { label: "B", text: "useful" },
  { label: "C", text: "limited value" },
  { label: "D", text: "read first section" },
  { label: "E", text: "read research methods" },
  { label: "F", text: "read conclusion" },
  { label: "G", text: "don't read" },
];

const id = (book, test_, skill, extra = {}) => ({ book, test: test_, skill, ...extra });
const cand = (source, identity, entries, extra = {}) => ({
  source, identity, kind: "numbered", entries, ...extra,
});

/* ======================= T1: 空LI不移位 ======================= */

test("T1 空LI不移位：顺序数组中的空值保留原位，不借用下一个非空值", () => {
  const r = matchAnswers({
    identity: id(10, 1, "reading"),
    questions: [{ number: 1 }, { number: 2 }, { number: 3 }],
    expected: { numbers: [1, 2, 3] },
    answerCandidates: [{
      source: "pte_page", identity: id(10, 1, "reading"),
      kind: "answer_key_array", values: ["A", "", "C"], start: 1, order_verified: true,
    }],
  });
  const [q1, q2, q3] = r.questions;
  assert.equal(q1.status, "identity_linked");
  assert.equal(q1.answer, "A");
  assert.equal(q2.status, "missing");
  assert.equal(q2.answer, null);
  assert.equal(q3.status, "identity_linked");
  assert.equal(q3.answer, "C");
  assert.deepEqual(r.coverage.missing, [2]);
});

/* ================== T2: Q34 空答案 / Q41 41题分母 ================== */

test("T2a 剑10 T1 阅读 Q34 空答案保持 missing（不移位、不借用 Q35）", () => {
  const r = matchAnswers({
    identity: id(10, 1, "reading"),
    questions: [31, 32, 33, 34, 35, 36].map((n) => ({ number: n })),
    expected: { numbers: [31, 32, 33, 34, 35, 36] },
    answerCandidates: [{
      source: "pte_page", identity: id(10, 1, "reading"),
      kind: "answer_key_array", values: ["a", "b", "c", "", "e", "f"], start: 31, order_verified: true,
    }],
  });
  const q = (n) => r.questions.find((x) => x.number === n);
  assert.equal(q(34).status, "missing");
  assert.equal(q(34).answer, null);
  assert.equal(q(35).answer, "e");
  assert.equal(q(33).answer, "c");
  assert.deepEqual(r.coverage.missing, [34]);
  assert.equal(r.coverage.processed, 6);
});

test("T2b 剑1 T2 听力 41 题：expected=41 时 Q41 在分母内、不丢失不位移", () => {
  const numbers = Array.from({ length: 41 }, (_, i) => i + 1);
  const values = numbers.map((n) => `ans${n}`);
  const r = matchAnswers({
    identity: id(1, 2, "listening"),
    questions: numbers.map((n) => ({ number: n })),
    expected: { numbers },
    answerCandidates: [{
      source: "pte_page", identity: id(1, 2, "listening"),
      kind: "answer_key_array", values, range: [1, 41], order_verified: true,
    }],
  });
  assert.equal(r.coverage.expected_total, 41);
  assert.equal(r.coverage.processed, 41);
  assert.equal(r.coverage.missing.length, 0);
  assert.equal(r.questions[40].number, 41);
  assert.equal(r.questions[40].answer, "ans41");
});

/* ============ T3/T4: 单字母与长文本直接比较不匹配 ============ */

test("T3 E 与 'read research methods' 直接比较不匹配（禁单字母子串/ token 子集）", () => {
  assert.equal(compareAnswers("E", "read research methods").equal, false);
  assert.equal(compareAnswers("read", "read research methods").equal, false);
  assert.equal(compareAnswers("research methods", "read research methods").equal, false);
  assert.equal(compareAnswers("research", "read research methods").equal, false);
});

test("T4 A 与 'uncooperative landlord' 直接比较不匹配；经真实选项表确认后映射为 A", () => {
  assert.equal(compareAnswers("A", "uncooperative landlord").equal, false);
  // adj-08: 4-1 Q29 官方键 A = uncooperative landlord（option_mapping，none）
  const r = matchAnswers({
    identity: id(4, 1, "listening"),
    questions: [{ number: 29 }],
    groups: [{ group_id: "g-4-1-28-30", numbers: [28, 29, 30], options: [
      { label: "A", text: "uncooperative landlord" }, { label: "B", text: "environment" },
      { label: "C", text: "noisy neighbours" }, { label: "D", text: "near a park" },
    ], instruction: "Choose A-D" }],
    expected: { numbers: [29] },
    answerCandidates: [cand("practicepteonline.com", id(4, 1, "listening"), [{ number: 29, value: "uncooperative landlord" }])],
  });
  const q = r.questions[0];
  assert.equal(q.status, "official_verified");
  assert.equal(q.rule_id, RULES.DECISION_CONFIRMED);
  assert.equal(q.answer, "A");
  assert.equal(q.display.label, "a");
});

/* ============ T5: 真实完整选项文本唯一映射字母 ============ */

test("T5 真实选项文本唯一映射（4-1 Q24 'useful' -> B；禁单字母映射）", () => {
  const r = matchAnswers({
    identity: id(4, 1, "listening"),
    questions: [{ number: 24 }],
    groups: [{ group_id: "g-4-1-23-27", numbers: [23, 24, 25, 26, 27], options: B4_OPTIONS, instruction: "Choose A-G" }],
    expected: { numbers: [24] },
    decisions: [], // 纯映射路径（不借裁决）
    answerCandidates: [cand("practicepteonline.com", id(4, 1, "listening"), [{ number: 24, value: "useful" }])],
  });
  const q = r.questions[0];
  assert.equal(q.display.kind, "letter");
  assert.equal(q.display.label, "b");
  assert.equal(q.candidates[0].mapped_label, "b");
  assert.equal(q.candidates[0].mapping_rule, RULES.MCQ_LETTER_MAP);
  // 完整文本才能映射：截断文本不映射
  const r2 = matchAnswers({
    identity: id(4, 1, "listening"),
    questions: [{ number: 24 }],
    groups: [{ group_id: "g-4-1-23-27", numbers: [23, 24, 25, 26, 27], options: B4_OPTIONS, instruction: "Choose A-G" }],
    expected: { numbers: [24] },
    decisions: [],
    answerCandidates: [cand("practicepteonline.com", id(4, 1, "listening"), [{ number: 24, value: "use" }])],
  });
  assert.equal(r2.questions[0].candidates[0].mapped_label, null);
});

/* ================== T6: 6/Six 需显式允许 ================== */

test("T6 '6' 与 'Six' 默认不判等；numberWord 或 allowed_variants 显式允许才合并", () => {
  assert.equal(compareAnswers("6", "Six").equal, false);
  assert.equal(compareAnswers("6", "Six", { numberWord: true }).equal, true);
  assert.equal(compareAnswers("6", "Six", { allowedVariantsB: ["6"] }).equal, true);
  // 多源合并在 matchAnswers 中同样遵循该规则
  const mk = (expected) => matchAnswers({
    identity: id(9, 1, "listening"),
    questions: [{ number: 5 }],
    expected,
    answerCandidates: [
      cand("srcA", id(9, 1, "listening"), [{ number: 5, value: "6" }]),
      cand("srcB", id(9, 1, "listening"), [{ number: 5, value: "Six" }]),
    ],
  });
  assert.equal(mk({ numbers: [5] }).questions[0].status, "conflict");
  assert.equal(mk({ numbers: [5], numberWord: true }).questions[0].status, "identity_linked");
  assert.equal(mk({ numbers: [5], allowed_variants: { 5: ["Six"] } }).questions[0].status, "identity_linked");
});

/* ============ T7: IN ANY ORDER 数量与重复 ============ */

test("T7 IN ANY ORDER：集合比较拒绝重复；数量不符 -> count_mismatch", () => {
  const spec = { required_count: 3, ordered: false, allow_reuse: false, scoring: "exact_set" };
  assert.equal(compareGroupAnswer(["C", "E", "F"], [["C", "E", "F"]], spec).pass, true);
  assert.equal(compareGroupAnswer(["F", "C", "E"], [["C", "E", "F"]], spec).pass, true);
  const dup = compareGroupAnswer(["C", "C", "E"], [["C", "E", "F"]], spec);
  assert.equal(dup.pass, false);
  assert.equal(dup.reason, "set_mismatch");
  assert.equal(compareGroupAnswer(["C", "E"], [["C", "E", "F"]], spec).reason, "count_mismatch");
  assert.equal(compareGroupAnswer(["C", "E", "F", "G"], [["C", "E", "F"]], spec).reason, "count_mismatch");
});

/* ============ T8: both required 与任选不同 ============ */

test("T8 both required（exact_set）与 any_of 任选不同", () => {
  const both = { required_count: 2, ordered: false, allow_reuse: false, scoring: "exact_set" };
  assert.equal(compareGroupAnswer(["A", "E"], [["A", "E"]], both).pass, true);
  assert.equal(compareGroupAnswer(["A"], [["A", "E"]], both).pass, false);
  const anyOf = { required_count: 2, scoring: "any_of" };
  assert.equal(compareGroupAnswer(["A"], [["A", "E"]], anyOf).pass, true);
  assert.equal(compareGroupAnswer(["E"], [["A", "E"]], anyOf).pass, true);
  assert.equal(compareGroupAnswer(["B"], [["A", "E"]], anyOf).pass, false);
});

/* ============ T9: variant gate（A/G 同题号不互串） ============ */

test("T9 variant gate：A/G 同题号不互串，跨 variant 候选拒绝并保留原因", () => {
  const r = matchAnswers({
    identity: id(14, 1, "reading", { variant: "G" }),
    questions: [{ number: 1 }],
    expected: { numbers: [1] },
    answerCandidates: [
      cand("academic-src", id(14, 1, "reading", { variant: "A" }), [{ number: 1, value: "wrong-book" }]),
      cand("general-src", id(14, 1, "reading", { variant: "G" }), [{ number: 1, value: "right-book" }]),
    ],
  });
  assert.equal(r.questions[0].answer, "right-book");
  const rej = r.rejections.find((x) => x.source === "academic-src");
  assert.ok(rej);
  assert.equal(rej.reason, "identity_variant_mismatch");
  assert.equal(rej.expected, "G");
  assert.equal(rej.actual, "A");
});

/* ============ T10: 来源变化使窄修正失效 ============ */

test("T10 来源值变化使窄修正失效（decision_stale），不强套旧值", () => {
  const r = matchAnswers({
    identity: id(7, 2, "listening"),
    questions: [{ number: 2 }],
    expected: { numbers: [2] },
    answerCandidates: [cand("practicepteonline.com", id(7, 2, "listening"), [{ number: 2, value: "730453x" }])],
  });
  const q = r.questions[0];
  assert.equal(q.answer, "730453x");
  assert.notEqual(q.answer, "(a) dentist");
  assert.ok(r.notes.some((n) => n.kind === "decision_stale" && n.decision_id === "adj-39" && n.expected_from === "730453"));
});

test("T10b 原值命中时应用修正（7-2 Q2 '730453' -> '(a) dentist'）且可溯源", () => {
  const r = matchAnswers({
    identity: id(7, 2, "listening"),
    questions: [{ number: 2 }],
    expected: { numbers: [2] },
    answerCandidates: [cand("practicepteonline.com", id(7, 2, "listening"), [{ number: 2, value: "730453" }])],
  });
  const q = r.questions[0];
  assert.equal(q.status, "official_verified");
  assert.equal(q.rule_id, RULES.DECISION_CORRECTION);
  assert.equal(q.answer, "(a) dentist");
  assert.equal(q.candidates[0].decision_applied, true);
  assert.equal(q.decision.id, "adj-39");
});

/* ============ T11: 无答案题不伪造 ============ */

test("T11 无答案题不伪造：无候选 -> missing、answer null、display null", () => {
  const r = matchAnswers({
    identity: id(10, 1, "reading"),
    questions: [{ number: 1 }, { number: 2 }],
    expected: { numbers: [1, 2] },
    answerCandidates: [cand("pte_page", id(10, 1, "reading"), [{ number: 1, value: "x" }])],
  });
  const q2 = r.questions[1];
  assert.equal(q2.status, "missing");
  assert.equal(q2.answer, null);
  assert.equal(q2.display, null);
  assert.equal(q2.rule_id, RULES.MISSING);
});

/* ============ T12: 错 OCR 不自动成权威 ============ */

test("T12 错OCR不自动成权威：ocr=true 无 visual_verified 封顶 priority 3", () => {
  const r = matchAnswers({
    identity: id(3, 2, "listening"),
    questions: [{ number: 1 }],
    expected: { numbers: [1] },
    answerCandidates: [{
      source: "ocr_page", source_class: "official_pdf", ocr: true,
      identity: id(3, 2, "listening"), kind: "numbered", entries: [{ number: 1, value: "misread" }],
    }],
  });
  assert.equal(r.questions[0].status, "identity_linked");
  assert.equal(r.questions[0].candidates[0].priority, 3);
  // 经视觉核验的原书页才升 official_verified
  const r2 = matchAnswers({
    identity: id(3, 2, "listening"),
    questions: [{ number: 1 }],
    expected: { numbers: [1] },
    answerCandidates: [{
      source: "official_page", source_class: "official_pdf", visual_verified: true,
      identity: id(3, 2, "listening"), kind: "numbered", entries: [{ number: 1, value: "correct" }],
    }],
  });
  assert.equal(r2.questions[0].status, "official_verified");
});

/* ============ 45 条裁决迁移完整性 ============ */

test("ADJ-INTEGRITY 45 条裁决：id 唯一、identity/pdf.sha256/verifier 齐备、分类计数一致", () => {
  assert.equal(DECISIONS.length, 45);
  const ids = new Set();
  for (const d of DECISIONS) {
    assert.ok(d.id && !ids.has(d.id), `dup id ${d.id}`);
    ids.add(d.id);
    assert.equal(d.identity.skill, "listening", d.id);
    assert.ok(Number.isInteger(d.identity.book) && Number.isInteger(d.identity.test) && Number.isInteger(d.identity.question), d.id);
    assert.ok(d.pdf && /^[0-9a-f]{64}$/.test(d.pdf.sha256), `${d.id} pdf.sha256`);
    assert.ok(d.pdf.file && Number.isInteger(d.pdf.page), `${d.id} pdf ref`);
    assert.ok(d.verifier && d.verifier.type === "independent_visual_review" && d.verifier.at, `${d.id} verifier`);
    assert.ok(typeof d.basis === "string" && d.basis.length > 0, `${d.id} basis`);
    assert.ok(d.official_extracted != null, `${d.id} official_extracted`);
    assert.ok(["correct", "none"].includes(d.action), `${d.id} action=${d.action}`);
    assert.ok(["diff", "masked_by_comparator_bug"].includes(d.origin), `${d.id} origin`);
  }
  const cats = {};
  for (const d of DECISIONS) cats[d.category] = (cats[d.category] || 0) + 1;
  assert.deepEqual(cats, {
    option_mapping: 8, representation: 7, source_error: 7, order_semantics: 14, extraction_artifact: 9,
  });
  assert.equal(DECISIONS.filter((d) => d.action === "correct").length, 7);
  assert.equal(DECISIONS.filter((d) => d.action === "none").length, 38);
});

test("ADJ-7CORR 7 条窄修正逐条生效 + 原值守卫", () => {
  const corrections = DECISIONS.filter((d) => d.action === "correct");
  assert.equal(corrections.length, 7);
  for (const d of corrections) {
    const r = matchAnswers({
      identity: id(d.identity.book, d.identity.test, "listening"),
      questions: [{ number: d.identity.question }],
      expected: { numbers: [d.identity.question] },
      answerCandidates: [cand("practicepteonline.com", id(d.identity.book, d.identity.test, "listening"), [{ number: d.identity.question, value: d.from }])],
    });
    const q = r.questions[0];
    assert.equal(q.status, "official_verified", d.id);
    assert.equal(q.answer, d.to, d.id);
    assert.equal(q.rule_id, RULES.DECISION_CORRECTION, d.id);
    // 原值守卫：换一个值不套用
    const r2 = matchAnswers({
      identity: id(d.identity.book, d.identity.test, "listening"),
      questions: [{ number: d.identity.question }],
      expected: { numbers: [d.identity.question] },
      answerCandidates: [cand("practicepteonline.com", id(d.identity.book, d.identity.test, "listening"), [{ number: d.identity.question, value: d.from + "!" }])],
    });
    assert.notEqual(r2.questions[0].answer, d.to, d.id);
  }
  // correctionsFor 可溯源到 basis/decision_id
  const c = correctionsFor(7, 2).get(2);
  assert.equal(c.from, "730453");
  assert.equal(c.to, "(a) dentist");
  assert.equal(c.decision_id, "adj-39");
});

test("ADJ-GROUPS 组裁决合并：5-2 Q18-20 无候选时由官方集合覆盖为 official_verified", () => {
  const r = matchAnswers({
    identity: id(5, 2, "listening"),
    questions: [18, 19, 20].map((n) => ({ number: n })),
    expected: { numbers: [18, 19, 20] },
    answerCandidates: [],
  });
  for (const q of r.questions) assert.equal(q.status, "official_verified");
  const g = r.groups.find((x) => x.group_id === "g-5-2-18-20");
  assert.ok(g);
  assert.deepEqual(g.accepted_sets, [["C", "E", "F"]]);
  assert.equal(g.required_count, 3);
  assert.equal(g.ordered, false);
  // 组集合比较：正确集合通过、重复拒绝
  assert.equal(compareGroupAnswer(["F", "C", "E"], g.accepted_sets, g).pass, true);
  assert.equal(compareGroupAnswer(["C", "C", "E"], g.accepted_sets, g).pass, false);
});

test("ADJ-12-1 剑12 T1 组 g-12-1-15-16 [A,E] 与 Q14 单值并存", () => {
  const r = matchAnswers({
    identity: id(12, 1, "listening"),
    questions: [14, 15, 16].map((n) => ({ number: n })),
    expected: { numbers: [14, 15, 16] },
    answerCandidates: [],
  });
  const g = r.groups.find((x) => x.group_id === "g-12-1-15-16");
  assert.ok(g);
  assert.deepEqual(g.accepted_sets, [["A", "E"]]);
  assert.equal(g.required_count, 2);
  const q15 = r.questions.find((x) => x.number === 15);
  assert.equal(q15.status, "official_verified");
  assert.equal(q15.display.kind, "set");
});

/* ============ 家族 / Roman / 有序组 / 规范化 ============ */

test("TFNG 与 YNNG 分别标准化，不互相混同；家族由题组指令推断", () => {
  assert.equal(compareAnswers("T", "TRUE", { family: "tfng" }).equal, true);
  assert.equal(compareAnswers("F", "FALSE", { family: "tfng" }).equal, true);
  assert.equal(compareAnswers("NG", "NOT GIVEN", { family: "tfng" }).equal, true);
  assert.equal(compareAnswers("Y", "YES", { family: "ynng" }).equal, true);
  assert.equal(compareAnswers("N", "NO", { family: "ynng" }).equal, true);
  assert.equal(compareAnswers("Y", "TRUE", { family: "tfng" }).equal, false);
  assert.equal(compareAnswers("T", "TRUE", { family: "ynng" }).equal, false);
  assert.equal(normalizeChoice("NotGiven", "tfng"), "not given");
  assert.equal(choiceFamilyOf("Do the following statements agree with the information given? TRUE FALSE NOT GIVEN"), "tfng");
  assert.equal(choiceFamilyOf("YES NO NOT GIVEN"), "ynng");
  assert.equal(choiceFamilyOf("Choose the correct letter A-D"), null);
});

test("Roman heading 标签：单字符不判等；完整文本唯一映射", () => {
  assert.equal(compareAnswers("i", "ii").equal, false);
  assert.equal(compareAnswers("iv", "v").equal, false);
  assert.equal(compareAnswers("iii", "iii").equal, true);
  const r = matchAnswers({
    identity: id(4, 3, "reading"),
    questions: [{ number: 14 }],
    groups: [{
      group_id: "g-4-3-headings", numbers: [14, 15, 16],
      options: [{ label: "i", text: "introduction" }, { label: "ii", text: "conclusion" }, { label: "iii", text: "methods" }],
      instruction: "Choose the correct heading i-iii",
    }],
    expected: { numbers: [14] },
    decisions: [],
    answerCandidates: [cand("pte", id(4, 3, "reading"), [{ number: 14, value: "conclusion" }])],
  });
  assert.equal(r.questions[0].display.label, "ii");
});

test("ordered 组按位置逐位比较（per_slot）", () => {
  const spec = { ordered: true, scoring: "per_slot" };
  assert.equal(compareGroupAnswer(["A", "B", "C"], [["A", "B", "C"]], spec).pass, true);
  assert.equal(compareGroupAnswer(["B", "A", "C"], [["A", "B", "C"]], spec).pass, false);
  assert.equal(compareGroupAnswer(["A", "B"], [["A", "B", "C"]], spec).pass, false);
  assert.equal(compareGroupAnswer(["A", "B", "C"], [["A", "B", "C"]], spec).reason, "ordered_match");
});

test("identity gate 拒绝跨册/跨技能/缺身份候选并保留原因", () => {
  const r = matchAnswers({
    identity: id(10, 1, "reading"),
    questions: [{ number: 1 }],
    expected: { numbers: [1] },
    answerCandidates: [
      cand("wrong-book", id(11, 1, "reading"), [{ number: 1, value: "x" }]),
      cand("wrong-skill", id(10, 1, "listening"), [{ number: 1, value: "y" }]),
      { source: "no-identity", kind: "numbered", entries: [{ number: 1, value: "z" }] },
    ],
  });
  assert.equal(r.questions[0].status, "missing");
  assert.equal(r.rejections.length, 3);
  const reasons = r.rejections.map((x) => x.reason).sort();
  assert.deepEqual(reasons, ["identity_book_mismatch", "identity_missing", "identity_skill_mismatch"]);
});

test("顺序数组容器未验证时 order_unverified，不按序号均分、不补位", () => {
  const r = matchAnswers({
    identity: id(10, 1, "reading"),
    questions: [{ number: 1 }, { number: 2 }, { number: 3 }],
    expected: { numbers: [1, 2, 3] },
    answerCandidates: [{
      source: "pte_page", identity: id(10, 1, "reading"),
      kind: "answer_key_array", values: ["A", "B", "C"], start: 1, order_verified: false,
    }],
  });
  for (const q of r.questions) assert.equal(q.status, "order_unverified");
  assert.ok(r.notes.some((n) => n.kind === "order_unverified"));
});

test("规范化：NFKC/弯引号/破折号/空白/大小写；显式备选展开", () => {
  assert.equal(normalizeAnswer("  Hello\u2019s   World  "), "hello's world");
  assert.equal(normalizeAnswer("A\u2013B\u2014C"), "a-b-c");
  assert.equal(normalizeAnswer("ＡＢＣ"), "abc");
  const v = expandVariants("(a) dentist");
  assert.ok(v.includes("a dentist") && v.includes("dentist") && v.includes("(a) dentist"));
  const w = expandVariants("beach / beaches");
  assert.ok(w.includes("beach") && w.includes("beaches"));
  const x = expandVariants("send (out/the) newsletter(s)");
  assert.ok(x.includes("send out newsletter") && x.includes("send newsletter"));
  assert.equal(compareAnswers("(a) dentist", "dentist").equal, true);
  assert.equal(compareAnswers("beach", "beaches").equal, false);
});

test("numberWord/dateVariants 为显式 opt-in；日期变体", () => {
  assert.equal(numberWordForm("six"), "6");
  assert.equal(numberWordForm("6"), "6");
  assert.equal(numberWordForm("1,000"), "1000");
  assert.equal(dateForm("1.2.2020"), "2020-02-01");
  assert.equal(compareAnswers("six", "6").equal, false);
  assert.equal(compareAnswers("six", "6", { numberWord: true }).equal, true);
  assert.equal(compareAnswers("1.2.2020", "01/02/2020").equal, false);
  assert.equal(compareAnswers("1.2.2020", "01/02/2020", { dateVariants: true }).equal, true);
});

test("多镜像同一 upstream 不算独立双源：同值不冲突、异值同 upstream 不升级冲突", () => {
  const mk = (v) => matchAnswers({
    identity: id(8, 1, "listening"),
    questions: [{ number: 1 }],
    expected: { numbers: [1] },
    decisions: [],
    answerCandidates: [
      { ...cand("mirrorA", id(8, 1, "listening"), [{ number: 1, value: v }]), upstream: "same-hub" },
      { ...cand("mirrorB", id(8, 1, "listening"), [{ number: 1, value: v }]), upstream: "same-hub" },
    ],
  });
  const q = mk("same").questions[0];
  assert.equal(q.status, "identity_linked");
  assert.equal(q.conflicts.length, 0);
});

test("冲突保留各来源与原值，显示最佳优先级候选（不静默选一个）", () => {
  const r = matchAnswers({
    identity: id(8, 1, "listening"),
    questions: [{ number: 1 }],
    expected: { numbers: [1] },
    decisions: [],
    answerCandidates: [
      { ...cand("pte", id(8, 1, "listening"), [{ number: 1, value: "cat" }]), verified: true, source_class: "structured_source" },
      { ...cand("official_page", id(8, 1, "listening"), [{ number: 1, value: "dog" }]), source_class: "official_pdf", visual_verified: true },
    ],
  });
  const q = r.questions[0];
  assert.equal(q.status, "conflict");
  assert.equal(q.display.conflict, true);
  assert.equal(q.answer, "dog");
  assert.equal(q.conflicts.length, 2);
  const vals = q.conflicts.map((c) => c.value).sort();
  assert.deepEqual(vals, ["cat", "dog"]);
  assert.ok(q.conflicts.every((c) => Array.isArray(c.sources) && c.sources.length >= 1));
});

test("组规格拒绝跨组/越界 input_numbers；组内覆盖不依赖解析组 id 一致", () => {
  const r = matchAnswers({
    identity: id(6, 2, "listening"),
    questions: [18, 19, 20, 21].map((n) => ({ number: n })),
    groups: [{ group_id: "parsed-g1", numbers: [18, 19, 20], instruction: "Choose THREE letters A-G" }],
    expected: { numbers: [18, 19, 20, 21] },
    answerCandidates: [{
      source: "pte", identity: id(6, 2, "listening"), kind: "group",
      group_id: "g-6-2-18-20", input_numbers: [18, 19, 20], accepted_sets: [["C", "D", "G"]], required_count: 3,
    }],
  });
  const g = r.groups.find((x) => x.group_id === "g-6-2-18-20");
  assert.ok(g);
  // 解析组 id 不同但 input_numbers 相同 -> 合并覆盖 Q18-20
  const q18 = r.questions.find((x) => x.number === 18);
  assert.equal(q18.status, "official_verified");
  assert.equal(q18.group_ref.group_id, "g-6-2-18-20");
  // Q21 不在组内 -> 不受组覆盖
  assert.equal(r.questions.find((x) => x.number === 21).status, "missing");
});

test("allowed_variants 多源 union 合并：显式允许时才归一，单字母保护不放松", () => {
  const r = matchAnswers({
    identity: id(9, 1, "listening"),
    questions: [{ number: 5 }],
    expected: { numbers: [5] },
    decisions: [],
    answerCandidates: [
      cand("srcA", id(9, 1, "listening"), [{ number: 5, value: "6" }]),
      cand("srcB", id(9, 1, "listening"), [{ number: 5, value: "Six", allowed_variants: ["6"] }]),
    ],
  });
  assert.equal(r.questions[0].status, "identity_linked");
  assert.equal(r.questions[0].conflicts.length, 0);
  // E 与长文本仍不合并：allowed_variants 只有显式声明才生效，子串永不自动判等
  const r2 = matchAnswers({
    identity: id(9, 1, "listening"),
    questions: [{ number: 6 }],
    expected: { numbers: [6] },
    decisions: [],
    answerCandidates: [
      cand("srcA", id(9, 1, "listening"), [{ number: 6, value: "E" }]),
      cand("srcB", id(9, 1, "listening"), [{ number: 6, value: "read research methods" }]),
    ],
  });
  assert.equal(r2.questions[0].status, "conflict");
  assert.equal(compareAnswers("E", "read research methods").equal, false);
});

test("coverage 汇总：expected_total/answered/missing 准确，缺答案题计入分母", () => {
  const r = matchAnswers({
    identity: id(10, 1, "reading"),
    questions: [1, 2, 3, 4].map((n) => ({ number: n })),
    expected: { numbers: [1, 2, 3, 4] },
    answerCandidates: [{
      source: "pte_page", identity: id(10, 1, "reading"),
      kind: "answer_key_array", values: ["a", "", "c", "d"], start: 1, order_verified: true,
    }],
  });
  assert.equal(r.coverage.expected_total, 4);
  assert.equal(r.coverage.processed, 4);
  assert.equal(r.coverage.answered, 3);
  assert.deepEqual(r.coverage.missing, [2]);
  assert.equal(r.coverage.status_counts.missing, 1);
});

test("decisionById 与 decisionsFor 按 identity 过滤（跨册不串）", () => {
  assert.equal(decisionById("adj-39").identity.book, 7);
  assert.equal(decisionById("nope"), null);
  const d72 = decisionsFor(7, 2);
  assert.ok(d72.length >= 2);
  assert.ok(d72.every((d) => d.identity.book === 7 && d.identity.test === 2));
  assert.equal(decisionsFor(7, 1).length, 0);
});

/* ============ compare-official.mjs（唯一新比较路径） ============ */

test("COMPARE-TOOL 逐题 match/conflict/pdf_only/missing 判定", async () => {
  const { compareOfficial } = await import("../tools/compare-official.mjs");
  const identity = id(10, 1, "reading");
  const out = compareOfficial({
    identity,
    pdfCandidates: {
      source: "book10_p145_visual",
      identity,
      entries: [
        { number: 1, value: "FALSE", page: 145, sha256: "a".repeat(64), visual_verified: true },
        { number: 2, value: "TRUE", page: 145, sha256: "a".repeat(64), visual_verified: true },
        { number: 3, value: "F", page: 145, sha256: "a".repeat(64), visual_verified: true },
      ],
    },
    answerCandidates: {
      source: "pte", identity, kind: "answer_key_array",
      values: ["FALSE", "FALSE", ""], start: 1, order_verified: true,
    },
    groups: [],
    expected: "1-3",
    noDecisions: true,
  });
  assert.equal(out.ok, true);
  const v = (n) => out.items.find((x) => x.number === n).verdict;
  assert.equal(v(1), "match");
  assert.equal(v(2), "conflict");
  assert.equal(v(3), "pdf_only");
  assert.equal(out.summary.match, 1);
  assert.equal(out.summary.conflict, 1);
  assert.equal(out.summary.pdf_only, 1);
  assert.equal(out.summary.unverified, 1);
  // 无 PDF、无答案 -> missing
  const out2 = compareOfficial({
    identity,
    pdfCandidates: { entries: [{ number: 1, value: "x", visual_verified: true }] },
    answerCandidates: [{ source: "pte", identity, kind: "numbered", entries: [{ number: 1, value: "x" }] }],
    expected: "1-2",
    noDecisions: true,
  });
  assert.equal(out2.items.find((x) => x.number === 2).verdict, "missing");
  assert.equal(out2.summary.missing, 1);
  // 单字母保护在工具层同样生效：'E' vs 'read research methods' 为 conflict 而非 match
  const out3 = compareOfficial({
    identity,
    pdfCandidates: { entries: [{ number: 1, value: "E", visual_verified: true }] },
    answerCandidates: [{ source: "pte", identity, kind: "numbered", entries: [{ number: 1, value: "read research methods" }] }],
    expected: "1",
    noDecisions: true,
  });
  assert.equal(out3.items[0].verdict, "conflict");
});
