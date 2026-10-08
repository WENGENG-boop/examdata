/**
 * coverage.mjs — S12 完整度权威对象（只读、离线，无网络）
 *
 * 语义（与 IELTS_REPAIR_IMPLEMENTATION_PLAN.md 249–251 行一致）：
 * - 单元 = (book, test, skill, variant)：21 册 ×（剑12 为 5–8，其余 1–4）× 4 技能，
 *   加上 manifest general.tests 声明的 General reading/writing 单元（不因抓不到而删分母）。
 * - content_complete：manifest 期待题/组/正文/选项/assets 齐且身份正确；
 *   阅读=三篇正文齐；听力=四 Part 原文 available。
 * - answers_complete：标准答案适用 slots 非空且无冲突；open_response（写/说）为 null。
 * - answers_verified：所有适用 slots 有独立核验（official decision）。
 * - audio_complete：期待 Parts 有「可解码且身份 verified」的音频。
 * - alignment_complete：所有期待题号有 verified 逐题对齐。
 * - fully_complete：上述适用维度全 true + 题型明确 + 分母 verified；未核验不得 fully_complete。
 * - 旧 score 字段不再承担完整度含义（由 ielts-api.mjs 改为 availability_score/deprecated）。
 */

import fs from "node:fs";
import {
  loadResolverContext,
  resolveReading,
  resolveListening,
  resolveTest,
  resolvePdf,
  RESOLVER_VERSION,
} from "./resolver.mjs";

export const COVERAGE_VERSION = "coverage/1.0.0";
export const COVERAGE_SCHEMA = "ielts.coverage/1";

/* ---------------------------------- 单元定义 ---------------------------------- */

const CANON_TESTS = (book) => (Number(book) === 12 ? ["5", "6", "7", "8"] : ["1", "2", "3", "4"]);

function unitId({ book, variant, skill, test }) {
  return `cambridge:${book}:${variant}:${skill}:${test}`;
}

/** 本册全部单元（分母不因来源缺失而删减；general 按 manifest general.tests） */
export function unitsForBook(ctx, book) {
  const b = Number(book);
  const bookNode = ctx.manifestByBook.get(b) || null;
  const units = [];
  for (const t of CANON_TESTS(b)) {
    units.push({ book: b, test: t, skill: "reading", variant: "academic" });
    units.push({ book: b, test: t, skill: "listening", variant: "shared" });
    units.push({ book: b, test: t, skill: "writing", variant: "academic" });
    units.push({ book: b, test: t, skill: "speaking", variant: "shared" });
  }
  for (const t of (bookNode?.general?.tests || []).map(String)) {
    units.push({ book: b, test: t, skill: "reading", variant: "general" });
    units.push({ book: b, test: t, skill: "writing", variant: "general" });
  }
  return units;
}

/* ---------------------------------- 工具 ---------------------------------- */

function itemsFor(bookNode, u) {
  return ((bookNode && bookNode.items) || []).filter(
    (it) => String(it.test) === String(u.test) && it.skill === u.skill && it.variant === u.variant,
  );
}

function expectedNumbers(items, fallback) {
  const nums = items.flatMap((it) => it.expected_numbers || []);
  return nums.length ? nums : fallback || [];
}

function numbersDiff(expected, observed) {
  const exp = [...new Set(expected)].sort((a, b) => a - b);
  const obs = [...new Set(observed)].sort((a, b) => a - b);
  const missing = exp.filter((n) => !obs.includes(n));
  const extra = obs.filter((n) => !exp.includes(n));
  return { expected: exp, observed: obs, missing, extra };
}

function groupMembersMissing(groups, observed) {
  const obs = new Set(observed);
  const missing = new Set();
  for (const g of groups) {
    for (const n of g.numbers || []) if (!obs.has(n)) missing.add(n);
  }
  return [...missing].sort((a, b) => a - b);
}

function hasOfficial(ctx, q) {
  const a = q.answer_ref && ctx.index && ctx.index.answers ? ctx.index.answers[q.answer_ref] : null;
  return !!(a && a.official);
}

