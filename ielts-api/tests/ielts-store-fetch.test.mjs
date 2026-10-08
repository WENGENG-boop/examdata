/**
 * ielts-store-fetch.test.mjs — S03 验收测试
 *
 * 覆盖计划 S03 验收：raw hash 去重、两 run 并发写入（含子进程）、崩溃恢复（checkpoint 续跑）、
 * stale 返回、404/403/429/5xx、坏 JSON、HTTP200 HTML 错误页、锁（持有/过期接管）、
 * 预算（请求数/字节/单请求上限）、本地复用优先、按来源串行。
 */
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";
import {
  storeRaw,
  storeBinary,
  writeJsonAtomic,
  readJson,
  acquireLock,
  releaseLock,
  LockError,
  writeCheckpoint,
  readCheckpoint,
  writeIndex,
  writeCoverage,
  publishCurrent,
  readCurrent,
  currentOrStale,
  computeDatasetRevision,
  ensureLayout,
  sha256Hex,
} from "../data-store.mjs";
import {
  createFetcher,
  fetchBatch,
  looksLikeErrorPage,
  SourceBlockedError,
  ResourceMissingError,
  BadResponseError,
  BudgetExceededError,
  NetworkError,
} from "../fetch-source.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE = path.resolve(HERE, "..", "..");
const TEST_DATA = path.join(WORKSPACE, "ielts-data", "test-s03");

let server;
let base;
const hits = new Map();
const bump = (k) => hits.set(k, (hits.get(k) || 0) + 1);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

before(async () => {
  fs.rmSync(TEST_DATA, { recursive: true, force: true });
  ensureLayout(TEST_DATA);
  server = http.createServer((req, res) => {
    const u = new URL(req.url, "http://x");
    bump(u.pathname);
    const n = hits.get(u.pathname);
    if (u.pathname === "/ok") {
      res.writeHead(200, { "content-type": "application/json", etag: '"v1"', "last-modified": "Wed, 01 Oct 2025 00:00:00 GMT" });
      res.end('{"hello":1}');
    } else if (u.pathname === "/html-error") {
      res.writeHead(200, { "content-type": "text/html" });
      res.end("<html><head><title>404 Not Found</title></head><body>not found</body></html>");
    } else if (u.pathname === "/html-ok") {
      res.writeHead(200, { "content-type": "text/html" });
      res.end("<html><body><h1>Hello</h1></body></html>");
    } else if (u.pathname === "/bad-json") {
      res.writeHead(200, { "content-type": "application/json" });
      res.end("{not json");
    } else if (u.pathname === "/missing") {
      res.writeHead(404);
      res.end("nope");
    } else if (u.pathname === "/forbidden") {
      res.writeHead(403);
      res.end("forbidden");
    } else if (u.pathname === "/ratelimit") {
      res.writeHead(429);
      res.end("slow down");
    } else if (u.pathname === "/flaky") {
      if (n <= 2) { res.writeHead(500); res.end("boom"); }
      else { res.writeHead(200, { "content-type": "application/json" }); res.end('{"ok":true}'); }
    } else if (u.pathname === "/always-500") {
      res.writeHead(500);
      res.end("boom");
    } else if (u.pathname === "/bytes") {
      const size = Number(u.searchParams.get("n") || 100);
      res.writeHead(200, { "content-type": "application/octet-stream" });
      res.end(Buffer.alloc(size, 7));
    } else if (u.pathname === "/slow") {
      // 故意不响应，测超时
    } else {
      res.writeHead(404);
      res.end();
    }
  });
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  base = "http://127.0.0.1:" + server.address().port;
});

after(() => {
  server.close();
});

// ---------------------------------------------------------------- data-store

test("raw hash 去重：同内容同路径、meta 不覆写、无 tmp 残留", () => {
  const body = Buffer.from("same content for dedup");
  const a = storeRaw({ root: TEST_DATA, source: "s-dedup", body, meta: { note: "first" } });
  const b = storeRaw({ root: TEST_DATA, source: "s-dedup", body, meta: { note: "second" } });
  assert.equal(a.sha256, b.sha256);
  assert.equal(b.deduped, true);
  assert.equal(a.metaWritten, true);
  assert.equal(b.metaWritten, false);
  const meta = readJson(a.metaPath);
  assert.equal(meta.note, "first");
  assert.equal(meta.sha256, a.sha256);
  const files = fs.readdirSync(path.dirname(a.bodyPath));
  assert.equal(files.filter((f) => f.includes(".tmp-")).length, 0);
  assert.equal(files.filter((f) => f.endsWith(".body")).length, 1);
});

