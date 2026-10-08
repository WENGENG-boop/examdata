// ielts-api/tests/ielts-taxonomy.test.mjs
// S08 acceptance tests for taxonomy.mjs (23 题型统一分类) and question-index.mjs (统一题目索引).
// Part A: inline fixtures (no network, no local files).
// Part B: invariants against the real built index
//         ielts-data/runs/20261003T140007Z-repair/index/question-index.json (skipped when absent).
// Run: node --test ielts-api/tests/*.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  QUESTION_TYPES,
  SKILLS,
  VARIANTS,
  TYPE_FAMILIES,
  typeFamily,
  typeLabel,
  resolveTypeName,
  resolveSkillName,
  resolveVariantName,
  sourceTypeToCanonical,
  matchInstruction,
  deriveStructure,
  judgementFromPools,
  classifyGroup,
} from "../taxonomy.mjs";
import {
  INDEX_SCHEMA,
  CONTENT_STATUS,
  ANSWER_STATUS,
  CLASSIFICATION_STATUS,
  resolveFamilyName,
  normTest,
  skillVariantOf,
  parseWordLimit,
  partOfNumber,
  passageTextOf,
  contentStatusOf,
  buildFromPtePage,
  buildFromCam21Page,
  buildIndex,
  queryIndex,
  summarize,
  applyGroupVerifications,
} from "../question-index.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_ROOT = process.env.EXAMDATA_IELTS_DATA_DIR || path.resolve(__dirname, "..", "..", "ielts-data");
const REAL_INDEX_PATH = path.join(DATA_ROOT, "runs", "20261003T140007Z-repair", "index", "question-index.json");

/* ================================ Part A: taxonomy ================================ */

test("A1: 23 canonical types resolve to themselves; zh/en labels + aliases resolve", () => {
  assert.equal(QUESTION_TYPES.length, 23);
  for (const t of QUESTION_TYPES) {
    assert.equal(resolveTypeName(t), t, `canonical ${t}`);
    assert.equal(resolveTypeName(t.replace(/_/g, " ")), t, `spaced ${t}`);
  }
  assert.equal(resolveTypeName("单项选择"), "multiple_choice_single");
  assert.equal(resolveTypeName("多项选择"), "multiple_choice_multiple");
  assert.equal(resolveTypeName("判断正误"), "true_false_not_given");
  assert.equal(resolveTypeName("观点判断"), "yes_no_not_given");
  assert.equal(resolveTypeName("标题匹配"), "matching_headings");
  assert.equal(resolveTypeName("MCQ"), "multiple_choice_single");
  assert.equal(resolveTypeName("TFNG"), "true_false_not_given");
  assert.equal(resolveTypeName("choose two letters"), "multiple_choice_multiple");
  assert.equal(resolveTypeName("True / False / Not Given"), "true_false_not_given");
  assert.equal(resolveTypeName("list of headings"), "matching_headings");
  assert.equal(resolveTypeName("banana"), null);
  assert.equal(resolveTypeName(null), null);
  assert.equal(typeLabel("multiple_choice_single", "zh"), "单项选择");
  assert.equal(typeLabel("multiple_choice_single"), "Multiple choice (single answer)");
  assert.equal(typeLabel("nope"), null);
});

test("A2: skill/variant names resolve from en/zh/alias; families cover all types", () => {
  for (const s of SKILLS) assert.equal(resolveSkillName(s), s);
  assert.equal(resolveSkillName("听力"), "listening");
  assert.equal(resolveSkillName("Reading"), "reading");
  assert.equal(resolveSkillName("口语"), "speaking");
  assert.equal(resolveSkillName("nope"), null);
  for (const v of VARIANTS) assert.equal(resolveVariantName(v), v);
  assert.equal(resolveVariantName("GT"), "general");
  assert.equal(resolveVariantName("General Training"), "general");
  assert.equal(resolveVariantName("学术"), "academic");
  assert.equal(resolveVariantName("通用"), "shared");
  assert.equal(resolveVariantName("nope"), null);
  for (const t of QUESTION_TYPES) {
    assert.equal(typeFamily(t), TYPE_FAMILIES[t], `family ${t}`);
    assert.ok(TYPE_FAMILIES[t], `family defined for ${t}`);
  }
  assert.equal(typeFamily("nope"), null);
});

test("A3: sourceTypeToCanonical maps canonical/semantic/mcq-variant forms; rejects unknown", () => {
  assert.equal(sourceTypeToCanonical("note completion"), "note_completion");
  assert.equal(sourceTypeToCanonical("matching people"), "matching_features");
  assert.equal(sourceTypeToCanonical("map plan labeling"), "map_plan_labeling");
  assert.equal(sourceTypeToCanonical("Multiple Choice (choose TWO)"), "multiple_choice_multiple");
  assert.equal(sourceTypeToCanonical("Multiple choice (choose three)"), "multiple_choice_multiple");
  assert.equal(sourceTypeToCanonical("Multiple Choice"), "multiple_choice_single");
  assert.equal(sourceTypeToCanonical("Multiple Choice (choose one)"), "multiple_choice_single");
  assert.equal(sourceTypeToCanonical("summary completion"), "summary_completion");
  assert.equal(sourceTypeToCanonical("banana"), null);
  assert.equal(sourceTypeToCanonical(null), null);
});