function assetsFor(bookNode, u, rawQs, groups) {
  const missing = [];
  for (const q of rawQs) {
    if (q.content_status === "missing_asset") missing.push({ source: "index", number: q.number, kind: null });
  }
  const expectedAssets = itemsFor(bookNode, u).flatMap((it) =>
    (it.expected_assets || []).map((a) => ({ ...a, part: it.part })),
  );
  for (const a of expectedAssets) {
    const hit =
      groups.some(
        (g) =>
          (g.identity && g.identity.part === a.part && g.type === "diagram_labeling") ||
          (g.assets || []).some((x) => x.kind === a.kind && (!g.identity || g.identity.part === a.part)),
      ) ||
      rawQs.some((q) => q.part === a.part && (q.assets || []).some((x) => x.kind === a.kind));
    if (!hit) missing.push({ source: "manifest", id: a.id ?? null, kind: a.kind ?? null, note: a.note ?? null });
  }
  return { missing };
}

function conflictsFor(ctx, u) {
  const match = (c) => {
    if (c.book != null && Number(c.book) !== u.book) return false;
    if (c.test != null && String(c.test) !== String(u.test)) return false;
    if (c.skill && c.skill !== u.skill) return false;
    if (c.variant && c.variant !== u.variant) return false;
    return true;
  };
  const conflicts = ((ctx.index && ctx.index.cross_source_conflicts) || []).filter(match);
  const issues = ((ctx.index && ctx.index.verification_issues) || []).filter(match);
  const answers = conflicts
    .filter((c) => c.kind !== "test_numbering")
    .map((c) => ({
      kind: c.kind,
      decision_id: c.decision_id ?? null,
      group_id: c.group_id ?? null,
      range: c.range ?? null,
      ruling: c.ruling ?? null,
    }));
  const identity = conflicts
    .filter((c) => c.kind === "test_numbering")
    .map((c) => ({ kind: c.kind, ruling: c.ruling ?? null, mapping: (c.source && c.source.mapping) || null }));
  return {
    answers,
    identity,
    issues: issues.map((i) => ({ kind: i.kind, decision_id: i.decision_id ?? null, note: i.note ?? null })),
  };
}

function audioRecordState(rec) {
  if (!rec) {
    return { exists: false, available: false, verified: false, identity_status: null, file_ok: false, decode_ok: null, error: null, reason: "record_missing" };
  }
  const fileOk = !!(rec.file_path && fs.existsSync(rec.file_path));
  const decodeOk = rec.decode ? rec.decode.ok !== false : null;
  const identityOk = rec.identity_status === "available" || rec.identity_status === "verified";
  const noErr = !rec.error;
  const reasons = [];
  if (!identityOk) reasons.push("identity_status:" + String(rec.identity_status ?? "null"));
  if (!fileOk) reasons.push("file_missing");
  if (decodeOk === false) reasons.push("decode_failed");
  if (!noErr) reasons.push("error:" + String(rec.error));
  return {
    exists: true,
    available: identityOk && fileOk && decodeOk !== false && noErr,
    verified: identityOk && rec.identity_status === "verified" && fileOk && decodeOk === true && noErr,
    identity_status: rec.identity_status ?? null,
    file_ok: fileOk,
    decode_ok: decodeOk,
    error: rec.error ?? null,
    reason: reasons.length ? reasons.join("; ") : null,
  };
}

function audioPartsOf(ctx, u, webTest) {
  const parts = [];
  for (let p = 1; p <= 4; p++) {
    const identity = `cambridge:${u.book}:shared:listening:${webTest}:P${p}`;
    const state = audioRecordState(ctx.audioByIdentity.get(identity) || null);
    parts.push({ part: "P" + p, identity, ...state });
  }
  const fullIdentity = `cambridge:${u.book}:shared:listening:${webTest}`;
  const full = audioRecordState(ctx.audioByIdentity.get(fullIdentity) || null);
  return {
    parts,
    available_count: parts.filter((x) => x.available).length,
    verified_count: parts.filter((x) => x.verified).length,
    full_test: { identity: fullIdentity, ...full },
  };
}

