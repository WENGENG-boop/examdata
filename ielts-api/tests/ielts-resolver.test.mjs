// ielts-api/tests/ielts-resolver.test.mjs
// S12 acceptance tests: resolver + coverage false-positive scenarios, offline against the
// saved repair run (ielts-data/runs/<run>). Anchors A01–A16: empty-answer no-shift (b10t1 Q34),
// answer-only book 3, cam21 multi-select accepted sets, book12 test-number mapping, book20/21 PDF,
// GT not-extracted, index integrity, b1 t2 Q40/41, reader single-passage fallback, audio degradation.
// Run: node --test ielts-api/tests/ielts-resolver.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import {
  loadResolverContext, resolveReading, resolveListening, resolveAudio, resolvePdf, resolveTest,
  normalizeIdentity, canonicalTestOf, webTestOf,
} from "../resolver.mjs";
import { coverageForTest, coverageForBook } from "../coverage.mjs";

const ctx = loadResolverContext();
const skipIfNoData = (t) => {
  if (!ctx.index || !ctx.manifest) {
    t.skip(`question-index/manifest 不可用（离线数据缺失, run=${ctx.runId}）`);
    return true;
  }
  return false;
};

/* ========================= A. 身份规范化 ========================= */

test("A1: 剑12 编号映射（1→5、5→1）与非法值拒绝", (t) => {
  if (skipIfNoData(t)) return;
  const n12 = normalizeIdentity({ book: 12, test: 1, skill: "reading" });
  assert.equal(n12.ok, true);
  assert.equal(n12.identity.test, "5");
  assert.equal(n12.identity.requested_test, "1");
  assert.ok(n12.identity.test_number_mapping, "带映射证据");
  assert.equal(n12.identity.test_number_mapping.canonical, "5");
  assert.equal(n12.identity.test_number_mapping.evidence.length, 2);
  assert.equal(String(canonicalTestOf(12, 1)), "5");
  assert.equal(String(webTestOf(12, "5")), "1");
  assert.equal(String(canonicalTestOf(12, 5)), "5");
  assert.equal(String(webTestOf(12, "1")), "1");

  const bad = normalizeIdentity({ book: 22, test: 1, skill: "reading" });
  assert.equal(bad.ok, false);
  assert.equal(bad.code, "invalid_identity");
  const badT = normalizeIdentity({ book: 1, test: 5, skill: "reading" });
  assert.equal(badT.ok, false);
  assert.equal(badT.code, "invalid_identity");
  const gta = normalizeIdentity({ book: 1, test: "gta", skill: "reading" });
  assert.equal(gta.ok, true);
  assert.equal(gta.identity.variant, "general");
  const r22 = resolveReading(22, 1);
  assert.equal(r22.ok, false);
  assert.equal(r22.code, "invalid_identity");
});

/* ========================= B. 空答案不移位 ========================= */

test("B1: 剑10 T1 阅读 Q34 空答案不移位（空槽≠缺题）", (t) => {
  if (skipIfNoData(t)) return;
  const r = resolveReading(10, 1);
  assert.equal(r.ok, true);
  assert.deepEqual(r.numbers.missing, []);
  assert.deepEqual(r.numbers.extra, []);
  assert.equal(r.numbers.observed.length, 40);
  const q34 = r.passages[2].questions.find((q) => q.number === 34);
  assert.ok(q34, "Q34 槽位存在");
  assert.equal(q34.answer_status, "empty");
  assert.equal(q34.answer.raw, "");
  assert.equal(q34.answer.form, "numbered_empty");
  assert.equal(q34.answer.status, "empty");
  assert.equal(q34.group_id, "cambridge:10:academic:reading:1:P3:G1");
  assert.equal(r.status, "partial");
  assert.deepEqual(r.status_reasons, ["answers_incomplete:1"]);

  const u = coverageForTest(ctx, 10, "1").units.find((x) => x.skill === "reading");
  assert.deepEqual(u.empty_answers, [34]);
  assert.equal(u.completion.content_complete, true);
  assert.equal(u.completion.answers_complete, false);
  assert.equal(u.completion.fully_complete, false);
});

/* ========================= C. 剑3 阅读 answer-only / 听力 pdf-extract ========================= */

