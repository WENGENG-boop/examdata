/**
 * resolver.mjs — S12 统一解析/查询层（只读、离线，无网络）
 *
 * 职责：把 ielts-data run 产物（question-index / audio-catalog / alignment /
 * cam21-transcripts）+ 本地 raw/原文/PDF 组合成规范化的 resolve 结果。
 *
 * 约定：
 * - 所有函数不联网、不写文件；缺任何输入都如实返回 status/error（不 throw、不静默回落）。
 * - 题号/答案/组以 question-index 为准；原文正文按 page.raw_file 重解析（索引不存正文）。
 * - 剑12 编号裁决：对外请求 1–4 视为网页编号并映射到原书内部 5–8（带 mapping 记录，
 *   与 build-question-index.mjs 的 TEST_NUMBER_MAP 一致）；音频目录身份使用网页编号
 *   （webTestOf 反向映射）。
 * - 音频：先验证目录记录身份与实际文件（file_exists/content_sha256），
 *   再挂对齐；对齐缺失记 not_run，不生成假的 verified 区间。
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { WORKSPACE_ROOT, resolveDataDir, readJson } from "./data-store.mjs";
import { parsePtePage, expectedFor } from "./pte.mjs";
import { parseReadingHtml, parseListeningHtml } from "./cam21.mjs";
import { parseBook3ListeningPage } from "./book3-listening.mjs";
import { BOOK_PDF, BOOK_PDF_ALT, BOOK20_TESTS, url as lfsUrl } from "./lfs.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));

export const RESOLVER_VERSION = "resolver/1.0.0";
export const RESOLVE_SCHEMA = "ielts.resolve/1";

/* ------------------------------ 编号裁决（与 build 工具一致） ------------------------------ */

export const TEST_NUMBER_MAP = { 12: { 1: 5, 2: 6, 3: 7, 4: 8 } };
export const TEST_NUMBER_EVIDENCE = {
  12: [
    "book_12.pdf 目录页: Test 5 p10 / Test 6 p30 / Test 7 p53 / Test 8 p74",
    "内容比对: PTE t1-t4 听力/阅读与 Test 5-8 逐套命中（Kenton Festival, Flying tortoises, Glass 等）",
  ],
};

/** 网页/顺序编号 → 原书内部编号（无映射册原样返回） */
export function canonicalTestOf(book, test) {
  const m = TEST_NUMBER_MAP[Number(book)];
  const mapped = m ? m[Number(test)] : undefined;
  return mapped != null ? String(mapped) : test;
}

/** 原书内部编号 → 网页/顺序编号（音频/对齐目录身份使用；无映射册原样返回） */
export function webTestOf(book, canonical) {
  const m = TEST_NUMBER_MAP[Number(book)];
  if (!m) return String(canonical);
  const entry = Object.entries(m).find(([, canon]) => String(canon) === String(canonical));
  return entry ? entry[0] : String(canonical);
}

/* ---------------------------------- run 发现 ---------------------------------- */

/** 含 index/question-index.json 的 run 目录名（字典序取最后 = 最新） */
export function findLatestRun(dataDir) {
  const root = resolveDataDir(dataDir);
  const runsDir = path.join(root, "runs");
  if (!fs.existsSync(runsDir)) return null;
  const candidates = [];
  for (const name of fs.readdirSync(runsDir)) {
    if (fs.existsSync(path.join(runsDir, name, "index", "question-index.json"))) candidates.push(name);
  }
  candidates.sort();
  return candidates.length ? candidates[candidates.length - 1] : null;
}

/* ---------------------------------- 上下文 ---------------------------------- */

const pushTo = (map, key, v) => {
  if (!map.has(key)) map.set(key, []);
  map.get(key).push(v);
};

/**
 * 载入 resolver 上下文（全部本地文件；缺失记 warnings，不 throw）。
 * @param {{dataDir?:string, runId?:string}} opts
 */
export function loadResolverContext(opts = {}) {
  const dataDir = resolveDataDir(opts.dataDir);
  const warnings = [];
  const runId = opts.runId || findLatestRun(dataDir);
  if (!runId) warnings.push({ kind: "no_run", note: "未找到含 question-index.json 的 run 目录" });
  const runDir = runId ? path.join(dataDir, "runs", runId) : null;

  const index = runDir ? readJson(path.join(runDir, "index", "question-index.json")) : null;
  if (!index) warnings.push({ kind: "index_missing", note: runDir ? path.join(runDir, "index", "question-index.json") : null });
  const audioCatalog = runDir ? readJson(path.join(runDir, "audio", "audio-catalog.json")) : null;
  if (!audioCatalog) warnings.push({ kind: "audio_catalog_missing" });
  const cam21Transcripts = runDir ? readJson(path.join(runDir, "audio", "cam21-transcripts.json")) : null;
  if (!cam21Transcripts) warnings.push({ kind: "cam21_transcripts_missing" });
  const manifest = readJson(path.join(HERE, "data", "expected-manifest.json"));
  if (!manifest) warnings.push({ kind: "manifest_missing" });

  const alignments = new Map();
  if (runDir) {
    const adir = path.join(runDir, "alignment");
    if (fs.existsSync(adir)) {
      for (const f of fs.readdirSync(adir)) {
        if (!f.endsWith(".json") || f.endsWith(".asr.json") || f === "summary.json") continue;
        const doc = readJson(path.join(adir, f));
        if (doc && doc.identity) alignments.set(doc.identity, doc);
      }
    } else {
      warnings.push({ kind: "alignment_dir_missing" });
    }
  }

  const pagesByKey = new Map(); // `${book}|${test}|${skill}` → page（skill: reading|listening）
  const pageByRef = new Map();
  for (const p of index?.pages || []) {
    pageByRef.set(p.page_ref, p);
    pagesByKey.set(`${p.book}|${p.test}|${p.skill}`, p);
  }
  const groupsByPage = new Map();
  const questionsByPage = new Map();
  for (const g of index?.groups || []) pushTo(groupsByPage, g.page_ref, g);
  for (const q of index?.questions || []) pushTo(questionsByPage, q.page_ref, q);
  const audioByIdentity = new Map();
  for (const r of audioCatalog?.records || []) if (r.identity) audioByIdentity.set(r.identity, r);
  const manifestByBook = new Map();
  for (const b of manifest?.books || []) manifestByBook.set(b.book, b);

  return {
    dataDir,
    runId,
    runDir,
    index,
    audioCatalog,
    cam21Transcripts,
    manifest,
    alignments,
    pagesByKey,
    pageByRef,
    groupsByPage,
    questionsByPage,
    audioByIdentity,
    manifestByBook,
    parsedCache: new Map(),
    scriptCache: new Map(),
    warnings,
  };
}

