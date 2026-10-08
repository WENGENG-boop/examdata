/**
 * 雅思 v2 规范化 API（schema ielts.v2/1）
 *
 * 设计目标（S13）：把 resolver.mjs / coverage.mjs 的本地规范化解析暴露为
 * 统一、可验证、无网络依赖的三入口 API（CLI / Node HTTP / FastAPI 包装层）。
 *
 * 原则：
 * - 全部数据来自本地索引（ielts-data/runs/<run>/index/question-index.json）与
 *   本地资产（assets/ audio/ pdf/），不发起网络请求。
 * - 题目—答案按完整身份连接：book/test/skill/variant/part/group/编号；
 *   拒绝单字母子串匹配。
 * - 听力逐题对齐仅在音频身份与时间基准通过校验后标 verified；否则原样
 *   暴露 unverified / candidate，不伪造区间。
 * - Writing/Speaking 为开放题：只给原书期望清单，不标唯一标准答案。
 * - question_id 形如 q-<book>-<test>-<skill>-<variant>-<number>，其中 test
 *   为 canonical 编号（book12 为 5–8；book12 的 1–4 自动映射到 5–8）。
 * - asset_id 为 sha256（图片 assets/<sha>.*、音频 audio/<sha>.mp3）或
 *   book-pdf-<n>（本地下载的整本 PDF）。
 */

import fs from "node:fs";
import path from "node:path";
import {
  RESOLVER_VERSION,
  RESOLVE_SCHEMA,
  loadResolverContext,
  resolveReading,
  resolveListening,
  resolveAudio,
  resolvePdf,
  resolveTest,
} from "./resolver.mjs";
import {
  COVERAGE_SCHEMA,
  COVERAGE_VERSION,
  buildCoverage,
  coverageForBook,
  coverageForTest,
  unitsForBook,
} from "./coverage.mjs";
import { WORKSPACE_ROOT, resolveDataDir, readJson } from "./data-store.mjs";

export const V2_SCHEMA = "ielts.v2/1";
export const V2_VERSION = "v2/1.0.0";

/* ============================ 基础设施 ============================ */

/* ctx 缓存：60s TTL；dataDir 变化立即失效（EXAMDATA_IELTS_DATA_DIR 切换时不能串数据） */
let __v2CtxCache = { at: 0, dir: null, ctx: null };
function ctxCached() {
  const dir = resolveDataDir();
  if (!__v2CtxCache.ctx || __v2CtxCache.dir !== dir || Date.now() - __v2CtxCache.at > 60000) {
    __v2CtxCache = { at: Date.now(), dir, ctx: loadResolverContext() };
  }
  return __v2CtxCache.ctx;
}

/** 测试/调试用：清空全部缓存（下一调用重新加载索引与资产清单）。 */
export function v2ResetCache() {
  __v2CtxCache = { at: 0, dir: null, ctx: null };
  __assetCache = { at: 0, dir: null, assets: null, audio: null, provenance: null, catalog: null };
}

function toInt(value) {
  if (typeof value === "number") return Number.isInteger(value) ? value : null;
  if (typeof value === "string" && /^\d+$/.test(value)) return Number(value);
  return null;
}

function validBook(book) {
  const b = toInt(book);
  return b !== null && b >= 1 && b <= 21 ? b : null;
}

function validTest(test) {
  const s = String(test ?? "").trim().toLowerCase();
  if (s === "gta" || s === "gtb") return s;
  const t = toInt(test);
  return t !== null && t >= 1 && t <= 8 ? t : null;
}

function normPart(value) {
  const n = toInt(value);
  if (n !== null && n >= 1 && n <= 4) return "P" + n;
  const s = String(value ?? "").toUpperCase();
  return /^P[1-4]$/.test(s) ? s : null;
}

function fail(code, error, extra = {}) {
  return {
    ok: false,
    schema: V2_SCHEMA,
    version: V2_VERSION,
    board: "ielts",
    code,
    error,
    ...extra,
  };
}