function alignmentPartsOf(ctx, u, webTest, expectedTotal) {
  const parts = [];
  let verified = 0;
  let total = 0;
  for (let p = 1; p <= 4; p++) {
    const identity = `cambridge:${u.book}:shared:listening:${webTest}:P${p}`;
    const doc = ctx.alignments.get(identity) || null;
    const qs = (doc && doc.provider && doc.provider.alignment && doc.provider.alignment.questions) || [];
    const v = qs.filter((q) => q.status === "verified").length;
    verified += v;
    total += qs.length;
    parts.push({
      part: "P" + p,
      identity,
      exists: !!doc,
      questions: qs.length,
      verified: v,
      unverified: qs.length - v,
      audio_sha256: (doc && doc.provider && doc.provider.asr && doc.provider.asr.audio_sha256) || null,
      clock: (doc && doc.provider && doc.provider.alignment && doc.provider.alignment.clock) || null,
    });
  }
  return {
    parts,
    verified_count: verified,
    questions_total: total,
    expected_count: expectedTotal,
    complete: expectedTotal > 0 && verified === expectedTotal,
  };
}

function scriptPartsOf(rl) {
  const parts = (rl.parts || []).map((p) => ({
    part: p.part,
    status: (p.script && p.script.status) || null,
    source: (p.script && p.script.source) || null,
    reason: (p.script && p.script.reason) || null,
    chars: (p.script && p.script.chars) || 0,
  }));
  const counts = {};
  for (const p of parts) counts[p.status] = (counts[p.status] || 0) + 1;
  return { parts, counts, available_count: parts.filter((p) => p.status === "available").length };
}

function buildCompletion({
  content_complete,
  answers_complete,
  answers_verified,
  audio_complete,
  alignment_complete,
  types_clear,
  denominator_verified,
  reasons = [],
}) {
  const dims = [content_complete, answers_complete, answers_verified, audio_complete, alignment_complete].filter(
    (v) => v !== null,
  );
  const fully =
    dims.length > 0 && dims.every((v) => v === true) && types_clear === true && denominator_verified === true;
  return {
    content_complete,
    answers_complete,
    answers_verified,
    audio_complete,
    alignment_complete,
    types_clear,
    denominator_verified,
    fully_complete: fully,
    reasons: reasons.filter(Boolean),
  };
}

function denominatorFor(items) {
  if (!items.length) return null;
  return items.every((it) => it.status === "verified");
}

function openResponseUnit(ctx, bookNode, u, view) {
  const items = view.items;
  const denominator = denominatorFor(items);
  const raw = items.length ? items[0].status ?? null : "source_missing";
  const status = raw === "verified" ? "not_extracted" : raw === "unverified" ? "unverified" : "source_missing";
  return {
    unit_id: unitId(u),
    book: u.book,
    test: u.test,
    skill: u.skill,
    variant: u.variant,
    status,
    status_reasons: ["open_response_or_not_extracted"],
    numbers: { expected: [], observed: [], verified: [], missing: [], extra: [] },
    expected_source: items.length ? "manifest" : null,
    missing_group_members: [],
    missing_assets: [],
    missing_options: [],
    unknown_types: [],
    empty_answers: [],
    answer_conflicts: [],
    identity_conflicts: conflictsFor(ctx, u).identity,
    official: { verified_numbers: [], attached: 0, official_count: 0 },
    script_parts: null,
    audio: null,
    alignment: null,
    denominator: { verified: denominator, items: items.length },
    completion: buildCompletion({
      content_complete: false,
      answers_complete: null,
      answers_verified: null,
      audio_complete: null,
      alignment_complete: null,
      types_clear: true,
      denominator_verified: denominator,
      reasons: [
        "content_not_extracted",
        u.skill === "writing" || u.skill === "speaking" ? "open_response_no_unique_answer" : null,
      ],
    }),
    evidence: view.parts.map((p) => ({ part: p.part, status: p.status, reason: p.reason, evidence: p.evidence })),
  };
}

/* ---------------------------------- 单元构建 ---------------------------------- */