/* ---------------------------------- 身份规范化 ---------------------------------- */

const SKILLS = ["reading", "listening", "writing", "speaking"];

function normalizePart(input, skill) {
  if (input == null) return null;
  const s = String(input).trim().toUpperCase();
  if (skill === "writing") {
    const m = /^(?:WT)?([12])$/.exec(s);
    return m ? "WT" + m[1] : null;
  }
  if (skill === "speaking") return s === "SP" || s === "1" ? "SP" : null;
  const m = /^P?([1-4])$/.exec(s);
  return m ? "P" + m[1] : null;
}

/**
 * 校验/规范化身份。test 可为 1–4、剑12 的 5–8 或 gta/gtb；剑12 的 1–4 自动映射到 5–8。
 * @returns {{ok:true, identity}|{ok:false, code:"invalid_identity", error:string}}
 */
export function normalizeIdentity(input = {}) {
  const book = Number(input.book);
  if (!Number.isInteger(book) || book < 1 || book > 21) {
    return { ok: false, code: "invalid_identity", error: "book 需为 1–21 的整数" };
  }
  let test;
  let variant = null;
  let mapping = null;
  const rawTest = input.test;
  if (typeof rawTest === "string" && /^gt[ab]$/i.test(rawTest.trim())) {
    test = rawTest.trim().toLowerCase();
    variant = "general";
  } else {
    const t = Number(rawTest);
    if (!Number.isInteger(t) || t < 1 || t > 8) {
      return { ok: false, code: "invalid_identity", error: "test 需为 1–4（剑12 可 1–8）或 gta/gtb" };
    }
    if (t > 4 && book !== 12) {
      return { ok: false, code: "invalid_identity", error: "test 5–8 仅适用于剑12（原书内部编号）" };
    }
    test = String(t);
    if (book === 12) {
      const canon = TEST_NUMBER_MAP[12][t];
      if (canon != null) {
        mapping = { requested: String(t), canonical: String(canon), evidence: TEST_NUMBER_EVIDENCE[12] };
        test = String(canon);
      }
    }
  }

  let skill = String(input.skill || "reading").toLowerCase();
  if (!SKILLS.includes(skill)) {
    return { ok: false, code: "invalid_identity", error: `skill 需为 ${SKILLS.join("|")}` };
  }
  if (variant === "general" && skill !== "reading") {
    return { ok: false, code: "invalid_identity", error: "gta/gtb 仅适用于 general reading" };
  }
  if (variant == null) variant = skill === "reading" ? "academic" : "shared";

  const part = normalizePart(input.part, skill);
  if (input.part != null && part == null) {
    return { ok: false, code: "invalid_identity", error: `part 无效: ${JSON.stringify(input.part)}` };
  }
  let passage = null;
  if (input.passage != null) {
    passage = Number(input.passage);
    if (!Number.isInteger(passage) || passage < 1 || passage > 3) {
      return { ok: false, code: "invalid_identity", error: "passage 需为 1–3" };
    }
  }

  const sourceSkill = variant === "general" ? "general_reading" : skill === "reading" ? "academic_reading" : skill;
  const identity = {
    book,
    test,
    requested_test: mapping ? mapping.requested : String(rawTest),
    variant,
    skill,
    source_skill: sourceSkill,
    part,
    passage,
  };
  if (mapping) identity.test_number_mapping = mapping;
  return { ok: true, identity };
}

/* ---------------------------------- 重解析（正文） ---------------------------------- */

