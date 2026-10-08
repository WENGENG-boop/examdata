#!/usr/bin/env node
// ielts-api/tools/audit-all.mjs
// S14: 全量验收审计工具。绝不发网络请求（媒体只验证本地文件）。
//
// 用法:
//   node ielts-api/tools/audit-all.mjs --offline --fixtures <dir> --out <dir>
//   node ielts-api/tools/audit-all.mjs --dataset current --verify-assets --verify-audio --out <dir>
//
// 模式:
//   --offline   载入本地 run 数据 + fixtures，离线校验（fixtures 枚举/hash/parse、
//               alignment-gold 与本地 alignment docs 对照、run 数据自洽性）
//   --dataset   读 current 指针（indexes/manifests），对 168 个 Academic 阅读/听力组合
//               与 coverage units 矩阵做全量检查；--verify-assets / --verify-audio
//               对真实本地媒体做文件级验证（sha256 流式实测）
//
// 输出（--out 目录）: matrix.json / matrix.md / errors.jsonl / questions.jsonl / summary.json
//
// 退出码: 0=所要求检查全部通过; 1=存在真实缺口/冲突/未验证; 2=参数/配置错误; 3=预算/来源停止。

import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
import { resolveDataDir, readJson, readCurrent, sha256FileSync } from "../data-store.mjs";
import { findLatestRun, loadResolverContext } from "../resolver.mjs";
import { buildCoverage } from "../coverage.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "..", "..");

const USAGE = `usage: node ielts-api/tools/audit-all.mjs <mode> [options]

  --offline              离线校验：本地 run 数据 + fixtures（不发网络请求）
  --fixtures <dir>       配合 --offline；fixtures 目录（默认 <repo>/ielts-api/tests/fixtures）
  --dataset current      校验已发布的 current 数据集（indexes/manifests 指针）
  --verify-assets        校验题目/组 assets 的真实性（本地文件 sha256 / 结构化内容）
  --verify-audio         校验 336 个听力 Part 音频：catalog 记录 → 文件存在 → sha256 实测
  --out <dir>            输出目录（必填）
  --run <run_id>         --offline 模式指定 run（默认最新）
  --data-dir <dir>       数据根（默认 EXAMDATA_IELTS_DATA_DIR 或 <repo>/ielts-data）
  --json                 只输出 summary JSON（stdout）

退出码: 0=全部通过; 1=真实缺口/冲突/未验证; 2=参数; 3=预算/来源停止`;

function parseArgs(argv) {
  const opts = { flags: {}, verifyAssets: false, verifyAudio: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--offline") opts.flags.offline = true;
    else if (a === "--dataset") opts.dataset = argv[++i];
    else if (a === "--fixtures") opts.fixtures = argv[++i];
    else if (a === "--verify-assets") opts.verifyAssets = true;
    else if (a === "--verify-audio") opts.verifyAudio = true;
    else if (a === "--out") opts.out = argv[++i];
    else if (a === "--run") opts.run = argv[++i];
    else if (a === "--data-dir") opts.dataDir = argv[++i];
    else if (a === "--json") opts.flags.json = true;
    else if (a === "--help" || a === "-h") return { help: true };
    else return { error: "unknown arg: " + a };
  }
  if (opts.help) return opts;
  if (!opts.out) return { error: USAGE };
  if (opts.flags.offline && opts.dataset) return { error: "--offline 与 --dataset 互斥" };
  if (!opts.flags.offline && !opts.dataset) return { error: USAGE };
  if (opts.dataset && opts.dataset !== "current") return { error: `unsupported --dataset: ${opts.dataset} (only "current")` };
  return opts;
}

function rel(p, base) {
  return path.relative(base, p).split(path.sep).join("/");
}

/** 流式 sha256（大文件不整读内存） */
function sha256Stream(filePath) {
  return new Promise((resolve, reject) => {
    const h = crypto.createHash("sha256");
    const s = fs.createReadStream(filePath);
    s.on("data", (d) => h.update(d));
    s.on("end", () => resolve(h.digest("hex")));
    s.on("error", reject);
  });
}

/** 有限并发 map */
async function pMap(items, limit, fn) {
  const out = new Array(items.length);
  let i = 0;
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (i < items.length) {
      const idx = i++;
      out[idx] = await fn(items[idx], idx);
    }
  });
  await Promise.all(workers);
  return out;
}

// ---------- offline 模式 ----------