function statSafe(filePath) {
  try {
    const st = fs.statSync(filePath);
    return st.isFile() ? st : null;
  } catch {
    return null;
  }
}

/* ============================ 资产注册表 ============================ */

/* 资产索引：assets/<sha>.*、audio/<sha>.*、PDF 下载、provenance 与音频目录富化 */
let __assetCache = { at: 0, dir: null, assets: null, audio: null, provenance: null, catalog: null };

function scanContentDir(dir) {
  const out = new Map();
  let names = [];
  try {
    names = fs.readdirSync(dir);
  } catch {
    return out;
  }
  for (const name of names) {
    const ext = path.extname(name).toLowerCase();
    const base = path.basename(name, ext);
    if (base && !out.has(base)) out.set(base, path.join(dir, name));
  }
  return out;
}

function assetIndex() {
  const dir = resolveDataDir();
  if (!__assetCache.assets || __assetCache.dir !== dir || Date.now() - __assetCache.at > 60000) {
    const ctx = ctxCached();
    const assets = scanContentDir(path.join(dir, "assets"));
    const audio = scanContentDir(path.join(dir, "audio"));

    const provenance = new Map();
    const prov = readJson(path.join(dir, "manifests", "pdf-provenance.json"));
    for (const entry of (prov && prov.entries) || []) {
      for (const a of entry.assets || []) {
        if (a && a.sha256) {
          provenance.set(String(a.sha256).toLowerCase(), {
            book: entry.book ?? null,
            name: a.name ?? null,
            pdf_sha256: (entry.pdf && entry.pdf.sha256) || null,
            derived: a.derived ?? null,
          });
        }
      }
    }

    const catalog = new Map();
    for (const rec of (ctx.audioCatalog && ctx.audioCatalog.records) || []) {
      const entry = {
        audio_id: rec.audio_id ?? null,
        identity: rec.identity ?? null,
        source: rec.source ?? null,
        status: rec.status ?? null,
        duration_sec: rec.duration_sec ?? null,
        bytes: rec.bytes ?? null,
      };
      const sha = rec.content_sha256 ? String(rec.content_sha256).toLowerCase() : null;
      if (sha && !catalog.has(sha)) catalog.set(sha, entry);
      for (const s of rec.local_samples || []) {
        if (s && s.sha256) {
          const ssha = String(s.sha256).toLowerCase();
          if (!catalog.has(ssha)) catalog.set(ssha, { ...entry, local_sample: s.path ?? null });
        }
      }
    }
    __assetCache = { at: Date.now(), dir, assets, audio, provenance, catalog };
  }
  return __assetCache;
}

const MIME_BY_EXT = {
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".webp": "image/webp",
  ".svg": "image/svg+xml",
  ".mp3": "audio/mpeg",
  ".m4a": "audio/mp4",
  ".wav": "audio/wav",
  ".pdf": "application/pdf",
};

function mimeOf(filePath, fallback = "application/octet-stream") {
  return MIME_BY_EXT[path.extname(filePath).toLowerCase()] || fallback;
}

function assetResult(kind, id, filePath, extra = {}) {
  const st = statSafe(filePath);
  if (!st) return fail("not_found", "资产文件不存在：" + filePath, { id, kind });
  return {
    ok: true,
    schema: V2_SCHEMA,
    version: V2_VERSION,
    board: "ielts",
    id,
    kind,
    mime: mimeOf(filePath),
    file_path: filePath,
    file_name: path.basename(filePath),
    bytes: st.size,
    mtime_ms: st.mtimeMs,
    exists: true,
    ...extra,
  };
}

/**
 * 资产解析：sha256（图片/音频）或 book-pdf-<n>（本地整本 PDF）。
 * 返回 file_path（绝对路径）供 CLI 流式返回 / FastAPI FileResponse 使用。
 */