test("二进制按 sha256 命名并去重", () => {
  const buf = Buffer.from("%PDF-1.4 fake pdf bytes");
  const a = storeBinary({ root: TEST_DATA, kind: "pdf", ext: ".PDF", body: buf });
  const b = storeBinary({ root: TEST_DATA, kind: "pdf", ext: "pdf", body: buf });
  assert.equal(a.path, b.path);
  assert.ok(a.path.endsWith(a.sha256 + ".pdf"));
  assert.equal(b.deduped, true);
  assert.equal(sha256Hex(buf), a.sha256);
});

test("两 run 并发写入（子进程）：同一 raw 文件、无半文件", async () => {
  const code = `
    import { storeRaw } from ${JSON.stringify(pathToFileURL(path.join(WORKSPACE, "ielts-api", "data-store.mjs")).href)};
    const r = storeRaw({ root: process.env.C_ROOT, source: "s-conc", body: Buffer.from(process.env.C_BODY), meta: { note: "proc-" + process.pid } });
    console.log(JSON.stringify({ sha256: r.sha256, deduped: r.deduped }));
  `;
  const run = () =>
    new Promise((resolve, reject) => {
      const c = spawn(process.execPath, ["--input-type=module", "-e", code], {
        env: { ...process.env, C_ROOT: TEST_DATA, C_BODY: "cross-process concurrent body" },
      });
      let out = "";
      c.stdout.on("data", (d) => (out += d));
      c.on("error", reject);
      c.on("exit", (codeNum) => (codeNum === 0 ? resolve(JSON.parse(out)) : reject(new Error("child exit " + codeNum))));
    });
  const [a, b] = await Promise.all([run(), run()]);
  assert.equal(a.sha256, b.sha256);
  assert.equal([a.deduped, b.deduped].filter((x) => x === false).length, 1); // 恰有一个进程首次写入
  const dir = path.join(TEST_DATA, "raw", "s-conc");
  const files = fs.readdirSync(dir);
  assert.equal(files.filter((f) => f.endsWith(".body")).length, 1);
  assert.equal(files.filter((f) => f.includes(".tmp-")).length, 0);
  assert.equal(fs.readFileSync(path.join(dir, a.sha256 + ".body"), "utf8"), "cross-process concurrent body");
  assert.ok(readJson(path.join(dir, a.sha256 + ".meta.json")).sha256);
});

test("锁：独占、拒绝、过期接管保留证据、token 不符拒绝释放", () => {
  const lockPath = path.join(TEST_DATA, "locks", "t1.lock");
  const h1 = acquireLock(lockPath, { ttlMs: 60_000, meta: { purpose: "test" } });
  assert.throws(() => acquireLock(lockPath, { ttlMs: 60_000 }), LockError);
  assert.throws(() => releaseLock(lockPath, "bogus-token"), LockError);
  h1.release();
  const h2 = acquireLock(lockPath, { ttlMs: 60_000 });
  h2.release();

  // 过期锁：写一个已过期的锁文件，接管成功且旧锁改名保留
  const stale = { token: "old", pid: 999999, acquired_at: "2020-01-01T00:00:00.000Z", expires_at: "2020-01-01T00:10:00.000Z" };
  writeJsonAtomic(lockPath, stale);
  const h3 = acquireLock(lockPath, { ttlMs: 60_000 });
  assert.ok(h3.tookOverStale && fs.existsSync(h3.tookOverStale));
  assert.equal(readJson(h3.tookOverStale).token, "old");
  h3.release();
});

test("checkpoint：合并写读、崩溃后可恢复", () => {
  const runId = "cp-test";
  writeCheckpoint({ root: TEST_DATA, runId, data: { stage: "s03", fetcher: { counters: { requests: 3 }, sources: { s1: { blocked: null } } } } });
  writeCheckpoint({ root: TEST_DATA, runId, data: { stage: "s03b" } });
  const cp = readCheckpoint({ root: TEST_DATA, runId });
  assert.equal(cp.stage, "s03b");
  assert.equal(cp.fetcher.counters.requests, 3);
  assert.equal(cp.schema_version, "ielts-run-checkpoint/1");
});

