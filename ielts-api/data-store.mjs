/**
 * data-store.mjs — 雅思数据存储层（计划 S03）
 *
 * 目录固定（相对数据根，默认工作区 `ielts-data/`，可用 `EXAMDATA_IELTS_DATA_DIR` 覆盖；
 * 不可复用 EXAMDATA_DATA_DIR）：
 *   raw/<source>/<sha256>.body / .meta.json
 *   pdf/<sha256>.pdf
 *   audio/<sha256>.<extension>
 *   assets/<sha256>.<extension>
 *   normalized/<schema_version>/<dataset_revision>/<test_id>.json
 *   indexes/<dataset_revision>/questions.json   (+ current 指针)
 *   manifests/<dataset_revision>/coverage.json  (+ current 指针)
 *   decisions/<decision_id>.json
 *   runs/<run_id>/{checkpoint.json,requests.jsonl,errors.jsonl,backup/}
 *   derived/pdf/<book>/<pdf_sha8>/{extract-*.json,provenance-*.json,assets/}   (S06)
 *
 * 规则（计划 S03）：
 * - JSON 先写同目录临时文件再 rename，绝不产生半文件；失败保留 checkpoint。
 * - raw 正文按 hash 追加，绝不覆写旧版本；meta 首次写入后保留（后续拉取进 requests.jsonl）。
 * - dataset_revision 由输入 hash + parser/schema 版本计算，不以运行时间随意变。
 * - 索引只有在全量校验后才原子发布 current 指针；绝不删除旧 current 数据。
 * - 并发用锁文件的独占创建（含到期信息）；过期锁可接管，旧锁改名保留为证据。
 */
import { createHash, randomBytes } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const WORKSPACE_ROOT = path.resolve(HERE, "..");

export const LAYOUT_DIRS = ["raw", "pdf", "audio", "assets", "normalized", "indexes", "manifests", "decisions", "runs", "derived"];

/** 数据根：显式参数 > EXAMDATA_IELTS_DATA_DIR > 工作区 ielts-data/ */
export function resolveDataDir(explicit) {
  const dir = explicit || process.env.EXAMDATA_IELTS_DATA_DIR || path.join(WORKSPACE_ROOT, "ielts-data");
  return path.resolve(dir);
}

/** 建立固定目录布局；返回数据根 */
export function ensureLayout(root) {
  const r = root || resolveDataDir();
  for (const d of LAYOUT_DIRS) fs.mkdirSync(path.join(r, d), { recursive: true });
  return r;
}

/** 路径片段安全校验（拒绝空、`..`、斜杠与反斜杠） */
export function sanitizeSegment(name, what = "segment") {
  const s = String(name ?? "");
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(s) || s.includes("..")) {
    throw new Error(`invalid ${what}: ${JSON.stringify(name)}`);
  }
  return s;
}

export function sha256Hex(data) {
  return createHash("sha256").update(data).digest("hex");
}

/** 流式计算文件 SHA256（大文件不整读） */
export async function sha256File(filePath) {
  const h = createHash("sha256");
  await new Promise((resolve, reject) => {
    const s = fs.createReadStream(filePath);
    s.on("data", (d) => h.update(d));
    s.on("error", reject);
    s.on("end", resolve);
  });
  return h.digest("hex");
}

/** 同步分块计算文件 SHA256 */
export function sha256FileSync(filePath) {
  const h = createHash("sha256");
  const fd = fs.openSync(filePath, "r");
  const buf = Buffer.alloc(1024 * 1024);
  try {
    let n;
    while ((n = fs.readSync(fd, buf, 0, buf.length, null)) > 0) h.update(buf.subarray(0, n));
  } finally {
    fs.closeSync(fd);
  }
  return h.digest("hex");
}

/** 原子写：同目录临时文件 + fsync + rename；失败清理临时文件 */
export function atomicWriteFile(filePath, data, { fsync = true } = {}) {
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });
  const tmp = path.join(dir, `.tmp-${process.pid}-${randomBytes(6).toString("hex")}`);
  const buf = Buffer.isBuffer(data) ? data : Buffer.from(data);
  try {
    const fd = fs.openSync(tmp, "w");
    try {
      fs.writeSync(fd, buf);
      if (fsync) fs.fsyncSync(fd);
    } finally {
      fs.closeSync(fd);
    }
    fs.renameSync(tmp, filePath);
  } catch (e) {
    try { fs.unlinkSync(tmp); } catch {}
    throw e;
  }
}