/** 按 page.raw_file 重解析页面（缓存）；返回 {doc, error, raw_file} */
function parsedPageFor(ctx, page) {
  if (!page) return { doc: null, error: "no_page", raw_file: null };
  if (ctx.parsedCache.has(page.page_ref)) return ctx.parsedCache.get(page.page_ref);
  let out;
  const file = page.raw_file ? path.join(WORKSPACE_ROOT, page.raw_file) : null;
  try {
    if (!file || !fs.existsSync(file)) {
      out = { doc: null, error: "raw_file_missing", raw_file: page.raw_file };
    } else if (page.kind === "pdf-extract" && page.book === 3 && page.skill === "listening") {
      const doc = parseBook3ListeningPage(page.test, { file: page.raw_file });
      out = { doc, error: doc && doc.ok ? null : "parse_failed", raw_file: page.raw_file };
    } else if (page.kind === "cam21-html") {
      const html = fs.readFileSync(file, "utf8");
      const doc =
        page.skill === "listening"
          ? parseListeningHtml(html, { book: page.book, test: page.test, skill: "listening", file: page.raw_file })
          : parseReadingHtml(html, { book: page.book, test: page.test, skill: "reading", file: page.raw_file });
      out = { doc, error: doc && doc.ok ? null : "parse_failed", raw_file: page.raw_file };
    } else {
      const text = fs.readFileSync(file, "utf8");
      const srcSkill = page.source_skill || (page.skill === "listening" ? "listening" : "academic_reading");
      const expected = expectedFor(page.book, page.test, srcSkill);
      const doc = parsePtePage(
        text,
        { book: page.book, test: page.test, skill: srcSkill, slug: page.slug, page_id: page.source_page_id },
        expected,
      );
      out = { doc, error: doc && doc.ok ? null : (doc && doc.error) || "parse_failed", raw_file: page.raw_file };
    }
  } catch (e) {
    out = { doc: null, error: "read_error: " + (e && e.message), raw_file: page.raw_file };
  }
  ctx.parsedCache.set(page.page_ref, out);
  return out;
}

/* ---------------------------------- 投影工具 ---------------------------------- */

function projectAnswer(ans) {
  if (!ans) return null;
  const out = { raw: ans.raw, form: ans.form, status: ans.status, source: ans.source, ref: ans.ref };
  if (ans.accept != null) out.accept = ans.accept;
  if (ans.group_ref != null) out.group_ref = ans.group_ref;
  if (ans.note != null) out.note = ans.note;
  if (ans.official != null) out.official = ans.official;
  return out;
}

function projectQuestion(ctx, q, alignByNumber = null) {
  const ans = q.answer_ref && ctx.index && ctx.index.answers ? ctx.index.answers[q.answer_ref] : null;
  const out = {
    ...q,
    answer: projectAnswer(ans),
  };
  if (alignByNumber && alignByNumber.has(q.number)) out.audio_alignment = alignByNumber.get(q.number);
  return out;
}

/** 多选答案组（inputs/accepted set/required_count；无序集合评分语义）——按 page_ref 投影 */
function projectAnswerGroups(ctx, page) {
  const ags = (ctx.index && ctx.index.answer_groups) || [];
  return ags
    .filter((ag) => page && ag.page_ref === page.page_ref)
    .map((ag) => ({
      id: ag.id,
      numbers: ag.numbers || [],
      inputs_raw: ag.inputs_raw || [],
      accept: ag.accept || [],
      required_count: ag.required_count ?? null,
      section: ag.section ?? null,
      source: ag.source ?? null,
    }));
}

function projectAudio(rec) {
  if (!rec) return null;
  return {
    audio_id: rec.audio_id,
    identity: rec.identity,
    scope: rec.scope,
    part: rec.part ?? null,
    status: rec.status,
    source: rec.source,
    identity_status: rec.identity_status ?? null,
    content_sha256: rec.content_sha256 ?? null,
    bytes: rec.bytes ?? null,
    duration_sec: rec.duration_sec ?? null,
    container: rec.container ?? null,
    codec: rec.codec ?? null,
    sample_rate: rec.sample_rate ?? null,
    channels: rec.channels ?? null,
    file_path: rec.file_path ?? null,
    file_exists: rec.file_path ? fs.existsSync(rec.file_path) : false,
    urls: (rec.urls || []).map((u) => ({ url: u.url, via: u.via, tried: !!u.tried, last_error: u.last_error ?? null })),
    local_samples: (rec.local_samples || []).map((s) => ({
      ...s,
      file_exists: fs.existsSync(path.join(WORKSPACE_ROOT, s.path)),
    })),
    verification_refs: rec.verification_refs ?? null,
    fetched_at: rec.fetched_at ?? null,
    tree_blob: rec.tree_blob ?? null,
    error: rec.error ?? null,
  };
}

function projectAlignment(doc) {
  if (!doc) return { status: "not_run", questions: [], counts: {} };
  const qs = (doc.provider?.alignment?.questions || []).map((q) => ({
    number: q.number,
    group_id: q.group_id ?? null,
    status: q.status,
    intervals: q.intervals || [],
    confidence: q.confidence ?? null,
  }));
  const counts = {};
  for (const q of qs) counts[q.status] = (counts[q.status] || 0) + 1;
  return {
    status: qs.length ? "ok" : "empty",
    identity: doc.identity,
    method: doc.provider?.alignment?.method ?? null,
    clock: doc.provider?.alignment?.clock ?? null,
    audio_sha256: doc.provider?.asr?.audio_sha256 ?? null,
    asr_model: doc.provider?.asr?.model_version ?? null,
    generated_at: doc.generated_at ?? null,
    elapsed_sec: doc.elapsed_sec ?? null,
    questions: qs,
    counts,
  };
}

function numbersDiff(expected, observed) {
  const exp = [...new Set(expected)].sort((a, b) => a - b);
  const obs = [...new Set(observed)].sort((a, b) => a - b);
  const missing = exp.filter((n) => !obs.includes(n));
  const extra = obs.filter((n) => !exp.includes(n));
  return { expected: exp, observed: obs, missing, extra };
}