test("A4: matchInstruction hits each rule family; writing/speaking gated by skill", () => {
  const hit = (text, skill) => {
    const m = matchInstruction(text, skill);
    return m ? m.type : null;
  };
  assert.equal(hit("Complete each sentence with the correct ending, A–H below."), "matching_sentence_endings");
  assert.equal(hit("Match each sentence with the correct ending."), "matching_sentence_endings");
  assert.equal(hit("Choose the correct heading for each paragraph from the list of headings below."), "matching_headings");
  assert.equal(hit("Which paragraph contains the following information?"), "matching_information");
  assert.equal(hit("In which section does the writer mention the cost?"), "matching_information");
  assert.equal(hit("Label the diagram below."), "diagram_labeling");
  assert.equal(hit("Complete the labels on the diagram."), "diagram_labeling");
  assert.equal(hit("Label the map below."), "map_plan_labeling");
  assert.equal(hit("Complete the flow-chart below."), "flow_chart_completion");
  assert.equal(hit("Complete the form below."), "form_completion");
  assert.equal(hit("Complete the notes below."), "note_completion");
  assert.equal(hit("Complete the table below."), "table_completion");
  assert.equal(hit("Complete the summary below."), "summary_completion");
  assert.equal(hit("Complete the sentences below."), "sentence_completion");
  assert.equal(hit("Do the following statements agree with the claims of the writer?"), "yes_no_not_given");
  assert.equal(hit("Write YES if the statement agrees with the views of the writer."), "yes_no_not_given");
  assert.equal(hit("Do the following statements agree with the information given in the text?"), "true_false_not_given");
  assert.equal(hit("Match each person with the correct statement."), "matching_features");
  assert.equal(hit("Choose TWO letters, A–E."), "multiple_choice_multiple");
  assert.equal(hit("Choose the correct letter, A, B or C."), "multiple_choice_single");
  assert.equal(hit("Answer the following questions."), "short_answer");
  assert.equal(hit("Task 1", "writing"), "writing_task1");
  assert.equal(hit("Task 2", "writing"), "writing_task2");
  assert.equal(hit("Task 1", "listening"), null);
  assert.equal(hit("Part 2", "speaking"), "speaking_part2");
  assert.equal(hit("Part 3", "speaking"), "speaking_part3");
  assert.equal(hit("Part 1", "reading"), null);
  assert.equal(matchInstruction(""), null);
  assert.equal(matchInstruction(null), null);
});

test("A5: deriveStructure + judgementFromPools extract slots/pools/prompts", () => {
  const s = deriveStructure({
    slots: [
      { number: 1, kind: "gap", prompt: "same" },
      { number: 2, kind: "gap", prompt: "same" },
    ],
    pools: [{ kind: "judgement", options: [{ label: "YES" }, { label: "NO" }] }],
  });
  assert.equal(s.slot_count, 2);
  assert.deepEqual(s.slot_kinds, ["gap"]);
  assert.equal(s.has_pool, true);
  assert.deepEqual(s.pool_kinds, ["judgement"]);
  assert.deepEqual(s.pool_labels, ["YES", "NO"]);
  assert.equal(s.same_prompt_slots, true);
  assert.equal(s.has_slot_options, false);
  assert.equal(judgementFromPools(s), "yes_no_not_given");
  assert.equal(judgementFromPools(deriveStructure({ pools: [{ kind: "judgement", options: [{ label: "TRUE" }, { label: "FALSE" }] }] })), "true_false_not_given");
  assert.equal(judgementFromPools(deriveStructure({ pools: [{ kind: "choice", options: [{ label: "A" }, { label: "B" }] }] })), null);
  assert.equal(judgementFromPools(null), null);
});

test("A6: classifyGroup — source+instruction agree; conflict keeps candidates", () => {
  const ok = classifyGroup({ source_type: "note completion", instruction: "Complete the notes below.", skill: "listening" });
  assert.equal(ok.type, "note_completion");
  assert.equal(ok.status, "classified");
  assert.equal(ok.reason, "source_type+instruction");
  const ok2 = classifyGroup({ source_type: "matching information", instruction: "Which paragraph contains the following information?", skill: "reading" });
  assert.equal(ok2.type, "matching_information");
  const conflict = classifyGroup({ source_type: "summary completion", instruction: "Choose the correct heading for each paragraph from the list of headings below.", skill: "reading" });
  assert.equal(conflict.type, "unknown");
  assert.equal(conflict.status, "conflict");
  assert.deepEqual(conflict.candidates, ["summary_completion", "matching_headings"]);
});

test("A7: classifyGroup — instruction-only; generic hint mismatch recorded; pool overrides judgement", () => {
  const instrOnly = classifyGroup({ instruction: "Which paragraph contains the following information?", skill: "reading" });
  assert.equal(instrOnly.type, "matching_information");
  assert.equal(instrOnly.reason, "instruction");
  const hintOk = classifyGroup({ source_type: "gap", instruction: "Complete the notes below.", skill: "listening" });
  assert.equal(hintOk.type, "note_completion");
  assert.deepEqual(hintOk.notes || [], []);
  const hintBad = classifyGroup({ source_type: "gap", instruction: "Choose the correct letter, A, B or C.", skill: "listening" });
  assert.equal(hintBad.type, "multiple_choice_single");
  assert.ok((hintBad.notes || []).some((n) => n.startsWith("source_hint_mismatch:")));
  const poolWin = classifyGroup({
    instruction: "Write YES if the statement agrees with the views of the writer.",
    skill: "reading",
    structure: deriveStructure({ pools: [{ kind: "judgement", options: [{ label: "TRUE" }, { label: "FALSE" }] }] }),
  });
  assert.equal(poolWin.type, "true_false_not_given");
  assert.equal(poolWin.reason, "pool_overrides_instruction");
  assert.ok((poolWin.notes || []).some((n) => n === "pool_overrides_instruction:yes_no_not_given"));
});

