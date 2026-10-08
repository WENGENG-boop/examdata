// ielts-api/tests/book3-listening.test.mjs
// S12 acceptance tests for the book3-listening.mjs converter (剑3 T2–T4 听力静态转录).
// Anchors: 40 题/套不移位、官方答案键原样（含 NOT/ACCEPT/顺序标记）、位图笔记资产、
// 多选组 accepted sets（T2 26-27 / T3 25-27）、选项透传（lineSlot mcOptions 回归）、
// 分类（map_plan/matching_features/table cell_gap 回退）、来源 sha256。
// Part A: 纯模块断言（离线，不读文件）；Part B: 本地证据文件（缺失即 skip）。
// Run: node --test ielts-api/tests/book3-listening.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseBook3ListeningPage, buildBook3ListeningTests, B3_PARSER_VERSION } from "../book3-listening.mjs";
import { classifyGroup, deriveStructure } from "../taxonomy.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(__dirname, "..", "..");
const PDF_REL = "tmp_audit_ielts/downloads/book_3.pdf";
const PDF_SHA256 = "da273b47cbfa1fe324b2f289374bcfdbc7276a763e216be4f86ae6a070f06845";

const T = (n) => parseBook3ListeningPage(n);
const groupOf = (doc, first, last) =>
  doc.question_groups.find((g) => g.range[0] === first && g.range[1] === last);
const answerOf = (doc, n) => doc.answer_slots.find((a) => a.number === n);

/* ================================ Part A ================================ */

test("A1: T2/T3/T4 结构 — 40 题/套、组数 11/8/11、编号 1-40 连续无重复", () => {
  const counts = { 2: 11, 3: 8, 4: 11 };
  for (const t of ["2", "3", "4"]) {
    const doc = T(t);
    assert.equal(doc.ok, true);
    assert.equal(doc.parser_version, B3_PARSER_VERSION);
    assert.equal(doc.questions.length, 40, `T${t} questions`);
    assert.equal(doc.answer_slots.length, 40, `T${t} answers`);
    assert.equal(doc.question_groups.length, counts[t], `T${t} groups`);
    assert.deepEqual(doc.questions.map((q) => q.number), Array.from({ length: 40 }, (_, i) => i + 1));
    assert.deepEqual(doc.answer_slots.map((a) => a.number), Array.from({ length: 40 }, (_, i) => i + 1));
    assert.equal(doc.passages.length, 0);
  }
  assert.deepEqual(parseBook3ListeningPage("1"), { ok: false, error: 'book3 listening 支持 T2/T3/T4，收到 "1"' });
});

test("A2: 官方答案抽查 — 原样保留 NOT/ACCEPT/斜杠形式，无猜测补全", () => {
  const t2 = T("2");
  assert.equal(answerOf(t2, 1).raw, "(the) Main Hall NOT Hall");
  assert.equal(answerOf(t2, 6).raw, "L // Library");
  const t3 = T("3");
  assert.equal(answerOf(t3, 24).raw, "20 (cm) 50 (cm) 2.5 (cm) // 2 and a half (cm)");
  assert.equal(answerOf(t3, 24).note, "MUST BE IN ORDER（官方键标记）");
  assert.equal(answerOf(t3, 9).note, "ALTERNATIVE FORMS ACCEPTED（官方键标记）");
  assert.equal(answerOf(t3, 10).note, "ALTERNATIVE FORMS ACCEPTED（官方键标记）");
  const t4 = T("4");
  assert.equal(answerOf(t4, 1).raw, "4.25 // 4 1/4 // four and (a) quarter");
  assert.equal(answerOf(t4, 30).note, "ALTERNATIVE FORMS ACCEPTED（官方键标记）");
  assert.equal(answerOf(t4, 40).raw, "C");
});

test("A3: official 元数据 — form=book_answer_key、decision_id、答案键页引用", () => {
  const pages = { 2: 155, 3: 157, 4: 159 };
  for (const t of ["2", "3", "4"]) {
    const doc = T(t);
    for (const a of doc.answer_slots) {
      assert.equal(a.form, "book_answer_key");
      assert.equal(a.official.form, "book_answer_key");
      assert.equal(a.official.decision_id, `b3-t${t}-listening-official-key`);
      assert.equal(a.official.source_ref, `pdf:book3:answer-key:p${pages[t]}`);
      assert.equal(a.official.value, a.raw);
    }
  }
});

test("A4: 多选组 accepted sets — T2 26-27 / T3 25-27；T4 无组", () => {
  const t2 = T("2");
  assert.equal(t2.answer_groups.length, 1);
  const g2 = t2.answer_groups[0];
  assert.equal(g2.key, "b3-t2-q26-27");
  assert.deepEqual(g2.slots, [26, 27]);
  assert.equal(g2.required_count, 2);
  assert.deepEqual(g2.accept, ["(the) (ancient) Chinese", "(the) military // army"]);
  for (const n of [26, 27]) {
    assert.equal(answerOf(t2, n).note, "EITHER ORDER（26-27 共享键行）");
  }
  const t3 = T("3");
  assert.equal(t3.answer_groups.length, 1);
  const g3 = t3.answer_groups[0];
  assert.equal(g3.key, "b3-t3-q25-27");
  assert.deepEqual(g3.slots, [25, 26, 27]);
  assert.equal(g3.required_count, 3);
  assert.equal(g3.accept.length, 3);
  assert.deepEqual(g3.accept, [
    "safe for children",
    "(it’s) educational",
    "price (is) good // inexpensive // not expensive // cheap (price) // (is) good price",
  ]);
  const t4 = T("4");
  assert.deepEqual(t4.answer_groups, []);
});