function completenessStatus({ page, questions, missingNumbers, notes = [] }) {
  if (!page) return { status: "source_missing", reasons: ["page_not_indexed"] };
  if (!questions.length) return { status: "missing_content", reasons: ["no_questions_indexed"] };
  const reasons = [];
  if (missingNumbers.length) reasons.push(`missing_numbers:${missingNumbers.length}`);
  const contentBad = questions.filter((q) => q.content_status && q.content_status !== "complete");
  if (contentBad.length) reasons.push(`content_incomplete:${contentBad.length}`);
  const answerBad = questions.filter(
    (q) => q.answer_status && q.answer_status !== "attached" && q.answer_mode !== "open_response",
  );
  if (answerBad.length) reasons.push(`answers_incomplete:${answerBad.length}`);
  for (const n of notes) reasons.push(n);
  return { status: reasons.length ? "partial" : "complete", reasons };
}

/* ------------------------------- 期望题号（parts） ------------------------------- */

function flattenParts(parts) {
  if (!Array.isArray(parts)) return [];
  return parts
    .filter((p) => Array.isArray(p.ranges) && p.ranges.length)
    .map((p) => {
      const numbers = [];
      for (const [a, z] of p.ranges) for (let n = a; n <= z; n++) numbers.push(n);
      return { part: p.part, ranges: p.ranges, numbers, pages: p.pages ?? null };
    });
}

function partExpected(expected, partIndex) {
  if (!expected) return [];
  const flat = flattenParts(expected.parts);
  const hit = flat.find((p) => String(p.part).toUpperCase() === "P" + partIndex);
  if (hit) return hit.numbers;
  return expected.numbers || [];
}

/* ---------------------------------- 阅读 ---------------------------------- */

/**
 * 阅读解析：剑1–20（PTE raw，含剑12 编号映射）、剑21（cam21 HTML）、GT（manifest 预期）。
 * @param {number} book 1–21
 * @param {number|string} test 1–4（剑12 1–8）或 gta/gtb
 * @param {{passage?:number, ctx?:object, dataDir?:string, runId?:string, variant?:string}} opts
 */
export function resolveReading(book, test, opts = {}) {
  const ctx = opts.ctx || loadResolverContext(opts);
  const norm = normalizeIdentity({ book, test, skill: "reading", variant: opts.variant });
  if (!norm.ok) return norm;
  const id = norm.identity;
  if (id.variant === "general") return resolveGeneralReading(ctx, id, opts);

  const page = ctx.pagesByKey.get(`${id.book}|${id.test}|reading`);
  if (!page) {
    return {
      ok: false,
      schema: RESOLVE_SCHEMA,
      resolver: RESOLVER_VERSION,
      identity: id,
      run_id: ctx.runId,
      code: "source_missing",
      error: `索引中无 ${id.book} 册 Test ${id.test} 阅读页（PTE raw 未抓取或未进索引）`,
      expected: expectedFor(id.book, id.test, "academic_reading"),
      warnings: ctx.warnings,
    };
  }

  const { doc, error: parseError } = parsedPageFor(ctx, page);
  const expected = expectedFor(id.book, id.test, "academic_reading") || page.expected || null;
  const questionsAll = (ctx.questionsByPage.get(page.page_ref) || []).slice().sort((a, b) => a.number - b.number);
  const groupsAll = (ctx.groupsByPage.get(page.page_ref) || []).slice();
  const flat = flattenParts(expected && expected.parts);
  const passageCount = Math.max(
    flat.length,
    doc && Array.isArray(doc.passages) ? doc.passages.length : 0,
    3,
  );

  const passageContentFor = (d, i) => {
    if (!d || !Array.isArray(d.passages)) return null;
    const zeroBasedPassage = d.passages.some((p) => Number(p.passage) === 0);
    return (
      d.passages.find((p) => {
        if (p.passage != null) return Number(p.passage) + (zeroBasedPassage ? 1 : 0) === i;
        if (p.index != null) return Number(p.index) + 1 === i;
        return false;
      }) || null
    );
  };

  const passages = [];
  for (let i = 1; i <= passageCount; i++) {
    if (opts.passage != null && Number(opts.passage) !== i) continue;
    const partKey = "P" + i;
    const expNumbers = flat.length ? flat.find((p) => String(p.part).toUpperCase() === partKey)?.numbers || [] : (expected?.numbers || []);
    const questions = questionsAll.filter((q) => q.passage === i || (!q.passage && q.part === partKey));
    const groups = groupsAll.filter((g) => (g.identity && (g.identity.part === partKey || g.identity.range)) && g.identity?.part === partKey);
    const diff = numbersDiff(expNumbers, questions.map((q) => q.number));
    const content = passageContentFor(doc, i);
    const st = completenessStatus({ page, questions, missingNumbers: diff.missing });
    passages.push({
      passage: i,
      part: partKey,
      title: content ? content.title ?? null : null,
      title_is_label: content ? content.title_is_label ?? null : null,
      paragraphs: content ? (content.paragraphs || []).map((p) => (typeof p === "string" ? { text: p } : p)) : [],
      tables: content ? content.tables || [] : [],
      figures: content ? content.figures || [] : [],
      images: content ? content.images || [] : [],
      content_source_ref: content ? content.source_ref ?? page.raw_file ?? null : null,
      content_present: !!content,
      range: flat.find((p) => String(p.part).toUpperCase() === partKey)?.ranges ?? null,
      numbers: diff,
      status: st.status,
      status_reasons: st.reasons,
      questions: questions.map((q) => projectQuestion(ctx, q)),
      groups,
    });
  }

  const observedAll = questionsAll.map((q) => q.number);
  const diffAll = numbersDiff(expected?.numbers || observedAll, observedAll);
  const allStatus = completenessStatus({ page, questions: questionsAll, missingNumbers: diffAll.missing });

  return {
    ok: true,
    schema: RESOLVE_SCHEMA,
    resolver: RESOLVER_VERSION,
    identity: id,
    run_id: ctx.runId,
    source: {
      kind: page.kind,
      page_ref: page.page_ref,
      raw_file: page.raw_file,
      slug: page.slug ?? null,
      url: page.url ?? null,
      source_sha256: page.source_sha256 ?? null,
      source_test: page.source_test ?? null,
      parser_version: doc?.parser_version ?? null,
    },
    expected: expected
      ? { status: expected.status ?? null, expected_total: expected.expected_total ?? null, parts: flat.map((p) => ({ part: p.part, ranges: p.ranges, numbers: p.numbers.length })) }
      : null,
    numbers: diffAll,
    status: allStatus.status,
    status_reasons: allStatus.reasons,
    passages,
    answer_groups: projectAnswerGroups(ctx, page),
    warnings: [...(page.warnings || []), ...(parseError ? [{ kind: "content_parse", error: parseError, raw_file: page.raw_file }] : [])],
  };
}