test("A8: classifyGroup — structure fallback chain (pool/multi/options/cell/question/summary/sentence/single/neighbor)", () => {
  const empty = classifyGroup({ skill: "listening", structure: deriveStructure({}) });
  assert.equal(empty.type, "unknown");
  assert.equal(empty.reason, "empty_group_no_content");
  const poolOnly = classifyGroup({ skill: "reading", structure: deriveStructure({ pools: [{ kind: "judgement", options: [{ label: "YES" }, { label: "NO" }] }] }) });
  assert.equal(poolOnly.type, "yes_no_not_given");
  assert.equal(poolOnly.reason, "pool_labels");
  const multi = classifyGroup({ skill: "listening", structure: deriveStructure({ slots: [{ number: 21, kind: "multi_select", prompt: "" }] }) });
  assert.equal(multi.type, "multiple_choice_multiple");
  assert.equal(multi.reason, "slot_multi_select");
  const opt = classifyGroup({ skill: "listening", structure: deriveStructure({ slots: [{ number: 1, kind: "line", prompt: "", options: [{ label: "A" }] }] }) });
  assert.equal(opt.type, "multiple_choice_single");
  assert.equal(opt.reason, "slot_options");
  const cell = classifyGroup({ skill: "reading", structure: deriveStructure({ slots: [{ number: 1, kind: "cell_gap", prompt: "" }, { number: 2, kind: "cell_gap", prompt: "" }] }) });
  assert.equal(cell.type, "table_completion");
  assert.equal(cell.reason, "cell_gap_table");
  const qLike = classifyGroup({
    instruction: "Write NO MORE THAN THREE WORDS for each answer.",
    skill: "listening",
    structure: deriveStructure({ slots: [{ number: 1, kind: "line", prompt: "What is the name?" }, { number: 2, kind: "line", prompt: "Where is it?" }] }),
  });
  assert.equal(qLike.type, "short_answer");
  assert.equal(qLike.reason, "question_like_slots");
  const sharedBlock = classifyGroup({
    skill: "reading",
    structure: deriveStructure({ slots: [{ number: 1, kind: "gap", prompt: "same text" }, { number: 2, kind: "gap", prompt: "same text" }] }),
  });
  assert.equal(sharedBlock.type, "summary_completion");
  assert.equal(sharedBlock.reason, "shared_prompt_block");
  const sentences = classifyGroup({
    skill: "reading",
    structure: deriveStructure({ slots: [{ number: 1, kind: "gap", prompt: "first ___" }, { number: 2, kind: "gap", prompt: "second ___" }] }),
  });
  assert.equal(sentences.type, "sentence_completion");
  assert.equal(sentences.reason, "independent_sentence_slots");
  const single = classifyGroup({
    instruction: "Write ONE WORD ONLY for each answer.",
    skill: "listening",
    structure: deriveStructure({ slots: [{ number: 1, kind: "line", prompt: "The museum is closed on ___" }] }),
  });
  assert.equal(single.type, "sentence_completion");
  assert.equal(single.reason, "single_slot_completion");
  const neighbor = classifyGroup({
    instruction: "Write ONE WORD ONLY.",
    skill: "listening",
    neighbor_type: "note_completion",
    structure: deriveStructure({ slots: [{ number: 1, kind: "input", prompt: "" }, { number: 2, kind: "input", prompt: "" }] }),
  });
  assert.equal(neighbor.type, "note_completion");
  assert.equal(neighbor.status, "inferred");
  assert.equal(neighbor.reason, "neighbor_continuation:note_completion");
  const unknown = classifyGroup({
    instruction: "Look at the text.",
    skill: "listening",
    structure: deriveStructure({ slots: [{ number: 1, kind: "gap", prompt: "The ___ is blue" }] }),
  });
  assert.equal(unknown.type, "unknown");
  assert.equal(unknown.reason, "no_instruction_match");
});

/* ================================ Part A: question-index ================================ */

test("B1: resolveFamilyName / normTest / skillVariantOf", () => {
  assert.equal(resolveFamilyName("multiple_choice_single"), "choice");
  assert.equal(resolveFamilyName("choice"), "choice");
  assert.equal(resolveFamilyName("选择"), "choice");
  assert.equal(resolveFamilyName("判断"), "judgement");
  assert.equal(resolveFamilyName("matching"), "matching");
  assert.equal(resolveFamilyName("completion"), "completion");
  assert.equal(resolveFamilyName("nope"), null);
  assert.equal(resolveFamilyName(null), null);
  assert.equal(normTest(1), "1");
  assert.equal(normTest("gta"), "gta");
  assert.equal(normTest(null), null);
  assert.deepEqual(skillVariantOf("academic_reading"), { skill: "reading", variant: "academic" });
  assert.deepEqual(skillVariantOf("general_reading"), { skill: "reading", variant: "general" });
  assert.deepEqual(skillVariantOf("reading"), { skill: "reading", variant: "academic" });
  assert.deepEqual(skillVariantOf("listening"), { skill: "listening", variant: "shared" });
  assert.deepEqual(skillVariantOf("speaking"), { skill: "speaking", variant: "shared" });
  assert.deepEqual(skillVariantOf("foo"), { skill: "foo", variant: null });
});

test("B2: parseWordLimit extracts max words / number allowance; none → null", () => {
  assert.deepEqual(parseWordLimit("Write NO MORE THAN TWO WORDS for each answer."), { raw: "no more than two words", max_words: 2, allows_number: false });
  assert.deepEqual(parseWordLimit("Write ONE WORD ONLY for each answer."), { raw: "one word only", max_words: 1, allows_number: false });
  assert.deepEqual(parseWordLimit("Write NO MORE THAN THREE WORDS AND/OR A NUMBER for each answer."), { raw: "no more than three words", max_words: 3, allows_number: true });
  assert.deepEqual(parseWordLimit("Write ONE WORD AND/OR A NUMBER for each answer."), { raw: "one word and/or a number", max_words: 1, allows_number: true });
  assert.deepEqual(parseWordLimit("Write TWO WORDS AND/OR A NUMBER for each answer."), { raw: "two words and/or a number", max_words: 2, allows_number: true });
  assert.equal(parseWordLimit("Choose the correct letter, A, B or C."), null);
  assert.equal(parseWordLimit(""), null);
  assert.equal(parseWordLimit(null), null);
});

test("B3: partOfNumber / passageTextOf", () => {
  const parts = [
    { part: "P1", ranges: [[1, 10]] },
    { part: "P2", ranges: [[11, 20]] },
  ];
  assert.equal(partOfNumber(5, parts), "P1");
  assert.equal(partOfNumber(12, parts), "P2");
  assert.equal(partOfNumber(99, parts), null);
  assert.equal(partOfNumber(5, null), null);
  assert.equal(passageTextOf({ text: "abc" }), "abc");
  assert.equal(passageTextOf({ paragraphs: [{ text: "a" }, { text: "b" }] }), "a\n\nb");
  assert.equal(passageTextOf({}), "");
  assert.equal(passageTextOf(null), "");
});