export function v2Asset(id) {
  const raw = String(id ?? "").trim();
  if (!raw) return fail("bad_id", "asset id 不能为空");
  const lower = raw.toLowerCase();

  if (/^[0-9a-f]{64}$/.test(lower)) {
    const idx = assetIndex();
    const img = idx.assets.get(lower);
    if (img) {
      return assetResult("image", lower, img, { sha256: lower, provenance: idx.provenance.get(lower) || null });
    }
    const aud = idx.audio.get(lower);
    if (aud) {
      return assetResult("audio", lower, aud, {
        sha256: lower,
        audio_record: idx.catalog.get(lower) || null,
      });
    }
    const rec = idx.catalog.get(lower);
    if (rec && rec.local_sample) {
      const p = path.join(WORKSPACE_ROOT, rec.local_sample);
      const st = statSafe(p);
      if (st) {
        return assetResult("audio", lower, p, { sha256: lower, audio_record: rec, source: "local_sample" });
      }
    }
    return fail("not_found", "资产不在本地存储（assets/ 与 audio/ 均无该 sha256）", {
      id: lower,
      tried: ["assets/<sha>.*", "audio/<sha>.*", "audio-catalog local_samples"],
    });
  }

  const pm = /^book-pdf-(\d{1,2})$/.exec(lower);
  if (pm) {
    const n = Number(pm[1]);
    if (n < 1 || n > 21) return fail("bad_id", "book-pdf 编号需为 1–21", { id: raw });
    const p = path.join(WORKSPACE_ROOT, "tmp_audit_ielts", "downloads", "book_" + n + ".pdf");
    const st = statSafe(p);
    if (!st) {
      return fail("not_found", "本地未找到该册 PDF（tmp_audit_ielts/downloads/book_<n>.pdf）", { id: raw, tried: [p] });
    }
    return {
      ok: true,
      schema: V2_SCHEMA,
      version: V2_VERSION,
      board: "ielts",
      id: lower,
      kind: "pdf",
      book: n,
      mime: "application/pdf",
      file_path: p,
      file_name: path.basename(p),
      bytes: st.size,
      mtime_ms: st.mtimeMs,
      exists: true,
    };
  }

  return fail("bad_id", "asset id 需为 64 位 sha256 或 book-pdf-<n>", { id: raw });
}

/* ============================ info / books ============================ */

export function v2Info() {
  const ctx = ctxCached();
  const index = ctx.index || {};
  const pages = Array.isArray(index.pages) ? index.pages : [];
  return {
    ok: true,
    schema: V2_SCHEMA,
    version: V2_VERSION,
    board: "ielts",
    generated_at_utc: new Date().toISOString(),
    run_id: ctx.runId || null,
    data_dir: ctx.dataDir || null,
    resolver: RESOLVER_VERSION,
    resolve_schema: RESOLVE_SCHEMA,
    coverage: { schema: COVERAGE_SCHEMA, version: COVERAGE_VERSION },
    books: {
      range: [1, 21],
      tests: {
        default: [1, 2, 3, 4],
        book12: [5, 6, 7, 8],
        general: ["gta", "gtb"],
        note: "book12 的 1–4 自动映射到 canonical 5–8；gta/gtb 为 General Training（按 manifest 登记，需显式选择）",
      },
      skills: ["reading", "listening", "writing", "speaking"],
      variants: { reading: ["academic", "general"], listening: ["shared"], writing: ["shared"], speaking: ["shared"] },
    },
    question_id: {
      format: "q-<book>-<test>-<skill>-<variant>-<number>",
      note: "test 为 canonical 编号（book12 为 5–8，GT 为 gta/gtb）；number 为套内题号",
    },
    asset_id: {
      format: "sha256（图片 assets/<sha>.*、音频 audio/<sha>.mp3）或 book-pdf-<n>",
    },
    routes: [
      { path: "/api/ielts/v2/info", does: "本清单（版本、路由、run_id、证据计数）" },
      { path: "/api/ielts/v2/books", does: "21 册目录：每册 units/tests/完成度计数" },
      { path: "/api/ielts/v2/test/{book}/{test}?variant=academic|general", does: "单套结构视图（阅读/听力/写作/口语/音频/PDF + completion）；general 需 test=gta/gtb" },
      { path: "/api/ielts/v2/questions/{book}/{test}?skill=&variant=&part=&passage=&type=&status=&alignment=&offset=&limit=", does: "逐题列表（question_id + answer + 对齐状态；分页以 question 为单位，默认全量）" },
      { path: "/api/ielts/v2/question/{question_id}", does: "单题（按完整身份）" },
      { path: "/api/ielts/v2/coverage?book=&test=", does: "覆盖度（全量/单册/单套）" },
      { path: "/api/ielts/v2/asset/{id}", does: "资产元数据/流（图片/音频/本地 PDF；支持 Range）" },
    ],
    evidence: {
      index_pages: pages.length,
      index_groups: Array.isArray(index.groups) ? index.groups.length : null,
      index_questions: Array.isArray(index.questions) ? index.questions.length : null,
      audio_records: Array.isArray(ctx.audioCatalog && ctx.audioCatalog.records) ? ctx.audioCatalog.records.length : null,
      warnings: ctx.warnings || [],
    },
    notes: [
      "全部数据来自本地索引与本地资产，不发起网络请求。",
      "题目—答案按完整身份（book/test/skill/variant/part/group/编号）连接；不采用单字母子串匹配。",
      "听力逐题对齐仅在音频身份与时间基准通过校验后标 verified；否则原样保留 unverified/candidate。",
      "Writing/Speaking 为开放题：仅给出来源期望清单，样例答案不标唯一标准答案。",
      "旧 v1 端点的 score（如 5/5）只表示槽位可用性；权威完成度见 /api/ielts/v2/coverage。",
    ],
  };
}

