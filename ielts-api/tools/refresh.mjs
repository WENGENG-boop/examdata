#!/usr/bin/env node
// ielts-api/tools/refresh.mjs
// S14: 受控全量刷新/恢复工具。
//
// 语义：把 current 数据集（normalized revision）中每个任务所引用的 raw 证据
// （PTE 快照 / cam21 HTML / 原书 PDF）固化进 ielts-data 内容寻址存储，
// 并核对听力音频 catalog。全部复用本地文件，绝不发网络请求；
// 证据 hash 与引用不一致（source_changed）时如实记录，绝不静默重取或放宽。
//
// 用法:
//   node ielts-api/tools/refresh.mjs --books 1,3,10,20,21 --variant academic --skills reading,listening --jobs 2 --max-requests 300 --resume
//   node ielts-api/tools/refresh.mjs --books 1-21 --variant general --skills reading,writing,speaking --resume
//
// 选项:
//   --books <list>        册号：逗号/连字符混合，如 "1,3,10,20,21" 或 "1-21"（必填）
//   --variant <v>         academic | general（必填；general 不含 listening）
//   --skills <list>       reading,listening,writing,speaking 子集（必填）
//   --jobs <n>            任务并发 1-8（默认 2）
//   --max-requests <n>    请求预算（默认 200；本工具只复用本地文件，实际网络请求恒为 0）
//   --max-bytes <n>       字节预算（默认 1 GiB；触顶即 checkpoint + 退出 3，不放宽）
//   --resume              跳过 ledger 中已验证且证据 hash 未变的任务（skipped_verified）
//   --dry-run             只检查并输出计划，不写入 raw/二进制存储
//   --data-dir <dir>      数据根（默认 EXAMDATA_IELTS_DATA_DIR 或 <repo>/ielts-data）
//   --json                只输出 summary JSON（stdout）
//   --help                输出本用法
//
// 输出:
//   <data>/refresh/<scope>/ledger.json            跨 run 任务台账（resume 依据）
//   <data>/refresh/<scope>/report-<run_id>.json   本次 run 报告
//   <data>/refresh/<scope>/report-latest.json     最新报告副本
//   <data>/runs/<run_id>/checkpoint.json          运行 checkpoint
//
// 退出码: 0=范围内全部任务 verified/pdf_verified/not_in_book; 1=存在真实缺口;
//         2=参数/配置错误; 3=预算/来源停止（已写 checkpoint）。

import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
import { resolveDataDir, readJson, readCurrent, writeJsonAtomic } from "../data-store.mjs";
import { createFetcher, BudgetExceededError, SourceBlockedError } from "../fetch-source.mjs";
import { webTestOf } from "../resolver.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "..", "..");

const GIB = 1024 * 1024 * 1024;
const SKILLS = ["reading", "listening", "writing", "speaking"];
const RAW_SKILLS = new Set(["reading", "listening"]);
const OK_STATUS = new Set(["verified", "pdf_verified", "not_in_book", "skipped_verified"]);
const PTE_PARSER_VERSION = "pte-s04-2026.10.2";

const USAGE = `usage: node ielts-api/tools/refresh.mjs --books <list> --variant <academic|general> --skills <list> [options]

  --books <list>       册号列表，逗号/连字符混合，如 "1,3,10,20,21" 或 "1-21"（必填）
  --variant <v>        academic | general（必填；general 不含 listening）
  --skills <list>      reading,listening,writing,speaking 子集（必填）
  --jobs <n>           任务并发 1-8（默认 2）
  --max-requests <n>   请求预算（默认 200；本工具只复用本地文件，网络请求恒为 0）
  --max-bytes <n>      字节预算（默认 ${GIB} = 1 GiB）
  --resume             跳过 ledger 中已验证且证据 hash 未变的任务
  --dry-run            只检查并输出计划，不写入 raw/二进制存储
  --data-dir <dir>     数据根（默认 EXAMDATA_IELTS_DATA_DIR 或 <repo>/ielts-data）
  --json               只输出 summary JSON（stdout）

退出码: 0=全部通过; 1=真实缺口; 2=参数/配置错误; 3=预算/来源停止（含 checkpoint）`;