function readingUnit(ctx, bookNode, u, rr) {
  const items = itemsFor(bookNode, u);
  const page = ctx.pagesByKey.get(`${u.book}|${u.test}|reading`) || null;
  const rawQs = page ? (ctx.questionsByPage.get(page.page_ref) || []).slice().sort((a, b) => a.number - b.number) : [];
  const groups = page ? ctx.groupsByPage.get(page.page_ref) || [] : [];
  const expected = expectedNumbers(items, rr && rr.ok ? rr.numbers.expected : []);
  const observed = rawQs.map((q) => q.number);
  const diff = numbersDiff(expected, observed);
  const questionsComplete = rawQs.length > 0 && rawQs.every((q) => q.content_status === "complete");
  const missingMembers = groupMembersMissing(groups, observed);
  const assets = assetsFor(bookNode, u, rawQs, groups);
  const conflicts = conflictsFor(ctx, u);
  const officialNumbers = rawQs.filter((q) => hasOfficial(ctx, q)).map((q) => q.number);
  const emptyAnswers = rawQs
    .filter((q) => q.answer_status && q.answer_status !== "attached" && q.answer_mode !== "open_response")
    .map((q) => q.number);
  const unknownTypes = rawQs
    .filter((q) => q.type === "unknown" || (q.classification_status && q.classification_status !== "classified"))
    .map((q) => q.id)
    .concat(
      groups
        .filter((g) => g.type === "unknown" || (g.classification_status && g.classification_status !== "classified"))
        .map((g) => g.id),
    );
  const missingOptions = rawQs.filter((q) => q.content_status === "missing_options").map((q) => q.number);
  const expectedParts = items.filter((it) => it.part && /^P\d$/.test(it.part)).length;
  const passagesPresent = rr && rr.ok ? rr.passages.filter((p) => p.content_present).length : 0;
  const passagesExpected = expectedParts || (rr && rr.ok ? rr.passages.length : 0);
  const contentComplete = !!(
    rr &&
    rr.ok &&
    page &&
    observed.length > 0 &&
    diff.missing.length === 0 &&
    diff.extra.length === 0 &&
    questionsComplete &&
    missingMembers.length === 0 &&
    assets.missing.length === 0 &&
    passagesExpected > 0 &&
    passagesPresent >= passagesExpected
  );
  const answersComplete =
    observed.length > 0 && diff.missing.length === 0 && emptyAnswers.length === 0 && conflicts.answers.length === 0;
  const answersVerified = expected.length > 0 && officialNumbers.length === expected.length && conflicts.answers.length === 0;
  const typesClear = unknownTypes.length === 0;
  const denominator = denominatorFor(items);
  const reasons = [];
  if (!rr || !rr.ok) reasons.push("source_missing");
  if (!page) reasons.push("page_not_indexed");
  if (diff.missing.length) reasons.push(`missing_numbers:${diff.missing.length}`);
  if (diff.extra.length) reasons.push(`extra_numbers:${diff.extra.length}`);
  if (!questionsComplete) reasons.push("content_incomplete");
  if (missingMembers.length) reasons.push(`missing_group_members:${missingMembers.length}`);
  if (assets.missing.length) reasons.push(`missing_assets:${assets.missing.length}`);
  if (passagesPresent < passagesExpected) reasons.push(`passages_present:${passagesPresent}/${passagesExpected}`);
  if (emptyAnswers.length) reasons.push(`empty_answers:${emptyAnswers.length}`);
  if (conflicts.answers.length) reasons.push(`answer_conflicts:${conflicts.answers.length}`);
  if (!typesClear) reasons.push(`unknown_types:${unknownTypes.length}`);
  if (officialNumbers.length < expected.length) reasons.push(`official_unverified:${officialNumbers.length}/${expected.length}`);
  const completion = buildCompletion({
    content_complete: contentComplete,
    answers_complete: answersComplete,
    answers_verified: answersVerified,
    audio_complete: null,
    alignment_complete: null,
    types_clear: typesClear,
    denominator_verified: denominator,
    reasons,
  });
  return {
    unit_id: unitId(u),
    book: u.book,
    test: u.test,
    skill: u.skill,
    variant: u.variant,
    status: !page || !(rr && rr.ok) ? "source_missing" : completion.fully_complete ? "complete" : "partial",
    status_reasons: reasons,
    numbers: { ...diff, verified: officialNumbers },
    expected_source: items.length ? "manifest" : rr && rr.ok ? "structure" : null,
    source: rr && rr.ok ? rr.source : null,
    missing_group_members: missingMembers,
    missing_assets: assets.missing,
    missing_options: missingOptions,
    unknown_types: unknownTypes,
    empty_answers: emptyAnswers,
    answer_conflicts: conflicts.answers,
    identity_conflicts: conflicts.identity,
    official: { verified_numbers: officialNumbers, attached: observed.length - emptyAnswers.length, official_count: officialNumbers.length },
    script_parts: null,
    audio: null,
    alignment: null,
    passages: rr && rr.ok ? rr.passages.map((p) => ({ passage: p.passage, content_present: p.content_present, status: p.status })) : [],
    denominator: { verified: denominator, items: items.length },
    completion,
  };
}