export function v2Books() {
  const ctx = ctxCached();
  const books = [];
  for (let b = 1; b <= 21; b++) {
    let units = [];
    try {
      units = unitsForBook(ctx, b);
    } catch {
      units = [];
    }
    const tests = {};
    const unitStatus = {};
    for (const u of units) {
      const key = u.skill + "/" + u.variant;
      if (!tests[key]) tests[key] = [];
      if (!tests[key].includes(u.test)) tests[key].push(u.test);
      unitStatus[u.status] = (unitStatus[u.status] || 0) + 1;
    }
    for (const key of Object.keys(tests)) tests[key].sort();
    books.push({
      book: b,
      units: units.length,
      tests,
      unit_status: unitStatus,
      units_fully_complete: units.filter((u) => u.completion && u.completion.fully_complete).length,
    });
  }
  return {
    ok: true,
    schema: V2_SCHEMA,
    version: V2_VERSION,
    board: "ielts",
    generated_at_utc: new Date().toISOString(),
    run_id: ctx.runId || null,
    books,
  };
}

/* ============================ 单套 / 题目 ============================ */

function trimReading(r) {
  if (!r) return null;
  if (r.ok === false) {
    return { ok: false, code: r.code ?? null, error: r.error ?? null, status: r.status ?? null, status_reasons: r.status_reasons ?? [] };
  }
  return {
    ok: true,
    status: r.status,
    status_reasons: r.status_reasons || [],
    numbers: r.numbers ?? null,
    expected: r.expected ?? null,
    source: r.source ?? null,
    run_id: r.run_id ?? null,
    passages: (r.passages || []).map((p) => ({
      passage: p.passage,
      part: p.part,
      title: p.title ?? null,
      status: p.status,
      status_reasons: p.status_reasons || [],
      numbers: p.numbers ?? null,
      questions_count: (p.questions || []).length,
      groups_count: (p.groups || []).length,
      content_present: p.content_present ?? null,
    })),
    answer_groups_count: (r.answer_groups || []).length,
    warnings: r.warnings || [],
  };
}