function resolveGeneralReading(ctx, id, opts = {}) {
  const bookNode = ctx.manifestByBook.get(id.book);
  const items = ((bookNode && bookNode.items) || []).filter(
    (it) => it.variant === "general" && String(it.test) === id.test && it.skill === "reading",
  );
  const general = bookNode ? bookNode.general : null;
  const presence = items.length ? items[0].status || null : (general && general.status) || null;
  const contentStatus =
    presence === "verified" ? "not_extracted" : presence === "unverified" ? "unverified" : presence || "source_missing";
  return {
    ok: true,
    schema: RESOLVE_SCHEMA,
    resolver: RESOLVER_VERSION,
    identity: id,
    run_id: ctx.runId,
    status: contentStatus,
    content_status: contentStatus,
    presence_status: presence,
    passages: items.map((it) => ({
      part: it.part,
      expected_numbers: it.expected_numbers,
      status: it.status,
      reason: it.reason ?? null,
      evidence: it.evidence || [],
      content_present: false,
    })),
    general_meta: general ? { status: general.status ?? null, reason: general.reason ?? null, probe: general.probe ?? null } : null,
    note: "General Training 内容未进索引（S04 raw 无 general 条目）；以上为逐 Part 有证据的预期清单，正文待 PDF 侧提取",
    warnings: ctx.warnings,
  };
}

/* ---------------------------------- 听力 ---------------------------------- */

const MASLOW_PLACEHOLDER_MIN_BYTES = 1024;

/** 逐 Part 文本质检：答案键/中文垃圾不算原文；仅真实英文原文记 available（S12 诚实分类） */
function assessScriptText(text) {
  const t = String(text ?? "");
  const chars = t.trim().length;
  const cjk = (t.match(/[\u4e00-\u9fff]/g) || []).length;
  const cjkRatio = cjk / Math.max(1, chars);
  const lines = t.split(/\n+/).map((s) => s.trim()).filter(Boolean);
  const numbered = lines.filter((l) => /^\d{1,2}[\s.:)\-]/.test(l)).length;
  const numberedRatio = numbered / Math.max(1, lines.length);
  const metrics = {
    chars,
    cjk_ratio: Number(cjkRatio.toFixed(3)),
    lines: lines.length,
    numbered_lines: numbered,
    numbered_ratio: Number(numberedRatio.toFixed(3)),
  };
  if (cjkRatio > 0.05) return { status: "junk", reason: "non_english_text", metrics };
  if (numbered >= 5 && numberedRatio >= 0.4) return { status: "answer_key", reason: "looks_like_answer_key", metrics };
  if (chars < 200) return { status: "insufficient", reason: "too_short", metrics };
  return { status: "available", reason: null, metrics };
}

/** 本地 maslow audioscripts.md（占位/404 按大小+内容拒收；无 Part 分节记 unsegmented）；解析结果缓存 */
function maslowLocalFor(ctx, book) {
  if (ctx.scriptCache.has(book)) return ctx.scriptCache.get(book);
  const candidates = [
    `tmp_audit_ielts/maslow_${String(book).padStart(2, "0")}.md`,
    `tmp_audit_ielts/maslow_${book}.md`,
  ];
  let out = null;
  for (const rel of candidates) {
    const p = path.join(WORKSPACE_ROOT, rel);
    if (!fs.existsSync(p)) continue;
    const bytes = fs.statSync(p).size;
    if (bytes < MASLOW_PLACEHOLDER_MIN_BYTES) {
      out = { ok: false, reason: "placeholder_file", rel, bytes };
      continue;
    }
    const text = fs.readFileSync(p, "utf8");
    if (!/Cambridge\s+IELTS/i.test(text)) {
      out = { ok: false, reason: "content_mismatch", rel, bytes };
      continue;
    }
    const { tests, flat } = parseMaslowMarkdown(text);
    if (Object.keys(tests).length) {
      out = { ok: true, rel, bytes, tests, flat };
    } else {
      out = { ok: false, reason: "unsegmented", rel, bytes, tests, flat };
    }
    if (out.ok) break;
  }
  ctx.scriptCache.set(book, out);
  return out;
}