test("dataset_revision：同输入同值、与时间无关、不同 parser 版本不同值", () => {
  const inputs = { "b1.pdf": "aa", "v5.json": "bb" };
  const r1 = computeDatasetRevision({ inputHashes: inputs, parserVersion: "p1", schemaVersion: "v1" });
  const r2 = computeDatasetRevision({ inputHashes: { "v5.json": "bb", "b1.pdf": "aa" }, parserVersion: "p1", schemaVersion: "v1" });
  const r3 = computeDatasetRevision({ inputHashes: inputs, parserVersion: "p2", schemaVersion: "v1" });
  assert.equal(r1, r2);
  assert.notEqual(r1, r3);
  assert.match(r1, /^rev-[0-9a-f]{16}$/);
});

test("current 指针：未校验拒发、原子发布、stale 返回保留最后成功版本", () => {
  const rev = "rev-s03test";
  writeIndex({ root: TEST_DATA, datasetRevision: rev, questions: [{ id: "q1" }] });
  writeCoverage({ root: TEST_DATA, datasetRevision: rev, coverage: { ok: true } });
  assert.throws(() => publishCurrent({ root: TEST_DATA, kind: "indexes", datasetRevision: rev }), /validated/);
  publishCurrent({ root: TEST_DATA, kind: "indexes", datasetRevision: rev, validated: true });
  const cur = readCurrent({ root: TEST_DATA, kind: "indexes" });
  assert.equal(cur.dataset_revision, rev);
  const stale = currentOrStale({ root: TEST_DATA, kind: "indexes", refreshError: "network down" });
  assert.equal(stale.ok, true);
  assert.equal(stale.stale, true);
  assert.equal(stale.dataset_revision, rev);
  const fresh = currentOrStale({ root: TEST_DATA, kind: "indexes" });
  assert.equal(fresh.stale, false);
  // 旧版本目录仍在
  assert.ok(fs.existsSync(path.join(TEST_DATA, "indexes", rev, "questions.json")));
});

// ---------------------------------------------------------------- fetch-source

function mkFetcher(runId, limits = {}, extra = {}) {
  return createFetcher({ root: TEST_DATA, runId, limits: { retryBackoffMs: 10, ...limits }, ...extra });
}

test("looksLikeErrorPage：识别 Cloudflare/404 标题，普通 HTML 不算错误页", () => {
  assert.deepEqual(looksLikeErrorPage("text/html", "<html><title>Just a moment...</title>"), { html: true, error_page: true });
  assert.equal(looksLikeErrorPage("text/html", "<html><body>hello</body></html>").error_page, false);
  assert.equal(looksLikeErrorPage("application/json", '{"a":1}').html, false);
});

test("fetchToRaw 成功：body+meta 落盘、meta 字段、requests.jsonl 记录", async () => {
  const f = mkFetcher("run-ok");
  const r = await f.fetchToRaw({ source: "s-ok", url: base + "/ok", parserVersion: "t1", expect: { json: true } });
  assert.equal(r.status, 200);
  assert.equal(r.deduped, false);
  assert.ok(fs.existsSync(r.bodyPath));
  const meta = readJson(r.metaPath);
  assert.equal(meta.status, 200);
  assert.equal(meta.etag, '"v1"');
  assert.equal(meta.last_modified, "Wed, 01 Oct 2025 00:00:00 GMT");
  assert.equal(meta.parser_version, "t1");
  assert.equal(meta.sha256, r.sha256);
  assert.ok(fs.existsSync(path.join(TEST_DATA, "runs", "run-ok", "requests.jsonl")));
  const again = await f.fetchToRaw({ source: "s-ok", url: base + "/ok", parserVersion: "t1" });
  assert.equal(again.deduped, true);
});