function parseArgs(argv) {
  const opts = { flags: {}, jobs: 2, maxRequests: 200, maxBytes: GIB };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--books") opts.books = argv[++i];
    else if (a === "--variant") opts.variant = argv[++i];
    else if (a === "--skills") opts.skills = argv[++i];
    else if (a === "--jobs") opts.jobs = argv[++i];
    else if (a === "--max-requests") opts.maxRequests = argv[++i];
    else if (a === "--max-bytes") opts.maxBytes = argv[++i];
    else if (a === "--resume") opts.flags.resume = true;
    else if (a === "--dry-run") opts.flags.dryRun = true;
    else if (a === "--data-dir") opts.dataDir = argv[++i];
    else if (a === "--json") opts.flags.json = true;
    else if (a === "--help" || a === "-h") return { help: true };
    else return { error: "unknown arg: " + a };
  }
  return opts;
}

function parseBooks(spec) {
  const out = new Set();
  for (const part of String(spec).split(",")) {
    const t = part.trim();
    if (!t) continue;
    const m = /^(\d+)(?:-(\d+))?$/.exec(t);
    if (!m) return { error: `invalid --books segment: "${t}"` };
    const a = Number(m[1]);
    const b = m[2] ? Number(m[2]) : a;
    if (a < 1 || b > 21 || a > b) return { error: `--books out of range (1-21): "${t}"` };
    for (let i = a; i <= b; i++) out.add(i);
  }
  if (!out.size) return { error: "--books is empty" };
  return { books: [...out].sort((x, y) => x - y) };
}

function parseSkills(spec) {
  const out = [];
  for (const part of String(spec).split(",")) {
    const t = part.trim();
    if (!t) continue;
    if (!SKILLS.includes(t)) return { error: `invalid --skills entry: "${t}" (allowed: ${SKILLS.join(",")})` };
    if (!out.includes(t)) out.push(t);
  }
  if (!out.length) return { error: "--skills is empty" };
  return { skills: out };
}

function parsePositiveInt(v, name) {
  if (v == null || v === true) return { error: `${name} requires a value` };
  const n = Number(v);
  if (!Number.isInteger(n) || n <= 0) return { error: `${name} must be a positive integer` };
  return { value: n };
}

function validate(opts) {
  if (!opts.books) return { error: "--books is required\n" + USAGE };
  if (!opts.variant) return { error: "--variant is required\n" + USAGE };
  if (!opts.skills) return { error: "--skills is required\n" + USAGE };
  if (opts.variant !== "academic" && opts.variant !== "general") return { error: `invalid --variant: ${opts.variant} (academic|general)` };
  const b = parseBooks(opts.books);
  if (b.error) return b;
  const s = parseSkills(opts.skills);
  if (s.error) return s;
  if (opts.variant === "general" && s.skills.includes("listening")) return { error: "general variant has no listening; use --variant academic for listening" };
  const jobs = parsePositiveInt(opts.jobs, "--jobs");
  if (jobs.error) return jobs;
  if (jobs.value > 8) return { error: "--jobs max is 8" };
  const mr = parsePositiveInt(opts.maxRequests, "--max-requests");
  if (mr.error) return mr;
  const mb = parsePositiveInt(opts.maxBytes, "--max-bytes");
  if (mb.error) return mb;
  return { books: b.books, skills: s.skills, jobs: jobs.value, maxRequests: mr.value, maxBytes: mb.value };
}

function rel(p, base) {
  return path.relative(base, p).split(path.sep).join("/");
}

function sha256Stream(filePath) {
  return new Promise((resolve, reject) => {
    const h = crypto.createHash("sha256");
    const s = fs.createReadStream(filePath);
    s.on("data", (d) => h.update(d));
    s.on("end", () => resolve(h.digest("hex")));
    s.on("error", reject);
  });
}

async function pMap(items, limit, fn) {
  const out = new Array(items.length);
  let i = 0;
  const workers = Array.from({ length: Math.max(1, Math.min(limit, items.length)) }, async () => {
    while (i < items.length) {
      const idx = i++;
      out[idx] = await fn(items[idx], idx);
    }
  });
  await Promise.all(workers);
  return out;
}

function nowIso() {
  return new Date().toISOString();
}

function compactTs() {
  return nowIso().replace(/[-:]/g, "").replace(/\.\d+Z$/, "Z");
}