test("C1: 剑3 T2（阅读 partial / 听力 pdf-extract partial:3，均不完整）", (t) => {
  if (skipIfNoData(t)) return;
  const r = resolveReading(3, 2);
  assert.equal(r.ok, true);
  assert.equal(r.status, "partial");
  assert.ok(r.status_reasons.includes("content_incomplete:5"));
  const l = resolveListening(3, 2);
  assert.equal(l.ok, true);
  assert.equal(l.status, "partial");
  assert.deepEqual(l.status_reasons, ["content_incomplete:3"]);
  assert.equal(l.source.kind, "pdf-extract");
  assert.equal(l.source.parser_version, "book3-listening/1.0.0");
  assert.deepEqual(l.parts.map((p) => p.questions.length), [10, 10, 10, 10]);

  const cov = coverageForTest(ctx, 3, "2");
  const ur = cov.units.find((x) => x.skill === "reading");
  const ul = cov.units.find((x) => x.skill === "listening");
  assert.equal(ur.completion.content_complete, false);
  assert.ok(ur.status_reasons.includes("content_incomplete"));
  assert.equal(ul.status, "partial");
  assert.equal(ul.audio.verified_count, 0);
  assert.equal(cov.completion.fully_complete, false);
  assert.equal(cov.completion.units_fully_complete, 0);
});

/* ========================= D. 剑21 多选组/音频/对齐 ========================= */

test("D1: 剑21 T1 多选 accepted sets 投影 + 音频 4/4 verified + 对齐 13/40 不完整", (t) => {
  if (skipIfNoData(t)) return;
  const l = resolveListening(21, 1);
  assert.equal(l.ok, true);
  assert.equal(l.status, "complete");
  assert.deepEqual(l.status_reasons, []);
  assert.equal(l.answer_groups.length, 2);
  const g0 = l.answer_groups.find((g) => g.numbers.join(",") === "21,22");
  assert.ok(g0, "组 21-22 存在");
  assert.deepEqual(g0.accept, ["B", "D"]);
  assert.equal(g0.required_count, 2);
  assert.equal(g0.section, 3);
  assert.equal(g0.source, "cam21-html");
  const q21 = l.parts[2].questions.find((q) => q.number === 21);
  assert.deepEqual(q21.answer.accept, ["B", "D"]);
  assert.equal(q21.answer.group_ref, g0.id);
  assert.equal(q21.type, "multiple_choice_multiple");

  const a = resolveAudio(21, 1);
  assert.equal(a.ok, true);
  assert.equal(a.parts.length, 4);
  for (const p of a.parts) {
    assert.equal(p.record.identity_status, "verified");
    assert.equal(p.record.file_exists, true);
    const raw = ctx.audioByIdentity.get(p.identity);
    assert.equal(raw.decode.ok, true);
  }

  const u = coverageForTest(ctx, 21, "1").units.find((x) => x.skill === "listening");
  assert.equal(u.audio.verified_count, 4);
  assert.equal(u.alignment.verified_count, 13);
  assert.equal(u.alignment.expected_count, 40);
  assert.equal(u.alignment.complete, false);
  assert.equal(u.completion.audio_complete, true);
  assert.equal(u.completion.alignment_complete, false);
  assert.equal(u.completion.fully_complete, false);
  assert.equal(u.status, "partial");
  const p1 = u.alignment.parts[0];
  assert.equal(p1.verified, 10);
  assert.equal(p1.questions, 10);
  assert.match(p1.audio_sha256, /^[0-9a-f]{64}$/);
  assert.equal(p1.clock.valid, true);
});

/* ========================= E. 剑12 音频映射 ========================= */

test("E1: 剑12 音频 web 编号映射；available≠verified；身份冲突保留", (t) => {
  if (skipIfNoData(t)) return;
  assert.equal(String(webTestOf(12, "5")), "1");
  assert.equal(String(canonicalTestOf(12, 1)), "5");
  const a = resolveAudio(12, "5");
  assert.equal(a.ok, true);
  assert.equal(String(a.web_test), "1");
  assert.equal(a.parts.length, 4);
  for (const p of a.parts) {
    assert.equal(p.record.identity_status, "available");
    assert.notEqual(p.record.identity_status, "verified");
    assert.equal(p.record.file_exists, true);
  }
  assert.equal(a.full_test, null);
  const t1 = resolveTest(12, "1");
  assert.equal(t1.identity.test, "5");
  assert.equal(t1.identity.test_number_mapping.requested, "1");
  const cov = coverageForTest(ctx, 12, "5");
  assert.equal(cov.ok, true);
  assert.equal(cov.units.length, 4);
  for (const u of cov.units) assert.equal(u.identity_conflicts.length, 1);
});