test("A5: 选项透传 — MC 槽位带 options（lineSlot mcOptions 回归）；图片选项组如实 notes", () => {
  const t2 = T("2");
  for (const n of [21, 22, 23, 24, 30]) {
    const q = t2.questions.find((x) => x.number === n);
    assert.equal(q.options.length, 3, `T2 Q${n}`);
    assert.deepEqual(q.options.map((o) => o.label), ["A", "B", "C"]);
  }
  const t4 = T("4");
  assert.equal(t4.questions.find((x) => x.number === 35).options.length, 4);
  for (const n of [37, 38, 39, 40]) {
    assert.equal(T("3").questions.find((x) => x.number === n).options.length, 3);
  }
  const g2img = groupOf(t2, 38, 40);
  assert.ok(g2img.notes.some((n) => n.includes("图片")));
  const g4img = groupOf(t4, 39, 40);
  assert.ok(g4img.notes.some((n) => n.includes("图片")));
  assert.deepEqual(g4img.assets.map((a) => a.source_ref), ["pdf:book3:p0086:fig2", "pdf:book3:p0087:fig1"]);
});

test("A6: 位图笔记组 notes 透传 + 资产引用（T3 G0 / T4 G0/G6）", () => {
  const t3 = T("3");
  const g0 = groupOf(t3, 1, 10);
  assert.ok(g0.notes.some((n) => n.includes("OCR")));
  assert.equal(g0.assets[0].source_ref, "pdf:book3:p0058:fig1");
  for (const q of t3.questions.filter((x) => x.number <= 10)) {
    assert.ok(Array.isArray(q.notes) && q.notes.length >= 1);
  }
  const t4 = T("4");
  const g6 = groupOf(t4, 27, 30);
  assert.ok(g6.notes.some((n) => n.includes("Hand in to Faculty Office")));
});

test("B1: 分类 — map_plan/matching_features/table 回退（与索引一致）", () => {
  const cls = (t, first, last) => {
    const g = groupOf(T(t), first, last);
    return classifyGroup({
      instruction: g.instruction,
      shared_prompt: g.shared_prompt,
      heading_text: g.heading_text,
      skill: "listening",
      group: g,
      structure: deriveStructure(g),
    });
  };
  assert.equal(cls("2", 6, 10).type, "map_plan_labeling");
  assert.equal(cls("2", 38, 40).type, "matching_features");
  assert.equal(cls("3", 17, 20).type, "map_plan_labeling");
  assert.equal(cls("4", 6, 10).type, "table_completion");
  assert.equal(cls("4", 6, 10).status, "classified");
  assert.equal(cls("4", 3, 5).type, "map_plan_labeling");
  assert.equal(cls("3", 1, 10).type, "note_completion");
  assert.equal(cls("3", 37, 40).type, "multiple_choice_single");
});

/* ================================ Part B ================================ */

test("C1: 来源证据 — book_3.pdf sha256 与 OCR 转换来源清单", (t) => {
  const built = buildBook3ListeningTests({ repoRoot: REPO });
  assert.equal(built.length, 3);
  for (const b of built) {
    assert.equal(b.ok, true);
    assert.equal(b.meta.source, "book3-pdf");
    assert.equal(b.meta.page_kind, "pdf-extract");
    assert.equal(b.meta.expected.expected_total, 40);
    assert.equal(b.meta.expected.status, "verified");
  }
  const pdf = path.join(REPO, PDF_REL);
  if (!fs.existsSync(pdf)) {
    t.skip(`本地 PDF 缺失: ${PDF_REL}`);
    return;
  }
  const src = built[0].sources.find((s) => s.file === PDF_REL);
  assert.ok(src, "PDF 在来源清单中");
  assert.equal(src.sha256, PDF_SHA256);
  assert.equal(built[0].sources.length, 3, "PDF + 2 OCR json");
});

test("C2: 资产 local_path 存在（位图/表格记录）", (t) => {
  const missing = [];
  for (const tt of ["2", "3", "4"]) {
    for (const g of T(tt).question_groups) {
      for (const a of g.assets) {
        if (!a.local_path) continue;
        if (!fs.existsSync(path.join(REPO, a.local_path))) missing.push(a.local_path);
      }
    }
  }
  if (missing.length && missing.every((m) => !fs.existsSync(path.join(REPO, path.dirname(m))))) {
    t.skip("book3-assets 目录不存在（离线证据缺失）");
    return;
  }
  assert.deepEqual(missing, []);
});