test("B4: contentStatusOf — all seven statuses incl. image fallback partial", () => {
  assert.equal(contentStatusOf({}).status, "missing_content");
  assert.equal(contentStatusOf({ assets: [{ source_ref: "img" }] }).status, "missing_prompt");
  assert.equal(contentStatusOf({ prompt: "x", type: "multiple_choice_single" }).status, "missing_options");
  assert.equal(contentStatusOf({ prompt: "x", type: "matching_information", skill: "listening" }).status, "missing_options");
  assert.equal(contentStatusOf({ prompt: "x", type: "matching_information", skill: "listening", letterOptions: true }).status, "complete");
  assert.equal(contentStatusOf({ prompt: "x", type: "diagram_labeling" }).status, "missing_asset");
  assert.equal(contentStatusOf({ prompt: "x", type: "table_completion" }).status, "missing_asset");
  assert.equal(contentStatusOf({ prompt: "x", type: "short_answer", skill: "reading" }).status, "missing_passage");
  const fallback = contentStatusOf({ prompt: "x", type: "multiple_choice_single", skill: "listening", assets: [{ source_ref: "img" }] });
  assert.equal(fallback.status, "partial");
  assert.equal(fallback.presentation, "source_image");
  assert.ok(fallback.notes.includes("choice_options_missing_image_fallback"));
  const noCtx = contentStatusOf({ prompt: "x", skill: "listening", groupContext: false });
  assert.equal(noCtx.status, "partial");
  assert.ok(noCtx.notes.includes("group_context_missing"));
  assert.equal(contentStatusOf({ prompt: "x", skill: "listening" }).status, "complete");
  assert.equal(contentStatusOf({ prompt: "x", type: "table_completion", assets: [{ source_ref: "img" }] }).status, "complete");
  for (const s of CONTENT_STATUS) assert.ok(typeof s === "string");
});

function pteFixture() {
  const parsed = {
    ok: true,
    passages: [],
    question_groups: [
      {
        index: 0, range: [1, 2], numbers: [1, 2],
        instruction: "Complete the notes below. Write ONE WORD ONLY for each answer.",
        shared_prompt: "Notes\n______", heading_text: null, word_limit: "ONE WORD ONLY",
        pools: [], options: [],
        slots: [{ number: 1, kind: "gap", prompt: "", options: [] }, { number: 2, kind: "gap", prompt: "", options: [] }],
      },
      { index: 1, range: [3, 3], numbers: [3], instruction: null, shared_prompt: null, heading_text: null, word_limit: null, pools: [], options: [], slots: [] },
      {
        index: 2, range: [4, 5], numbers: [4, 5],
        instruction: "Choose the correct letter, A, B or C.",
        shared_prompt: null, heading_text: null, word_limit: null, pools: [], options: [],
        slots: [
          { number: 4, kind: "line", prompt: "What time?", options: [{ label: "A", text: "x" }] },
          { number: 5, kind: "line", prompt: "How much?", options: [{ label: "A", text: "y" }] },
        ],
      },
    ],
    questions: [
      { number: 1, group: 0, prompt: "The centre is closed on ____", options: [], source_ref: "#1" },
      { number: 2, group: 0, prompt: "", options: [] },
      { number: 3, group: 1, prompt: null, options: [] },
      { number: 4, group: 2, prompt: "What time?", options: [{ label: "A", text: "x" }] },
      { number: 5, group: 2, prompt: "How much?", options: [{ label: "A", text: "y" }] },
    ],
    answer_slots: [
      { number: 1, raw: "Monday", form: "numbered", source_ref: "#a1" },
      { number: 2, raw: "", form: "numbered_empty", source_ref: "#a2" },
      { number: 3, raw: "TRUE", form: "numbered", source_ref: "#a3" },
      { number: 4, raw: "A", form: "numbered", source_ref: "#a4" },
    ],
    answer_missing_detail: [{ number: 5, reason: "empty" }],
    warnings: [],
  };
  const meta = { book: 1, test: "1", skill: "listening", slug: "x", page_key: "pte:1:1:listening" };
  return { parsed, meta };
}

test("B5: buildFromPtePage — ids/parts/empty-group gap/empty-vs-missing answers", () => {
  const { parsed, meta } = pteFixture();
  const built = buildFromPtePage(parsed, meta);
  assert.equal(built.page.page_ref, "pte:1:1:listening");
  assert.equal(built.questions.length, 5);
  assert.equal(built.groups.length, 2);
  assert.equal(built.gaps.length, 1);
  assert.equal(built.gaps[0].kind, "empty_group_excluded");
  assert.deepEqual(built.gaps[0].numbers, [3]);
  const q = (n) => built.questions.find((x) => x.number === n);
  assert.equal(q(1).id, "cambridge:1:shared:listening:1:P1:Q1");
  assert.equal(q(1).group_id, "cambridge:1:shared:listening:1:P1:G0");
  // 被排除的空组仍占用其序号（G1 保留），后续组顺延为 G2——与真实 b11t3 听力空组行为一致，
  // 保证空组日后由 PDF 补齐时其余组 id 不移位。
  assert.equal(q(4).group_id, "cambridge:1:shared:listening:1:P1:G2");
  assert.equal(built.groups[0].id, "cambridge:1:shared:listening:1:P1:G0");
  assert.equal(built.groups[0].type, "note_completion");
  assert.equal(built.groups[0].classification_status, "classified");
  assert.equal(built.groups[0].constraints.max_words, 1);
  assert.equal(built.groups[1].type, "multiple_choice_single");
  assert.equal(q(1).content_status, "complete");
  assert.equal(q(1).answer_status, "attached");
  assert.equal(q(1).fully_complete, true);
  assert.equal(built.answers[q(1).id].raw, "Monday");
  assert.equal(q(2).answer_status, "empty");
  assert.equal(built.answers[q(2).id].raw, "");
  assert.equal(q(3).group_id, null);
  assert.equal(q(3).classification_status, "unknown");
  assert.equal(q(3).classification_reason, "empty_group_no_content");
  assert.equal(q(3).content_status, "missing_content");
  assert.equal(q(5).answer_status, "missing");
  assert.equal(built.answers[q(5).id].note, "empty_slot_no_entry");
  assert.equal(q(4).fully_complete, true);
  assert.equal(q(5).fully_complete, false);
});