function enumerateFixtures(fixturesDir, errors) {
  const entries = [];
  if (!fixturesDir || !fs.existsSync(fixturesDir)) {
    errors.push({ kind: "fixtures_missing", path: fixturesDir });
    return entries;
  }
  const walk = (dir) => {
    for (const name of fs.readdirSync(dir).sort()) {
      const p = path.join(dir, name);
      const st = fs.statSync(p);
      if (st.isDirectory()) walk(p);
      else {
        const rec = { path: rel(p, fixturesDir), bytes: st.size, sha256: sha256FileSync(p) };
        if (name.endsWith(".json")) {
          try {
            const doc = readJson(p, { missingOk: false });
            rec.json_ok = true;
            rec.json_schema = doc && doc.schema ? doc.schema : null;
          } catch (e) {
            rec.json_ok = false;
            rec.json_error = String(e && e.message ? e.message : e);
            errors.push({ kind: "fixture_json_invalid", path: rec.path, error: rec.json_error });
          }
        }
        entries.push(rec);
      }
    }
  };
  walk(fixturesDir);
  return entries;
}

function checkAlignmentGold(goldPath, ctx, errors, findings) {
  const gold = readJson(goldPath, { missingOk: true });
  if (!gold) {
    errors.push({ kind: "alignment_gold_missing", path: goldPath });
    return null;
  }
  const result = {
    schema: gold.schema,
    parts_with_windows: (gold.parts || []).filter((p) => (p.windows || []).length).length,
    windows_total: (gold.parts || []).reduce((n, p) => n + (p.windows || []).length, 0),
    windows_checked: 0,
    windows_audio_sha_match: 0,
    windows_audio_sha_mismatch: [],
    windows_identity_missing: [],
    windows_doc_interval_match: 0,
    windows_doc_interval_missing: [],
    confirmed_windows: 0,
    unconfirmed_windows: 0,
    windows_false_verified: [],
    windows_correctly_unverified: 0,
    stats_claimed: gold.stats || null,
  };
  const alignDir = ctx && ctx.runDir ? path.join(ctx.runDir, "alignment") : null;
  for (const part of gold.parts || []) {
    const identity = part.identity;
    if (!identity) continue;
    // 本地 alignment doc 是否存在（doc 文件名 = identity 冒号换下划线）
    const docPath = alignDir ? path.join(alignDir, identity.replace(/:/g, "_") + ".json") : null;
    const doc = docPath && fs.existsSync(docPath) ? readJson(docPath, { missingOk: true }) : null;
    const docQ = new Map();
    if (doc && doc.provider && doc.provider.alignment) {
      for (const q of doc.provider.alignment.questions || []) docQ.set(q.number, q);
    }
    for (const w of part.windows || []) {
      result.windows_checked++;
      // 1) 音频 sha 与 catalog 一致
      const rec = ctx && ctx.audioByIdentity ? ctx.audioByIdentity.get(identity) : null;
      if (rec && rec.content_sha256 && w.audio_sha256 && rec.content_sha256 !== w.audio_sha256) {
        result.windows_audio_sha_mismatch.push({ identity, number: w.number, gold: w.audio_sha256.slice(0, 16), catalog: rec.content_sha256.slice(0, 16) });
      } else if (w.audio_sha256) {
        result.windows_audio_sha_match++;
      }
      // 2) doc 存在且有该题
      if (!doc) {
        result.windows_identity_missing.push({ identity, number: w.number, reason: "no alignment doc" });
        continue;
      }
      const q = docQ.get(w.number);
      if (!q) {
        result.windows_identity_missing.push({ identity, number: w.number, reason: "no question in doc" });
        continue;
      }
      // 3) 与 doc 对照，按 fixture 自身的 crosscheck 标签区分：
      //    asr_confirmed → doc 必须出现同区间（verified 证据）；否则是缺证据。
      //    not_text_verifiable / no_match → doc 不得把该题标为 verified（否则是虚假验证）。
      const cross = (w.evidence && w.evidence.asr_crosscheck && w.evidence.asr_crosscheck.status) || null;
      const ivs = (q.intervals || []).filter((iv) => iv.role === "answer_evidence");
      const match = ivs.some((iv) => Math.abs(iv.start_sec - w.start_sec) < 0.02 && Math.abs(iv.end_sec - w.end_sec) < 0.02);
      if (cross === "asr_confirmed") {
        result.confirmed_windows++;
        if (match) result.windows_doc_interval_match++;
        else result.windows_doc_interval_missing.push({ identity, number: w.number, gold: [w.start_sec, w.end_sec], doc: ivs.map((iv) => [iv.start_sec, iv.end_sec]), status: q.status, crosscheck: cross });
      } else {
        result.unconfirmed_windows++;
        if (q.status === "verified") result.windows_false_verified.push({ identity, number: w.number, status: q.status, crosscheck: cross });
        else result.windows_correctly_unverified++;
      }
    }
  }
  // 问题清单（problems）保留计数
  result.problems_total = (gold.problems || []).length;
  if (result.windows_audio_sha_mismatch.length) errors.push({ kind: "gold_audio_sha_mismatch", count: result.windows_audio_sha_mismatch.length, sample: result.windows_audio_sha_mismatch.slice(0, 5) });
  if (result.windows_doc_interval_missing.length) errors.push({ kind: "gold_confirmed_missing_in_doc", count: result.windows_doc_interval_missing.length, sample: result.windows_doc_interval_missing.slice(0, 5) });
  if (result.windows_false_verified.length) errors.push({ kind: "gold_false_verified", count: result.windows_false_verified.length, sample: result.windows_false_verified.slice(0, 5) });
  findings.alignment_gold = result;
  return result;
}