/** maslow markdown 分 Test/Part（与 ielts-api.mjs maslowScript 同一解析规则）；flat 保留各 Test 未分节正文 */
function parseMaslowMarkdown(md) {
  let s = md;
  s = s.replace(/^[ \t]*\*\*[ \t]*(PART|SECTION)[ \t]*(\d+)[ \t]*\*\*[ \t]*$/gim, "## $1 $2");
  s = s.replace(/^[ \t]*\*+[ \t]*$/gm, "");
  const tests = {};
  const flat = {};
  const re = /#+\s*Test\s*(\d+)([\s\S]*?)(?=#+\s*Test\s*\d+|$)/gi;
  let m;
  while ((m = re.exec(s))) {
    const t = Number(m[1]);
    let body = m[2].replace(/^\s*\|\s*$/gm, "");
    const junk = body.search(
      /^[ \t]*(?:LISTENING KEYS\b|\*{2,3}[ \t]*(?:Answer[ \t]+)?Cam[ \t]*\d+[ \t]+Listening[ \t]+Test\b)/im,
    );
    if (junk > 0) body = body.slice(0, junk);
    const parts = {};
    const pr = /#+\s*(?:PART|SECTION)\s*(\d+)([\s\S]*?)(?=#+\s*(?:PART|SECTION)\s*\d+|$)/gi;
    let pm;
    while ((pm = pr.exec(body))) {
      const txt = pm[2].trim();
      if (txt) parts["part" + pm[1]] = txt;
    }
    if (Object.keys(parts).length) tests["test" + t] = parts;
    flat["test" + t] = body.trim();
  }
  return { tests, flat };
}

/** 逐 Part 原文：剑21 用 cam21-transcripts（时间戳 candidate_unvalidated）；剑1–20 用本地 maslow（质检分类） */
function scriptFor(ctx, book, webTest, part, cam21Test) {
  if (book === 21) {
    const pages = ctx.cam21Transcripts && ctx.cam21Transcripts.pages;
    const pg = pages && (pages[String(cam21Test)] || pages[cam21Test]);
    const segs = pg && pg.sections && (pg.sections[String(part)] || pg.sections[part]);
    if (Array.isArray(segs) && segs.length) {
      const text = segs.map((x) => (x.sp ? x.sp + ": " : "") + x.text).join("\n");
      const q = assessScriptText(text);
      const ref = "ielts-data/runs/" + ctx.runId + "/audio/cam21-transcripts.json";
      if (q.status === "junk" || q.status === "answer_key") {
        return { status: q.status, source: "cam21-transcripts", source_ref: ref, reason: q.reason, metrics: q.metrics, text: null, chars: text.length, segments: [] };
      }
      return {
        status: q.status === "available" ? "available" : "insufficient",
        source: "cam21-transcripts",
        source_ref: ref,
        timestamp_status: ctx.cam21Transcripts.timestamp_status ?? null,
        segments: segs,
        text,
        chars: text.length,
      };
    }
    return { status: "source_missing", source: "cam21-transcripts", text: null, chars: 0, segments: [] };
  }
  const local = maslowLocalFor(ctx, book);
  if (!local) {
    return { status: "source_missing", source: "maslow-local", source_ref: null, reason: "file_not_found", text: null, chars: 0, segments: [] };
  }
  if (!local.ok) {
    const reason = local.reason || "file_not_found";
    const flatLen = local.flat && local.flat["test" + webTest] ? local.flat["test" + webTest].length : 0;
    return {
      status: reason === "unsegmented" && flatLen > 200 ? "unsegmented" : "source_missing",
      source: "maslow-local",
      source_ref: local.rel,
      reason,
      test_text_chars: flatLen,
      text: null,
      chars: 0,
      segments: [],
    };
  }
  const byTest = local.tests["test" + webTest];
  if (byTest) {
    const text = byTest["part" + part] ?? null;
    if (text) {
      const q = assessScriptText(text);
      if (q.status === "available") {
        return { status: "available", source: "maslow-local", source_ref: local.rel, text, chars: text.length, segments: [] };
      }
      return { status: q.status, source: "maslow-local", source_ref: local.rel, reason: q.reason, metrics: q.metrics, text: null, chars: text.length, segments: [] };
    }
    return {
      status: "source_missing",
      source: "maslow-local",
      source_ref: local.rel,
      reason: `test${webTest} 已分节但无 part${part}`,
      text: null,
      chars: 0,
      segments: [],
    };
  }
  const flatText = local.flat && local.flat["test" + webTest] ? local.flat["test" + webTest] : "";
  if (flatText.length > 200) {
    return {
      status: "unsegmented",
      source: "maslow-local",
      source_ref: local.rel,
      reason: `test${webTest} 有正文但无 Part 分节（unsegmented），不按 Part 可用`,
      test_text_chars: flatText.length,
      text: null,
      chars: 0,
      segments: [],
    };
  }
  return {
    status: "source_missing",
    source: "maslow-local",
    source_ref: local.rel,
    reason: `test${webTest}/part${part} 未在文件中分节`,
    text: null,
    chars: 0,
    segments: [],
  };
}