export function writeJsonAtomic(filePath, obj) {
  atomicWriteFile(filePath, JSON.stringify(obj, null, 2) + "\n");
}

export function readJson(filePath, { missingOk = true } = {}) {
  let text;
  try {
    text = fs.readFileSync(filePath, "utf8");
  } catch (e) {
    if (e.code === "ENOENT" && missingOk) return null;
    throw e;
  }
  return JSON.parse(text);
}

// ---------------------------------------------------------------- raw / binary

export function rawDir(root, source) {
  return path.join(root, "raw", sanitizeSegment(source, "source"));
}

/**
 * 存 raw 正文：按 sha256 追加，绝不覆写旧版本。
 * meta 首次写入后保留；返回 {sha256, bodyPath, metaPath, deduped, bytes, metaWritten}。
 */
export function storeRaw({ root, source, body, meta = {} }) {
  const r = root || resolveDataDir();
  const src = sanitizeSegment(source, "source");
  const buf = Buffer.isBuffer(body) ? body : Buffer.from(body);
  const sha256 = sha256Hex(buf);
  const dir = path.join(r, "raw", src);
  fs.mkdirSync(dir, { recursive: true });
  const bodyPath = path.join(dir, sha256 + ".body");
  const metaPath = path.join(dir, sha256 + ".meta.json");
  let deduped = false;
  if (fs.existsSync(bodyPath)) deduped = true;
  else atomicWriteFile(bodyPath, buf);
  let metaWritten = false;
  if (!fs.existsSync(metaPath)) {
    writeJsonAtomic(metaPath, { ...meta, sha256, bytes: buf.length, stored_at: new Date().toISOString() });
    metaWritten = true;
  }
  return { sha256, bodyPath, metaPath, deduped, bytes: buf.length, metaWritten };
}

const BINARY_KINDS = new Set(["pdf", "audio", "assets"]);

function normalizeExt(ext) {
  const x = String(ext || "bin").replace(/^\./, "").toLowerCase();
  return /^[a-z0-9]{1,8}$/.test(x) ? x : "bin";
}

/** 存二进制（pdf/audio/assets）：按 sha256 命名，重复内容去重不覆写 */
export function storeBinary({ root, kind, ext, body }) {
  const r = root || resolveDataDir();
  if (!BINARY_KINDS.has(kind)) throw new Error(`invalid binary kind: ${kind}`);
  const buf = Buffer.isBuffer(body) ? body : Buffer.from(body);
  const sha256 = sha256Hex(buf);
  const dir = path.join(r, kind);
  fs.mkdirSync(dir, { recursive: true });
  const filePath = path.join(dir, sha256 + "." + normalizeExt(ext));
  const deduped = fs.existsSync(filePath);
  if (!deduped) atomicWriteFile(filePath, buf);
  return { sha256, path: filePath, deduped, bytes: buf.length, ext: normalizeExt(ext) };
}

/** 从本地文件存二进制（流式 hash + 复制，不整读大文件） */
export function storeBinaryFromFile({ root, kind, ext, filePath }) {
  const r = root || resolveDataDir();
  if (!BINARY_KINDS.has(kind)) throw new Error(`invalid binary kind: ${kind}`);
  const sha256 = sha256FileSync(filePath);
  const dir = path.join(r, kind);
  fs.mkdirSync(dir, { recursive: true });
  const target = path.join(dir, sha256 + "." + normalizeExt(ext));
  const deduped = fs.existsSync(target);
  if (!deduped) {
    const tmp = path.join(dir, `.tmp-${process.pid}-${randomBytes(6).toString("hex")}`);
    try {
      fs.copyFileSync(filePath, tmp);
      fs.renameSync(tmp, target);
    } catch (e) {
      try { fs.unlinkSync(tmp); } catch {}
      throw e;
    }
  }
  return { sha256, path: target, deduped, bytes: fs.statSync(target).size, ext: normalizeExt(ext) };
}