function runOffline(opts, dataDir, errors, findings) {
  const runId = opts.run || findLatestRun(dataDir);
  if (!runId) {
    errors.push({ kind: "no_run", message: "no run found in " + dataDir });
    return { runId: null };
  }
  const ctx = loadResolverContext({ dataDir, runId });
  findings.run_id = runId;

  // 1) fixtures 枚举 + parse
  const fixturesDir = opts.fixtures || path.join(REPO, "ielts-api", "tests", "fixtures");
  findings.fixtures_dir = fixturesDir;
  findings.fixtures = enumerateFixtures(fixturesDir, errors);

  // 2) alignment-gold 与本地 alignment docs 对照
  const goldPath = path.join(fixturesDir, "alignment-gold.json");
  if (fs.existsSync(goldPath)) checkAlignmentGold(goldPath, ctx, errors, findings);

  // 3) run 数据自洽性（index/audio/alignment 三源交叉）
  const idxPath = path.join(dataDir, "runs", runId, "index", "question-index.json");
  const index = readJson(idxPath, { missingOk: true });
  findings.index_present = Boolean(index);
  if (!index) {
    errors.push({ kind: "run_index_missing", path: idxPath });
    return { runId, ctx };
  }
  findings.index_stats = index.stats || null;
  findings.index_stats_actual = {
    pages: (index.pages || []).length,
    groups: (index.groups || []).length,
    questions: (index.questions || []).length,
    answers: index.answers ? Object.keys(index.answers).length : 0,
  };
  for (const k of ["pages", "groups", "questions", "answers"]) {
    if (index.stats && index.stats[k] !== undefined && index.stats[k] !== findings.index_stats_actual[k]) {
      errors.push({ kind: "index_stats_mismatch", field: k, claimed: index.stats[k], actual: findings.index_stats_actual[k] });
    }
  }

  // 4) alignment docs 与 index 的 stale 检查（doc 中 question_count=0 但 index 已有题目 → stale）
  const alignDir = path.join(dataDir, "runs", runId, "alignment");
  const stale = [];
  const alignSummary = { docs: 0, with_questions: 0, zero_question_docs: [], stale_docs: [] };
  if (fs.existsSync(alignDir)) {
    const files = fs.readdirSync(alignDir).filter((f) => f.endsWith(".json") && !f.endsWith(".asr.json") && f !== "summary.json");
    const qCounts = new Map();
    for (const q of index.questions || []) {
      if (q.skill !== "listening") continue;
      const key = `${q.book}:${q.test}:${q.part}`;
      qCounts.set(key, (qCounts.get(key) || 0) + 1);
    }
    for (const f of files) {
      const doc = readJson(path.join(alignDir, f), { missingOk: true });
      if (!doc || !doc.identity) continue;
      alignSummary.docs++;
      const n = doc.inputs ? doc.inputs.question_count : 0;
      if (n > 0) alignSummary.with_questions++;
      else alignSummary.zero_question_docs.push(doc.identity);
      const [, book, , , test, part] = doc.identity.split(":");
      const expected = qCounts.get(`${book}:${test}:${part}`) || 0;
      if (expected > 0 && n === 0) {
        stale.push({ identity: doc.identity, doc_questions: 0, index_questions: expected });
      }
    }
  }
  alignSummary.stale_docs = stale;
  findings.alignment_docs = alignSummary;
  if (stale.length) errors.push({ kind: "alignment_stale", count: stale.length, sample: stale.slice(0, 8) });

  // 5) 音频 catalog 与文件存在性（不计算 sha，交给 --verify-audio）
  const catPath = path.join(dataDir, "runs", runId, "audio", "audio-catalog.json");
  const cat = readJson(catPath, { missingOk: true });
  findings.audio_catalog_present = Boolean(cat);
  if (cat) {
    const partRecs = (cat.records || []).filter((r) => r.identity && r.identity.split(":").length === 6);
    const missingFiles = [];
    const statuses = {};
    for (const r of partRecs) {
      statuses[r.status] = (statuses[r.status] || 0) + 1;
      if (r.file_path && !fs.existsSync(r.file_path)) missingFiles.push(r.identity);
    }
    findings.audio = { part_records: partRecs.length, statuses, missing_files: missingFiles };
    if (partRecs.length !== 336) errors.push({ kind: "audio_part_records_count", count: partRecs.length, expected: 336 });
    if (missingFiles.length) errors.push({ kind: "audio_files_missing", count: missingFiles.length, sample: missingFiles.slice(0, 8) });
  } else {
    errors.push({ kind: "audio_catalog_missing", path: catPath });
  }

  return { runId, ctx, index };
}

