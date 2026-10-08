/**
 * fetch-source.mjs — 统一取源（计划 S03）
 *
 * 预算（默认，可覆盖）：并发 2、每来源最大 1 同时请求、每次 30s 超时、
 * 网络异常最多 2 次重试、总 run 请求数 / 下载字节上限、单请求字节上限。
 * 失败停止：403/429 或连续 5xx（默认 5 次）→ 立即停止该来源新请求，持久化 checkpoint；
 * 不换代理绕过。404 记为资源缺失（不重试；回落只允许已登记合法备用源，由调用方决定）。
 * 响应校验：HTTP 200 的 HTML 错误页、坏 JSON、content-type 不符、过小正文 → BadResponseError，
 * 不得当作成功内容。本地 PDF/raw 复用优先（reuseLocal*，不产生网络请求）。
 *
 * 所有网络尝试与错误落盘到 runs/<run_id>/requests.jsonl / errors.jsonl；
 * 状态（计数、每来源 blocked）写 runs/<run_id>/checkpoint.json，可用 resume:true 续跑。
 */
import fs from "node:fs";
import path from "node:path";
import {
  resolveDataDir,
  ensureLayout,
  storeRaw,
  storeBinary,
  storeBinaryFromFile,
  findRaw,
  appendRequest,
  appendError,
  writeCheckpoint,
  readCheckpoint,
  fileUrl,
} from "./data-store.mjs";

const MiB = 1024 * 1024;

export const DEFAULT_LIMITS = Object.freeze({
  concurrency: 2,
  perSource: 1,
  timeoutMs: 30_000,
  maxRetries: 2,
  retryBackoffMs: 800,
  maxConsecutive5xx: 5,
  maxRequests: Number(process.env.EXAMDATA_IELTS_MAX_REQUESTS || 200),
  maxBytes: Number(process.env.EXAMDATA_IELTS_MAX_BYTES || 1024 * MiB),
  maxBytesPerRequest: Number(process.env.EXAMDATA_IELTS_MAX_BYTES_PER_REQUEST || 512 * MiB),
});

export class FetchError extends Error {
  constructor(kind, message, info = {}) {
    super(message);
    this.name = "FetchError";
    this.kind = kind;
    Object.assign(this, info);
  }
}

export class NetworkError extends FetchError {
  constructor(message, info) { super("network", message, info); this.name = "NetworkError"; }
}
export class SourceBlockedError extends FetchError {
  constructor(source, info = {}) {
    super("source_blocked", `source ${source} blocked: ${info.reason || "unknown"}`, { source, ...info });
    this.name = "SourceBlockedError";
  }
}
export class BudgetExceededError extends FetchError {
  constructor(kind, message, info = {}) { super("budget_exceeded", message, { budget: kind, ...info }); this.name = "BudgetExceededError"; }
}
export class ResourceMissingError extends FetchError {
  constructor(message, info = {}) { super("resource_missing", message, info); this.name = "ResourceMissingError"; }
}
export class BadResponseError extends FetchError {
  constructor(reason, message, info = {}) { super("bad_response", message, { reason, ...info }); this.name = "BadResponseError"; }
}