/** 按 hash 查 raw（复用优先） */
export function findRaw({ root, source, sha256 }) {
  const bodyPath = path.join(rawDir(root || resolveDataDir(), source), sha256 + ".body");
  if (!fs.existsSync(bodyPath)) return null;
  const metaPath = bodyPath.replace(/\.body$/, ".meta.json");
  return { sha256, bodyPath, metaPath, meta: readJson(metaPath) };
}

// ---------------------------------------------------------------- normalized / indexes / manifests

export function normalizedPath({ root, schemaVersion, datasetRevision, testId }) {
  return path.join(
    root || resolveDataDir(),
    "normalized",
    sanitizeSegment(schemaVersion, "schema_version"),
    sanitizeSegment(datasetRevision, "dataset_revision"),
    sanitizeSegment(testId, "test_id") + ".json"
  );
}

/** 标准化结果引用 raw hash / 页 / DOM 路径 / 提取方法（由调用方写入 data 内） */
export function writeNormalized({ root, schemaVersion, datasetRevision, testId, data }) {
  const p = normalizedPath({ root, schemaVersion, datasetRevision, testId });
  writeJsonAtomic(p, data);
  return p;
}

export function writeIndex({ root, datasetRevision, questions }) {
  const p = path.join(root || resolveDataDir(), "indexes", sanitizeSegment(datasetRevision, "dataset_revision"), "questions.json");
  writeJsonAtomic(p, questions);
  return p;
}

export function writeCoverage({ root, datasetRevision, coverage }) {
  const p = path.join(root || resolveDataDir(), "manifests", sanitizeSegment(datasetRevision, "dataset_revision"), "coverage.json");
  writeJsonAtomic(p, coverage);
  return p;
}

const POINTER_KINDS = { indexes: "questions.json", manifests: "coverage.json" };

/** 原子发布 current 指针；必须先经全量校验（validated:true），且目标产物存在 */
export function publishCurrent({ root, kind, datasetRevision, validated = false }) {
  const r = root || resolveDataDir();
  if (!POINTER_KINDS[kind]) throw new Error(`invalid pointer kind: ${kind}`);
  if (validated !== true) throw new Error("publishCurrent requires validated:true (索引只有在全量校验后才发布)");
  const rev = sanitizeSegment(datasetRevision, "dataset_revision");
  const artifact = path.join(r, kind, rev, POINTER_KINDS[kind]);
  if (!fs.existsSync(artifact)) throw new Error(`artifact missing, refuse to publish current: ${artifact}`);
  const pointerPath = path.join(r, kind, "current");
  writeJsonAtomic(pointerPath, { dataset_revision: rev, published_at: new Date().toISOString(), artifact: path.relative(r, artifact).split(path.sep).join("/") });
  return pointerPath;
}

export function readCurrent({ root, kind }) {
  const r = root || resolveDataDir();
  if (!POINTER_KINDS[kind]) throw new Error(`invalid pointer kind: ${kind}`);
  return readJson(path.join(r, kind, "current"));
}

/**
 * 刷新失败时返回最后成功版本并标 stale=true；无成功版本时 ok:false/stale:true。
 * 旧 current 数据绝不删除。
 */
export function currentOrStale({ root, kind, refreshError = null }) {
  const cur = readCurrent({ root, kind });
  if (!cur) return { ok: false, dataset_revision: null, stale: true, error: refreshError || "no current published" };
  return { ok: true, dataset_revision: cur.dataset_revision, published_at: cur.published_at, stale: Boolean(refreshError), error: refreshError || null };
}

// ---------------------------------------------------------------- decisions / revisions

export function decisionPath({ root, decisionId }) {
  return path.join(root || resolveDataDir(), "decisions", sanitizeSegment(decisionId, "decision_id") + ".json");
}

export function writeDecision({ root, decisionId, data }) {
  const p = decisionPath({ root, decisionId });
  writeJsonAtomic(p, data);
  return p;
}

/** dataset_revision = sha256(schema_version + parser_version + 排序后的输入 hash)；不用运行时间 */
export function computeDatasetRevision({ inputHashes = {}, parserVersion = "0", schemaVersion = "0" }) {
  const h = createHash("sha256");
  h.update(`schema=${schemaVersion}\nparser=${parserVersion}\n`);
  for (const k of Object.keys(inputHashes).sort()) h.update(`${k}=${inputHashes[k]}\n`);
  return "rev-" + h.digest("hex").slice(0, 16);
}