function trimListening(l) {
  if (!l) return null;
  if (l.ok === false) {
    return { ok: false, code: l.code ?? null, error: l.error ?? null, status: l.status ?? null, status_reasons: l.status_reasons ?? [] };
  }
  return {
    ok: true,
    status: l.status,
    status_reasons: l.status_reasons || [],
    numbers: l.numbers ?? null,
    expected: l.expected ?? null,
    web_test: l.web_test ?? null,
    source: l.source ?? null,
    run_id: l.run_id ?? null,
    parts: (l.parts || []).map((p) => {
      const align = p.alignment || null;
      const alignQuestions = (align && align.questions) || [];
      return {
        part: p.part,
        status: p.status,
        status_reasons: p.status_reasons || [],
        numbers: p.numbers ?? null,
        questions_count: (p.questions || []).length,
        groups_count: (p.groups || []).length,
        audio: p.audio
          ? {
              audio_id: p.audio.audio_id ?? null,
              status: p.audio.status ?? null,
              identity_status: p.audio.identity_status ?? null,
              duration_sec: p.audio.duration_sec ?? null,
              content_sha256: p.audio.content_sha256 ?? null,
              file_exists: !!p.audio.file_exists,
            }
          : null,
        alignment: align
          ? {
              status: align.status ?? null,
              method: align.method ?? null,
              questions_total: alignQuestions.length,
              verified: alignQuestions.filter((q) => q.status === "verified").length,
              counts: align.counts ?? null,
            }
          : null,
        script: p.script
          ? {
              status: p.script.status ?? null,
              source: p.script.source ?? null,
              timestamp_status: p.script.timestamp_status ?? null,
              chars: p.script.chars ?? null,
            }
          : null,
      };
    }),
    warnings: l.warnings || [],
  };
}

function trimAudio(a) {
  if (!a) return null;
  if (a.ok === false) return { ok: false, code: a.code ?? null, error: a.error ?? null };
  return {
    ok: true,
    web_test: a.web_test ?? null,
    parts: (a.parts || []).map((p) => ({
      part: p.part,
      identity: p.identity ?? null,
      audio_id: p.record ? p.record.audio_id ?? null : null,
      status: p.record ? p.record.status ?? null : null,
      identity_status: p.record ? p.record.identity_status ?? null : null,
      duration_sec: p.record ? p.record.duration_sec ?? null : null,
      content_sha256: p.record ? p.record.content_sha256 ?? null : null,
      file_exists: p.record ? !!p.record.file_exists : false,
      error: p.record ? p.record.error ?? null : null,
    })),
    full_test: a.full_test ?? null,
    warnings: a.warnings || [],
  };
}

function trimPdf(p) {
  if (!p) return null;
  if (p.ok === false) return { ok: false, code: p.code ?? null, error: p.error ?? null };
  return {
    ok: true,
    scope: p.scope ?? null,
    files: (p.files || []).map((f) => ({
      kind: f.kind ?? null,
      path: f.path ?? null,
      url: f.url ?? null,
      exists: !!f.exists,
      bytes: f.bytes ?? null,
      note: f.note ?? null,
    })),
    warnings: p.warnings || [],
  };
}