// ---------- dataset 模式 ----------

function loadCurrentDataset(dataDir, errors) {
  const idxPtr = readCurrent({ root: dataDir, kind: "indexes" });
  const covPtr = readCurrent({ root: dataDir, kind: "manifests" });
  if (!idxPtr || !covPtr) {
    errors.push({
      kind: "dataset_missing",
      message: "current 数据集未发布",
      hint: "先运行: node ielts-api/tools/build-index.mjs --dataset current",
    });
    return null;
  }
  const index = readJson(path.join(dataDir, idxPtr.artifact), { missingOk: true });
  const coverage = readJson(path.join(dataDir, covPtr.artifact), { missingOk: true });
  if (!index || !coverage) {
    errors.push({ kind: "dataset_artifact_missing", index: idxPtr.artifact, coverage: covPtr.artifact });
    return null;
  }
  if (index.dataset_revision !== idxPtr.dataset_revision || coverage.dataset_revision !== covPtr.dataset_revision) {
    errors.push({
      kind: "dataset_revision_mismatch",
      pointer: idxPtr.dataset_revision,
      index: index.dataset_revision,
      coverage: coverage.dataset_revision,
    });
  }
  return { index, coverage, revision: idxPtr.dataset_revision };
}

function readExpectedManifest(errors) {
  const p = path.join(REPO, "ielts-api", "data", "expected-manifest.json");
  const m = readJson(p, { missingOk: true });
  if (!m) {
    errors.push({ kind: "expected_manifest_missing", path: p });
    return null;
  }
  const items = [];
  for (const b of m.books || []) for (const it of b.items || []) items.push(it);
  return { doc: m, items, path: p };
}

/** 168 组合矩阵：21 册 × 4 套 × reading/listening */
function buildCombos(index, manifest, errors) {
  const pageByKey = new Map();
  for (const p of index.pages || []) {
    pageByKey.set(`${p.book}|${p.variant}|${p.skill}|${p.test}`, p);
  }
  const qByKey = new Map();
  for (const q of index.questions || []) {
    const k = `${q.book}|${q.variant}|${q.skill}|${q.test}`;
    if (!qByKey.has(k)) qByKey.set(k, []);
    qByKey.get(k).push(q);
  }
  const itemsByKey = new Map();
  for (const it of manifest.items) {
    const k = `${it.book}|${it.variant}|${it.skill}|${it.test}`;
    if (!itemsByKey.has(k)) itemsByKey.set(k, []);
    itemsByKey.get(k).push(it);
  }
  const combos = [];
  for (const book of manifest.doc.books.map((b) => b.book)) {
    for (const skill of ["reading", "listening"]) {
      const variant = skill === "reading" ? "academic" : "shared";
      const tests = [...new Set(manifest.items.filter((i) => i.book === book && i.variant === variant && i.skill === skill).map((i) => i.test))];
      for (const test of tests.sort((a, b) => Number(a) - Number(b))) {
        const key = `${book}|${variant}|${skill}|${test}`;
        const page = pageByKey.get(key) || null;
        const qs = (qByKey.get(key) || []).slice().sort((a, b) => a.number - b.number);
        const items = itemsByKey.get(key) || [];
        const expectedNumbers = items.flatMap((i) => i.expected_numbers || []).sort((a, b) => a - b);
        const observedNumbers = qs.map((q) => q.number);
        const missingNumbers = expectedNumbers.filter((n) => !observedNumbers.includes(n));
        const extraNumbers = observedNumbers.filter((n) => !expectedNumbers.includes(n));
        const answerCounts = { attached: 0, missing: 0, empty: 0, other: 0 };
        for (const q of qs) {
          if (q.answer_status === "attached") answerCounts.attached++;
          else if (q.answer_status === "missing") answerCounts.missing++;
          else if (q.answer_status === "empty") answerCounts.empty++;
          else answerCounts.other++;
        }
        const combo = {
          book,
          variant,
          skill,
          test,
          page_ref: page ? page.page_ref : null,
          page_present: Boolean(page),
          page_counts: page ? page.counts : null,
          passages: page && page.counts ? page.counts.passages : null,
          parts: skill === "listening" ? [...new Set(qs.map((q) => q.part))].sort() : null,
          expected_numbers: expectedNumbers,
          observed_numbers: observedNumbers,
          missing_numbers: missingNumbers,
          extra_numbers: extraNumbers,
          questions: qs.length,
          answers: answerCounts,
          content_status: qs.reduce((acc, q) => { acc[q.content_status] = (acc[q.content_status] || 0) + 1; return acc; }, {}),
          issues: [],
        };
        if (!page) combo.issues.push("page_missing");
        if (skill === "reading" && page && page.counts && page.counts.passages !== 3) combo.issues.push(`passages=${page.counts.passages}`);
        if (skill === "listening") {
          const parts = combo.parts || [];
          if (parts.length !== 4) combo.issues.push(`parts=${parts.length}`);
        }
        if (missingNumbers.length) combo.issues.push(`missing_numbers=${missingNumbers.length}`);
        if (extraNumbers.length) combo.issues.push(`extra_numbers=${extraNumbers.length}`);
        if (answerCounts.missing || answerCounts.empty) combo.issues.push(`answers_missing=${answerCounts.missing} empty=${answerCounts.empty}`);
        combos.push(combo);
      }
    }
  }
  return combos;
}

