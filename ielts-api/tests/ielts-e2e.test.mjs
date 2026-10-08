// ielts-api/tests/ielts-e2e.test.mjs
// S15 end-to-end acceptance battery for the A01–A16 repair contract (22 cases).
//
// Every child process is spawned with tests/stub-fetch.cjs preloaded through
// NODE_OPTIONS so any stray fetch() fails loudly; STUB_FETCH_LOG records the
// call count for cases that assert "zero network". Scratch fixtures live under
// ielts-data/test-s15/e2e/ and are rebuilt by the tests themselves. Tests run
// serially in declaration order; cases 5 and 7 share the `cycle` fixture
// (case 5 builds it, case 7 drives the refresh lifecycle on it).
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { spawnSync, spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

import { currentOrStale } from "../data-store.mjs";
import { parsePtePage } from "../pte.mjs";
import { compareAnswers } from "../answer-matcher.mjs";
import { detectTimestampUnit, validateClock, estimateOffset, applyOffset } from "../audio-matcher.mjs";
import { applyAdjudications } from "../adjudications.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "..", "..");
const CLI = path.join(REPO, "ielts-api", "ielts-cli.mjs");
const REFRESH = path.join(REPO, "ielts-api", "tools", "refresh.mjs");
const AUDIT = path.join(REPO, "ielts-api", "tools", "audit-all.mjs");
const STUB = path.join(HERE, "stub-fetch.cjs");
const DATA = path.join(REPO, "ielts-data");
const SCRATCH = path.join(DATA, "test-s15", "e2e");

const RAW_V1 = "hello-s15-raw-v1\n";
const RAW_V2 = "hello-s15-raw-v2-CHANGED\n";
const sha256 = (s) => crypto.createHash("sha256").update(s).digest("hex");

const rmrf = (p) => fs.rmSync(p, { recursive: true, force: true });
const mkdirp = (p) => fs.mkdirSync(p, { recursive: true });
const readJson = (p) => JSON.parse(fs.readFileSync(p, "utf8"));
const writeJson = (p, obj) => {
  mkdirp(path.dirname(p));
  fs.writeFileSync(p, JSON.stringify(obj, null, 2));
};

rmrf(SCRATCH);
mkdirp(SCRATCH);

const STUB_REQUIRE = STUB.replace(/\\/g, "/");

function baseEnv(dataDir, extra = {}) {
  const env = { ...process.env };
  delete env.STUB_FETCH_LOG;
  delete env.EXAMDATA_IELTS_DATA_DIR;
  env.NODE_OPTIONS = `--require ${STUB_REQUIRE}`;
  env.STUB_FETCH_MODE = "throw";
  if (dataDir) env.EXAMDATA_IELTS_DATA_DIR = dataDir;
  return { ...env, ...extra };
}

const MAX_BUFFER = 64 * 1024 * 1024; // coverage-v2 on an empty dir alone is ~1.1 MB

function runCli(args, { dataDir = DATA, env = {} } = {}) {
  return spawnSync(process.execPath, [CLI, ...args], {
    cwd: path.join(REPO, "ielts-api"),
    env: baseEnv(dataDir, env),
    encoding: "utf8",
    timeout: 180000,
    maxBuffer: MAX_BUFFER,
  });
}

function runRefresh(args, { dataDir, env = {} } = {}) {
  const argv = [...args];
  if (dataDir && !argv.includes("--data-dir")) argv.push("--data-dir", dataDir);
  return spawnSync(process.execPath, [REFRESH, ...argv], {
    cwd: REPO,
    env: baseEnv(null, env),
    encoding: "utf8",
    timeout: 180000,
    maxBuffer: MAX_BUFFER,
  });
}

function spawnRefresh(args, { dataDir, env = {} } = {}) {
  const argv = [...args, "--data-dir", dataDir];
  const child = spawn(process.execPath, [REFRESH, ...argv], {
    cwd: REPO,
    env: baseEnv(null, env),
    stdio: ["ignore", "pipe", "pipe"],
  });
  let stdout = "";
  let stderr = "";
  child.stdout.on("data", (d) => (stdout += d));
  child.stderr.on("data", (d) => (stderr += d));
  const done = new Promise((resolve) => child.on("close", (code, signal) => resolve({ code, signal, stdout, stderr })));
  return { child, done };
}

function parseJsonOut(r, label) {
  try {
    return JSON.parse(r.stdout);
  } catch (e) {
    assert.fail(`${label}: stdout is not valid JSON (${e.message})\nstdout: ${String(r.stdout).slice(0, 400)}\nstderr: ${String(r.stderr).slice(0, 400)}`);
  }
}

/** Isolated refresh scratch: current pointer + one normalized page per book. */
function buildCycle(root, { books = [10], rawText = RAW_V1 } = {}) {
  rmrf(root);
  const rev = "rev-test-s15";
  writeJson(path.join(root, "indexes", "current"), { dataset_revision: rev, published_at: "2026-10-05T00:00:00.000Z" });
  for (const b of books) {
    const rawPath = path.join(root, "raw", `t${b}.txt`);
    mkdirp(path.dirname(rawPath));
    fs.writeFileSync(rawPath, rawText);
    const rawRel = path.relative(REPO, rawPath).split(path.sep).join("/");
    writeJson(path.join(root, "normalized", "normalized-v1", rev, `cambridge-${b}.json`), {
      book: b,
      pages: [
        {
          test: 1,
          skill: "reading",
          page_ref: `test-s15-page-${b}`,
          kind: "pte-raw",
          raw_file: rawRel,
          source_sha256: sha256(rawText),
        },
      ],
    });
  }
}

const CYCLE = path.join(SCRATCH, "cycle");
const REFRESH_ARGS = ["--books", "10", "--variant", "academic", "--skills", "reading", "--jobs", "1", "--resume", "--json"];

/* ------------------------------------------------------------------ 1 */

test("case 1: empty data dir → coverage-v2 ok/run_id null, questions-v2 ok/count 0, refresh exit 2", () => {
  const dir = path.join(SCRATCH, "empty");
  rmrf(dir);
  mkdirp(dir);

  const cov = runCli(["coverage-v2"], { dataDir: dir });
  assert.equal(cov.status, 0, cov.stderr);
  const covJ = parseJsonOut(cov, "coverage-v2 empty");
  assert.equal(covJ.ok, true);
  assert.equal(covJ.run_id, null);

  const q = runCli(["questions-v2", "10", "1"], { dataDir: dir });
  assert.equal(q.status, 0, q.stderr);
  const qJ = parseJsonOut(q, "questions-v2 empty");
  assert.equal(qJ.ok, true);
  assert.equal(qJ.count, 0);

  const ref = runRefresh(["--books", "10", "--variant", "academic", "--skills", "reading", "--jobs", "1"], { dataDir: dir });
  assert.equal(ref.status, 2, `stderr: ${ref.stderr}`);
  assert.match(ref.stderr, /no current dataset pointer/);
});

/* ------------------------------------------------------------------ 2 */

test("case 2: cached refresh dry-run on real data → exit 0, zero network, real ledger present", () => {
  const r = runRefresh(["--books", "10", "--variant", "academic", "--skills", "reading", "--jobs", "1", "--dry-run", "--json"], { dataDir: DATA });
  assert.equal(r.status, 0, r.stderr);
  const j = parseJsonOut(r, "refresh dry-run");
  assert.equal(j.network_requests, 0);
  assert.equal(j.gaps, 0);
  assert.equal(j.counts.verified, 4);
  const ptr = readJson(path.join(DATA, "indexes", "current"));
  assert.equal(j.dataset_revision, ptr.dataset_revision);

  const ledgerPath = path.join(DATA, "refresh", "academic-reading+listening", "ledger.json");
  assert.ok(fs.existsSync(ledgerPath), "real refresh ledger missing: " + ledgerPath);
  const ledger = readJson(ledgerPath);
  const statuses = Object.values(ledger.tasks || {}).map((t) => t.status);
  assert.ok(statuses.length >= 1, "real ledger has no tasks");
  assert.ok(
    statuses.some((s) => s === "verified" || s === "skipped_verified"),
    "real ledger has no verified/skipped_verified task"
  );
});

/* ------------------------------------------------------------------ 3 */

test("case 3: corrupt current pointer → refresh exit 2 with 'refresh failed'", () => {
  const dir = path.join(SCRATCH, "badcache");
  rmrf(dir);
  mkdirp(path.join(dir, "indexes"));
  fs.writeFileSync(path.join(dir, "indexes", "current"), "{ not json");
  const r = runRefresh(["--books", "10", "--variant", "academic", "--skills", "reading", "--jobs", "1"], { dataDir: dir });
  assert.equal(r.status, 2);
  assert.match(r.stderr, /refresh failed/);
});

/* ------------------------------------------------------------------ 4 */

test("case 4: refresh never touches the network (fetch stub logs 0 calls)", () => {
  const log = path.join(SCRATCH, "case4-stub.json");
  rmrf(log);
  const r = runRefresh(["--books", "10", "--variant", "academic", "--skills", "reading", "--jobs", "1", "--dry-run", "--json"], {
    dataDir: DATA,
    env: { STUB_FETCH_LOG: log },
  });
  assert.equal(r.status, 0, r.stderr);
  assert.equal(readJson(log).count, 0);
});

/* ------------------------------------------------------------------ 5 */

test("case 5: currentOrStale — none → ok:false/stale; present → ok; refreshError → stale with revision kept", () => {
  const empty = path.join(SCRATCH, "empty");
  rmrf(empty);
  mkdirp(empty);
  const a = currentOrStale({ root: empty, kind: "indexes" });
  assert.equal(a.ok, false);
  assert.equal(a.stale, true);
  assert.equal(a.dataset_revision, null);

  buildCycle(CYCLE);
  const b = currentOrStale({ root: CYCLE, kind: "indexes" });
  assert.equal(b.ok, true);
  assert.equal(b.dataset_revision, "rev-test-s15");
  assert.equal(b.stale, false);

  const c = currentOrStale({ root: CYCLE, kind: "indexes", refreshError: "synthetic failure" });
  assert.equal(c.ok, true);
  assert.equal(c.stale, true);
  assert.equal(c.dataset_revision, "rev-test-s15");
  assert.equal(c.error, "synthetic failure");
});

/* ------------------------------------------------------------------ 7 (declared before 6 on purpose: shares CYCLE with case 5) */

test("case 7: refresh resume lifecycle — import → skip → source_changed → re-verify", () => {
  const rawPath = path.join(CYCLE, "raw", "t10.txt");

  const r1 = runRefresh(REFRESH_ARGS, { dataDir: CYCLE });
  assert.equal(r1.status, 1, r1.stderr);
  const j1 = parseJsonOut(r1, "cycle run1");
  assert.equal(j1.counts.verified, 1);
  assert.equal(j1.imports.raw_imported, 1);
  assert.equal(j1.gaps, 3);
  assert.equal(j1.network_requests, 0);

  const r2 = runRefresh(REFRESH_ARGS, { dataDir: CYCLE });
  assert.equal(r2.status, 1, r2.stderr);
  const j2 = parseJsonOut(r2, "cycle run2");
  assert.equal(j2.counts.skipped_verified, 1);

  fs.writeFileSync(rawPath, RAW_V2);
  const r3 = runRefresh(REFRESH_ARGS, { dataDir: CYCLE });
  assert.equal(r3.status, 1, r3.stderr);
  const j3 = parseJsonOut(r3, "cycle run3");
  assert.equal(j3.counts.source_changed, 1);

  fs.writeFileSync(rawPath, RAW_V1);
  const r4 = runRefresh(REFRESH_ARGS, { dataDir: CYCLE });
  assert.equal(r4.status, 1, r4.stderr);
  const j4 = parseJsonOut(r4, "cycle run4");
  assert.equal(j4.counts.verified, 1);
});

/* ------------------------------------------------------------------ 6 */

test("case 6: two concurrent resume refreshes — both complete, ledger stays valid JSON", async () => {
  const dir = path.join(SCRATCH, "cycle-conc");
  buildCycle(dir);

  const seed = runRefresh(REFRESH_ARGS, { dataDir: dir });
  assert.equal(seed.status, 1, seed.stderr);
  assert.equal(parseJsonOut(seed, "conc seed").counts.verified, 1);

  const a = spawnRefresh(REFRESH_ARGS, { dataDir: dir });
  const b = spawnRefresh(REFRESH_ARGS, { dataDir: dir });
  const [ra, rb] = await Promise.all([a.done, b.done]);
  for (const [name, r] of [["a", ra], ["b", rb]]) {
    assert.equal(r.code, 1, `${name} exit code; stderr: ${r.stderr}`);
    const j = JSON.parse(r.stdout);
    assert.equal(j.counts.skipped_verified, 1, `${name} skipped_verified`);
  }

  const ledger = readJson(path.join(dir, "refresh", "academic-reading", "ledger.json"));
  assert.equal(Object.keys(ledger.tasks).length, 4);
  assert.equal(ledger.tasks["cambridge:10:academic:reading:1"].status, "skipped_verified");
});

/* ------------------------------------------------------------------ 8 */

test("case 8: Cambridge 1 Test 2 listening keeps 41 questions", () => {
  const r = runCli(["questions-v2", "1", "2", "--skill=listening"], { dataDir: DATA });
  assert.equal(r.status, 0, r.stderr);
  const j = parseJsonOut(r, "questions-v2 1 2");
  assert.equal(j.ok, true);
  assert.equal(j.count, 41);
  assert.equal(j.questions.length, 41);
  const nums = j.questions.map((q) => q.number);
  assert.equal(new Set(nums).size, 41);
  assert.equal(Math.max(...nums), 41);
});

/* ------------------------------------------------------------------ 9 */

test("case 9: Cambridge 10 Test 1 reading Q34 stays numbered-empty (no shifting)", () => {
  const empty = runCli(["questions-v2", "10", "1", "--skill=reading", "--status=empty"], { dataDir: DATA });
  assert.equal(empty.status, 0, empty.stderr);
  const ej = parseJsonOut(empty, "questions-v2 status=empty");
  assert.equal(ej.count, 1);
  assert.equal(ej.questions[0].question_id, "q-10-1-reading-academic-34");
  assert.equal(ej.questions[0].answer.status, "empty");

  const full = runCli(["questions-v2", "10", "1", "--skill=reading"], { dataDir: DATA });
  assert.equal(full.status, 0, full.stderr);
  const fj = parseJsonOut(full, "questions-v2 full reading");
  const nums = fj.questions.map((q) => q.number);
  assert.equal(nums.length, 40);
  assert.equal(new Set(nums).size, 40);
  assert.ok(nums.includes(34));
  const q34 = fj.questions.find((q) => q.number === 34);
  assert.equal(q34.answer.status, "empty");
});

/* ------------------------------------------------------------------ 10 */

test("case 10: pte parser — empty middle/tail LI stay positional and null", () => {
  const html = `<!doctype html><html><head><meta charset="utf-8"></head><body><div id="bg-showmore-hidden-1"><ol start="11"><li>eleven</li><li></li><li value="15">fifteen</li><li></li></ol></div></body></html>`;
  const out = parsePtePage(html, { book: 1, test: 1, skill: "listening" }, { numbers: [11, 12, 15, 16], max: 16, expected_total: 4, status: "fixture", source: "fixture" });
  assert.equal(out.ok, true);
  assert.deepEqual(out.answer_slots.map((s) => s.number), [11, 12, 15, 16]);
  assert.deepEqual(out.answer_slots.map((s) => s.raw), ["eleven", "", "fifteen", ""]);
  assert.equal(out.counts.empty_slots, 2);
  assert.deepEqual(out.answer_missing_detail, [{ number: 12, reason: "empty" }, { number: 16, reason: "empty" }]);
});

/* ------------------------------------------------------------------ 11 */

test("case 11: Cambridge 3 Tests 2–4 listening pages all parse to 40 questions", () => {
  for (const t of [2, 3, 4]) {
    const r = runCli(["questions-v2", "3", String(t), "--skill=listening"], { dataDir: DATA });
    assert.equal(r.status, 0, r.stderr);
    const j = parseJsonOut(r, `questions-v2 3 ${t}`);
    assert.equal(j.ok, true);
    assert.equal(j.count, 40, `book 3 test ${t}`);
  }
});

/* ------------------------------------------------------------------ 12 */

test("case 12: Cambridge 21 listening P3 multiple-choice groups carry accepted sets", () => {
  const r = runCli(["questions-v2", "21", "1", "--skill=listening", "--part=P3"], { dataDir: DATA });
  assert.equal(r.status, 0, r.stderr);
  const j = parseJsonOut(r, "questions-v2 21 1 P3");
  assert.equal(j.count, 10);
  const byNum = new Map(j.questions.map((q) => [q.number, q]));
  for (const n of [21, 22]) {
    const q = byNum.get(n);
    assert.equal(q.type, "multiple_choice_multiple", `Q${n} type`);
    assert.deepEqual(q.answer.accept, ["B", "D"], `Q${n} accept`);
    assert.equal(q.answer.group_ref, "cambridge:21:shared:listening:1:P3:G0");
  }
  for (const n of [23, 24]) {
    const q = byNum.get(n);
    assert.equal(q.type, "multiple_choice_multiple", `Q${n} type`);
    assert.deepEqual(q.answer.accept, ["C", "E"], `Q${n} accept`);
    assert.equal(q.answer.group_ref, "cambridge:21:shared:listening:1:P3:G1");
  }
  assert.deepEqual(byNum.get(21).options.map((o) => o.label), ["A", "B", "C", "D", "E"]);
});

/* ------------------------------------------------------------------ 13 */

test("case 13: asset-v2 resolves a real sha / rejects unknown; missing_asset question is incomplete", () => {
  const assetDir = path.join(DATA, "assets");
  const first = fs.readdirSync(assetDir).filter((f) => fs.statSync(path.join(assetDir, f)).isFile()).sort()[0];
  assert.ok(first, "no asset files under ielts-data/assets/");
  const realSha = first.replace(/\.[^.]+$/, "");

  const r1 = runCli(["asset-v2", realSha], { dataDir: DATA });
  assert.equal(r1.status, 0, r1.stderr);
  const j1 = parseJsonOut(r1, "asset-v2 real");
  assert.equal(j1.ok, true);
  assert.equal(j1.kind, "image");
  assert.equal(j1.exists, true);
  assert.equal(j1.sha256, realSha);
  assert.ok(fs.existsSync(j1.file_path));

  const fake = "deadbeef".repeat(8);
  const r2 = runCli(["asset-v2", fake], { dataDir: DATA });
  assert.equal(r2.status, 0, r2.stderr);
  const j2 = parseJsonOut(r2, "asset-v2 fake");
  assert.equal(j2.ok, false);
  assert.equal(j2.code, "not_found");

  const r3 = runCli(["question-v2", "q-12-6-listening-shared-26"], { dataDir: DATA });
  assert.equal(r3.status, 0, r3.stderr);
  const j3 = parseJsonOut(r3, "question-v2 q-12-6");
  assert.equal(j3.ok, true);
  assert.equal(j3.question.content_status, "missing_asset");
  assert.equal(j3.question.fully_complete, false);
});

/* ------------------------------------------------------------------ 14 */

test("case 14: general-variant routing — gta resolves; variant mismatch and bad filter are typed errors", () => {
  const r1 = runCli(["test-v2", "10", "gta"], { dataDir: DATA });
  assert.equal(r1.status, 0, r1.stderr);
  const j1 = parseJsonOut(r1, "test-v2 10 gta");
  assert.equal(j1.ok, true);
  assert.equal(j1.identity.variant, "general");
  assert.equal(j1.identity.source_skill, "general_reading");
  const unit = (j1.completion.units || []).find((u) => u.unit_id === "cambridge:10:general:reading:gta");
  assert.ok(unit, "gta completion unit missing");
  assert.equal(unit.status, "not_extracted");
  assert.deepEqual(unit.numbers.expected, Array.from({ length: 40 }, (_, i) => i + 1));

  const r2 = runCli(["test-v2", "10", "1", "--variant=general"], { dataDir: DATA });
  assert.equal(r2.status, 0, r2.stderr);
  const j2 = parseJsonOut(r2, "test-v2 10 1 general");
  assert.equal(j2.ok, false);
  assert.equal(j2.code, "variant_mismatch");

  const r3 = runCli(["questions-v2", "9", "gta", "--skill=listening"], { dataDir: DATA });
  assert.equal(r3.status, 0, r3.stderr);
  const j3 = parseJsonOut(r3, "questions-v2 9 gta listening");
  assert.equal(j3.ok, false);
  assert.equal(j3.code, "bad_filter");
});

/* ------------------------------------------------------------------ 15 */

test("case 15: transcript fallback — cam1 T1 all Parts available, cam3 T2 all Parts source_missing", () => {
  const log = path.join(SCRATCH, "case15-stub.json");
  const r1 = runCli(["aggregate", "1", "1"], { dataDir: DATA, env: { STUB_FETCH_LOG: log } });
  assert.equal(r1.status, 0, r1.stderr);
  const j1 = parseJsonOut(r1, "aggregate 1 1");
  const ps1 = j1.parts.listening_script.part_status;
  for (const key of ["1", "2", "3", "4"]) {
    assert.equal(ps1[key].status, "available", `cam1 T1 P${key}`);
    assert.ok(ps1[key].chars >= 200, `cam1 T1 P${key} chars=${ps1[key].chars}`);
  }
  assert.equal(readJson(log).count, 0);

  const r2 = runCli(["aggregate", "3", "2"], { dataDir: DATA });
  assert.equal(r2.status, 0, r2.stderr);
  const j2 = parseJsonOut(r2, "aggregate 3 2");
  const ps2 = j2.parts.listening_script.part_status;
  for (const key of ["1", "2", "3", "4"]) {
    assert.equal(ps2[key].status, "source_missing", `cam3 T2 P${key}`);
    assert.ok(ps2[key].reason, `cam3 T2 P${key} reason empty`);
  }
});

/* ------------------------------------------------------------------ 16 */

test("case 16: tampered audio hash is caught by audit-all --verify-audio (exit 1, typed error)", () => {
  const scratch = path.join(SCRATCH, "audio-tamper");
  rmrf(scratch);
  mkdirp(scratch);

  const idxPtr = readJson(path.join(DATA, "indexes", "current"));
  const manPtr = readJson(path.join(DATA, "manifests", "current"));
  for (const relPath of ["indexes/current", "manifests/current", idxPtr.artifact, manPtr.artifact]) {
    const dst = path.join(scratch, relPath);
    mkdirp(path.dirname(dst));
    fs.copyFileSync(path.join(DATA, relPath), dst);
  }

  const runsDir = path.join(DATA, "runs");
  const catalogRun = fs
    .readdirSync(runsDir)
    .filter((d) => fs.existsSync(path.join(runsDir, d, "audio", "audio-catalog.json")))
    .sort()
    .reverse()[0];
  assert.ok(catalogRun, "no real audio catalog under ielts-data/runs/*/audio/");
  const realCatalog = readJson(path.join(runsDir, catalogRun, "audio", "audio-catalog.json"));
  const rec = (realCatalog.records || []).find((r) => r.identity === "cambridge:1:shared:listening:1:P1");
  assert.ok(rec, "cambridge:1 listening P1 record missing from real catalog");
  assert.ok(rec.file_path && fs.existsSync(rec.file_path), "real P1 audio file missing: " + rec.file_path);
  writeJson(path.join(scratch, "runs", "zz-test-s15-audio", "audio", "audio-catalog.json"), {
    schema: "ielts.audio-catalog/1",
    records: [{ ...rec, content_sha256: "deadbeef".repeat(8) }],
  });

  const outDir = path.join(scratch, "out");
  const r = spawnSync(process.execPath, [AUDIT, "--dataset", "current", "--verify-audio", "--data-dir", scratch, "--out", outDir, "--json"], {
    cwd: REPO,
    env: baseEnv(null),
    encoding: "utf8",
    timeout: 300000,
    maxBuffer: MAX_BUFFER,
  });
  assert.equal(r.status, 1, `audit-all exit; stderr: ${r.stderr}`);
  const j = parseJsonOut(r, "audit-all");
  assert.equal(j.errors_by_kind.audio_hash_mismatch, 1);
  const errLines = fs.readFileSync(path.join(outDir, "errors.jsonl"), "utf8");
  assert.ok(errLines.includes("cambridge:1:shared:listening:1:P1"), "errors.jsonl missing tampered identity");
});

/* ------------------------------------------------------------------ 17 */

test("case 17: timestamp unit detection, clock validation, offset fit/apply", () => {
  assert.equal(detectTimestampUnit([100, 200], 400).unit, "sec");
  assert.equal(detectTimestampUnit([100000, 200000], 400).unit, "ms");

  const bad = validateClock([{ t_sec: 10 }, { t_sec: 5 }]);
  assert.equal(bad.valid, false);
  assert.ok(bad.reasons.includes("non_monotonic"));

  const fit = estimateOffset([
    { source_sec: 0, target_sec: 1 },
    { source_sec: 100, target_sec: 101 },
    { source_sec: 200, target_sec: 201 },
    { source_sec: 300, target_sec: 301 },
  ]);
  assert.equal(fit.ok, true);
  assert.ok(Math.abs(fit.a - 1) < 1e-9, `a=${fit.a}`);
  assert.ok(Math.abs(fit.b - 1) < 1e-9, `b=${fit.b}`);
  assert.equal(applyOffset(fit, 150), 151);
});

/* ------------------------------------------------------------------ 18 */

test("case 18: comparator rejects single-letter substring decoys, accepts bracketed variants", () => {
  const a = compareAnswers("A", "the letter A appears in the text");
  assert.equal(a.equal, false);
  assert.equal(a.reason, "single_letter_mismatch");

  const b = compareAnswers("(the) newsletter", "newsletter");
  assert.equal(b.equal, true);
  assert.equal(b.reason, "variant");
});

/* ------------------------------------------------------------------ 19 */

test("case 19: adjudication applies only on upstream match; tampered value goes stale", () => {
  const key = new Array(40).fill("");
  key[37] = "Stream"; // Q38
  const applied = applyAdjudications(17, 4, { ok: true, answer_key: key, questions: [] });
  assert.equal(applied.answer_key[37], "steam");
  assert.ok(Array.isArray(applied.answer_corrections));
  assert.ok(applied.answer_corrections.some((c) => c.question === 38 && c.from === "Stream" && c.to === "steam"));

  const tampered = new Array(40).fill("");
  tampered[37] = "Stream ";
  const stale = applyAdjudications(17, 4, { ok: true, answer_key: tampered, questions: [] });
  assert.ok(Array.isArray(stale.adjudication_stale));
  assert.equal(stale.adjudication_stale[0].question, 38);
  assert.equal(stale.adjudication_stale[0].expected_from, "Stream");
  assert.equal(stale.adjudication_stale[0].actual, "Stream ");
  assert.equal(stale.adjudication_stale[0].reason, "upstream_value_changed");
  assert.equal(stale.answer_key[37], "Stream ");
});

/* ------------------------------------------------------------------ 20 */

test("case 20: invalid refresh args exit 2 without any network call", () => {
  const log1 = path.join(SCRATCH, "case20a.json");
  const r1 = runRefresh(["--books", "22", "--variant", "academic", "--skills", "reading"], { dataDir: DATA, env: { STUB_FETCH_LOG: log1 } });
  assert.equal(r1.status, 2);
  assert.match(r1.stderr, /--books out of range \(1-21\)/);
  assert.equal(readJson(log1).count, 0);

  const log2 = path.join(SCRATCH, "case20b.json");
  const r2 = runRefresh([], { dataDir: DATA, env: { STUB_FETCH_LOG: log2 } });
  assert.equal(r2.status, 2);
  assert.match(r2.stderr, /usage:/);
  assert.equal(readJson(log2).count, 0);
});

/* ------------------------------------------------------------------ 21 */

test("case 21: SIGTERM mid-refresh leaves the ledger absent or valid JSON", async () => {
  const dir = path.join(SCRATCH, "cycle-kill");
  buildCycle(dir, { books: [10, 11, 12] });

  const { child, done } = spawnRefresh(["--books", "10-12", "--variant", "academic", "--skills", "reading", "--jobs", "1", "--resume", "--json"], { dataDir: dir });
  await new Promise((res) => setTimeout(res, 1200));
  child.kill("SIGTERM");
  await done;

  const ledgerPath = path.join(dir, "refresh", "academic-reading", "ledger.json");
  if (fs.existsSync(ledgerPath)) {
    const ledger = readJson(ledgerPath); // throws when the kill left corrupt JSON
    assert.ok(ledger && typeof ledger === "object");
  }
});

/* ------------------------------------------------------------------ 22 */

test("case 22: legacy reading route still serves from local pte-raw without network", () => {
  const log = path.join(SCRATCH, "case22.json");
  const r = runCli(["reading", "10", "1"], { dataDir: DATA, env: { STUB_FETCH_LOG: log } });
  assert.equal(r.status, 0, r.stderr);
  const j = parseJsonOut(r, "reading 10 1");
  assert.equal(j.ok, true);
  assert.equal(readJson(log).count, 0);
});