function listeningUnit(ctx, bookNode, u, rl) {
  const items = itemsFor(bookNode, u);
  const page = ctx.pagesByKey.get(`${u.book}|${u.test}|listening`) || null;
  const rawQs = page ? (ctx.questionsByPage.get(page.page_ref) || []).slice().sort((a, b) => a.number - b.number) : [];
  const groups = page ? ctx.groupsByPage.get(page.page_ref) || [] : [];
  const expected = expectedNumbers(items, rl && rl.ok ? rl.numbers.expected : []);
  const observed = rawQs.map((q) => q.number);
  const diff = numbersDiff(expected, observed);
  const questionsComplete = rawQs.length > 0 && rawQs.every((q) => q.content_status === "complete");
  const missingMembers = groupMembersMissing(groups, observed);
  const assets = assetsFor(bookNode, u, rawQs, groups);
  const conflicts = conflictsFor(ctx, u);
  const officialNumbers = rawQs.filter((q) => hasOfficial(ctx, q)).map((q) => q.number);
  const emptyAnswers = rawQs
    .filter((q) => q.answer_status && q.answer_status !== "attached" && q.answer_mode !== "open_response")
    .map((q) => q.number);
  const unknownTypes = rawQs
    .filter((q) => q.type === "unknown" || (q.classification_status && q.classification_status !== "classified"))
    .map((q) => q.id)
    .concat(
      groups
        .filter((g) => g.type === "unknown" || (g.classification_status && g.classification_status !== "classified"))
        .map((g) => g.id),
    );
  const missingOptions = rawQs.filter((q) => q.content_status === "missing_options").map((q) => q.number);
  const scripts = rl && rl.ok ? scriptPartsOf(rl) : { parts: [], counts: {}, available_count: 0 };
  const webTest = rl && rl.ok ? rl.web_test : String(u.test);
  const audio = audioPartsOf(ctx, u, webTest);
  const alignment = alignmentPartsOf(ctx, u, webTest, expected.length);
  const scriptsAvailable = scripts.parts.length === 4 && scripts.available_count === 4;
  const contentComplete = !!(
    rl &&
    rl.ok &&
    page &&
    observed.length > 0 &&
    diff.missing.length === 0 &&
    diff.extra.length === 0 &&
    questionsComplete &&
    missingMembers.length === 0 &&
    assets.missing.length === 0 &&
    scriptsAvailable
  );
  const answersComplete =
    observed.length > 0 && diff.missing.length === 0 && emptyAnswers.length === 0 && conflicts.answers.length === 0;
  const answersVerified = expected.length > 0 && officialNumbers.length === expected.length && conflicts.answers.length === 0;
  const typesClear = unknownTypes.length === 0;
  const denominator = denominatorFor(items);
  const audioComplete = audio.verified_count === 4;
  const reasons = [];
  if (!rl || !rl.ok) reasons.push("source_missing");
  if (!page) reasons.push("page_not_indexed");
  if (diff.missing.length) reasons.push(`missing_numbers:${diff.missing.length}`);
  if (diff.extra.length) reasons.push(`extra_numbers:${diff.extra.length}`);
  if (!questionsComplete) reasons.push("content_incomplete");
  if (missingMembers.length) reasons.push(`missing_group_members:${missingMembers.length}`);
  if (assets.missing.length) reasons.push(`missing_assets:${assets.missing.length}`);
  if (!scriptsAvailable) reasons.push(`scripts_available:${scripts.available_count}/4`);
  if (emptyAnswers.length) reasons.push(`empty_answers:${emptyAnswers.length}`);
  if (conflicts.answers.length) reasons.push(`answer_conflicts:${conflicts.answers.length}`);
  if (!typesClear) reasons.push(`unknown_types:${unknownTypes.length}`);
  if (officialNumbers.length < expected.length) reasons.push(`official_unverified:${officialNumbers.length}/${expected.length}`);
  if (!audioComplete) reasons.push(`audio_verified:${audio.verified_count}/4`);
  if (!alignment.complete) reasons.push(`alignment_verified:${alignment.verified_count}/${expected.length}`);
  const completion = buildCompletion({
    content_complete: contentComplete,
    answers_complete: answersComplete,
    answers_verified: answersVerified,
    audio_complete: audioComplete,
    alignment_complete: alignment.complete,
    types_clear: typesClear,
    denominator_verified: denominator,
    reasons,
  });
  return {
    unit_id: unitId(u),
    book: u.book,
    test: u.test,
    skill: u.skill,
    variant: u.variant,
    status: !page || !(rl && rl.ok) ? "source_missing" : completion.fully_complete ? "complete" : "partial",
    status_reasons: reasons,
    numbers: { ...diff, verified: officialNumbers },
    expected_source: items.length ? "manifest" : rl && rl.ok ? "structure" : null,
    source: rl && rl.ok ? rl.source : null,
    missing_group_members: missingMembers,
    missing_assets: assets.missing,
    missing_options: missingOptions,
    unknown_types: unknownTypes,
    empty_answers: emptyAnswers,
    answer_conflicts: conflicts.answers,
    identity_conflicts: conflicts.identity,
    official: { verified_numbers: officialNumbers, attached: observed.length - emptyAnswers.length, official_count: officialNumbers.length },
    script_parts: scripts,
    audio,
    alignment,
    denominator: { verified: denominator, items: items.length },
    completion,
  };
}