export function v2Test(book, test, opts = {}) {
  const b = validBook(book);
  if (b === null) return fail("invalid_book", "book 需为 1–21 的整数", { book: String(book) });
  const t = validTest(test);
  if (t === null) {
    return fail("invalid_test", "test 需为 1–8 的整数（book12 为 5–8，其余 1–4）或 gta/gtb（General Training）", { test: String(test) });
  }
  const tvIsGt = t === "gta" || t === "gtb";
  const variantReq = opts.variant === undefined || opts.variant === null || opts.variant === "" ? null : String(opts.variant);
  if (variantReq && !["academic", "general"].includes(variantReq)) {
    return fail("bad_filter", "variant 需为 academic（默认）或 general（需显式 test=gta/gtb）", { variant: variantReq });
  }
  if (variantReq === "general" && !tvIsGt) {
    return fail("variant_mismatch", "variant=general 需显式选择 GT 测试编号 test=gta/gtb", { book: b, test: String(t) });
  }
  if (variantReq === "academic" && tvIsGt) {
    return fail("variant_mismatch", "gta/gtb 为 General Training 测试；Academic 请用整数 test", { book: b, test: String(t) });
  }
  const ctx = ctxCached();

  let resolved;
  try {
    resolved = resolveTest(b, t, variantReq ? { variant: variantReq } : {});
  } catch (e) {
    return fail("resolver_error", String((e && e.message) || e), { book: b, test: String(t) });
  }
  let audio = null;
  if (!tvIsGt) {
    try {
      audio = resolveAudio(b, t);
    } catch (e) {
      audio = { ok: false, error: String((e && e.message) || e) };
    }
  }
  let pdf = null;
  if (!tvIsGt) {
    try {
      pdf = resolvePdf(b, t, {});
    } catch (e) {
      pdf = { ok: false, error: String((e && e.message) || e) };
    }
  }
  let cov = null;
  try {
    cov = coverageForTest(ctx, b, t);
  } catch {
    cov = null;
  }

  const warnings = [...(resolved.warnings || [])];
  if (tvIsGt) warnings.push("General Training 测试（gta/gtb）为 reading/writing 单元；listening/音频/PDF-test scope 不适用（listening 按整数测试编号登记）");
  if (cov && cov.ok === false) warnings.push("coverage: " + (cov.error || cov.code || "unavailable"));

  return {
    ok: resolved.ok !== false,
    schema: V2_SCHEMA,
    version: V2_VERSION,
    board: "ielts",
    book: b,
    test: t,
    identity: resolved.identity || null,
    reading: trimReading(resolved.reading),
    listening: tvIsGt ? null : trimListening(resolved.listening),
    writing: resolved.writing ?? null,
    speaking: resolved.speaking ?? null,
    audio: trimAudio(audio),
    pdf: trimPdf(pdf),
    completion:
      cov && cov.ok
        ? {
            schema: cov.schema,
            units: (cov.units || []).map((u) => ({
              unit_id: u.unit_id,
              skill: u.skill,
              variant: u.variant,
              status: u.status,
              numbers: u.numbers ?? null,
              completion: u.completion ?? null,
            })),
          }
        : null,
    warnings,
  };
}

/* ============================ 逐题列表 ============================ */

function questionIdOf(q) {
  return "q-" + q.book + "-" + q.test + "-" + q.skill + "-" + q.variant + "-" + q.number;
}

function projectV2Question(q) {
  return {
    question_id: questionIdOf(q),
    number: q.number,
    book: q.book,
    test: q.test,
    skill: q.skill,
    variant: q.variant,
    part: q.part ?? null,
    passage: q.passage ?? null,
    group_id: q.group_id ?? null,
    type: q.type ?? null,
    instruction: q.instruction ?? null,
    prompt: q.prompt ?? null,
    options: q.options ?? [],
    constraints: q.constraints ?? null,
    assets: q.assets ?? [],
    answer: q.answer ?? null,
    answer_status: q.answer_status ?? null,
    content_status: q.content_status ?? null,
    classification_status: q.classification_status ?? null,
    fully_complete: q.fully_complete ?? null,
    audio_alignment: q.audio_alignment ?? null,
    source_refs: q.source_refs ?? [],
    page_ref: q.page_ref ?? null,
  };
}

function passQuestionFilter(item, f) {
  if (f.variant && item.variant !== f.variant) return false;
  if (f.part && String(item.part ?? "").toUpperCase() !== f.part) return false;
  if (f.passage !== null && item.passage !== f.passage) return false;
  if (f.type && item.type !== f.type) return false;
  if (f.status) {
    const s = item.answer && item.answer.status ? item.answer.status : item.answer_status;
    if (s !== f.status) return false;
  }
  if (f.alignment) {
    const a = item.audio_alignment && item.audio_alignment.status;
    if (a !== f.alignment) return false;
  }
  return true;
}