function cam21ListeningFixture() {
  const parsed = {
    sections: [],
    groups: [
      { index: 0, type: null, instruction: "Complete the notes below. Write ONE WORD ONLY for each answer.", word_limit: "ONE WORD ONLY", label: null, sublabel: null, id: "g0" },
      { index: 1, type: null, instruction: "Choose TWO letters, A–E.", word_limit: null, label: null, sublabel: null, id: "g1" },
    ],
    questions: [
      { number: 21, section: 2, group: 1, type: "multi", prompt: "Which TWO changes were made?", options: [{ label: "A", text: "..." }, { label: "B", text: "..." }] },
      { number: 22, section: 2, group: 1, type: "multi", prompt: "Which TWO changes were made?", options: [{ label: "A", text: "..." }, { label: "B", text: "..." }] },
      { number: 11, section: 2, group: 0, type: "gap", prompt: "Stay at the Grand Hotel", options: [] },
    ],
    answer_key: [
      { number: 11, answer: "hotel", kind: "single" },
      { number: 21, kind: "multi_member", accept: ["B", "D"] },
      { number: 22, kind: "multi_member", accept: ["B", "D"] },
    ],
    answer_groups: [
      { key: "21", inputs_raw: ["B", "D"], slots: [21, 22], accept: ["B", "D"], required_count: 2, section: 2 },
    ],
    passages: [],
    warnings: [],
  };
  const meta = { book: 21, test: "1", skill: "listening", file: "tmp_audit_ielts/cam21/t1-listening.html", page_key: "cam21:21:1:listening" };
  return { parsed, meta };
}

test("B6: buildFromCam21Page listening — multi answer group resolves via slot group (regression)", () => {
  const { parsed, meta } = cam21ListeningFixture();
  const built = buildFromCam21Page(parsed, meta);
  assert.equal(built.questions.length, 3);
  assert.equal(built.answer_groups.length, 1);
  const ag = built.answer_groups[0];
  assert.equal(ag.id, "cambridge:21:shared:listening:1:P2:G1");
  assert.ok(!ag.id.includes("answer_group:"));
  assert.deepEqual(ag.numbers, [21, 22]);
  assert.deepEqual(ag.accept, ["B", "D"]);
  assert.equal(ag.required_count, 2);
  const q = (n) => built.questions.find((x) => x.number === n);
  assert.equal(q(21).group_id, "cambridge:21:shared:listening:1:P2:G1");
  assert.equal(q(21).answer_status, "attached");
  assert.equal(q(21).answer_mode, "standard");
  assert.equal(built.answers[q(21).id].form, "group_set");
  assert.equal(built.answers[q(21).id].group_ref, ag.id);
  assert.deepEqual(built.answers[q(21).id].accept, ["B", "D"]);
  assert.equal(q(11).answer_status, "attached");
  assert.equal(built.answers[q(11).id].raw, "hotel");
  assert.equal(q(11).content_status, "complete");
  assert.equal(q(11).fully_complete, true);
  assert.equal(q(21).fully_complete, true);
});

test("B7: buildFromCam21Page reading — passage text gates content; multi group via ag.group", () => {
  const parsed = {
    passages: [{ passage: 1, paragraphs: [{ text: "Some passage text." }] }],
    groups: [{ id: "rg1", type: "Multiple Choice (choose TWO)", instruction: "Choose TWO letters, A–E.", word_limit: null }],
    questions: [
      { number: 27, passage: 1, group: "rg1", slot_kind: "multi", prompt: "Which TWO ...", options: [{ label: "A", text: "..." }, { label: "C", text: "..." }] },
    ],
    answer_key: [{ number: 27, kind: "multi_member", accept: ["A", "C"] }],
    answer_groups: [{ group: "rg1", slots: [27], accept: ["A", "C"], required_count: 2 }],
    warnings: [],
  };
  const meta = { book: 21, test: "2", skill: "reading", file: "tmp_audit_ielts/cam21/t2-reading.html", page_key: "cam21:21:2:reading" };
  const built = buildFromCam21Page(parsed, meta);
  const q27 = built.questions[0];
  assert.equal(q27.id, "cambridge:21:academic:reading:2:P1:Q27");
  assert.equal(q27.group_id, "cambridge:21:academic:reading:2:P1:G0");
  assert.equal(built.answer_groups[0].id, "cambridge:21:academic:reading:2:P1:G0");
  assert.equal(q27.content_status, "complete");
  assert.equal(q27.fully_complete, true);
  const noPassage = buildFromCam21Page({ ...parsed, passages: [] }, meta);
  assert.equal(noPassage.questions[0].content_status, "missing_passage");
});

test("B8: buildIndex + manifestGaps — content_not_indexed / missing_questions / part_mismatch", () => {
  const { parsed, meta } = cam21ListeningFixture();
  const manifest = {
    books: [
      {
        book: 21,
        items: [
          { id: "m-listen", variant: "shared", skill: "listening", test: "1", part: "P2", expected_numbers: [11, 21, 22], status: "verified" },
          { id: "m-listen2", variant: "shared", skill: "listening", test: "1", part: "P2", expected_numbers: [11, 23], status: "verified" },
          { id: "m-write", variant: "academic", skill: "writing", test: "1", part: "WT1", expected_numbers: [1, 2], status: "verified" },
          { id: "m-mismatch", variant: "shared", skill: "listening", test: "1", part: "P1", expected_numbers: [21], status: "verified" },
        ],
      },
    ],
  };
  const index = buildIndex({ cam21Pages: [{ parsed, meta }], manifest, options: { run_id: "test" } });
  assert.equal(index.schema, INDEX_SCHEMA);
  assert.equal(index.stats.questions, 3);
  const kinds = index.gaps.map((g) => g.kind);
  assert.ok(kinds.includes("content_not_indexed"));
  assert.ok(kinds.includes("missing_questions"));
  assert.ok(kinds.includes("part_mismatch"));
  const missing = index.gaps.find((g) => g.kind === "missing_questions");
  assert.deepEqual(missing.numbers, [23]);
  const mismatch = index.gaps.find((g) => g.kind === "part_mismatch");
  assert.deepEqual(mismatch.detail, [{ number: 21, got: "P2", want: "P1" }]);
  const cni = index.gaps.find((g) => g.kind === "content_not_indexed");
  assert.equal(cni.skill, "writing");
  assert.equal(cni.book, 21);
});