function generalReadingUnit(ctx, bookNode, u) {
  const items = itemsFor(bookNode, u);
  const rr = resolveReading(u.book, u.test, { ctx });
  const expected = expectedNumbers(items, []);
  const denominator = denominatorFor(items);
  const status = rr.content_status || "source_missing";
  const reasons = ["content_not_indexed"];
  if (status === "unverified") reasons.push("presence_unverified");
  if (status === "source_missing") reasons.push("source_missing");
  return {
    unit_id: unitId(u),
    book: u.book,
    test: u.test,
    skill: u.skill,
    variant: u.variant,
    status,
    status_reasons: reasons,
    numbers: { expected, observed: [], verified: [], missing: expected, extra: [] },
    expected_source: items.length ? "manifest" : null,
    source: { presence_status: rr.presence_status ?? null, general_meta: rr.general_meta ?? null },
    missing_group_members: [],
    missing_assets: [],
    missing_options: [],
    unknown_types: [],
    empty_answers: [],
    answer_conflicts: conflictsFor(ctx, u).answers,
    identity_conflicts: conflictsFor(ctx, u).identity,
    official: { verified_numbers: [], attached: 0, official_count: 0 },
    script_parts: null,
    audio: null,
    alignment: null,
    denominator: { verified: denominator, items: items.length },
    completion: buildCompletion({
      content_complete: false,
      answers_complete: null,
      answers_verified: null,
      audio_complete: null,
      alignment_complete: null,
      types_clear: true,
      denominator_verified: denominator,
      reasons,
    }),
  };
}

/* ---------------------------------- 书/套 ---------------------------------- */