export function v2Questions(book, test, opts = {}) {
  const b = validBook(book);
  if (b === null) return fail("invalid_book", "book 需为 1–21 的整数", { book: String(book) });
  const t = validTest(test);
  if (t === null) {
    return fail("invalid_test", "test 需为 1–8 的整数（book12 为 5–8，其余 1–4）或 gta/gtb（General Training）", { test: String(test) });
  }
  const tvIsGt = t === "gta" || t === "gtb";

  const skill = opts.skill === undefined || opts.skill === null ? null : String(opts.skill);
  if (skill && skill !== "reading" && skill !== "listening") {
    return fail("bad_filter", "skill 需为 reading 或 listening", { skill });
  }
  if (tvIsGt && skill === "listening") {
    return fail("bad_filter", "gta/gtb 为 General Training reading/writing 测试，不含 listening", { test: String(t) });
  }
  const variant = opts.variant === undefined || opts.variant === null || opts.variant === "" ? null : String(opts.variant);
  if (variant && !["academic", "general", "shared"].includes(variant)) {
    return fail("bad_filter", "variant 需为 academic / general / shared", { variant });
  }
  if (tvIsGt && variant === "academic") {
    return fail("variant_mismatch", "gta/gtb 为 general；variant=academic 请用整数 test", { test: String(t) });
  }
  if (!tvIsGt && variant === "general") {
    return fail("variant_mismatch", "variant=general 需显式选择 GT 测试编号 test=gta/gtb", { test: String(t) });
  }
  let part = null;
  if (opts.part !== undefined && opts.part !== null && opts.part !== "") {
    part = normPart(opts.part);
    if (!part) return fail("bad_filter", "part 需为 1–4 或 P1–P4", { part: String(opts.part) });
  }
  let passage = null;
  if (opts.passage !== undefined && opts.passage !== null && opts.passage !== "") {
    passage = toInt(opts.passage);
    if (passage === null || passage < 1 || passage > 3) {
      return fail("bad_filter", "passage 需为 1–3", { passage: String(opts.passage) });
    }
  }
  const status = opts.status ? String(opts.status) : null;
  const alignment = opts.alignment ? String(opts.alignment) : null;
  const type = opts.type === undefined || opts.type === null || opts.type === "" ? null : String(opts.type);
  let offset = null;
  if (opts.offset !== undefined && opts.offset !== null && opts.offset !== "") {
    offset = toInt(opts.offset);
    if (offset === null || offset < 0) return fail("bad_filter", "offset 需为 ≥0 的整数", { offset: String(opts.offset) });
  }
  let limit = null;
  if (opts.limit !== undefined && opts.limit !== null && opts.limit !== "") {
    limit = toInt(opts.limit);
    if (limit === null || limit < 1 || limit > 500) return fail("bad_filter", "limit 需为 1–500 的整数", { limit: String(opts.limit) });
  }

  const wantReading = !skill || skill === "reading";
  const wantListening = (!skill || skill === "listening") && !tvIsGt;

  let reading = null;
  let listening = null;
  if (wantReading) {
    try {
      reading = resolveReading(b, t, {});
    } catch (e) {
      reading = { ok: false, error: String((e && e.message) || e) };
    }
  }
  if (wantListening) {
    try {
      listening = resolveListening(b, t, {});
    } catch (e) {
      listening = { ok: false, error: String((e && e.message) || e) };
    }
  }

  const readingOk = !!(reading && reading.ok !== false);
  const listeningOk = !!(listening && listening.ok !== false);
  if (wantReading && !wantListening && !readingOk) {
    return fail((reading && reading.code) || "source_missing", (reading && reading.error) || "reading 解析失败", { book: b, test: String(t) });
  }
  if (wantListening && !wantReading && !listeningOk) {
    return fail((listening && listening.code) || "source_missing", (listening && listening.error) || "listening 解析失败", { book: b, test: String(t) });
  }
  if (wantReading && wantListening && !readingOk && !listeningOk) {
    return fail(
      (reading && reading.code) || "source_missing",
      "reading 与 listening 均无法解析：" + [(reading && reading.error) || "", (listening && listening.error) || ""].filter(Boolean).join("；"),
      { book: b, test: String(t) }
    );
  }

  const f = { variant, part, passage, type, status, alignment };
  const questions = [];
  const counts = { reading: 0, listening: 0 };
  for (const p of (readingOk ? reading.passages || [] : [])) {
    for (const q of p.questions || []) {
      const item = projectV2Question(q);
      if (passQuestionFilter(item, f)) {
        questions.push(item);
        counts.reading++;
      }
    }
  }
  for (const partObj of (listeningOk ? listening.parts || [] : [])) {
    for (const q of partObj.questions || []) {
      const item = projectV2Question(q);
      if (passQuestionFilter(item, f)) {
        questions.push(item);
        counts.listening++;
      }
    }
  }
  questions.sort(
    (a, z) =>
      a.book - z.book ||
      Number(a.test) - Number(z.test) ||
      (a.skill === z.skill ? 0 : a.skill === "reading" ? -1 : 1) ||
      a.number - z.number
  );

  const total = questions.length;
  const pageOffset = offset ?? 0;
  const page = questions.slice(pageOffset, pageOffset + (limit ?? total));

  const warnings = [];
  if (wantReading && !readingOk) warnings.push("reading 解析失败：" + ((reading && reading.error) || "unknown"));
  if (wantListening && !listeningOk) warnings.push("listening 解析失败：" + ((listening && listening.error) || "unknown"));
  if (readingOk) warnings.push(...(reading.warnings || []));
  if (listeningOk) warnings.push(...(listening.warnings || []));
  if (tvIsGt) warnings.push("General Training 逐题数据未抽取（content_present=false）；期望清单见 reading.passages[].expected_numbers");

  const canonicalTest =
    (readingOk && reading.identity && reading.identity.test) ||
    (listeningOk && listening.identity && listening.identity.test) ||
    String(t);

  return {
    ok: true,
    schema: V2_SCHEMA,
    version: V2_VERSION,
    board: "ielts",
    book: b,
    test: t,
    canonical_test: String(canonicalTest),
    filters: { skill, variant, part, passage, type, status, alignment },
    count: page.length,
    total,
    offset: pageOffset,
    limit: limit ?? total,
    counts_by_skill: counts,
    questions: page,
    warnings,
  };
}