/* ========================= F. PDF ========================= */

test("F1: PDF — 剑20 34页抢先版、剑21 无本地（book 级不完整）", (t) => {
  if (skipIfNoData(t)) return;
  const p20 = resolvePdf(20);
  const local20 = p20.files.find((f) => f.kind === "local_book_pdf");
  assert.equal(local20.exists, true);
  assert.equal(local20.bytes, 5327081);
  assert.ok(p20.warnings.some((w) => w.kind === "local_pdf_partial"));
  const p21 = resolvePdf(21);
  assert.equal(p21.files.find((f) => f.kind === "local_book_pdf").exists, false);
  assert.ok(p21.files.find((f) => f.kind === "community_book_pdf").url.includes("ielts-21.pdf"));
  assert.equal(coverageForBook(ctx, 20).pdf.complete, false);
  assert.equal(coverageForBook(ctx, 21).pdf.complete, false);
  assert.equal(coverageForBook(ctx, 1).pdf.complete, true);
});

/* ========================= G. GT not_extracted ========================= */

test("G1: GT 阅读 not_extracted（预期 14/15/12，不冒称已抽取）", (t) => {
  if (skipIfNoData(t)) return;
  const g = resolveReading(1, "gta");
  assert.equal(g.ok, true);
  assert.equal(g.status, "not_extracted");
  assert.equal(g.content_status, "not_extracted");
  assert.equal(g.passages.length, 3);
  assert.deepEqual(g.passages.map((p) => p.expected_numbers.length), [14, 15, 12]);
  assert.deepEqual(g.passages.map((p) => p.content_present), [false, false, false]);
  assert.deepEqual(g.passages.map((p) => (p.questions || []).length), [0, 0, 0]);
  const cov = coverageForTest(ctx, 1, "gta");
  assert.equal(cov.ok, true);
  assert.equal(cov.units.length, 2);
  const ur = cov.units.find((u) => u.skill === "reading");
  assert.equal(ur.status, "not_extracted");
  assert.equal(ur.completion.content_complete, false);
  assert.equal(cov.completion.fully_complete, false);
});

/* ========================= H. 索引完整性 ========================= */

test("H1: 索引完整性 — 组身份/范围非空；answer_groups 14 条均剑21", (t) => {
  if (skipIfNoData(t)) return;
  const groups = ctx.index.groups || [];
  assert.ok(groups.length > 1000, `groups=${groups.length}`);
  for (const g of groups) {
    assert.ok(g.identity, g.id);
    assert.ok(g.identity.range && g.identity.range.length > 0, `${g.id} 空范围`);
  }
  const ags = ctx.index.answer_groups || [];
  const cam21 = ags.filter((ag) => String(ag.page_ref).startsWith("cam21:21:"));
  assert.equal(cam21.length, 14);
  for (const ag of ags) {
    assert.ok(Array.isArray(ag.accept) && ag.accept.length > 0, ag.id);
    assert.equal(ag.required_count, ag.numbers.length, ag.id);
  }
  for (const ag of cam21) {
    assert.equal(ag.numbers.length, 2);
    assert.equal(ag.accept.length, 2);
    assert.equal(ag.required_count, 2);
  }
});

/* ========================= I. 剑1 T2 41题 ========================= */

test("I1: 剑1 T2 听力 41 题不移位；Q40/41 空槽保留；缺图资产不消失", (t) => {
  if (skipIfNoData(t)) return;
  const l = resolveListening(1, 2);
  assert.equal(l.ok, true);
  assert.equal(l.numbers.expected.length, 41);
  assert.equal(l.numbers.observed.length, 41);
  assert.deepEqual(l.numbers.missing, []);
  assert.deepEqual(l.numbers.extra, []);
  assert.equal(l.status, "partial");
  assert.ok(l.status_reasons.includes("content_incomplete:2"));
  assert.ok(l.status_reasons.includes("answers_incomplete:2"));
  const p4 = l.parts[3];
  assert.deepEqual(p4.questions.map((q) => q.number), [33, 34, 35, 36, 37, 38, 39, 40, 41]);
  for (const n of [40, 41]) {
    const q = p4.questions.find((x) => x.number === n);
    assert.equal(q.group_id, null);
    assert.equal(q.answer_status, "missing");
    assert.equal(q.classification_status, "unknown");
  }
  const u = coverageForBook(ctx, 1).units.find((x) => x.test === "2" && x.skill === "listening");
  assert.ok(u.missing_assets.some((a) => a.id === "b1-t2-l-p4-diagram" && a.kind === "diagram"));
  assert.deepEqual(u.empty_answers, [40, 41]);
  assert.ok(u.status_reasons.includes("missing_assets:1"));
});