function buildUnitMatrix(coverage) {
  const units = [];
  for (const b of coverage.books || []) {
    for (const u of b.units || []) {
      units.push({
        unit_id: u.unit_id,
        book: u.book,
        test: u.test,
        skill: u.skill,
        variant: u.variant,
        status: u.status,
        status_reasons: u.status_reasons || [],
        numbers: u.numbers ? { expected: (u.numbers.expected || []).length, observed: (u.numbers.observed || []).length, missing: (u.numbers.missing || []).length, extra: (u.numbers.extra || []).length } : null,
        completion: u.completion || null,
        audio: u.audio ? { status: u.audio.status, parts: u.audio.parts ? u.audio.parts.length : null } : null,
        alignment: u.alignment ? { status: u.alignment.status } : null,
      });
    }
  }
  return units;
}

async function verifyAssets(index, dataDir, errors, findings) {
  const qAssets = [];
  for (const q of index.questions || []) {
    for (const a of q.assets || []) qAssets.push({ owner: q.id, owner_type: "question", ...a });
  }
  for (const g of index.groups || []) {
    for (const a of g.assets || []) qAssets.push({ owner: g.id, owner_type: "group", ...a });
  }
  const result = { total: qAssets.length, verified_file: 0, verified_structured: 0, external_only: 0, broken: [], by_kind: {} };
  for (const a of qAssets) {
    const kind = a.kind || a.type || "unknown";
    result.by_kind[kind] = (result.by_kind[kind] || 0) + 1;
    const local = a.local_path ? path.resolve(REPO, a.local_path) : null;
    const isStructured = a.content && typeof a.content === "object" && (a.content.headers || a.content.rows || a.content.title || a.content.flowchart);
    if (local && fs.existsSync(local) && fs.statSync(local).size > 0) {
      result.verified_file++;
      a._verify = "verified_file";
    } else if (local && !fs.existsSync(local)) {
      result.broken.push({ owner: a.owner, kind, local_path: a.local_path, reason: "file_missing" });
      a._verify = "broken";
    } else if (isStructured) {
      result.verified_structured++;
      a._verify = "verified_structured";
    } else if (a.source_ref || a.url || a.source) {
      result.external_only++;
      a._verify = "external_only";
    } else {
      result.broken.push({ owner: a.owner, kind, reason: "no_local_no_structured_no_source" });
      a._verify = "broken";
    }
  }
  // expected_assets 对照（manifest）
  const manifest = readExpectedManifest(errors);
  const expected = [];
  if (manifest) {
    for (const it of manifest.items) {
      for (const ea of it.expected_assets || []) expected.push({ item_id: it.id, ...ea });
    }
  }
  const expectedCheck = expected.map((ea) => {
    const book = Number(ea.item_id.split(":")[1]);
    const matching = qAssets.filter((a) => String(a.owner).includes(`:${book}:`) && (a.kind === ea.kind || a.type === ea.kind));
    return { ...ea, matched_assets: matching.length, ok: matching.length > 0 };
  });
  result.expected_assets = expectedCheck;
  result.expected_assets_ok = expectedCheck.every((e) => e.ok);
  if (!result.expected_assets_ok) errors.push({ kind: "expected_assets_unmatched", items: expectedCheck.filter((e) => !e.ok) });
  if (result.broken.length) errors.push({ kind: "assets_broken", count: result.broken.length, sample: result.broken.slice(0, 8) });
  findings.assets = result;
}