export function v2Question(questionId) {
  const raw = String(questionId ?? "").trim();
  const m = /^q-(\d{1,2})-(\d{1,2}|gt[ab])-(reading|listening)-(academic|general|shared)-(\d{1,3})$/.exec(raw);
  if (!m) {
    return fail("bad_question_id", "question_id 需形如 q-<book>-<test>-<skill>-<variant>-<number>（test 可为 gta/gtb）", { question_id: raw });
  }
  const [, bs, ts, skill, variant, ns] = m;
  const res = v2Questions(bs, ts, { skill, variant });
  if (res.ok === false) return res;
  const q = (res.questions || []).find((x) => x.question_id === raw);
  if (!q) {
    return fail("not_found", "该身份下未找到此题目（编号或身份不匹配）", {
      question_id: raw,
      book: Number(bs),
      test: Number(ts),
      skill,
      variant,
      number: Number(ns),
    });
  }
  return { ok: true, schema: V2_SCHEMA, version: V2_VERSION, board: "ielts", question: q };
}

/* ============================ 覆盖度 ============================ */

export function v2Coverage(opts = {}) {
  const ctx = ctxCached();
  if (opts.book !== undefined && opts.book !== null && opts.book !== "") {
    const b = validBook(opts.book);
    if (b === null) return fail("invalid_book", "book 需为 1–21 的整数", { book: String(opts.book) });
    if (opts.test !== undefined && opts.test !== null && opts.test !== "") {
      const t = validTest(opts.test);
      if (t === null) return fail("invalid_test", "test 需为 1–8 的整数（book12 为 5–8，其余 1–4）或 gta/gtb（General Training）", { test: String(opts.test) });
      let cov;
      try {
        cov = coverageForTest(ctx, b, t);
      } catch (e) {
        return fail("coverage_error", String((e && e.message) || e), { book: b, test: t });
      }
      return { ok: cov.ok !== false, level: "test", ...cov };
    }
    let cov;
    try {
      cov = coverageForBook(ctx, b, opts);
    } catch (e) {
      return fail("coverage_error", String((e && e.message) || e), { book: b });
    }
    return { ok: cov.ok !== false, level: "book", ...cov };
  }
  const full = buildCoverage({ ctx });
  return { level: "all", ...full };
}
