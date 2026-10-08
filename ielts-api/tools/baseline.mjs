#!/usr/bin/env node
/**
 * baseline.mjs — S01 基线工具（只读勘察 + 修改前备份）
 *
 * 产物（数据目录默认 <workspace>/ielts-data，可用 EXAMDATA_IELTS_DATA_DIR 覆盖）：
 *   runs/<run_id>/baseline.json                 — 环境/哈希/副本差异/网关/8000快照/git状态
 *   runs/<run_id>/protected-files-baseline.json — CIE/Edexcel 受保护代码与生产数据库基线
 *   runs/<run_id>/backup/<相对路径>              — 每个将修改文件的修改前副本
 *
 * 用法: node ielts-api/tools/baseline.mjs [--run-id <id>] [--no-live]
 * 不写入 ielts-api 业务文件；不读数据库内容；不修改任何既有文件。
 */
import fs from "node:fs";
import fsp from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE = path.resolve(__dirname, "..", "..");
const IELTS_API_DIR = path.join(WORKSPACE, "ielts-api");
const OTHER_COPY_DIR = "C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api";
const EXAMDATA_DIR = path.join(WORKSPACE, "examdata");

const argv = process.argv.slice(2);
const flagValue = (name) => {
  const i = argv.indexOf(name);
  if (i < 0) return null;
  const v = argv[i + 1];
  return v && !v.startsWith("--") ? v : true;
};
const noLive = argv.includes("--no-live");

function utcStamp(d = new Date()) {
  const p = (x) => String(x).padStart(2, "0");
  return `${d.getUTCFullYear()}${p(d.getUTCMonth() + 1)}${p(d.getUTCDate())}T${p(d.getUTCHours())}${p(d.getUTCMinutes())}${p(d.getUTCSeconds())}Z`;
}
const RUN_ID = (typeof flagValue("--run-id") === "string" ? flagValue("--run-id") : null) || `${utcStamp()}-repair`;
const DATA_DIR = process.env.EXAMDATA_IELTS_DATA_DIR || path.join(WORKSPACE, "ielts-data");
const RUN_DIR = path.join(DATA_DIR, "runs", RUN_ID);
const BACKUP_DIR = path.join(RUN_DIR, "backup");

// ── 将修改的文件清单（相对 workspace 根，正斜杠） ────────────────────────────
const MODIFY_LIST = [
  "ielts-api/pte.mjs",
  "ielts-api/cam21.mjs",
  "ielts-api/ielts-cli.mjs",
  "ielts-api/ielts-api.mjs",
  "ielts-api/lfs.mjs",
  "ielts-api/ito.mjs",
  "ielts-api/iprog.mjs",
  "ielts-api/zhan.mjs",
  "ielts-api/verify-pdfs.mjs",
  "ielts-api/contract.test.mjs",
  "ielts-api/tests/contract.test.mjs",
  "ielts-api/tests/stub-fetch.cjs",
  "ielts-api/API.md",
  "ielts-api/DEVELOPMENT.md",
  "examdata/src/examdata/api/ielts.py",
  "examdata/tests/test_api_ielts.py",
  "examdata/tests/test_ielts_concurrency.py",
  "examdata/docs/IELTS_API.md",
];

// ── CIE/Edexcel 受保护代码目录 + 生产数据库（只登记，不修改） ────────────────
const PROTECTED_DIRS = [
  "examdata/src/examdata/adapters",
  "examdata/src/examdata/edexcel_papers",
  "examdata/src/examdata/markscheme",
  "examdata/src/examdata/specs",
];
const PROTECTED_DB_FILES = [
  "examdata/.data/examdata.db",
  "examdata/.data/backup/examdata_pre920.db",
];

const SKIP_DIRS = new Set(["node_modules", ".git", "__pycache__", ".pytest_cache", ".venv"]);

function sha256File(p) {
  return new Promise((resolve, reject) => {
    const h = crypto.createHash("sha256");
    const s = fs.createReadStream(p);
    s.on("data", (d) => h.update(d));
    s.on("error", reject);
    s.on("end", () => resolve(h.digest("hex")));
  });
}

function walkFiles(dir, base = dir, out = []) {
  let ents;
  try {
    ents = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return out;
  }
  for (const e of ents) {
    if (SKIP_DIRS.has(e.name)) continue;
    const full = path.join(dir, e.name);
    if (e.isDirectory()) walkFiles(full, base, out);
    else if (e.isFile()) out.push(path.relative(base, full).split(path.sep).join("/"));
  }
  return out;
}

