#!/usr/bin/env node
// ielts-api/tools/build-index.mjs
// S14: 从本地 run 索引构建 dataset 存储（indexes/ + manifests/ + normalized/），
// 全量校验通过后原子发布 current 指针。绝不发网络请求。
//
// 用法:
//   node ielts-api/tools/build-index.mjs --dataset current [--run <run_id>] [--data-dir <dir>] [--dry-run]
//
// 输入: <data-dir>/runs/<run_id>/index/question-index.json（由 tools/build-question-index.mjs 构建）
// 输出:
//   indexes/<rev>/questions.json            (+ current 指针)
//   manifests/<rev>/coverage.json           (+ current 指针)
//   normalized/normalized-v1/<rev>/cambridge-<book>-<test>.json
//
// 退出码: 0=构建并发布成功; 1=校验失败或缺失（不发布）; 2=参数/配置错误。

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  resolveDataDir,
  ensureLayout,
  writeJsonAtomic,
  readJson,
  sha256FileSync,
  computeDatasetRevision,
  publishCurrent,
} from "../data-store.mjs";
import { findLatestRun, loadResolverContext } from "../resolver.mjs";
import { buildCoverage } from "../coverage.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const STORE_SCHEMA = "store-v1";
const NORMALIZED_SCHEMA = "normalized-v1";
const PARSER_VERSION = "s14-build-index-2026.10.5";

const USAGE = `usage: node ielts-api/tools/build-index.mjs --dataset current [--run <run_id>] [--data-dir <dir>] [--dry-run]

  --dataset current   必填；构建并发布 current 数据集（indexes/ + manifests/ + normalized/）
  --run <run_id>      指定 run（默认取含 question-index.json 的最新 run）
  --data-dir <dir>    数据根（默认 EXAMDATA_IELTS_DATA_DIR 或 <repo>/ielts-data）
  --dry-run           只构建与校验，不写盘、不发布`;

function parseArgs(argv) {
  const opts = { flags: {} };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--dataset") opts.dataset = argv[++i];
    else if (a === "--run") opts.run = argv[++i];
    else if (a === "--data-dir") opts.dataDir = argv[++i];
    else if (a === "--dry-run") opts.flags.dryRun = true;
    else if (a === "--help" || a === "-h") return { help: true };
    else return { error: "unknown arg: " + a };
  }
  if (opts.help) return opts;
  if (!opts.dataset) return { error: USAGE };
  if (opts.dataset !== "current") return { error: `unsupported --dataset: ${opts.dataset} (only "current")` };
  return opts;
}

/** 索引结构校验：返回 {ok, errors[], stats} */
export function validateIndex(index) {
  const errors = [];
  if (!index || typeof index !== "object") return { ok: false, errors: ["index not an object"], stats: null };
  const pages = index.pages || [];
  const groups = index.groups || [];
  const questions = index.questions || [];
  if (!pages.length) errors.push("pages empty");
  if (!questions.length) errors.push("questions empty");

  const pageRefs = new Set();
  for (const p of pages) {
    if (!p.page_ref) errors.push("page without page_ref");
    else if (pageRefs.has(p.page_ref)) errors.push(`duplicate page_ref: ${p.page_ref}`);
    else pageRefs.add(p.page_ref);
  }
  const groupIds = new Set();
  for (const g of groups) {
    if (!g.id) errors.push("group without id");
    else if (groupIds.has(g.id)) errors.push(`duplicate group id: ${g.id}`);
    else groupIds.add(g.id);
    if (g.page_ref && !pageRefs.has(g.page_ref)) errors.push(`group ${g.id} references unknown page ${g.page_ref}`);
  }
  const qIds = new Set();
  for (const q of questions) {
    if (!q.id) { errors.push("question without id"); continue; }
    if (qIds.has(q.id)) errors.push(`duplicate question id: ${q.id}`);
    else qIds.add(q.id);
    if (q.page_ref && !pageRefs.has(q.page_ref)) errors.push(`question ${q.id} references unknown page ${q.page_ref}`);
    if (q.group_id && !groupIds.has(q.group_id)) errors.push(`question ${q.id} references unknown group ${q.group_id}`);
    const ident = q.identity || {};
    for (const k of ["book", "variant", "skill", "test", "number"]) {
      if (ident[k] === undefined || ident[k] === null) errors.push(`question ${q.id} identity.${k} missing`);
    }
  }
  const answersCount = index.answers && typeof index.answers === "object" && !Array.isArray(index.answers)
    ? Object.keys(index.answers).length
    : Array.isArray(index.answers) ? index.answers.length : 0;
  const stats = {
    pages: pages.length,
    groups: groups.length,
    questions: questions.length,
    answers: answersCount,
    answer_groups: (index.answer_groups || []).length,
  };
  if (index.stats) {
    for (const k of ["pages", "groups", "questions", "answers"]) {
      if (index.stats[k] !== undefined && index.stats[k] !== stats[k]) {
        errors.push(`stats.${k}=${index.stats[k]} != actual ${stats[k]}`);
      }
    }
  }
  return { ok: errors.length === 0, errors, stats };
}