test("404 = 资源缺失：不重试、不阻塞来源，随后同源请求正常", async () => {
  const f = mkFetcher("run-404");
  await assert.rejects(() => f.fetchToRaw({ source: "s-404", url: base + "/missing" }), ResourceMissingError);
  const hitsBefore = hits.get("/missing");
  const r = await f.fetchToRaw({ source: "s-404", url: base + "/ok" });
  assert.equal(r.status, 200);
  assert.equal(hits.get("/missing"), hitsBefore); // 没有重试
  assert.equal(f.snapshot().sources["s-404"].blocked, null);
});

test("403：立即阻塞来源、后续请求不发网络、checkpoint 持久化", async () => {
  const f = mkFetcher("run-403");
  await assert.rejects(() => f.fetchToRaw({ source: "s-403", url: base + "/forbidden" }), SourceBlockedError);
  const hitsAfterBlock = hits.get("/forbidden");
  await assert.rejects(() => f.fetchToRaw({ source: "s-403", url: base + "/ok" }), SourceBlockedError);
  assert.equal(hits.get("/forbidden"), hitsAfterBlock);
  const cp = f.readCheckpoint();
  assert.equal(cp.fetcher.sources["s-403"].blocked.reason, "http_403");

  // 崩溃恢复：新 fetcher 同 runId 续跑，blocked 保留且不发网络
  let networkCalls = 0;
  const f2 = createFetcher({
    root: TEST_DATA, runId: "run-403", limits: { retryBackoffMs: 10 },
    fetchImpl: async (...args) => { networkCalls++; return fetch(...args); },
  });
  await assert.rejects(() => f2.request({ source: "s-403", url: base + "/ok" }), SourceBlockedError);
  assert.equal(networkCalls, 0);
  assert.ok(f2.resumedFrom);
});

test("429：立即阻塞来源", async () => {
  const f = mkFetcher("run-429");
  await assert.rejects(() => f.fetchToRaw({ source: "s-429", url: base + "/ratelimit" }), SourceBlockedError);
  assert.equal(f.snapshot().sources["s-429"].blocked.reason, "http_429");
});

test("连续 5xx 达到阈值后阻塞来源（不再发网络）", async () => {
  const f = mkFetcher("run-5xx", { maxRetries: 0, maxConsecutive5xx: 2 });
  await assert.rejects(() => f.request({ source: "s-5xx", url: base + "/always-500" }), (e) => e.kind === "http_5xx");
  await assert.rejects(() => f.request({ source: "s-5xx", url: base + "/always-500" }), SourceBlockedError);
  const n = hits.get("/always-500");
  await assert.rejects(() => f.request({ source: "s-5xx", url: base + "/always-500" }), SourceBlockedError);
  assert.equal(hits.get("/always-500"), n);
  assert.equal(f.snapshot().sources["s-5xx"].consecutive_5xx, 2);
});

test("5xx 重试成功：计数重置、结果可用", async () => {
  hits.set("/flaky", 0);
  const f = mkFetcher("run-flaky", { maxRetries: 2, maxConsecutive5xx: 5 });
  const r = await f.request({ source: "s-flaky", url: base + "/flaky" });
  assert.equal(r.status, 200);
  assert.equal(r.attempt, 3);
  assert.equal(f.snapshot().sources["s-flaky"].consecutive_5xx, 0);
  assert.equal(f.snapshot().sources["s-flaky"].blocked, null);
});

test("超时 = 网络异常：重试后失败并记录", async () => {
  const f = mkFetcher("run-timeout", { timeoutMs: 80, maxRetries: 1 });
  await assert.rejects(() => f.request({ source: "s-slow", url: base + "/slow" }), NetworkError);
  assert.equal(hits.get("/slow"), 2); // 1 + 1 重试
});

test("坏 JSON 与 HTTP200 HTML 错误页：不得当作成功内容", async () => {
  const f = mkFetcher("run-bad");
  await assert.rejects(
    () => f.fetchToRaw({ source: "s-bad", url: base + "/bad-json", expect: { json: true } }),
    (e) => e instanceof BadResponseError && e.reason === "bad_json"
  );
  await assert.rejects(
    () => f.fetchToRaw({ source: "s-bad", url: base + "/html-error" }),
    (e) => e instanceof BadResponseError && e.reason === "html_error_page"
  );
  // 普通 HTML 默认放行；显式 rejectHtml 时拒绝
  const ok = await f.fetchToRaw({ source: "s-bad", url: base + "/html-ok" });
  assert.equal(ok.status, 200);
  await assert.rejects(
    () => f.fetchToRaw({ source: "s-bad", url: base + "/html-ok", expect: { rejectHtml: true } }),
    (e) => e instanceof BadResponseError && e.reason === "html"
  );
  const errs = fs.readFileSync(path.join(TEST_DATA, "runs", "run-bad", "errors.jsonl"), "utf8").trim().split("\n").map((l) => JSON.parse(l));
  assert.ok(errs.some((e) => e.error_kind === "bad_response" && e.reason === "bad_json"));
  assert.ok(errs.some((e) => e.error_kind === "bad_response" && e.reason === "html_error_page"));
});