function statSafe(p) {
  try {
    const st = fs.statSync(p);
    return { exists: true, bytes: st.size, mtime_iso: st.mtime.toISOString() };
  } catch {
    return { exists: false };
  }
}

function cmdRun(cmd, cmdArgs, opts = {}) {
  const r = spawnSync(cmd, cmdArgs, { encoding: "utf8", timeout: opts.timeout ?? 30000, cwd: opts.cwd });
  return {
    ok: r.status === 0,
    status: r.status,
    stdout: (r.stdout || "").trim().slice(0, 4000),
    stderr: (r.stderr || "").trim().slice(0, 2000),
    error: r.error ? String(r.error.message || r.error) : null,
  };
}

function gitStatus(dir) {
  const rev = cmdRun("git", ["rev-parse", "--short", "HEAD"], { cwd: dir });
  if (!rev.ok) return { is_git_repo: false, detail: (rev.stderr || rev.error || "not a git repository").slice(0, 300) };
  const porcelain = cmdRun("git", ["status", "--porcelain"], { cwd: dir });
  const lines = (porcelain.stdout || "").split("\n").filter(Boolean);
  return { is_git_repo: true, head: rev.stdout, dirty_count: lines.length, dirty_sample: lines.slice(0, 20) };
}

async function hashMapForDir(dir) {
  const map = {};
  for (const rel of walkFiles(dir)) {
    try {
      map[rel] = await sha256File(path.join(dir, rel));
    } catch (e) {
      map[rel] = "ERROR:" + String(e.message || e);
    }
  }
  return map;
}

async function liveInfoSnapshot() {
  const url = "http://127.0.0.1:8000/api/v1/ielts/info";
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(8000) });
    const text = await res.text();
    let parsed = null;
    try {
      parsed = JSON.parse(text);
    } catch {
      /* keep raw */
    }
    return { url, http_status: res.status, ok: res.ok, bytes: Buffer.byteLength(text), body: parsed ?? text.slice(0, 20000) };
  } catch (e) {
    return { url, error: String(e.message || e) };
  }
}

async function writeJsonAtomic(file, obj) {
  await fsp.mkdir(path.dirname(file), { recursive: true });
  const tmp = `${file}.tmp-${process.pid}`;
  await fsp.writeFile(tmp, JSON.stringify(obj, null, 2), "utf8");
  await fsp.rename(tmp, file);
}

// ── main ─────────────────────────────────────────────────────────────────────
const startedAt = new Date();
await fsp.mkdir(BACKUP_DIR, { recursive: true });

// 1) 备份将修改文件
const backups = [];
for (const rel of MODIFY_LIST) {
  const src = path.join(WORKSPACE, rel);
  const st = statSafe(src);
  if (!st.exists) {
    backups.push({ rel, backed_up: false, reason: "missing" });
    continue;
  }
  const dst = path.join(BACKUP_DIR, rel);
  await fsp.mkdir(path.dirname(dst), { recursive: true });
  await fsp.copyFile(src, dst);
  const sha = await sha256File(src);
  backups.push({ rel, backed_up: true, bytes: st.bytes, sha256: sha });
}

// 2) 两副本文件级差异
const dstMap = await hashMapForDir(IELTS_API_DIR);
const srcMap = await hashMapForDir(OTHER_COPY_DIR);
const allNames = [...new Set([...Object.keys(dstMap), ...Object.keys(srcMap)])].sort();
const copyDiff = { both_equal: [], both_differ: [], dst_only: [], src_only: [] };
for (const name of allNames) {
  const inDst = name in dstMap;
  const inSrc = name in srcMap;
  if (inDst && inSrc) {
    (dstMap[name] === srcMap[name] ? copyDiff.both_equal : copyDiff.both_differ).push(name);
  } else if (inDst) copyDiff.dst_only.push(name);
  else copyDiff.src_only.push(name);
}

// 3) 受保护文件基线
const protectedDirs = [];
for (const rel of PROTECTED_DIRS) {
  const abs = path.join(WORKSPACE, rel);
  const files = [];
  for (const f of walkFiles(abs)) {
    const p = path.join(abs, f);
    const st = statSafe(p);
    let sha = null;
    try {
      sha = await sha256File(p);
    } catch (e) {
      sha = "ERROR:" + String(e.message || e);
    }
    files.push({ rel: `${rel}/${f}`, bytes: st.bytes, mtime_iso: st.mtime_iso, sha256: sha });
  }
  protectedDirs.push({ dir: rel, file_count: files.length, files });
}
const protectedDb = [];
for (const rel of PROTECTED_DB_FILES) {
  const abs = path.join(WORKSPACE, rel);
  const st = statSafe(abs);
  if (!st.exists) {
    protectedDb.push({ rel, exists: false });
    continue;
  }
  let sha = null;
  try {
    sha = await sha256File(abs);
  } catch (e) {
    sha = "ERROR:" + String(e.message || e);
  }
  protectedDb.push({ rel, exists: true, bytes: st.bytes, mtime_iso: st.mtime_iso, sha256: sha });
}