test("B9: queryIndex — filters (en/zh), family, status kinds, text, pagination, invalid throws", () => {
  const { parsed: pteParsed, meta: pteMeta } = pteFixture();
  const { parsed: camParsed, meta: camMeta } = cam21ListeningFixture();
  const reading = {
    passages: [{ passage: 1, paragraphs: [{ text: "Some passage text." }] }],
    groups: [{ id: "rg1", type: "Multiple Choice (choose TWO)", instruction: "Choose TWO letters, A–E.", word_limit: null }],
    questions: [{ number: 27, passage: 1, group: "rg1", slot_kind: "multi", prompt: "Which TWO ...", options: [{ label: "A", text: "..." }] }],
    answer_key: [{ number: 27, kind: "multi_member", accept: ["A", "C"] }],
    answer_groups: [{ group: "rg1", slots: [27], accept: ["A", "C"], required_count: 2 }],
    warnings: [],
  };
  const readingMeta = { book: 21, test: "2", skill: "reading", file: "tmp_audit_ielts/cam21/t2-reading.html", page_key: "cam21:21:2:reading" };
  const index = buildIndex({
    pages: [{ parsed: pteParsed, meta: pteMeta }],
    cam21Pages: [{ parsed: camParsed, meta: camMeta }, { parsed: reading, meta: readingMeta }],
  });
  assert.equal(index.stats.questions, 9);
  assert.equal(queryIndex(index, { skill: "listening" }).total, 8);
  assert.equal(queryIndex(index, { skill: "听力" }).total, 8);
  assert.equal(queryIndex(index, { skill: "reading" }).total, 1);
  assert.equal(queryIndex(index, { type: "multiple_choice_multiple" }).total, 3);
  assert.equal(queryIndex(index, { type: "choice" }).total, 5);
  assert.equal(queryIndex(index, { type: "多项选择" }).total, 3);
  assert.equal(queryIndex(index, { book: 21, test: "1" }).total, 3);
  assert.equal(queryIndex(index, { book: 21, test: 1, part: "p2" }).total, 3);
  assert.equal(queryIndex(index, { number: 21 }).total, 1);
  assert.equal(queryIndex(index, { status: "fully_complete" }).total, 6);
  assert.equal(queryIndex(index, { status: "empty" }).total, 1);
  assert.equal(queryIndex(index, { status: "missing" }).total, 1);
  assert.equal(queryIndex(index, { status: "attached" }).total, 7);
  assert.equal(queryIndex(index, { text: "hotel" }).total, 1);
  assert.equal(queryIndex(index, { text: "cambridge:21" }).total, 4);
  const page2 = queryIndex(index, { pageSize: 4, page: 2 });
  assert.equal(page2.total, 9);
  assert.equal(page2.pageCount, 3);
  assert.equal(page2.items.length, 4);
  assert.equal(queryIndex(index, { pageSize: 1000 }).pageSize, 500);
  assert.throws(() => queryIndex(index, { skill: "nope" }), /未知 skill/);
  assert.throws(() => queryIndex(index, { variant: "nope" }), /未知 variant/);
  assert.throws(() => queryIndex(index, { type: "nope" }), /未知 type/);
  assert.throws(() => queryIndex(index, { status: "nope" }), /未知 status/);
  const sum = summarize(index);
  assert.equal(sum.questions, 9);
  assert.equal(sum.by_skill.listening, 8);
  assert.equal(sum.by_book["21"].questions, 4);
});