async function verifyAudio(dataDir, errors, findings, index) {
  const catPath = path.join(dataDir, "runs", findings.run_id || "", "audio", "audio-catalog.json");
  let cat = readJson(catPath, { missingOk: true });
  if (!cat) {
    // dataset 模式：从 run 列表里找含 audio 目录的最新 run
    const runsDir = path.join(dataDir, "runs");
    if (fs.existsSync(runsDir)) {
      for (const d of fs.readdirSync(runsDir).sort().reverse()) {
        const p = path.join(runsDir, d, "audio", "audio-catalog.json");
        if (fs.existsSync(p)) { cat = readJson(p, { missingOk: true }); findings.audio_catalog_path = rel(p, dataDir); break; }
      }
    }
  } else {
    findings.audio_catalog_path = rel(catPath, dataDir);
  }
  if (!cat) {
    errors.push({ kind: "audio_catalog_missing" });
    return;
  }
  const partRecs = (cat.records || []).filter((r) => r.identity && r.identity.split(":").length === 6);
  // 应有 336 个 Part identity：21×4×4
  const expectedIds = [];
  for (let book = 1; book <= 21; book++) {
    for (let test = 1; test <= 4; test++) {
      for (let part = 1; part <= 4; part++) {
        expectedIds.push(`cambridge:${book}:shared:listening:${test}:P${part}`);
      }
    }
  }
  const byId = new Map(partRecs.map((r) => [r.identity, r]));
  const result = {
    expected_parts: expectedIds.length,
    records: partRecs.length,
    verified_hash: 0,
    hash_mismatch: [],
    file_missing: [],
    not_run: [],
    identity_status: {},
    rows: [],
  };
  const todo = expectedIds.map((id) => {
    const rec = byId.get(id);
    if (!rec) return { id, status: "record_missing" };
    return { id, rec };
  });
  const rows = await pMap(todo, 4, async ({ id, rec, status }) => {
    if (status === "record_missing") {
      result.not_run.push({ identity: id, reason: "catalog record missing" });
      return { identity: id, status: "record_missing" };
    }
    const st = rec.status;
    result.identity_status[rec.identity_status || "null"] = (result.identity_status[rec.identity_status || "null"] || 0) + 1;
    if (!rec.file_path) {
      result.not_run.push({ identity: id, reason: `no file_path (status=${st})` });
      return { identity: id, status: "not_run", record_status: st };
    }
    if (!fs.existsSync(rec.file_path)) {
      result.file_missing.push({ identity: id, file_path: rec.file_path, record_status: st });
      return { identity: id, status: "file_missing", record_status: st };
    }
    const actual = await sha256Stream(rec.file_path);
    if (rec.content_sha256 && actual === rec.content_sha256) {
      result.verified_hash++;
      return { identity: id, status: "verified_hash", record_status: st, sha256: actual.slice(0, 16), bytes: rec.bytes, duration_sec: rec.duration_sec };
    }
    result.hash_mismatch.push({ identity: id, file_path: rec.file_path, expected: (rec.content_sha256 || "").slice(0, 16), actual: actual.slice(0, 16) });
    return { identity: id, status: "hash_mismatch", record_status: st };
  });
  result.rows = rows;
  findings.audio_verify = {
    expected_parts: result.expected_parts,
    records: result.records,
    verified_hash: result.verified_hash,
    hash_mismatch: result.hash_mismatch.length,
    file_missing: result.file_missing.length,
    not_run: result.not_run.length,
    identity_status: result.identity_status,
  };
  if (result.hash_mismatch.length) errors.push({ kind: "audio_hash_mismatch", count: result.hash_mismatch.length, sample: result.hash_mismatch.slice(0, 5) });
  if (result.file_missing.length) errors.push({ kind: "audio_file_missing", count: result.file_missing.length, sample: result.file_missing.slice(0, 5) });
  if (result.records !== 336) errors.push({ kind: "audio_records_count", count: result.records, expected: 336 });
  if (result.verified_hash !== 336) {
    errors.push({ kind: "audio_not_all_verified", verified: result.verified_hash, expected: 336, not_run: result.not_run.length });
  }
  findings.audio_verify.rows_path = null;
}