// ---------------------------------------------------------------- 上下文装载

function loadManifest() {
  return readJson(path.join(REPO, "ielts-api", "data", "expected-manifest.json"), { missingOk: false });
}

function loadNormalizedPages(dataDir, revision) {
  const dir = path.join(dataDir, "normalized", "normalized-v1", revision);
  if (!fs.existsSync(dir)) return { error: `normalized revision dir missing: ${dir}` };
  const byKey = new Map();
  for (const name of fs.readdirSync(dir).sort()) {
    if (!/^cambridge-.*\.json$/.test(name)) continue;
    const doc = readJson(path.join(dir, name), { missingOk: true });
    if (!doc || !Array.isArray(doc.pages)) continue;
    for (const p of doc.pages) {
      const key = `${doc.book}|${String(p.test)}|${p.skill}`;
      if (!byKey.has(key)) byKey.set(key, []);
      byKey.get(key).push({ ...p, doc_book: doc.book });
    }
  }
  return { byKey, dir };
}

function loadAudioCatalog(dataDir) {
  const runsDir = path.join(dataDir, "runs");
  if (!fs.existsSync(runsDir)) return { records: null, path: null };
  for (const d of fs.readdirSync(runsDir).sort().reverse()) {
    const p = path.join(runsDir, d, "audio", "audio-catalog.json");
    if (fs.existsSync(p)) {
      const cat = readJson(p, { missingOk: true });
      if (cat && Array.isArray(cat.records)) {
        const byIdentity = new Map();
        for (const r of cat.records) if (r.scope === "part" && r.identity) byIdentity.set(r.identity, r);
        return { records: byIdentity, path: p, run: d };
      }
    }
  }
  return { records: null, path: null };
}

// ---------------------------------------------------------------- 任务枚举

function groupTests(items, skill, mvariant) {
  const s = new Set();
  for (const it of items) if (it.skill === skill && it.variant === mvariant) s.add(String(it.test));
  return [...s].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
}

function buildTasks(manifest, books, variant, skills) {
  const tasks = [];
  const mvOf = (skill) => (skill === "listening" || skill === "speaking" ? "shared" : variant);
  for (const book of books) {
    const b = manifest.books.find((x) => x.book === book);
    if (!b) {
      tasks.push({ key: `cambridge:${book}:${variant}:manifest:book`, book, variant, skill: null, test: null, kind: "manifest_missing", reason: "book not in expected-manifest" });
      continue;
    }
    for (const skill of skills) {
      const mvariant = mvOf(skill);
      if (RAW_SKILLS.has(skill) && variant === "academic") {
        const tests = groupTests(b.items, skill, mvariant);
        if (!tests.length) {
          tasks.push({ key: `cambridge:${book}:${variant}:${skill}:none`, book, variant, skill, test: null, kind: "raw", reason: "no manifest items" });
        }
        for (const test of tests) {
          tasks.push({ key: `cambridge:${book}:${variant}:${skill}:${test}`, book, variant, skill, test, kind: "raw" });
        }
        continue;
      }
      if (variant === "general" && (skill === "reading" || skill === "writing")) {
        const g = b.general || {};
        const tests = Array.isArray(g.tests) ? g.tests : [];
        if (!tests.length) {
          const status = g.status === "not_in_book" ? "not_in_book" : "unverified";
          tasks.push({ key: `cambridge:${book}:${variant}:${skill}:gt-status`, book, variant, skill, test: null, kind: "gt_placeholder", gt_status: status, reason: g.reason || g.status || "general status unknown", note: b.note || null });
        } else {
          for (const test of tests) {
            tasks.push({ key: `cambridge:${book}:${variant}:${skill}:${test}`, book, variant, skill, test, kind: "pdf" });
          }
        }
        continue;
      }
      // academic writing / speaking（shared）等 pdf 任务
      const tests = groupTests(b.items, skill, mvariant);
      if (!tests.length) {
        tasks.push({ key: `cambridge:${book}:${variant}:${skill}:none`, book, variant, skill, test: null, kind: "pdf", reason: "no manifest items" });
      }
      for (const test of tests) {
        tasks.push({ key: `cambridge:${book}:${variant}:${skill}:${test}`, book, variant, skill, test, kind: "pdf" });
      }
    }
  }
  return tasks;
}