/**
 * 听力解析：逐 Part 题目/组/音频身份/对齐/原文。
 * @param {number} book 1–21
 * @param {number|string} test 1–4（剑12 1–8）
 * @param {{part?:string, ctx?:object, dataDir?:string, runId?:string}} opts
 */
export function resolveListening(book, test, opts = {}) {
  const ctx = opts.ctx || loadResolverContext(opts);
  const norm = normalizeIdentity({ book, test, skill: "listening" });
  if (!norm.ok) return norm;
  const id = norm.identity;

  const page = ctx.pagesByKey.get(`${id.book}|${id.test}|listening`);
  const { doc, error: parseError } = page ? parsedPageFor(ctx, page) : { doc: null, error: "no_page" };
  const expected = expectedFor(id.book, id.test, "listening") || null;
  const webTest = webTestOf(id.book, id.test);
  const questionsAll = page ? (ctx.questionsByPage.get(page.page_ref) || []).slice().sort((a, b) => a.number - b.number) : [];
  const groupsAll = page ? ctx.groupsByPage.get(page.page_ref) || [] : [];
  const partFilter = opts.part != null ? normalizePart(opts.part, "listening") : null;
  if (opts.part != null && partFilter == null) {
    return { ok: false, code: "invalid_identity", error: `part 无效: ${JSON.stringify(opts.part)}` };
  }

  const parts = [];
  for (let p = 1; p <= 4; p++) {
    const partKey = "P" + p;
    if (partFilter && partFilter !== partKey) continue;
    const audioIdentity = `cambridge:${id.book}:shared:listening:${webTest}:${partKey}`;
    const audio = projectAudio(ctx.audioByIdentity.get(audioIdentity) || null);
    const alignment = projectAlignment(ctx.alignments.get(audioIdentity) || null);
    const alignByNumber = new Map(alignment.questions.map((q) => [q.number, q]));
    const questions = questionsAll.filter((q) => q.part === partKey);
    const groups = groupsAll.filter((g) => g.identity && g.identity.part === partKey);
    const expNumbers = partExpected(expected, p);
    const diff = numbersDiff(expNumbers, questions.map((q) => q.number));
    const script = scriptFor(ctx, id.book, webTest, p, id.test);
    const st = completenessStatus({ page, questions, missingNumbers: diff.missing });
    parts.push({
      part: partKey,
      status: st.status,
      status_reasons: st.reasons,
      numbers: diff,
      questions: questions.map((q) => projectQuestion(ctx, q, alignByNumber)),
      groups,
      audio,
      alignment,
      script,
    });
  }

  const observedAll = questionsAll.map((q) => q.number);
  const diffAll = numbersDiff(expected?.numbers || observedAll, observedAll);
  const allStatus = completenessStatus({ page, questions: questionsAll, missingNumbers: diffAll.missing });

  return {
    ok: true,
    schema: RESOLVE_SCHEMA,
    resolver: RESOLVER_VERSION,
    identity: id,
    run_id: ctx.runId,
    web_test: webTest,
    source: page
      ? {
          kind: page.kind,
          page_ref: page.page_ref,
          raw_file: page.raw_file,
          slug: page.slug ?? null,
          url: page.url ?? null,
          source_sha256: page.source_sha256 ?? null,
          source_test: page.source_test ?? null,
          parser_version: doc?.parser_version ?? null,
        }
      : null,
    expected: expected
      ? { status: expected.status ?? null, expected_total: expected.expected_total ?? null, parts: flattenParts(expected.parts).map((p) => ({ part: p.part, ranges: p.ranges, numbers: p.numbers.length })) }
      : null,
    numbers: diffAll,
    status: allStatus.status,
    status_reasons: allStatus.reasons,
    parts,
    answer_groups: projectAnswerGroups(ctx, page),
    warnings: [...(page ? page.warnings || [] : []), ...(parseError && parseError !== "no_page" ? [{ kind: "content_parse", error: parseError }] : [])],
  };
}

/* ---------------------------------- 音频 ---------------------------------- */

/**
 * 音频解析：Part 级记录 + full_test 候选（full_test 不冒充已验证）。
 */
export function resolveAudio(book, test, opts = {}) {
  const ctx = opts.ctx || loadResolverContext(opts);
  const norm = normalizeIdentity({ book, test, skill: "listening" });
  if (!norm.ok) return norm;
  const id = norm.identity;
  const webTest = webTestOf(id.book, id.test);
  const partFilter = opts.part != null ? normalizePart(opts.part, "listening") : null;
  if (opts.part != null && partFilter == null) {
    return { ok: false, code: "invalid_identity", error: `part 无效: ${JSON.stringify(opts.part)}` };
  }
  const parts = [];
  for (let p = 1; p <= 4; p++) {
    const partKey = "P" + p;
    if (partFilter && partFilter !== partKey) continue;
    const identity = `cambridge:${id.book}:shared:listening:${webTest}:${partKey}`;
    parts.push({ part: partKey, identity, record: projectAudio(ctx.audioByIdentity.get(identity) || null) });
  }
  const fullIdentity = `cambridge:${id.book}:shared:listening:${webTest}`;
  const full = projectAudio(ctx.audioByIdentity.get(fullIdentity) || null);
  return {
    ok: true,
    schema: RESOLVE_SCHEMA,
    resolver: RESOLVER_VERSION,
    identity: id,
    run_id: ctx.runId,
    web_test: webTest,
    parts,
    full_test: full,
    warnings: ctx.warnings,
  };
}

/* ---------------------------------- PDF ---------------------------------- */