function buildAlignmentMatrix(index, dataDir, errors, findings) {
  const alignDirCandidates = [];
  const runsDir = path.join(dataDir, "runs");
  if (fs.existsSync(runsDir)) {
    for (const d of fs.readdirSync(runsDir).sort().reverse()) {
      const p = path.join(runsDir, d, "alignment");
      if (fs.existsSync(p)) alignDirCandidates.push(p);
    }
  }
  const alignDir = alignDirCandidates[0] || null;
  const result = { dir: alignDir ? rel(alignDir, dataDir) : null, docs: 0, per_part: [], totals: { questions: 0, verified: 0, needs_review: 0, section_only: 0, unverified: 0, missing: 0 } };
  if (!alignDir) {
    errors.push({ kind: "alignment_dir_missing" });
    findings.alignment = result;
    return;
  }
  const qCounts = new Map();
  for (const q of index.questions || []) {
    if (q.skill !== "listening") continue;
    const key = `${q.book}:${q.test}:${q.part}`;
    qCounts.set(key, (qCounts.get(key) || 0) + 1);
  }
  const files = fs.readdirSync(alignDir).filter((f) => f.endsWith(".json") && !f.endsWith(".asr.json") && f !== "summary.json");
  for (const f of files) {
    const doc = readJson(path.join(alignDir, f), { missingOk: true });
    if (!doc || !doc.identity || !doc.provider || !doc.provider.alignment) continue;
    result.docs++;
    const al = doc.provider.alignment;
    const cov = al.coverage || {};
    const [, book, , , test, part] = doc.identity.split(":");
    const idxQ = qCounts.get(`${book}:${test}:${part}`) || 0;
    const row = {
      identity: doc.identity,
      book: Number(book),
      test,
      part,
      method: al.method || null,
      clock_valid: al.clock ? al.clock.valid : null,
      audio_sha256: doc.inputs && doc.inputs.audio ? doc.inputs.audio.content_sha256 : null,
      index_questions: idxQ,
      doc_questions: doc.inputs ? doc.inputs.question_count : 0,
      coverage: cov,
      stale: idxQ > 0 && (doc.inputs ? doc.inputs.question_count : 0) === 0,
      has_question_intervals: false,
    };
    const qs = al.questions || [];
    row.has_question_intervals = qs.some((q) => (q.intervals || []).length > 0);
    result.per_part.push(row);
    for (const k of ["questions_total", "verified", "needs_review", "section_only", "unverified", "missing"]) {
      if (cov[k]) result.totals[k === "questions_total" ? "questions" : k] += cov[k];
    }
  }
  result.totals.verified = result.per_part.reduce((n, r) => n + (r.coverage.verified || 0), 0);
  result.totals.needs_review = result.per_part.reduce((n, r) => n + (r.coverage.needs_review || 0), 0);
  result.totals.section_only = result.per_part.reduce((n, r) => n + (r.coverage.section_only || 0), 0);
  result.totals.unverified = result.per_part.reduce((n, r) => n + (r.coverage.unverified || 0), 0);
  result.totals.missing = result.per_part.reduce((n, r) => n + (r.coverage.missing || 0), 0);
  result.totals.questions = result.per_part.reduce((n, r) => n + (r.coverage.questions_total || 0), 0);
  const stale = result.per_part.filter((r) => r.stale);
  if (stale.length) errors.push({ kind: "alignment_stale", count: stale.length, sample: stale.slice(0, 8).map((r) => r.identity) });
  const clockBad = result.per_part.filter((r) => r.clock_valid === false);
  if (clockBad.length) errors.push({ kind: "alignment_clock_invalid", count: clockBad.length, sample: clockBad.slice(0, 8).map((r) => r.identity) });
  findings.alignment = result;
}