// ---------------------------------------------------------------- locks

export class LockError extends Error {
  constructor(message) {
    super(message);
    this.name = "LockError";
  }
}

/** 独占创建锁文件（含到期信息）；过期锁改名 .stale-<ts> 保留证据后可接管 */
export function acquireLock(lockPath, { ttlMs = 10 * 60 * 1000, meta = {}, now = Date.now } = {}) {
  fs.mkdirSync(path.dirname(lockPath), { recursive: true });
  const attempt = () => {
    const token = randomBytes(8).toString("hex");
    const payload = {
      token,
      pid: process.pid,
      acquired_at: new Date(now()).toISOString(),
      expires_at: new Date(now() + ttlMs).toISOString(),
      meta,
    };
    try {
      const fd = fs.openSync(lockPath, "wx");
      try {
        fs.writeSync(fd, JSON.stringify(payload, null, 2) + "\n");
        fs.fsyncSync(fd);
      } finally {
        fs.closeSync(fd);
      }
      return {
        token,
        lockPath,
        payload,
        release() {
          releaseLock(lockPath, token);
        },
      };
    } catch (e) {
      if (e.code === "EEXIST") return null;
      throw e;
    }
  };

  let handle = attempt();
  if (handle) return handle;

  let existing = null;
  try { existing = JSON.parse(fs.readFileSync(lockPath, "utf8")); } catch {}
  const exp = existing && Date.parse(existing.expires_at);
  if (exp && exp < now()) {
    const stalePath = lockPath + ".stale-" + now();
    try { fs.renameSync(lockPath, stalePath); } catch {}
    handle = attempt();
    if (handle) {
      handle.tookOverStale = stalePath;
      return handle;
    }
  }
  throw new LockError("lock held: " + lockPath + (existing ? ` (pid ${existing.pid}, expires ${existing.expires_at})` : ""));
}

export function releaseLock(lockPath, token) {
  let cur = null;
  try { cur = JSON.parse(fs.readFileSync(lockPath, "utf8")); } catch {}
  if (!cur || cur.token !== token) throw new LockError("lock token mismatch; refusing to release " + lockPath);
  fs.unlinkSync(lockPath);
}

export async function withLock(lockPath, fn, opts) {
  const handle = acquireLock(lockPath, opts);
  try {
    return await fn(handle);
  } finally {
    try { handle.release(); } catch {}
  }
}

// ---------------------------------------------------------------- runs: checkpoint / journals

export function runDir(root, runId) {
  return path.join(root || resolveDataDir(), "runs", sanitizeSegment(runId, "run_id"));
}

export function checkpointPath(root, runId) {
  return path.join(runDir(root, runId), "checkpoint.json");
}

/** 合并写入 checkpoint（默认 merge=true）；原子写，失败保留旧文件 */
export function writeCheckpoint({ root, runId, data, merge = true }) {
  const p = checkpointPath(root, runId);
  fs.mkdirSync(path.dirname(p), { recursive: true });
  const base = {
    schema_version: "ielts-run-checkpoint/1",
    run_id: sanitizeSegment(runId, "run_id"),
    updated_at: new Date().toISOString(),
  };
  const cur = merge ? readJson(p) : null;
  const next = { ...base, ...(cur || {}), ...data, schema_version: base.schema_version, run_id: base.run_id, updated_at: base.updated_at };
  writeJsonAtomic(p, next);
  return p;
}

export function readCheckpoint({ root, runId }) {
  return readJson(checkpointPath(root, runId));
}

export function appendJsonl(filePath, entry) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.appendFileSync(filePath, JSON.stringify(entry) + "\n");
}

export function appendRequest({ root, runId, entry }) {
  appendJsonl(path.join(runDir(root, runId), "requests.jsonl"), entry);
}

export function appendError({ root, runId, entry }) {
  appendJsonl(path.join(runDir(root, runId), "errors.jsonl"), entry);
}

/** 本地文件 URL（provenance 用） */
export function fileUrl(filePath) {
  return pathToFileURL(path.resolve(filePath)).href;
}