/** 按 (book, test) 分组构建 normalized 文档（纯本地切片） */
export function buildNormalizedDocs(index, revision) {
  const byTest = new Map();
  const keyOf = (p) => `${p.book}|${p.test}`;
  for (const p of index.pages || []) {
    const k = keyOf(p);
    if (!byTest.has(k)) byTest.set(k, { book: p.book, test: p.test, pageRefs: new Set(), pages: [] });
    byTest.get(k).pageRefs.add(p.page_ref);
    byTest.get(k).pages.push(p);
  }
  const groupsByPage = new Map();
  for (const g of index.groups || []) {
    if (!groupsByPage.has(g.page_ref)) groupsByPage.set(g.page_ref, []);
    groupsByPage.get(g.page_ref).push(g);
  }
  const questionsByPage = new Map();
  for (const q of index.questions || []) {
    if (!questionsByPage.has(q.page_ref)) questionsByPage.set(q.page_ref, []);
    questionsByPage.get(q.page_ref).push(q);
  }
  const docs = [];
  for (const [k, t] of byTest) {
    const pages = t.pages.slice().sort((a, b) => String(a.page_ref).localeCompare(String(b.page_ref)));
    const groups = [];
    const questions = [];
    const warnings = [];
    for (const p of pages) {
      groups.push(...(groupsByPage.get(p.page_ref) || []));
      questions.push(...(questionsByPage.get(p.page_ref) || []));
      for (const w of p.warnings || []) warnings.push({ page_ref: p.page_ref, ...w });
    }
    const variants = [...new Set(pages.map((p) => p.variant))].sort();
    const skills = [...new Set(pages.map((p) => p.skill))].sort();
    const testId = `cambridge-${t.book}-${String(t.test).replace(/[^A-Za-z0-9._-]/g, "_")}`;
    docs.push({
      schema: "ielts.normalized/1",
      dataset_revision: revision,
      test_id: testId,
      book: t.book,
      test: t.test,
      variants,
      skills,
      pages,
      groups,
      questions,
      counts: { pages: pages.length, groups: groups.length, questions: questions.length },
      warnings,
    });
  }
  docs.sort((a, b) => a.test_id.localeCompare(b.test_id));
  return docs;
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (opts.help) { console.log(USAGE); process.exit(0); }
  if (opts.error) { console.error(opts.error); process.exit(2); }

  const dataDir = resolveDataDir(opts.dataDir);
  ensureLayout(dataDir);
  const runId = opts.run || findLatestRun(dataDir);
  if (!runId) {
    console.error(JSON.stringify({ ok: false, error: "no run with question-index.json found", data_dir: dataDir }));
    process.exit(1);
  }
  const indexPath = path.join(dataDir, "runs", runId, "index", "question-index.json");
  const index = readJson(indexPath, { missingOk: true });
  if (!index) {
    console.error(JSON.stringify({ ok: false, error: "index missing", path: indexPath }));
    process.exit(1);
  }

  const v = validateIndex(index);
  if (!v.ok) {
    console.error(JSON.stringify({ ok: false, error: "index validation failed", run_id: runId, errors: v.errors.slice(0, 50), error_count: v.errors.length }));
    process.exit(1);
  }

  const indexSha = sha256FileSync(indexPath);
  const revision = computeDatasetRevision({
    inputHashes: { run_index: indexSha },
    parserVersion: PARSER_VERSION,
    schemaVersion: STORE_SCHEMA,
  });

  const builtAt = new Date().toISOString();
  const indexDoc = {
    ...index,
    dataset_revision: revision,
    store: { schema: STORE_SCHEMA, built_at: builtAt, source_run: runId, source_path: path.relative(dataDir, indexPath).split(path.sep).join("/"), source_sha256: indexSha, builder: PARSER_VERSION },
  };
  const ctx = loadResolverContext({ dataDir, runId });
  const coverage = buildCoverage({ ctx });
  const coverageDoc = { ...coverage, dataset_revision: revision, store: { schema: STORE_SCHEMA, built_at: builtAt, source_run: runId, builder: PARSER_VERSION } };
  const normalizedDocs = buildNormalizedDocs(index, revision);

  // 构建产物校验（写盘前）
  const artifactErrors = [];
  if (coverageDoc.summary && coverageDoc.summary.units !== (index.pages || []).length * 0 + coverageDoc.summary.units) artifactErrors.push("coverage summary malformed");
  const normalizedQuestions = normalizedDocs.reduce((n, d) => n + d.questions.length, 0);
  if (normalizedQuestions !== (index.questions || []).length) {
    artifactErrors.push(`normalized questions ${normalizedQuestions} != index questions ${(index.questions || []).length}`);
  }
  const normalizedPages = normalizedDocs.reduce((n, d) => n + d.pages.length, 0);
  if (normalizedPages !== (index.pages || []).length) {
    artifactErrors.push(`normalized pages ${normalizedPages} != index pages ${(index.pages || []).length}`);
  }
  if (artifactErrors.length) {
    console.error(JSON.stringify({ ok: false, error: "artifact validation failed", errors: artifactErrors }));
    process.exit(1);
  }

  const summary = {
    ok: true,
    dataset_revision: revision,
    run_id: runId,
    dry_run: Boolean(opts.flags.dryRun),
    counts: {
      pages: (index.pages || []).length,
      groups: (index.groups || []).length,
      questions: (index.questions || []).length,
      normalized_tests: normalizedDocs.length,
      coverage_units: coverageDoc.summary ? coverageDoc.summary.units : null,
    },
  };

  if (opts.flags.dryRun) {
    console.log(JSON.stringify(summary, null, 2));
    process.exit(0);
  }

  const idxPath = path.join(dataDir, "indexes", revision, "questions.json");
  const covPath = path.join(dataDir, "manifests", revision, "coverage.json");
  writeJsonAtomic(idxPath, indexDoc);
  writeJsonAtomic(covPath, coverageDoc);
  const normPaths = [];
  for (const d of normalizedDocs) {
    const p = path.join(dataDir, "normalized", NORMALIZED_SCHEMA, revision, d.test_id + ".json");
    writeJsonAtomic(p, d);
    normPaths.push(p);
  }

  // 写盘回读校验
  const rt = readJson(idxPath);
  const rtCov = readJson(covPath);
  const rtErrors = [];
  if (!rt || rt.dataset_revision !== revision) rtErrors.push("indexes questions.json readback failed");
  if (!rtCov || rtCov.dataset_revision !== revision) rtErrors.push("manifests coverage.json readback failed");
  for (const p of normPaths) {
    const d = readJson(p);
    if (!d || d.dataset_revision !== revision) rtErrors.push(`normalized readback failed: ${p}`);
  }
  if (rtErrors.length) {
    console.error(JSON.stringify({ ok: false, error: "readback validation failed; current not published", errors: rtErrors }));
    process.exit(1);
  }

  const idxPointer = publishCurrent({ root: dataDir, kind: "indexes", datasetRevision: revision, validated: true });
  const covPointer = publishCurrent({ root: dataDir, kind: "manifests", datasetRevision: revision, validated: true });

  summary.paths = {
    index: path.relative(dataDir, idxPath).split(path.sep).join("/"),
    coverage: path.relative(dataDir, covPath).split(path.sep).join("/"),
    normalized_dir: path.relative(dataDir, path.join(dataDir, "normalized", NORMALIZED_SCHEMA, revision)).split(path.sep).join("/"),
    index_current: path.relative(dataDir, idxPointer).split(path.sep).join("/"),
    coverage_current: path.relative(dataDir, covPointer).split(path.sep).join("/"),
  };
  console.log(JSON.stringify(summary, null, 2));
  process.exit(0);
}

main();