function writeOutputs(outDir, { findings, errors, combos, units, questions }, dataDir) {
  fs.mkdirSync(outDir, { recursive: true });
  const errorsPath = path.join(outDir, "errors.jsonl");
  const errLines = errors.map((e) => JSON.stringify(e));
  fs.writeFileSync(errorsPath, errLines.length ? errLines.join("\n") + "\n" : "");
  if (questions) {
    const qPath = path.join(outDir, "questions.jsonl");
    const lines = questions.map((q) => JSON.stringify(q));
    fs.writeFileSync(qPath, lines.length ? lines.join("\n") + "\n" : "");
  }
  const matrix = {
    schema: "ielts.audit-matrix/1",
    generated_at_utc: new Date().toISOString(),
    data_dir: dataDir,
    mode: findings.mode,
    run_id: findings.run_id || null,
    dataset_revision: findings.dataset_revision || null,
    combos: combos || null,
    units: units || null,
    findings,
  };
  fs.writeFileSync(path.join(outDir, "matrix.json"), JSON.stringify(matrix, null, 1));
  // matrix.md
  const md = [];
  md.push(`# IELTS audit matrix (${findings.mode})`);
  md.push("");
  md.push(`- generated_at_utc: ${matrix.generated_at_utc}`);
  md.push(`- data_dir: ${dataDir}`);
  md.push(`- run_id: ${matrix.run_id || "-"}`);
  md.push(`- dataset_revision: ${matrix.dataset_revision || "-"}`);
  md.push(`- errors: ${errors.length}`);
  md.push("");
  if (combos) {
    md.push("## 168 Academic reading/listening combos");
    md.push("");
    md.push("| book | test | skill | page | passages/parts | questions | answers(att/miss/empty) | missing# | extra# | issues |");
    md.push("|---|---|---|---|---|---|---|---|---|---|");
    for (const c of combos) {
      const pp = c.skill === "reading" ? `passages=${c.passages}` : `parts=${(c.parts || []).join(",")}`;
      md.push(`| ${c.book} | ${c.test} | ${c.skill} | ${c.page_present ? "Y" : "N"} | ${pp} | ${c.questions} | ${c.answers.attached}/${c.answers.missing}/${c.answers.empty} | ${c.missing_numbers.length} | ${c.extra_numbers.length} | ${c.issues.join("; ") || "-"} |`);
    }
    md.push("");
  }
  if (units) {
    md.push("## Coverage units");
    md.push("");
    md.push("| unit | status | expected# | observed# | missing# | reasons |");
    md.push("|---|---|---|---|---|---|");
    for (const u of units) {
      md.push(`| ${u.unit_id} | ${u.status} | ${u.numbers ? u.numbers.expected : "-"} | ${u.numbers ? u.numbers.observed : "-"} | ${u.numbers ? u.numbers.missing : "-"} | ${(u.status_reasons || []).join("; ") || "-"} |`);
    }
    md.push("");
  }
  if (errors.length) {
    md.push("## Errors");
    md.push("");
    const byKind = {};
    for (const e of errors) byKind[e.kind] = (byKind[e.kind] || 0) + 1;
    md.push("| kind | count |");
    md.push("|---|---|");
    for (const [k, n] of Object.entries(byKind).sort((a, b) => b[1] - a[1])) md.push(`| ${k} | ${n} |`);
    md.push("");
  }
  fs.writeFileSync(path.join(outDir, "matrix.md"), md.join("\n"));
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (opts.help) { console.log(USAGE); process.exit(0); }
  if (opts.error) { console.error(opts.error); process.exit(2); }

  const dataDir = resolveDataDir(opts.dataDir);
  const outDir = path.resolve(opts.out);
  const errors = [];
  const findings = { mode: opts.flags.offline ? "offline" : "dataset" };
  let combos = null;
  let units = null;
  let questions = null;

  if (opts.flags.offline) {
    const r = runOffline(opts, dataDir, errors, findings);
    findings.run_id = r.runId || findings.run_id || null;
  } else {
    const ds = loadCurrentDataset(dataDir, errors);
    if (ds) {
      findings.dataset_revision = ds.revision;
      findings.index_stats = ds.index.stats || null;
      const manifest = readExpectedManifest(errors);
      if (manifest) {
        combos = buildCombos(ds.index, manifest, errors);
        findings.manifest_items = manifest.items.length;
      }
      units = buildUnitMatrix(ds.coverage);
      findings.coverage_summary = ds.coverage.summary || null;
      questions = (ds.index.questions || []).map((q) => ({
        id: q.id,
        book: q.book,
        variant: q.variant,
        skill: q.skill,
        test: q.test,
        part: q.part,
        passage: q.passage,
        number: q.number,
        group_id: q.group_id,
        type: q.type || null,
        classification_status: q.classification_status || null,
        content_status: q.content_status || null,
        answer_status: q.answer_status || null,
        answer_mode: q.answer_mode || null,
        source_refs: q.source_refs || null,
        audio_alignment_ref: q.audio_alignment_ref || null,
        fully_complete: q.fully_complete === true,
      }));
      // run_id for media paths
      const runsDir = path.join(dataDir, "runs");
      if (ds.index.store && ds.index.store.source_run) findings.run_id = ds.index.store.source_run;
      if (opts.verifyAssets) await verifyAssets(ds.index, dataDir, errors, findings);
      if (opts.verifyAudio) await verifyAudio(dataDir, errors, findings, ds.index);
      buildAlignmentMatrix(ds.index, dataDir, errors, findings);
    }
  }

  const summary = {
    schema: "ielts.audit-summary/1",
    mode: findings.mode,
    run_id: findings.run_id || null,
    dataset_revision: findings.dataset_revision || null,
    out_dir: outDir,
    combos_total: combos ? combos.length : null,
    combos_with_issues: combos ? combos.filter((c) => c.issues.length).length : null,
    units_total: units ? units.length : null,
    units_by_status: units ? units.reduce((acc, u) => { acc[u.status] = (acc[u.status] || 0) + 1; return acc; }, {}) : null,
    errors_total: errors.length,
    errors_by_kind: errors.reduce((acc, e) => { acc[e.kind] = (acc[e.kind] || 0) + 1; return acc; }, {}),
    overall: errors.length ? "partial" : "pass",
  };
  writeOutputs(outDir, { findings, errors, combos, units, questions }, dataDir);
  if (!opts.flags.json) {
    console.log(JSON.stringify(summary, null, 2));
  } else {
    console.log(JSON.stringify(summary));
  }
  process.exit(errors.length ? 1 : 0);
}

main().catch((e) => {
  console.error(JSON.stringify({ ok: false, error: String(e && e.stack ? e.stack : e) }));
  process.exit(2);
});