test("预算：请求数上限与字节上限、单请求上限", async () => {
  const f = mkFetcher("run-budget", { maxRequests: 2 });
  await f.request({ source: "s-b1", url: base + "/ok" });
  await f.request({ source: "s-b1", url: base + "/ok" });
  await assert.rejects(() => f.request({ source: "s-b1", url: base + "/ok" }), BudgetExceededError);

  const f2 = mkFetcher("run-budget2", { maxBytes: 300 });
  await assert.rejects(() => f2.request({ source: "s-b2", url: base + "/bytes?n=400" }), BudgetExceededError);

  const f3 = mkFetcher("run-budget3", { maxBytesPerRequest: 100 });
  await assert.rejects(() => f3.request({ source: "s-b3", url: base + "/bytes?n=400" }), (e) => e instanceof BadResponseError && e.reason === "too_large");
  await assert.rejects(
    () => f3.fetchToBinary({ source: "s-b3", url: base + "/bytes?n=400", kind: "audio", ext: "mp3", declaredBytes: 999999 }),
    BudgetExceededError
  );
});

test("本地复用优先：二进制入库不产生网络请求", async () => {
  const local = path.join(TEST_DATA, "local-sample.pdf");
  fs.mkdirSync(path.dirname(local), { recursive: true });
  fs.writeFileSync(local, "%PDF-1.4 local reuse test");
  const f = mkFetcher("run-reuse");
  const beforeHits = [...hits.values()].reduce((a, b) => a + b, 0);
  const a = f.reuseLocalBinary({ kind: "pdf", filePath: local, ext: "pdf" });
  const b = f.reuseLocalBinary({ kind: "pdf", filePath: local, ext: "pdf" });
  assert.equal(a.sha256, b.sha256);
  assert.equal(a.reused_local, true);
  assert.equal(b.deduped, true);
  const afterHits = [...hits.values()].reduce((a, b) => a + b, 0);
  assert.equal(afterHits, beforeHits);
  // reuseLocalRaw 同理
  const raw = f.reuseLocalRaw({ source: "s-local", filePath: local, parserVersion: "t" });
  assert.equal(raw.reused_local, true);
  assert.ok(fs.existsSync(raw.bodyPath));
});

test("每来源最大 1 并发：同源并发请求在飞数量 ≤1", async () => {
  let inflight = 0;
  let maxInflight = 0;
  const realFetch = globalThis.fetch;
  const f = createFetcher({
    root: TEST_DATA,
    runId: "run-serial",
    limits: { retryBackoffMs: 10 },
    fetchImpl: async (url, opts) => {
      inflight++;
      maxInflight = Math.max(maxInflight, inflight);
      try {
        await sleep(30);
        return await realFetch(url, opts);
      } finally {
        inflight--;
      }
    },
  });
  await Promise.all([
    f.request({ source: "s-ser", url: base + "/ok" }),
    f.request({ source: "s-ser", url: base + "/ok" }),
    f.request({ source: "s-ser", url: base + "/ok" }),
  ]);
  assert.equal(maxInflight, 1);
});

test("fetchBatch：全局并发 ≤ concurrency，结果按序", async () => {
  let cur = 0;
  let max = 0;
  const jobs = [1, 2, 3, 4].map((n) => async () => {
    cur++;
    max = Math.max(max, cur);
    try {
      await sleep(20);
      return n * 10;
    } finally {
      cur--;
    }
  });
  const rs = await fetchBatch(jobs, { concurrency: 2 });
  assert.deepEqual(rs.map((r) => r.value), [10, 20, 30, 40]);
  assert.ok(max <= 2);
});