export function coverageForBook(ctx, book, opts = {}) {
  const b = Number(book);
  const bookNode = ctx.manifestByBook.get(b) || null;
  const testCache = new Map();
  const getTest = (t) => {
    if (!testCache.has(String(t))) testCache.set(String(t), resolveTest(b, t, { ctx, ...opts }));
    return testCache.get(String(t));
  };
  const units = [];
  for (const u of unitsForBook(ctx, b)) {
    if (u.variant === "general") {
      units.push(u.skill === "reading" ? generalReadingUnit(ctx, bookNode, u) : openResponseUnit(ctx, bookNode, u, manifestView(bookNode, u)));
    } else if (u.skill === "reading") {
      const rt = getTest(u.test);
      units.push(readingUnit(ctx, bookNode, u, rt.reading));
    } else if (u.skill === "listening") {
      const rt = getTest(u.test);
      units.push(listeningUnit(ctx, bookNode, u, rt.listening));
    } else {
      units.push(openResponseUnit(ctx, bookNode, u, manifestView(bookNode, u)));
    }
  }
  const pdf = resolvePdf(b, null, { ctx });
  const local = (pdf.files || []).find((f) => f.kind === "local_book_pdf") || null;
  const pdfComplete = !!(local && local.exists) && b !== 20 && b !== 21;
  const pdfNote =
    b === 20
      ? "本地 book_20.pdf 为 34 页抢先版（仅 Test1 部分），不得当整册"
      : b === 21
        ? "无本地整册 PDF；仅社区镜像直链（未本地核验）"
        : pdfComplete
          ? "本地整册 PDF 存在"
          : "本地整册 PDF 缺失";
  const counts = { total: units.length, complete: 0, partial: 0, source_missing: 0, not_extracted: 0, unverified: 0, fully_complete: 0 };
  for (const u of units) {
    counts[u.status] = (counts[u.status] || 0) + 1;
    if (u.completion.fully_complete) counts.fully_complete++;
  }
  const allUnitsFully = units.length > 0 && units.every((u) => u.completion.fully_complete);
  return {
    book: b,
    edition: bookNode ? bookNode.edition ?? null : null,
    general: bookNode
      ? { status: bookNode.general?.status ?? null, tests: bookNode.general?.tests ?? [], reason: bookNode.general?.reason ?? null }
      : null,
    pdf: { scope: "book", complete: pdfComplete, note: pdfNote, local_exists: !!(local && local.exists), files: pdf.files, warnings: pdf.warnings },
    units,
    unit_counts: counts,
    completion: {
      units_total: units.length,
      units_fully_complete: counts.fully_complete,
      all_units_fully_complete: allUnitsFully,
      pdf_complete: pdfComplete,
      fully_complete: allUnitsFully && pdfComplete,
    },
  };
}

function manifestView(bookNode, u) {
  const items = itemsFor(bookNode, u);
  const byPart = new Map();
  for (const it of items) {
    if (!byPart.has(it.part)) byPart.set(it.part, []);
    byPart.get(it.part).push(it);
  }
  return {
    items,
    status: items.length ? items[0].status ?? null : "source_missing",
    parts: [...byPart.entries()].map(([part, its]) => ({
      part,
      status: its[0].status ?? null,
      reason: its[0].reason ?? null,
      expected_numbers: its.flatMap((x) => x.expected_numbers || []),
      evidence: its.flatMap((x) => x.evidence || []),
    })),
  };
}