// ---------------------------------------------------------------- 证据检查

function makeRawCheck(ctx) {
  const { dataDir, opts, fetcher, pagesByKey, audioByIdentity, warnings } = ctx;
  return async function processRawTask(task) {
    const evidence = [];
    let audio = null;
    if (!task.test) return { status: "source_missing", reason: task.reason || "no test enumerable", evidence };
    const pages = pagesByKey.get(`${task.book}|${task.test}|${task.skill}`) || [];
    if (!pages.length) return { status: "source_missing", reason: "no normalized page cites this task", evidence };
    let anyHashMismatch = false;
    let anyMissing = false;
    for (const page of pages) {
      const rec = { page_ref: page.page_ref, kind: page.kind, raw_file: page.raw_file, expected_sha256: page.source_sha256 || null };
      if (!page.raw_file || !page.source_sha256) {
        rec.status = "unverifiable";
        anyMissing = true;
        evidence.push(rec);
        continue;
      }
      const fileAbs = path.join(REPO, ...String(page.raw_file).split("/"));
      if (!fs.existsSync(fileAbs)) {
        rec.status = "file_missing";
        anyMissing = true;
        evidence.push(rec);
        continue;
      }
      const sha = await sha256Stream(fileAbs);
      rec.actual_sha256 = sha;
      if (sha !== page.source_sha256) {
        rec.status = "hash_mismatch";
        anyHashMismatch = true;
        evidence.push(rec);
        continue;
      }
      if (page.kind === "pdf-extract") {
        const storePath = path.join(dataDir, "pdf", sha + ".pdf");
        if (fs.existsSync(storePath)) rec.status = "cached";
        else if (opts.flags.dryRun) rec.status = "would_import";
        else {
          const r = fetcher.reuseLocalBinary({ kind: "pdf", ext: "pdf", filePath: fileAbs });
          rec.status = r.deduped ? "cached" : "imported_local";
          rec.stored_path = rel(r.path, dataDir);
        }
        rec.store = "pdf";
      } else {
        const source = page.kind === "cam21-html" ? "cam21" : "practicepteonline";
        rec.source = source;
        const found = fetcher.findRaw({ source, sha256: sha });
        if (found) rec.status = "cached";
        else if (opts.flags.dryRun) rec.status = "would_import";
        else {
          const r = fetcher.reuseLocalRaw({
            source,
            filePath: fileAbs,
            parserVersion: page.kind === "pte-raw" ? PTE_PARSER_VERSION : null,
            url: page.url || null,
            meta: {
              kind: page.kind,
              book: page.book,
              test: page.test,
              variant: page.variant,
              skill: page.skill,
              raw_index: page.raw_index ?? null,
              source_page_id: page.source_page_id ?? null,
              slug: page.slug ?? null,
              note: "refresh_local_reuse",
            },
          });
          rec.status = r.deduped ? "cached" : "imported_local";
          rec.stored_sha256 = r.sha256;
        }
      }
      evidence.push(rec);
    }
    if (task.skill === "listening") {
      audio = { parts: [] };
      const testWeb = webTestOf(task.book, task.test);
      for (let k = 1; k <= 4; k++) {
        const identity = `cambridge:${task.book}:shared:listening:${testWeb}:P${k}`;
        const rec = audioByIdentity ? audioByIdentity.get(identity) : null;
        const pr = { part: k, identity, status: "missing" };
        if (!rec) pr.status = "catalog_missing";
        else if (rec.status !== "available" && rec.status !== "verified") pr.status = "catalog_" + rec.status;
        else if (!rec.file_path || !fs.existsSync(rec.file_path)) pr.status = "file_missing";
        else {
          const st = fs.statSync(rec.file_path);
          if (rec.bytes != null && st.size !== rec.bytes) pr.status = "size_mismatch";
          else pr.status = "ok";
          pr.file_path = rel(rec.file_path, dataDir);
          pr.content_sha256 = rec.content_sha256 || null;
          pr.bytes = st.size;
          pr.catalog_status = rec.status;
        }
        if (pr.status !== "ok") anyMissing = true;
        audio.parts.push(pr);
      }
    }
    let status = "verified";
    if (anyHashMismatch) status = "source_changed";
    else if (anyMissing) status = "partial";
    return { status, evidence, audio };
  };
}