test("B10: applyGroupVerifications — classification override, answer representation, word limit; conflicts appended", () => {
  const index = {
    groups: [
      { id: "cambridge:9:academic:reading:1:P2:G2", type: "true_false_not_given", classification_reason: "pool_overrides_instruction", word_limit: null, constraints: null },
      { id: "cambridge:9:academic:reading:1:P2:G1", type: "short_answer", classification_reason: "instruction", word_limit: "NO MORE THAN TWO WORDS", constraints: parseWordLimit("NO MORE THAN TWO WORDS") },
    ],
    questions: [
      { id: "cambridge:9:academic:reading:1:P2:Q21", group_id: "cambridge:9:academic:reading:1:P2:G2", type: "true_false_not_given", classification_reason: "pool_overrides_instruction", constraints: null, fully_complete: true },
      { id: "cambridge:9:academic:reading:1:P2:Q18", group_id: "cambridge:9:academic:reading:1:P2:G1", type: "short_answer", classification_reason: "instruction", constraints: parseWordLimit("NO MORE THAN TWO WORDS"), fully_complete: true },
    ],
    answers: {
      "cambridge:9:academic:reading:1:P2:Q21": { raw: "true", form: "numbered", status: "attached" },
      "cambridge:9:academic:reading:1:P2:Q18": { raw: "several billion years", form: "numbered", status: "attached" },
    },
  };
  const v = [
    {
      id: "t-1", kind: "classification_conflict",
      identity: { book: 9, variant: "academic", skill: "reading", test: "1", part: "P2", group_id: "cambridge:9:academic:reading:1:P2:G2", range: [21, 21] },
      from: { type: "true_false_not_given", classification_reason: "pool_overrides_instruction", source_pool: ["TRUE", "FALSE", "NOT GIVEN"] },
      to: { type: "yes_no_not_given" },
      answer_representation: { form: "yes_no_not_given", numbers: [21], map: { "true": "YES", "false": "NO", "not given": "NOT GIVEN" }, official_values: { "21": "YES" } },
      evidence: { official_pdf: { file: "x.pdf", sha256: "abc" } },
      verifier: { type: "test" },
    },
    {
      id: "t-2", kind: "word_limit_conflict",
      identity: { book: 9, variant: "academic", skill: "reading", test: "1", part: "P2", group_id: "cambridge:9:academic:reading:1:P2:G1", range: [18, 18] },
      from: { word_limit: "NO MORE THAN TWO WORDS" },
      to: { word_limit: "NO MORE THAN THREE WORDS AND/OR A NUMBER" },
      evidence: null,
      verifier: null,
    },
  ];
  const res = applyGroupVerifications(index, v);
  assert.equal(res.applied.length, 2);
  assert.equal(res.issues.length, 0);
  // 分类覆盖 + 原值保留
  assert.equal(index.groups[0].type, "yes_no_not_given");
  assert.equal(index.groups[0].classification_reason, "official_pdf_override");
  assert.equal(index.groups[0].verification.decision_id, "t-1");
  assert.equal(index.groups[0].verification.from.type, "true_false_not_given");
  assert.equal(index.groups[0].verification.from.classification_reason, "pool_overrides_instruction");
  assert.equal(index.questions[0].type, "yes_no_not_given");
  assert.equal(index.questions[0].classification_reason, "official_pdf_override");
  // 答案表示映射：official 记录官方值，raw 不动
  assert.equal(index.answers["cambridge:9:academic:reading:1:P2:Q21"].raw, "true");
  assert.equal(index.answers["cambridge:9:academic:reading:1:P2:Q21"].official.value, "YES");
  assert.equal(index.answers["cambridge:9:academic:reading:1:P2:Q21"].official.form, "yes_no_not_given");
  assert.equal(index.answers["cambridge:9:academic:reading:1:P2:Q21"].official.mapped_from_raw, "YES");
  assert.equal(index.answers["cambridge:9:academic:reading:1:P2:Q21"].official.raw_form_consistent, true);
  // 字数限制覆盖 + constraints 重算
  assert.equal(index.groups[1].word_limit, "NO MORE THAN THREE WORDS AND/OR A NUMBER");
  assert.equal(index.groups[1].constraints.max_words, 3);
  assert.equal(index.groups[1].constraints.allows_number, true);
  assert.equal(index.groups[1].verification.from.word_limit, "NO MORE THAN TWO WORDS");
  assert.equal(index.questions[1].constraints.max_words, 3);
  // 冲突条目
  assert.equal(index.cross_source_conflicts.length, 2);
  assert.equal(index.cross_source_conflicts[0].kind, "classification_conflict");
  assert.equal(index.cross_source_conflicts[0].from.type, "true_false_not_given");
  assert.equal(index.cross_source_conflicts[0].decision_id, "t-1");
  assert.equal(index.cross_source_conflicts[1].kind, "word_limit_conflict");
  assert.equal(index.cross_source_conflicts[1].from.word_limit, "NO MORE THAN TWO WORDS");
});

test("B11: applyGroupVerifications — stale guard keeps original values; unknown group recorded", () => {
  const index = {
    groups: [{ id: "g-x", type: "yes_no_not_given", classification_reason: "official_pdf_override", word_limit: null, constraints: null }],
    questions: [],
    answers: {},
  };
  const res = applyGroupVerifications(index, [
    { id: "t-stale", identity: { book: 9, variant: "academic", skill: "reading", test: "1", part: "P2", group_id: "g-x" }, from: { type: "true_false_not_given" }, to: { type: "multiple_choice_single" } },
    { id: "t-missing", identity: { book: 9, variant: "academic", skill: "reading", test: "1", part: "P2", group_id: "g-none" }, from: { type: "x" }, to: { type: "y" } },
  ]);
  assert.equal(res.applied.length, 0);
  assert.equal(res.issues.length, 2);
  assert.equal(res.issues[0].kind, "decision_stale");
  assert.equal(res.issues[0].expected, "true_false_not_given");
  assert.equal(res.issues[0].actual, "yes_no_not_given");
  assert.equal(res.issues[1].kind, "group_not_found");
  assert.equal(index.groups[0].type, "yes_no_not_given"); // 未被二次覆盖
  assert.equal(index.cross_source_conflicts.length, 0);
});

/* ================================ Part B: real built index ================================ */

const REAL_INDEX = fs.existsSync(REAL_INDEX_PATH) ? JSON.parse(fs.readFileSync(REAL_INDEX_PATH, "utf8")) : null;
const requireReal = (t) => {
  if (!REAL_INDEX) t.skip(`real index not available: ${REAL_INDEX_PATH}`);
  return REAL_INDEX;
};

test("C1: real index — schema, unique ids, group/answer referential integrity", (t) => {
  const idx = requireReal(t);
  assert.equal(idx.schema, INDEX_SCHEMA);
  assert.ok(idx.stats.questions > 6000);
  assert.equal(idx.stats.questions, idx.questions.length);
  assert.equal(new Set(idx.questions.map((q) => q.id)).size, idx.questions.length);
  const gids = new Set(idx.groups.map((g) => g.id));
  for (const q of idx.questions) {
    assert.ok(idx.answers[q.id] !== undefined, `answer entry for ${q.id}`);
    if (q.group_id != null) assert.ok(gids.has(q.group_id), `group ref ${q.group_id}`);
  }
  assert.equal(Object.keys(idx.answers).length, idx.questions.length);
});

test("C2: real index — cam21 pages complete; multi answer groups resolved to group ids", (t) => {
  const idx = requireReal(t);
  const cam = idx.pages.filter((p) => p.kind === "cam21-html");
  assert.equal(cam.length, 8);
  for (const p of cam) assert.equal(p.counts.questions, 40, `${p.page_ref}`);
  const cam21Ags = idx.answer_groups.filter((ag) => String(ag.id).startsWith("cambridge:21:"));
  assert.equal(cam21Ags.length, 14);
  assert.ok(idx.answer_groups.length >= 14);
  for (const ag of idx.answer_groups) {
    assert.ok(!ag.id.includes("answer_group:"), `unresolved: ${ag.id}`);
  }
  const camQ = idx.questions.filter((q) => q.book === 21);
  assert.equal(camQ.length, cam.reduce((s, p) => s + p.counts.questions, 0));
});