/* ========================= J. reader 单篇回落 ========================= */

test("J1: reader 单篇回落 → passages_present:1/3，content 不完整", (t) => {
  if (skipIfNoData(t)) return;
  const page = ctx.pagesByKey.get("1|1|reading");
  assert.ok(page, "剑1 T1 阅读页在索引中");
  resolveReading(1, 1, { ctx }); // 填充 parsedCache
  const cached = ctx.parsedCache.get(page.page_ref);
  assert.ok(cached && cached.doc && cached.doc.passages.length >= 3, "真实文档含 3 篇");
  const truncated = { ...cached, doc: { ...cached.doc, passages: cached.doc.passages.slice(0, 1) } };
  const clone = { ...ctx, parsedCache: new Map([[page.page_ref, truncated]]) };
  const rr = resolveReading(1, 1, { ctx: clone });
  assert.deepEqual(rr.passages.map((p) => p.content_present), [true, false, false]);
  const u = coverageForTest(clone, 1, "1").units.find((x) => x.skill === "reading");
  assert.ok(u.status_reasons.includes("passages_present:1/3"));
  assert.equal(u.completion.content_complete, false);
  assert.equal(u.completion.fully_complete, false);
});

/* ========================= K. 音频对象失败 ========================= */

test("K1: 音频对象失败 → verified 降级（1个→3/4，4个→0/4），不完整", (t) => {
  if (skipIfNoData(t)) return;
  const id1 = "cambridge:21:shared:listening:1:P1";
  const base = ctx.audioByIdentity.get(id1);
  assert.equal(base.identity_status, "verified");

  const clone1 = { ...ctx, audioByIdentity: new Map(ctx.audioByIdentity) };
  clone1.audioByIdentity.set(id1, { ...base, decode: { ok: false, error: "synthetic" } });
  const u1 = coverageForTest(clone1, 21, "1").units.find((x) => x.skill === "listening");
  assert.equal(u1.audio.verified_count, 3);
  assert.equal(u1.audio.parts[0].decode_ok, false);
  assert.ok(String(u1.audio.parts[0].reason).includes("decode_failed"));
  assert.equal(u1.completion.audio_complete, false);
  assert.equal(u1.completion.fully_complete, false);

  const clone4 = { ...ctx, audioByIdentity: new Map(ctx.audioByIdentity) };
  for (let p = 1; p <= 4; p++) {
    const id = `cambridge:21:shared:listening:1:P${p}`;
    clone4.audioByIdentity.set(id, { ...ctx.audioByIdentity.get(id), decode: { ok: false, error: "synthetic" } });
  }
  const u4 = coverageForTest(clone4, 21, "1").units.find((x) => x.skill === "listening");
  assert.equal(u4.audio.verified_count, 0);
  assert.equal(u4.completion.audio_complete, false);
  assert.equal(u4.completion.fully_complete, false);

  // 克隆变异不影响原始 ctx（回归保护）
  const u0 = coverageForTest(ctx, 21, "1").units.find((x) => x.skill === "listening");
  assert.equal(u0.audio.verified_count, 4);
});

/* ========================= L. 真实“失败音频对象”场景 ========================= */

test("L1: 剑20 T1 音频 available≠verified（4 对象未验），不计完整", (t) => {
  if (skipIfNoData(t)) return;
  const u = coverageForTest(ctx, 20, "1").units.find((x) => x.skill === "listening");
  assert.equal(u.status, "partial");
  assert.equal(u.audio.verified_count, 0);
  assert.equal(u.audio.parts.length, 4);
  for (const p of u.audio.parts) {
    assert.equal(p.verified, false);
    assert.equal(p.identity_status, "available");
  }
  assert.ok(u.status_reasons.includes("audio_verified:0/4"));
  assert.equal(u.completion.audio_complete, false);
  assert.equal(u.completion.fully_complete, false);
});