function makePdfCheck(ctx) {
  const { manifest, dataDir, opts, fetcher } = ctx;
  const memo = new Map();
  return function pdfCheckForBook(book) {
    if (memo.has(book)) return memo.get(book);
    const p = (async () => {
      const b = manifest.books.find((x) => x.book === book);
      if (!b) return { status: "manifest_missing", reason: "book not in expected-manifest" };
      if (!b.pdf) return { status: "pdf_missing", reason: "manifest has no local PDF", note: b.note || null };
      const fileAbs = path.join(REPO, ...String(b.pdf.relpath).split("/"));
      if (!fs.existsSync(fileAbs)) return { status: "pdf_missing", reason: "file not found: " + b.pdf.relpath };
      const sha = await sha256Stream(fileAbs);
      if (sha !== b.pdf.sha256) return { status: "pdf_hash_mismatch", expected: b.pdf.sha256, actual: sha, file: b.pdf.relpath };
      if (b.text_layer !== true) {
        return { status: "pdf_no_text_layer", sha256: sha, file: b.pdf.relpath, pages: b.pdf.pages, reason: b.note || "pdf text layer unavailable", note: b.note || null };
      }
      let store = "cached";
      if (!opts.flags.dryRun) {
        const r = fetcher.reuseLocalBinary({ kind: "pdf", ext: "pdf", filePath: fileAbs });
        store = r.deduped ? "cached" : "imported_local";
      } else {
        store = fs.existsSync(path.join(dataDir, "pdf", sha + ".pdf")) ? "cached" : "would_import";
      }
      return { status: "pdf_verified", sha256: sha, file: b.pdf.relpath, pages: b.pdf.pages, store, note: b.note || null };
    })();
    memo.set(book, p);
    return p;
  };
}

// ---------------------------------------------------------------- ledger / report

function ledgerPath(dataDir, scope) {
  return path.join(dataDir, "refresh", scope, "ledger.json");
}

function loadLedger(dataDir, scope) {
  const p = ledgerPath(dataDir, scope);
  const doc = readJson(p, { missingOk: true });
  if (!doc || !doc.tasks) return { schema: "ielts.refresh-ledger/1", scope, tasks: {} };
  return doc;
}

function evidenceKeyOf(task, result) {
  const shas = [];
  if (result.evidence) {
    for (const e of result.evidence) {
      const s = e.actual_sha256 || e.expected_sha256 || e.stored_sha256;
      if (s) shas.push(s);
    }
  }
  if (result.audio && result.audio.parts) {
    for (const p of result.audio.parts) if (p.content_sha256) shas.push(p.content_sha256);
  }
  if (result.sha256) shas.push(result.sha256);
  return [...new Set(shas)].sort();
}

// ---------------------------------------------------------------- main