/** 判断正文是否为 HTML 错误页（HTTP 200 也可能出现；Cloudflare 拦截页等） */
export function looksLikeErrorPage(contentType, body) {
  const head = Buffer.isBuffer(body) ? body.subarray(0, 4096).toString("utf8") : String(body || "").slice(0, 4096);
  const ct = String(contentType || "").toLowerCase();
  const htmlish = ct.includes("text/html") || /^\s*(<!doctype\s+html|<html)/i.test(head);
  if (!htmlish) return { html: false, error_page: false };
  const errorPage = /(<title>[^<]*(error|not found|forbidden|denied|attention required|just a moment|access denied)[^<]*<\/title>|cloudflare|cf-error|access denied|404 not found|403 forbidden|429 too many)/i.test(head);
  return { html: true, error_page: errorPage };
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function validateExpect(expect = {}, buf, meta) {
  const ct = String(meta.content_type || "").toLowerCase();
  const html = looksLikeErrorPage(meta.content_type, buf);
  if (expect.rejectHtml === true && html.html) {
    throw new BadResponseError("html", `unexpected HTML body (HTTP ${meta.status}) from ${meta.final_url}`, { ...meta });
  }
  if (expect.rejectHtmlErrorPage !== false && html.error_page) {
    throw new BadResponseError("html_error_page", `HTML error page (HTTP ${meta.status}) from ${meta.final_url}`, { ...meta });
  }
  if (expect.contentType) {
    const re = expect.contentType instanceof RegExp ? expect.contentType : new RegExp(expect.contentType, "i");
    if (!re.test(ct)) throw new BadResponseError("content_type", `content-type ${ct || "(none)"} does not match ${re} for ${meta.final_url}`, { ...meta });
  }
  if (expect.minBytes && buf.length < expect.minBytes) {
    throw new BadResponseError("too_small", `body too small (${buf.length} < ${expect.minBytes}) from ${meta.final_url}`, { ...meta });
  }
  if (expect.json) {
    try {
      meta.json = JSON.parse(buf.toString("utf8"));
    } catch (e) {
      throw new BadResponseError("bad_json", `invalid JSON from ${meta.final_url}: ${String(e.message || e)}`, { ...meta });
    }
  }
  if (typeof expect.validate === "function") {
    const r = expect.validate(buf, meta);
    if (r !== true && r !== undefined) {
      throw new BadResponseError("validation", typeof r === "string" ? r : `validation failed for ${meta.final_url}`, { ...meta });
    }
  }
}

/** 通用并发池（全局并发上限；每来源串行由 fetcher 内部保证） */
export async function fetchBatch(jobs, { concurrency = 2 } = {}) {
  const results = new Array(jobs.length);
  let cursor = 0;
  const workers = Math.max(1, Math.min(concurrency, jobs.length || 1));
  await Promise.all(
    Array.from({ length: workers }, async () => {
      while (true) {
        const i = cursor++;
        if (i >= jobs.length) return;
        const job = jobs[i];
        try {
          results[i] = { ok: true, value: await (typeof job === "function" ? job() : job.run()) };
        } catch (e) {
          results[i] = { ok: false, error: e };
        }
      }
    })
  );
  return results;
}

/**
 * 创建统一 fetcher。
 * @param {object} opts
 * @param {string} [opts.root] 数据根（默认 resolveDataDir()）
 * @param {string} opts.runId 运行 ID（checkpoint/journal 归属）
 * @param {object} [opts.limits] 覆盖 DEFAULT_LIMITS
 * @param {Function} [opts.fetchImpl] 测试注入用（默认 globalThis.fetch）
 * @param {boolean} [opts.resume=true] 是否从 checkpoint 恢复计数与 blocked 状态
 */
export function createFetcher({ root, runId, limits = {}, fetchImpl, now = () => Date.now(), resume = true } = {}) {
  const dataRoot = ensureLayout(root || resolveDataDir());
  if (!runId) throw new Error("runId required");
  const lim = { ...DEFAULT_LIMITS, ...limits };
  const doFetch = fetchImpl || globalThis.fetch;

  const state = { counters: { requests: 0, bytes: 0, errors: 0 }, sources: new Map() };
  let resumedFrom = null;
  if (resume) {
    const cp = readCheckpoint({ root: dataRoot, runId });
    const f = cp && cp.fetcher;
    if (f) {
      state.counters = { ...state.counters, ...(f.counters || {}) };
      for (const [s, v] of Object.entries(f.sources || {})) {
        state.sources.set(s, {
          requests: v.requests || 0,
          bytes: v.bytes || 0,
          consecutive_5xx: v.consecutive_5xx || 0,
          blocked: v.blocked || null,
        });
      }
      resumedFrom = cp.updated_at || true;
    }
  }

  const sourceTail = new Map();

  function sourceState(source) {
    if (!state.sources.has(source)) {
      state.sources.set(source, { requests: 0, bytes: 0, consecutive_5xx: 0, blocked: null });
    }
    return state.sources.get(source);
  }

  function snapshot() {
    return {
      counters: { ...state.counters },
      sources: Object.fromEntries([...state.sources].map(([k, v]) => [k, { ...v }])),
    };
  }

  function saveCheckpoint(extra) {
    writeCheckpoint({ root: dataRoot, runId, data: { fetcher: snapshot(), ...(extra ? { extra } : {}) } });
  }

  function journalRequest(entry) {
    appendRequest({ root: dataRoot, runId, entry: { at: new Date(now()).toISOString(), run_id: runId, ...entry } });
  }

  function journalError(entry) {
    appendError({ root: dataRoot, runId, entry: { at: new Date(now()).toISOString(), run_id: runId, ...entry } });
  }

  function blockSource(source, reason, info = {}) {
    const st = sourceState(source);
    if (!st.blocked) st.blocked = { reason, ...info, at: new Date(now()).toISOString() };
    saveCheckpoint();
  }

  /** 每来源串行：并发调用同一 source 时排队，保证同时在飞 ≤1 */
  function enqueue(source, fn) {
    const tail = sourceTail.get(source) || Promise.resolve();
    const run = tail.then(fn, fn);
    sourceTail.set(source, run.then(() => {}, () => {}));
    return run;
  }

  async function doRequest(job) {
    const source = job.source;
    if (!source) throw new Error("job.source required");
    const st = sourceState(source);
    if (st.blocked) {
      throw new SourceBlockedError(source, { reason: st.blocked.reason, status: st.blocked.status, blocked_at: st.blocked.at, url: job.url });
    }
    const attempts = (job.maxRetries ?? lim.maxRetries) + 1;
    const timeoutMs = job.timeoutMs || lim.timeoutMs;
    const backoff = job.retryBackoffMs ?? lim.retryBackoffMs;
    let lastErr = null;

    for (let i = 1; i <= attempts; i++) {
      if (state.counters.requests >= lim.maxRequests) {
        throw new BudgetExceededError("maxRequests", `run request budget exhausted (${lim.maxRequests})`, { source, url: job.url });
      }
      state.counters.requests++;
      st.requests++;
      const t0 = now();

      let res = null;
      let netErr = null;
      try {
        const signal = AbortSignal.timeout(timeoutMs);
        res = await doFetch(job.url, {
          method: job.method || "GET",
          headers: job.headers,
          body: job.body,
          redirect: "follow",
          signal,
        });
      } catch (e) {
        netErr = e;
      }

      if (netErr) {
        lastErr = new NetworkError(`network error on ${job.url}: ${String((netErr && netErr.message) || netErr)}`, {
          source, url: job.url, attempt: i, attempts,
        });
        state.counters.errors++;
        journalError({ source, url: job.url, error_kind: "network", message: lastErr.message, attempt: i, attempts });
        if (i < attempts) {
          await sleep(backoff * i);
          continue;
        }
        saveCheckpoint();
        throw lastErr;
      }

      const status = res.status;
      const ct = res.headers.get("content-type") || "";

      if (status === 403 || status === 429) {
        const reason = status === 403 ? "http_403" : "http_429";
        state.counters.errors++;
        journalError({ source, url: job.url, status, error_kind: reason, message: `HTTP ${status}` });
        blockSource(source, reason, { status, url: job.url });
        throw new SourceBlockedError(source, { reason, status, url: job.url });
      }
      if (status === 404) {
        state.counters.errors++;
        journalRequest({ source, url: job.url, status, bytes: 0, outcome: "resource_missing" });
        journalError({ source, url: job.url, status, error_kind: "resource_missing", message: "HTTP 404" });
        saveCheckpoint();
        throw new ResourceMissingError(`HTTP 404 on ${job.url}`, { source, url: job.url, status });
      }
      if (status >= 500) {
        st.consecutive_5xx++;
        state.counters.errors++;
        journalError({ source, url: job.url, status, error_kind: "http_5xx", message: `HTTP ${status}`, consecutive_5xx: st.consecutive_5xx, attempt: i });
        if (st.consecutive_5xx >= lim.maxConsecutive5xx) {
          blockSource(source, "http_5xx_consecutive", { status, count: st.consecutive_5xx, url: job.url });
          throw new SourceBlockedError(source, { reason: "http_5xx_consecutive", status, count: st.consecutive_5xx, url: job.url });
        }
        if (i < attempts) {
          await sleep(backoff * i);
          continue;
        }
        saveCheckpoint();
        throw new FetchError("http_5xx", `HTTP ${status} on ${job.url}`, { source, url: job.url, status, attempts: i });
      }
      if (status < 200 || status >= 300) {
        state.counters.errors++;
        journalError({ source, url: job.url, status, error_kind: "http_" + status, message: `HTTP ${status}` });
        saveCheckpoint();
        throw new FetchError("http_" + status, `HTTP ${status} on ${job.url}`, { source, url: job.url, status });
      }

      // 2xx：读取正文（读失败按网络异常处理，可重试）
      st.consecutive_5xx = 0;
      let buf;
      try {
        buf = Buffer.from(await res.arrayBuffer());
      } catch (e) {
        lastErr = new NetworkError(`body read failed on ${job.url}: ${String((e && e.message) || e)}`, { source, url: job.url, attempt: i });
        state.counters.errors++;
        journalError({ source, url: job.url, error_kind: "network_body", message: lastErr.message, attempt: i });
        if (i < attempts) {
          await sleep(backoff * i);
          continue;
        }
        saveCheckpoint();
        throw lastErr;
      }

      state.counters.bytes += buf.length;
      st.bytes += buf.length;
      const perCap = job.maxBytesPerRequest || lim.maxBytesPerRequest;
      const meta = {
        source,
        url: job.url,
        final_url: res.url || job.url,
        status,
        content_type: ct,
        etag: res.headers.get("etag"),
        last_modified: res.headers.get("last-modified"),
        bytes: buf.length,
        attempt: i,
        duration_ms: now() - t0,
      };

      if (perCap && buf.length > perCap) {
        state.counters.errors++;
        journalError({ source, url: job.url, status, error_kind: "too_large", message: `body ${buf.length} > cap ${perCap}` });
        saveCheckpoint();
        throw new BadResponseError("too_large", `body ${buf.length} bytes exceeds per-request cap ${perCap}`, { ...meta });
      }
      if (state.counters.bytes > lim.maxBytes) {
        state.counters.errors++;
        journalError({ source, url: job.url, status, error_kind: "budget_bytes", message: `run bytes ${state.counters.bytes} > ${lim.maxBytes}` });
        saveCheckpoint();
        throw new BudgetExceededError("maxBytes", `run byte budget exceeded (${state.counters.bytes} > ${lim.maxBytes})`, { ...meta });
      }

      try {
        validateExpect(job.expect, buf, meta);
      } catch (e) {
        state.counters.errors++;
        journalError({ source, url: job.url, status, error_kind: e.kind || "bad_response", message: e.message, reason: e.reason });
        saveCheckpoint();
        throw e;
      }

      journalRequest({ source, url: job.url, final_url: meta.final_url, status, bytes: buf.length, attempt: i, duration_ms: meta.duration_ms, outcome: "ok" });
      saveCheckpoint();
      return { ...meta, headers: Object.fromEntries(res.headers), body: buf };
    }
    throw lastErr || new FetchError("unknown", "unreachable request state", { source, url: job.url });
  }

  // ------------------------------------------------------------ 本地复用

  function reuseLocalRaw({ source, filePath, parserVersion = null, url = null, meta = {} }) {
    const buf = fs.readFileSync(filePath);
    const stored = storeRaw({
      root: dataRoot,
      source,
      body: buf,
      meta: {
        source, url: url || fileUrl(filePath), fetched_at: new Date(now()).toISOString(),
        status: null, content_type: null, bytes: buf.length, parser_version: parserVersion,
        note: "local_reuse", local_path: path.resolve(filePath), ...meta,
      },
    });
    journalRequest({ source, url: url || fileUrl(filePath), local_path: path.resolve(filePath), bytes: stored.bytes, sha256: stored.sha256, deduped: stored.deduped, stored: "raw", network: false, outcome: "ok" });
    return { ...stored, reused_local: true };
  }

  function reuseLocalBinary({ kind, filePath, ext }) {
    const stored = storeBinaryFromFile({ root: dataRoot, kind, ext, filePath });
    journalRequest({ source: "local", url: fileUrl(filePath), local_path: path.resolve(filePath), bytes: stored.bytes, sha256: stored.sha256, deduped: stored.deduped, stored: kind, network: false, outcome: "ok" });
    return { ...stored, reused_local: true };
  }

  // ------------------------------------------------------------ 公开 API

  return {
    root: dataRoot,
    runId,
    limits: lim,
    resumedFrom,

    /** 原始请求（不落盘内容）；返回 {status, headers, body, ...meta} */
    request: (job) => enqueue(job.source, () => doRequest(job)),

    /** 拉取并落 raw/<source>/<sha256>.body + meta */
    async fetchToRaw(job) {
      if (job.localFile) return reuseLocalRaw(job);
      const r = await enqueue(job.source, () => doRequest(job));
      const stored = storeRaw({
        root: dataRoot,
        source: job.source,
        body: r.body,
        meta: {
          source: job.source,
          url: job.url,
          final_url: r.final_url,
          fetched_at: new Date(now()).toISOString(),
          status: r.status,
          content_type: r.content_type,
          etag: r.etag,
          last_modified: r.last_modified,
          bytes: r.bytes,
          parser_version: job.parserVersion || null,
          ...(job.meta || {}),
        },
      });
      journalRequest({ source: job.source, url: job.url, final_url: r.final_url, status: r.status, bytes: r.bytes, sha256: stored.sha256, deduped: stored.deduped, stored: "raw", phase: "store", outcome: "ok" });
      return { ...stored, status: r.status, final_url: r.final_url, content_type: r.content_type, etag: r.etag, last_modified: r.last_modified, reused_local: false };
    },

    /** 拉取并落二进制（pdf/audio/assets/<sha256>.<ext>） */
    async fetchToBinary(job) {
      if (job.localFile) return reuseLocalBinary({ kind: job.kind, filePath: job.localFile, ext: job.ext });
      if (job.declaredBytes && job.declaredBytes > (job.maxBytesPerRequest || lim.maxBytesPerRequest)) {
        throw new BudgetExceededError("maxBytesPerRequest", `declared size ${job.declaredBytes} exceeds per-request cap; refusing whole-book media expansion`, { source: job.source, url: job.url });
      }
      const r = await enqueue(job.source, () => doRequest(job));
      const stored = storeBinary({ root: dataRoot, kind: job.kind, ext: job.ext, body: r.body });
      journalRequest({ source: job.source, url: job.url, final_url: r.final_url, status: r.status, bytes: r.bytes, sha256: stored.sha256, deduped: stored.deduped, stored: job.kind, phase: "store", outcome: "ok" });
      return { ...stored, status: r.status, final_url: r.final_url, content_type: r.content_type, reused_local: false };
    },

    reuseLocalRaw,
    reuseLocalBinary,
    findRaw: ({ source, sha256 }) => findRaw({ root: dataRoot, source, sha256 }),

    /** 状态快照（计数 + 每来源 blocked） */
    snapshot,
    saveCheckpoint,
    readCheckpoint: () => readCheckpoint({ root: dataRoot, runId }),
    budgetStatus: () => ({
      requests: state.counters.requests,
      bytes: state.counters.bytes,
      errors: state.counters.errors,
      maxRequests: lim.maxRequests,
      maxBytes: lim.maxBytes,
    }),
  };
}