export function coverageForTest(ctx, book, test, opts = {}) {
  const b = Number(book);
  if (!Number.isInteger(b) || b < 1 || b > 21) {
    return { ok: false, code: "invalid_identity", error: "book 需为 1–21 的整数" };
  }
  const t = String(test);
  const bookNode = ctx.manifestByBook.get(b) || null;
  const units = [];
  if (/^gt[ab]$/i.test(t)) {
    const tt = t.toLowerCase();
    if (!(bookNode?.general?.tests || []).map(String).includes(tt)) {
      return { ok: false, code: "not_in_book", error: `剑${b} 无 general test ${tt}（manifest general.tests）` };
    }
    units.push(generalReadingUnit(ctx, bookNode, { book: b, test: tt, skill: "reading", variant: "general" }));
    units.push(openResponseUnit(ctx, bookNode, { book: b, test: tt, skill: "writing", variant: "general" }, manifestView(bookNode, { book: b, test: tt, skill: "writing", variant: "general" })));
  } else {
    if (!CANON_TESTS(b).includes(t)) {
      return { ok: false, code: "invalid_identity", error: `剑${b} test 需为 ${CANON_TESTS(b).join("/")}` };
    }
    const rt = resolveTest(b, t, { ctx, ...opts });
    units.push(readingUnit(ctx, bookNode, { book: b, test: t, skill: "reading", variant: "academic" }, rt.reading));
    units.push(listeningUnit(ctx, bookNode, { book: b, test: t, skill: "listening", variant: "shared" }, rt.listening));
    units.push(openResponseUnit(ctx, bookNode, { book: b, test: t, skill: "writing", variant: "academic" }, manifestView(bookNode, { book: b, test: t, skill: "writing", variant: "academic" })));
    units.push(openResponseUnit(ctx, bookNode, { book: b, test: t, skill: "speaking", variant: "shared" }, manifestView(bookNode, { book: b, test: t, skill: "speaking", variant: "shared" })));
  }
  return {
    ok: true,
    schema: COVERAGE_SCHEMA,
    version: COVERAGE_VERSION,
    resolver: RESOLVER_VERSION,
    run_id: ctx.runId,
    book: b,
    test: t,
    units,
    completion: {
      units_total: units.length,
      units_fully_complete: units.filter((u) => u.completion.fully_complete).length,
      fully_complete: units.length > 0 && units.every((u) => u.completion.fully_complete),
    },
  };
}

/* ---------------------------------- 汇总 ---------------------------------- */

export function buildCoverage(opts = {}) {
  const ctx = opts.ctx || loadResolverContext(opts);
  const books = [];
  for (let b = 1; b <= 21; b++) books.push(coverageForBook(ctx, b, opts));
  const summary = summarizeCoverage(books, { run_id: ctx.runId, data_dir: ctx.dataDir });
  return {
    ok: true,
    schema: COVERAGE_SCHEMA,
    version: COVERAGE_VERSION,
    resolver: RESOLVER_VERSION,
    run_id: ctx.runId,
    data_dir: ctx.dataDir,
    generated_at_utc: new Date().toISOString(),
    books,
    summary,
    warnings: ctx.warnings,
  };
}

export function summarizeCoverage(input, meta = {}) {
  const books = Array.isArray(input) ? input : (input && input.books) || [];
  const unitStatus = { complete: 0, partial: 0, source_missing: 0, not_extracted: 0, unverified: 0 };
  const bySkill = {};
  const byBook = [];
  let units = 0;
  let fully = 0;
  let audioVerified = 0;
  let alignmentComplete = 0;
  for (const bk of books) {
    let bookFully = 0;
    for (const u of bk.units || []) {
      units++;
      if (u.completion && u.completion.fully_complete) {
        fully++;
        bookFully++;
      }
      if (Object.prototype.hasOwnProperty.call(unitStatus, u.status)) unitStatus[u.status]++;
      const key = `${u.skill}/${u.variant}`;
      if (!bySkill[key]) bySkill[key] = { units: 0, fully_complete: 0, audio_verified_units: 0, alignment_complete_units: 0 };
      bySkill[key].units++;
      if (u.completion && u.completion.fully_complete) bySkill[key].fully_complete++;
      if (u.audio && u.audio.verified_count === 4) {
        audioVerified++;
        bySkill[key].audio_verified_units++;
      }
      if (u.alignment && u.alignment.complete) {
        alignmentComplete++;
        bySkill[key].alignment_complete_units++;
      }
    }
    byBook.push({
      book: bk.book,
      units: (bk.units || []).length,
      fully_complete: bookFully,
      pdf_complete: !!(bk.completion && bk.completion.pdf_complete),
    });
  }
  return {
    schema: COVERAGE_SCHEMA,
    version: COVERAGE_VERSION,
    generated_at_utc: meta.generated_at_utc || new Date().toISOString(),
    run_id: meta.run_id ?? null,
    data_dir: meta.data_dir ?? null,
    books: books.length,
    units,
    unit_status: unitStatus,
    fully_complete_units: fully,
    units_with_audio_verified: audioVerified,
    units_with_alignment_complete: alignmentComplete,
    books_pdf_complete: byBook.filter((b) => b.pdf_complete).map((b) => b.book),
    by_skill: bySkill,
    by_book: byBook,
  };
}