const protectedBaseline = {
  generated_at_utc: new Date().toISOString(),
  run_id: RUN_ID,
  note: "只登记清单/SHA256/大小/mtime；不读取数据库内容、不扫描密钥。运行中的数据库可能被服务独立写入，hash 变化不直接归因本任务。",
  protected_dirs: protectedDirs,
  protected_db_files: protectedDb,
  examdata_git: gitStatus(EXAMDATA_DIR),
};

// 4) 环境与网关信息
const venvPython = path.join(EXAMDATA_DIR, ".venv", "Scripts", "python.exe");
const env = {
  EXAMDATA_IELTS_DATA_DIR: process.env.EXAMDATA_IELTS_DATA_DIR ?? null,
  EXAMDATA_IELTS_DIR: process.env.EXAMDATA_IELTS_DIR ?? null,
  EXAMDATA_NODE: process.env.EXAMDATA_NODE ?? null,
  EXAMDATA_DATA_DIR: process.env.EXAMDATA_DATA_DIR ?? null,
  EXAMDATA_IELTS_TIMEOUT: process.env.EXAMDATA_IELTS_TIMEOUT ?? null,
};
const baseline = {
  run_id: RUN_ID,
  started_at_utc: startedAt.toISOString(),
  workspace_root: WORKSPACE,
  data_dir: DATA_DIR,
  run_dir: RUN_DIR,
  tool: "ielts-api/tools/baseline.mjs",
  versions: {
    node: cmdRun("node", ["--version"]).stdout,
    npm: (process.platform === "win32" ? cmdRun("cmd", ["/c", "npm --version"]).stdout : cmdRun("npm", ["--version"]).stdout),
    python_system: cmdRun("python", ["--version"]).stdout || cmdRun("python", ["--version"]).stderr,
    python_examdata_venv: fs.existsSync(venvPython) ? cmdRun(venvPython, ["--version"]).stdout : null,
  },
  env_non_sensitive: env,
  gateway_dir: {
    resolved: process.env.EXAMDATA_IELTS_DIR || IELTS_API_DIR,
    exists: fs.existsSync(process.env.EXAMDATA_IELTS_DIR || IELTS_API_DIR),
  },
  git: {
    workspace_root: gitStatus(WORKSPACE),
    ielts_api: gitStatus(IELTS_API_DIR),
    other_copy: gitStatus(OTHER_COPY_DIR),
    examdata: gitStatus(EXAMDATA_DIR),
  },
  shared_files_sha256: {
    dst_dir: IELTS_API_DIR,
    src_dir: OTHER_COPY_DIR,
    dst_count: Object.keys(dstMap).length,
    src_count: Object.keys(srcMap).length,
    both_equal: copyDiff.both_equal,
    both_differ: copyDiff.both_differ,
    dst_only: copyDiff.dst_only,
    src_only: copyDiff.src_only,
    dst_map: dstMap,
    src_map: srcMap,
  },
  backups,
  live_8000_info: noLive ? { skipped: true } : await liveInfoSnapshot(),
  finished_at_utc: new Date().toISOString(),
};

await writeJsonAtomic(path.join(RUN_DIR, "baseline.json"), baseline);
await writeJsonAtomic(path.join(RUN_DIR, "protected-files-baseline.json"), protectedBaseline);

const summary = {
  ok: true,
  run_id: RUN_ID,
  run_dir: RUN_DIR,
  baseline: path.join(RUN_DIR, "baseline.json"),
  protected_baseline: path.join(RUN_DIR, "protected-files-baseline.json"),
  backups: backups.filter((b) => b.backed_up).length,
  backups_missing: backups.filter((b) => !b.backed_up).map((b) => b.rel),
  copy_diff: {
    both_equal: copyDiff.both_equal.length,
    both_differ: copyDiff.both_differ.length,
    dst_only: copyDiff.dst_only,
    src_only: copyDiff.src_only,
  },
  live_8000: noLive ? "skipped" : (baseline.live_8000_info.http_status ?? baseline.live_8000_info.error),
};
console.log(JSON.stringify(summary, null, 2));