async function main() {
  const argv = process.argv.slice(2);
  const opts = parseArgs(argv);
  if (opts.help) {
    console.log(USAGE);
    process.exit(0);
  }
  if (opts.error) {
    console.error(opts.error);
    process.exit(2);
  }
  if (!argv.length) {
    console.error(USAGE);
    process.exit(2);
  }
  const v = validate(opts);
  if (v.error) {
    console.error(v.error);
    process.exit(2);
  }
  const { books, skills, jobs, maxRequests, maxBytes } = v;
  const variant = opts.variant;
  const dataDir = resolveDataDir(opts.dataDir);
  const scope = `${variant}-${skills.join("+")}`;
  const startedAt = nowIso();
  const runId = `refresh-${scope.replace(/\+/g, "-")}-${compactTs()}`;

  const warnings = [];

  const manifest = loadManifest();
  if (!manifest || !Array.isArray(manifest.books)) {
    console.error("expected-manifest.json missing or invalid (run tools/build-manifest.mjs)");
    process.exit(2);
  }
  const idxPtr = readCurrent({ root: dataDir, kind: "indexes" });
  if (!idxPtr || !idxPtr.dataset_revision) {
    console.error(`no current dataset pointer under ${dataDir}/indexes (run tools/build-index.mjs first)`);
    process.exit(2);
  }
  const revision = idxPtr.dataset_revision;
  const pagesRes = loadNormalizedPages(dataDir, revision);
  if (pagesRes.error) {
    console.error(pagesRes.error);
    process.exit(2);
  }
  const audio = loadAudioCatalog(dataDir);
  if (!audio.records) warnings.push("audio catalog not found; listening tasks will be partial");

  const fetcher = createFetcher({
    root: dataDir,
    runId,
    limits: { concurrency: jobs, maxRequests, maxBytes, maxBytesPerRequest: 512 * 1024 * 1024 },
    resume: false,
  });

  const tasks = buildTasks(manifest, books, variant, skills);
  const ledger = loadLedger(dataDir, scope);
  const ctx = { dataDir, opts, fetcher, manifest, pagesByKey: pagesRes.byKey, audioByIdentity: audio.records, warnings };
  const processRawTask = makeRawCheck(ctx);
  const pdfCheckForBook = makePdfCheck(ctx);

  const importedRaw = new Set();
  const cachedRaw = new Set();
  const importedBinary = new Set();
  const cachedBinary = new Set();
  let skippedVerified = 0;

  const results = await pMap(tasks, jobs, async (task) => {
    let result;
    try {
      if (task.kind === "manifest_missing") {
        result = { status: "manifest_missing", reason: task.reason };
      } else if (task.kind === "gt_placeholder") {
        result = { status: task.gt_status, reason: task.reason, note: task.note || null };
      } else if (task.kind === "raw") {
        result = await processRawTask(task);
      } else if (task.kind === "pdf") {
        const pdf = await pdfCheckForBook(task.book);
        result = { ...pdf };
      } else {
        result = { status: "error", reason: `unknown task kind: ${task.kind}` };
      }
    } catch (e) {
      if (e instanceof BudgetExceededError || e instanceof SourceBlockedError) throw e;
      result = { status: "error", reason: String((e && e.message) || e) };
    }
    const evidenceKey = evidenceKeyOf(task, result);
    const prev = ledger.tasks[task.key];
    const canSkip = opts.flags.resume && !opts.flags.dryRun && prev && OK_STATUS.has(prev.status) && JSON.stringify(prev.evidence_sha256s || []) === JSON.stringify(evidenceKey);
    if (canSkip) {
      skippedVerified++;
      result = { ...result, status: "skipped_verified", previous_status: prev.status, previous_checked_at: prev.checked_at || null };
    }
    if (!opts.flags.dryRun) {
      if (result.evidence) {
        for (const e of result.evidence) {
          const sha = e.actual_sha256 || e.stored_sha256 || e.expected_sha256 || e.raw_file;
          if (e.status === "imported_local" && e.store === "pdf") importedBinary.add(sha);
          else if (e.status === "imported_local") importedRaw.add(sha);
          else if (e.status === "cached" && e.store === "pdf") cachedBinary.add(sha);
          else if (e.status === "cached") cachedRaw.add(sha);
        }
      }
      if (result.status === "pdf_verified") {
        const sha = result.sha256 || task.key;
        if (result.store === "imported_local") importedBinary.add(sha);
        else if (result.store === "cached") cachedBinary.add(sha);
      }
      ledger.tasks[task.key] = {
        status: result.status,
        kind: task.kind,
        book: task.book,
        variant: task.variant,
        skill: task.skill,
        test: task.test,
        source_kind: result.evidence ? (task.kind === "raw" ? "raw" : null) : task.kind === "pdf" ? "pdf" : task.kind,
        evidence_sha256s: evidenceKey,
        checked_at: nowIso(),
      };
    }
    return { ...task, result, evidence_key: evidenceKey };
  }).catch(async (e) => {
    if (e instanceof BudgetExceededError || e instanceof SourceBlockedError) {
      fetcher.saveCheckpoint({ summary: { scope, run_id: runId, stopped: e.kind || "source_blocked", message: String(e.message || e) } });
      console.error(`refresh stopped (${e.kind || "source_blocked"}): ${String(e.message || e)}`);
      console.error(`checkpoint: ${rel(path.join(dataDir, "runs", runId, "checkpoint.json"), dataDir)}`);
      process.exit(3);
    }
    throw e;
  });

  const finishedAt = nowIso();
  const imports = {
    raw_imported: importedRaw.size,
    raw_cached: [...cachedRaw].filter((s) => !importedRaw.has(s)).length,
    binary_imported: importedBinary.size,
    binary_cached: [...cachedBinary].filter((s) => !importedBinary.has(s)).length,
  };
  const counts = {};
  for (const r of results) counts[r.result.status] = (counts[r.result.status] || 0) + 1;
  const gaps = results
    .filter((r) => !OK_STATUS.has(r.result.status))
    .map((r) => ({ key: r.key, book: r.book, skill: r.skill, test: r.test, status: r.result.status, reason: r.result.reason || null }));

  ledger.updated_at = finishedAt;
  if (!opts.flags.dryRun) {
    const lp = ledgerPath(dataDir, scope);
    writeJsonAtomic(lp, ledger);
  }

  const report = {
    schema: "ielts.refresh-report/1",
    run_id: runId,
    scope,
    command: "node " + path.join("ielts-api", "tools", "refresh.mjs") + " " + argv.join(" "),
    data_dir: dataDir,
    dataset_revision: revision,
    started_at: startedAt,
    finished_at: finishedAt,
    dry_run: Boolean(opts.flags.dryRun),
    network_requests: fetcher.budgetStatus().requests,
    tasks_total: results.length,
    counts,
    skipped_verified: skippedVerified,
    imports,
    gaps,
    warnings,
    audio_catalog: audio.path ? rel(audio.path, dataDir) : null,
    tasks: results.map((r) => ({
      key: r.key,
      book: r.book,
      variant: r.variant,
      skill: r.skill,
      test: r.test,
      kind: r.kind,
      status: r.result.status,
      reason: r.result.reason || null,
      note: r.result.note || null,
      evidence: r.result.evidence || null,
      audio: r.result.audio || null,
      pdf: r.result.status && String(r.result.status).startsWith("pdf_") ? { sha256: r.result.sha256 || null, file: r.result.file || null, store: r.result.store || null, pages: r.result.pages || null } : null,
    })),
    budget: fetcher.budgetStatus(),
    checkpoint: rel(path.join(dataDir, "runs", runId, "checkpoint.json"), dataDir),
  };

  const outDir = path.join(dataDir, "refresh", scope);
  if (!opts.flags.dryRun) {
    fs.mkdirSync(outDir, { recursive: true });
    writeJsonAtomic(path.join(outDir, `report-${runId}.json`), report);
    writeJsonAtomic(path.join(outDir, "report-latest.json"), report);
    fetcher.saveCheckpoint({ summary: { scope, run_id: runId, counts, gaps: gaps.length } });
  }

  const summary = {
    run_id: runId,
    scope,
    dataset_revision: revision,
    tasks_total: results.length,
    counts,
    skipped_verified: skippedVerified,
    imports,
    gaps: gaps.length,
    network_requests: report.network_requests,
    report: opts.flags.dryRun ? null : rel(path.join(outDir, `report-${runId}.json`), dataDir),
    checkpoint: report.checkpoint,
  };

  if (opts.flags.json) {
    console.log(JSON.stringify(summary, null, 2));
  } else {
    console.log(`refresh scope=${scope} run=${runId}`);
    console.log(`  revision=${revision} books=${books.join(",")} skills=${skills.join("+")} jobs=${jobs}`);
    console.log(`  tasks=${results.length} ` + Object.entries(counts).map(([k, n]) => `${k}=${n}`).join(" "));
    if (skippedVerified) console.log(`  skipped_verified=${skippedVerified}`);
    console.log(`  imports: raw_imported=${imports.raw_imported} raw_cached=${imports.raw_cached} binary_imported=${imports.binary_imported} binary_cached=${imports.binary_cached}`);
    if (gaps.length) {
      console.log(`  gaps (${gaps.length}):`);
      for (const g of gaps.slice(0, 40)) console.log(`    - ${g.key} [${g.status}] ${g.reason || ""}`);
      if (gaps.length > 40) console.log(`    ... and ${gaps.length - 40} more (see report)`);
    }
    if (!opts.flags.dryRun) console.log(`  report: ${summary.report}`);
    console.log(`  checkpoint: ${summary.checkpoint}`);
  }
  process.exit(gaps.length ? 1 : 0);
}

main().catch((e) => {
  console.error("refresh failed:", String((e && e.stack) || e));
  process.exit(2);
});