const PDF21_URL = "https://raw.githubusercontent.com/aqinaq/agylshyn/main/site/pdf/ielts-21.pdf";

/**
 * PDF 解析：本地优先 + LFS/社区直链（只给链接与本地存在性，不下载）。
 * @param {number} book 1–21
 * @param {number|string|null} test
 * @param {{scope?:"book"|"test", ctx?:object}} opts
 */
export function resolvePdf(book, test = null, opts = {}) {
  const b = Number(book);
  if (!Number.isInteger(b) || b < 1 || b > 21) {
    return { ok: false, code: "invalid_identity", error: "book 需为 1–21 的整数" };
  }
  const scope = opts.scope || (test != null ? "test" : "book");
  const files = [];
  const warnings = [];
  const localBook = path.join(WORKSPACE_ROOT, "tmp_audit_ielts", "downloads", `book_${b}.pdf`);
  const addLocal = (p, kind, extra = {}) => {
    const exists = fs.existsSync(p);
    files.push({
      kind,
      path: path.relative(WORKSPACE_ROOT, p).replace(/\\/g, "/"),
      exists,
      bytes: exists ? fs.statSync(p).size : null,
      ...extra,
    });
  };

  if (b <= 20) {
    addLocal(localBook, "local_book_pdf", b === 20 ? { note: "本地为 34 页抢先版（仅覆盖 Test1 部分），不得当整册" } : {});
    if (b === 20) {
      warnings.push({ kind: "local_pdf_partial", note: "book_20.pdf 仅 34 页抢先版；完整书需 LFS 分册（BOOK20_TESTS）或重下" });
    }
    if (scope === "book" || scope === "test") {
      if (BOOK_PDF[b]) files.push({ kind: "lfs_book_pdf", url: lfsUrl(BOOK_PDF[b]), exists: null, via: "media" });
      if (BOOK_PDF_ALT[b]) files.push({ kind: "lfs_book_pdf_alt", url: lfsUrl(BOOK_PDF_ALT[b]), exists: null, via: "media" });
    }
    if (b === 20) {
      const testKey = test != null ? "test" + Number(test) : null;
      for (const [k, p] of Object.entries(BOOK20_TESTS)) {
        if (scope === "test" && testKey && k !== testKey) continue;
        files.push({ kind: "lfs_test_pdf", test: k, url: lfsUrl(p), exists: null, via: "media" });
      }
    }
  } else {
    files.push({
      kind: "community_book_pdf",
      url: PDF21_URL,
      exists: null,
      bytes: 44148624,
      pages: 146,
      note: "剑21 完整书（社区镜像 aqinaq/agylshyn，146 页）",
    });
    addLocal(localBook, "local_book_pdf");
  }

  return {
    ok: true,
    schema: RESOLVE_SCHEMA,
    resolver: RESOLVER_VERSION,
    book: b,
    test: test != null ? String(test) : null,
    scope,
    files,
    warnings,
  };
}

/* ---------------------------------- 写/说（manifest 预期） ---------------------------------- */

function resolveManifestSkill(ctx, id, skill) {
  const variant = skill === "writing" ? "academic" : "shared";
  const bookNode = ctx.manifestByBook.get(id.book);
  const items = ((bookNode && bookNode.items) || []).filter(
    (it) => String(it.test) === id.test && it.skill === skill && it.variant === variant,
  );
  const byPart = new Map();
  for (const it of items) {
    if (!byPart.has(it.part)) byPart.set(it.part, []);
    byPart.get(it.part).push(it);
  }
  const parts = [...byPart.entries()].map(([part, its]) => ({
    part,
    status: its[0].status ?? null,
    reason: its[0].reason ?? null,
    expected_numbers: its.flatMap((x) => x.expected_numbers || []),
    evidence: its.flatMap((x) => x.evidence || []),
  }));
  return {
    status: parts.length ? parts[0].status : "source_missing",
    content_status: parts.length ? (parts[0].status === "verified" ? "not_extracted" : parts[0].status) : "source_missing",
    parts,
    note:
      skill === "writing"
        ? "Writing 为开放任务（无唯一标准答案）；此处仅给原书预期清单，正文/样文未进索引"
        : "Speaking 为开放任务（无唯一标准答案）；此处仅给原书预期清单，正文未进索引",
  };
}

/* ---------------------------------- 整卷 ---------------------------------- */

/**
 * 整卷解析：阅读 + 听力 + 写/说预期。阅读单篇与整卷语义一致（同一函数、同一 source）。
 */
export function resolveTest(book, test, opts = {}) {
  const ctx = opts.ctx || loadResolverContext(opts);
  const reading = resolveReading(book, test, { ...opts, ctx });
  const listening = resolveListening(book, test, { ...opts, ctx });
  const norm = normalizeIdentity({ book, test, skill: "reading", variant: opts.variant });
  let writing = null;
  let speaking = null;
  if (norm.ok && norm.identity.variant !== "general") {
    writing = resolveManifestSkill(ctx, norm.identity, "writing");
    speaking = resolveManifestSkill(ctx, norm.identity, "speaking");
  }
  return {
    ok: true,
    schema: RESOLVE_SCHEMA,
    resolver: RESOLVER_VERSION,
    run_id: ctx.runId,
    book: Number(book),
    test: String(test),
    identity: norm.ok ? norm.identity : null,
    reading,
    listening,
    writing,
    speaking,
    warnings: ctx.warnings,
  };
}