test("C3: real index — b10 t1 reading Q34 empty retained; b12 cross-source numbering ruling", (t) => {
  const idx = requireReal(t);
  const q34 = idx.questions.find((q) => q.id === "cambridge:10:academic:reading:1:P3:Q34");
  assert.ok(q34, "b10t1r Q34 present");
  assert.equal(q34.answer_status, "empty");
  assert.equal(idx.answers[q34.id].raw, "");
  const b12 = idx.pages.filter((p) => p.book === 12);
  assert.equal(b12.length, 8);
  for (const p of b12) {
    assert.ok(["5", "6", "7", "8"].includes(p.test), `b12 canonical test ${p.test}`);
    assert.ok(["1", "2", "3", "4"].includes(p.source_test), `b12 source test ${p.source_test}`);
  }
  const conflict = (idx.cross_source_conflicts || []).find((c) => c.kind === "test_numbering" && c.book === 12);
  assert.ok(conflict, "test_numbering conflict recorded");
  assert.equal(conflict.canonical.system, "book-internal");
  assert.deepEqual(conflict.source.mapping, { "1": "5", "2": "6", "3": "7", "4": "8" });
});

test("C4: real index — stale empty-group gaps resolved (not dropped); queryIndex works on real index", (t) => {
  const idx = requireReal(t);
  const eg = idx.gaps.filter((g) => g.kind === "empty_group_excluded");
  assert.equal(eg.length, 0);
  const resolved = idx.empty_group_resolved || [];
  assert.equal(resolved.length, 3);
  const key = resolved.map((g) => {
    const ns = g.numbers || [];
    return `${g.book}/${g.test}/${ns[0]}-${ns[ns.length - 1]}`;
  }).sort();
  assert.deepEqual(key, ["11/3/11-20", "14/1/11-20", "20/1/21-30"]);
  const cam21 = idx.pages.filter((p) => p.kind === "cam21-html");
  const total21 = cam21.reduce((s, p) => s + p.counts.questions, 0);
  assert.equal(queryIndex(idx, { book: 21 }).total, total21);
  assert.equal(queryIndex(idx, { book: 21, skill: "listening" }).total, total21 / 2);
  assert.equal(queryIndex(idx, { book: 21, skill: "reading" }).total, total21 / 2);
  // 剑21 问题级：内容/答案/分类全部就绪（含表格/地图/流程图资产），fully_complete=全量。
  // 未闭合项（官方答案未核验、音频对齐 13/40）由覆盖层 coverage 承担，不在此冒充——
  // 见 tests/ielts-resolver.test.mjs D1（b21 t1 不 fully_complete）与全量 coverage 证据。
  const fully21 = queryIndex(idx, { book: 21, status: "fully_complete" }).total;
  assert.equal(fully21, total21);
  assert.equal(queryIndex(idx, { book: 21, status: "missing_asset" }).total, 0);
});

test("C5: real index — b9t1r official verification applied (gv-01/gv-02); raw values retained", (t) => {
  const idx = requireReal(t);
  // gv-01：Q21-26 分类 true_false_not_given -> yes_no_not_given
  const g2 = idx.groups.find((g) => g.id === "cambridge:9:academic:reading:1:P2:G2");
  assert.ok(g2, "b9t1r P2 G2 present");
  assert.equal(g2.type, "yes_no_not_given");
  assert.equal(g2.classification_reason, "official_pdf_override");
  assert.equal(g2.verification.decision_id, "gv-01");
  assert.equal(g2.verification.from.type, "true_false_not_given");
  const q21 = idx.questions.find((q) => q.id === "cambridge:9:academic:reading:1:P2:Q21");
  assert.ok(q21, "Q21 present");
  assert.equal(q21.type, "yes_no_not_given");
  assert.equal(q21.classification_reason, "official_pdf_override");
  // 答案表示：raw 保留，official 记录官方值
  const a21 = idx.answers["cambridge:9:academic:reading:1:P2:Q21"];
  assert.equal(a21.raw, "true");
  assert.equal(a21.official.value, "YES");
  assert.equal(a21.official.form, "yes_no_not_given");
  assert.equal(a21.official.decision_id, "gv-01");
  assert.equal(a21.official.raw_form_consistent, true);
  const a23 = idx.answers["cambridge:9:academic:reading:1:P2:Q23"];
  assert.equal(a23.raw, "not given");
  assert.equal(a23.official.value, "NOT GIVEN");
  const a24 = idx.answers["cambridge:9:academic:reading:1:P2:Q24"];
  assert.equal(a24.raw, "false");
  assert.equal(a24.official.value, "NO");
  const a26 = idx.answers["cambridge:9:academic:reading:1:P2:Q26"];
  assert.equal(a26.official.value, "NO");
  // gv-02：Q18-20 字数限制官方覆盖
  const g1 = idx.groups.find((g) => g.id === "cambridge:9:academic:reading:1:P2:G1");
  assert.equal(g1.word_limit, "NO MORE THAN THREE WORDS AND/OR A NUMBER");
  assert.equal(g1.constraints.max_words, 3);
  assert.equal(g1.constraints.allows_number, true);
  assert.equal(g1.verification.decision_id, "gv-02");
  assert.equal(g1.verification.from.word_limit, "NO MORE THAN TWO WORDS");
  const q18 = idx.questions.find((q) => q.id === "cambridge:9:academic:reading:1:P2:Q18");
  assert.equal(q18.constraints.max_words, 3);
  // queryIndex 按新分类可查（6 题），旧分类不再命中
  assert.equal(queryIndex(idx, { book: 9, test: "1", part: "P2", type: "yes_no_not_given" }).total, 6);
  assert.equal(queryIndex(idx, { book: 9, test: "1", part: "P2", type: "true_false_not_given" }).total, 0);
  // 冲突记录与核验日志
  const cc = (idx.cross_source_conflicts || []).filter((c) => c.book === 9);
  assert.ok(cc.some((c) => c.kind === "classification_conflict" && c.group_id === g2.id), "classification_conflict recorded");
  assert.ok(cc.some((c) => c.kind === "word_limit_conflict" && c.group_id === g1.id), "word_limit_conflict recorded");
  assert.deepEqual((idx.official_verifications || []).map((a) => a.decision_id).sort(), ["gv-01", "gv-02"]);
  assert.equal((idx.verification_issues || []).length, 0);
});
