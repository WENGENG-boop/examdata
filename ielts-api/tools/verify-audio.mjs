#!/usr/bin/env node
/**
 * verify-audio.mjs — S09 听力音频目录构建 / 下载 / 探测 / 身份状态推进
 *
 * 用法：
 *   node tools/verify-audio.mjs --build
 *       从 tmp_audit_ielts/maslow_tree.json 提取 maslow 1–20 册覆盖 + cam21 21 册模式，
 *       构建候选目录（全部 candidate），写 <runDir>/audio/audio-catalog.json 与覆盖清单。
 *   node tools/verify-audio.mjs                       # 离线：只处理有本地样本的记录（复用本地音频）
 *   node tools/verify-audio.mjs --priority book1t2,book3t2 --download
 *       展开 bookNtT（四 Part）或 bookNtTpP（单 Part），实际下载 → magic/ffprobe/解码 → available。
 *   node tools/verify-audio.mjs --ids audio:... --download
 *   node tools/verify-audio.mjs --range-probe <url>
 *       单 URL 300 字节 Range 探测（校验 206 + Content-Range），只记录不改状态。
 *   node tools/verify-audio.mjs --fetch-cam21-pages
 *       拉取 cam21 t1..t4-listening.html（raw 落盘），提取 audioTracks/TRANSCRIPTS，
 *       与本地副本及仓库 tree blob sha 比对，写 cam21-page-bindings.json / cam21-transcripts.json。
 *   node tools/verify-audio.mjs --tree-check
 *       对 available/verified 记录计算 git blob sha1，与 maslow/cam21 tree 期望 sha 比对，写 rec.tree_blob。
 *   node tools/verify-audio.mjs --mark-cam21
 *       依据页面绑定 + tree blob 内容哈希，把 cam21 16 段推进为 verified（official_binding）。
 *
 * 状态语义见 audio-catalog.mjs：candidate → available（字节+解码通过）→ verified（身份证据）。
 * maslow verified 由 S10（ASR/原文锚点）提供；cam21 由官方页面绑定 + 仓库 blob 内容哈希提供。
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import { spawnSync } from "node:child_process";

import { createFetcher, SourceBlockedError, BudgetExceededError } from "../fetch-source.mjs";
import { resolveDataDir, runDir, writeJsonAtomic, readJson, WORKSPACE_ROOT } from "../data-store.mjs";
import {
  buildAudioCatalog, applyProbe, sniffAudio, validateRangeProbe, summarizeAudioCatalog,
  markVerified, gitBlobSha1Buffer, parseCam21ListeningPage, transcriptQNums, transcriptPlainText, pad2,
  AUDIO_STATUS, AUDIO_SCOPE, CHECKPOINT_SCHEMA,
  MASLOW, CAM21, partIdentity, audioIdFor,
} from "../audio-catalog.mjs";

const DEFAULT_RUN_ID = "20261003T140007Z-repair";

// ---------------------------------------------------------------- args

function parseArgs(argv) {
  const opts = {
    runId: DEFAULT_RUN_ID, catalog: null, build: false, rebuild: false, download: false,
    concurrency: 2, limit: 0, priority: [], ids: [], rangeProbe: null, reprobe: false, help: false,
    fetchCam21Pages: false, treeCheck: false, markCam21: false, reusePages: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    switch (a) {
      case "--run-id": opts.runId = argv[++i]; break;
      case "--catalog": opts.catalog = argv[++i]; break;
      case "--build": opts.build = true; break;
      case "--rebuild": opts.rebuild = true; break;
      case "--download": opts.download = true; break;
      case "--concurrency": opts.concurrency = +argv[++i]; break;
      case "--limit": opts.limit = +argv[++i]; break;
      case "--priority": opts.priority.push(...String(argv[++i] || "").split(",").map((s) => s.trim()).filter(Boolean)); break;
      case "--ids": opts.ids.push(...String(argv[++i] || "").split(",").map((s) => s.trim()).filter(Boolean)); break;
      case "--range-probe": opts.rangeProbe = argv[++i]; break;
      case "--reprobe": opts.reprobe = true; break;
      case "--fetch-cam21-pages": opts.fetchCam21Pages = true; break;
      case "--tree-check": opts.treeCheck = true; break;
      case "--mark-cam21": opts.markCam21 = true; break;
      case "--reuse-pages": opts.reusePages = true; break;
      case "--help": case "-h": opts.help = true; break;
      default: throw new Error("unknown arg: " + a);
    }
  }
  return opts;
}

function usage() {
  console.log(`verify-audio.mjs — S09 听力音频目录/下载/探测/身份核验

  --build                 构建候选目录（maslow 1–20 + cam21）并写覆盖清单
  --rebuild               目录已存在时强制重建（丢弃既有探测进度）
  --download              对选中记录实际下载（默认只复用本地样本）
  --priority <list>       book1t2,book3t2,book20t2p4,book21t1 逗号分隔
  --ids <list>            直接指定 audio_id（audio:cambridge:...）
  --limit N               最多处理 N 条
  --concurrency N         并发（默认 2；同来源内部串行）
  --reprobe               已 available/verified 的记录也重跑
  --range-probe <url>     单 URL Range 探测（只记录不改状态）
  --fetch-cam21-pages     拉取 cam21 听力页面并提取 audioTracks/TRANSCRIPTS 绑定
  --reuse-pages           配合 --fetch-cam21-pages：复用已落盘 raw 重算（不耗网络）
  --tree-check            下载字节的 git blob sha1 与仓库 tree 期望 sha 比对
  --mark-cam21            页面绑定 + tree blob 匹配 → cam21 记录 verified
  --run-id <id>           运行目录（默认 ${DEFAULT_RUN_ID}）
  --catalog <path>        目录文件路径（默认 <runDir>/audio/audio-catalog.json）`);
}

// ---------------------------------------------------------------- ffmpeg 发现

function findFfmpeg() {
  const tryPair = (dir) => {
    const ffprobe = dir ? path.join(dir, process.platform === "win32" ? "ffprobe.exe" : "ffprobe") : "ffprobe";
    const ffmpeg = dir ? path.join(dir, process.platform === "win32" ? "ffmpeg.exe" : "ffmpeg") : "ffmpeg";
    const r = spawnSync(ffprobe, ["-version"], { encoding: "utf8", timeout: 20000 });
    if (r.status !== 0) return null;
    const r2 = spawnSync(ffmpeg, ["-version"], { encoding: "utf8", timeout: 20000 });
    if (r2.status !== 0) return null;
    return { ffprobe, ffmpeg, dir: dir || "PATH" };
  };
  const cands = [];
  for (const env of ["EXAMDATA_FFMPEG_DIR", "FFMPEG_DIR"]) {
    if (process.env[env]) cands.push(process.env[env]);
  }
  cands.push(null);
  const wingetBase = path.join(os.homedir(), "AppData", "Local", "Microsoft", "WinGet", "Packages");
  try {
    for (const d of fs.readdirSync(wingetBase)) {
      if (!/^Gyan\.FFmpeg/i.test(d)) continue;
      const base = path.join(wingetBase, d);
      for (const sub of fs.readdirSync(base)) {
        const b = path.join(base, sub, "bin");
        if (fs.existsSync(b)) cands.push(b);
      }
    }
  } catch { /* winget 不存在 */ }
  cands.push("C:/ffmpeg/bin", "/usr/bin", "/usr/local/bin");
  for (const c of cands) {
    const found = tryPair(c);
    if (found) return found;
  }
  return null;
}

// ---------------------------------------------------------------- 文件探测

/** magic 嗅探 + ffprobe 元数据 + 全文件解码。同步执行；返回 applyProbe 可直接用的字段。 */
function probeAudioFile(filePath, bins) {
  const base = { magic_ok: null, html: null, reason: null, container: null, codec: null, sample_rate: null, channels: null, duration_sec: null, decode_ok: null, decode_error: null, bytes: null };
  let bytes = 0;
  try { bytes = fs.statSync(filePath).size; } catch (e) { return { ...base, reason: "stat_failed", decode_ok: false, decode_error: String(e.message || e) }; }
  base.bytes = bytes;
  if (!bytes) return { ...base, magic_ok: false, reason: "zero_length", decode_ok: false, decode_error: "zero_length" };

  const fd = fs.openSync(filePath, "r");
  const head = Buffer.alloc(Math.min(65536, bytes));
  try { fs.readSync(fd, head, 0, head.length, 0); } finally { fs.closeSync(fd); }
  const sniff = sniffAudio(head.subarray(0, 64));
  if (!sniff.ok) {
    return { ...base, magic_ok: false, html: sniff.html, reason: sniff.reason, decode_ok: false, decode_error: sniff.reason };
  }
  base.magic_ok = true;
  base.html = false;
  base.container = sniff.container;

  const pr = spawnSync(bins.ffprobe, ["-v", "error", "-print_format", "json", "-show_format", "-show_streams", filePath], { encoding: "utf8", maxBuffer: 8 * 1024 * 1024, timeout: 120000 });
  if (pr.status !== 0 || !pr.stdout) {
    return { ...base, reason: "ffprobe_failed", decode_ok: false, decode_error: String(pr.stderr || pr.error || "ffprobe failed").slice(0, 400) };
  }
  let info = null;
  try { info = JSON.parse(pr.stdout); } catch (e) {
    return { ...base, reason: "ffprobe_bad_json", decode_ok: false, decode_error: String(e.message || e) };
  }
  const astream = (info.streams || []).find((s) => s.codec_type === "audio");
  if (!astream) {
    return { ...base, reason: "no_audio_stream", decode_ok: false, decode_error: "no audio stream in container" };
  }
  base.codec = astream.codec_name || null;
  base.sample_rate = astream.sample_rate ? +astream.sample_rate : null;
  base.channels = astream.channels ?? null;
  const dur = parseFloat((info.format && info.format.duration) || astream.duration || "0");
  base.duration_sec = Number.isFinite(dur) && dur > 0 ? Math.round(dur * 1000) / 1000 : null;

  const dr = spawnSync(bins.ffmpeg, ["-v", "error", "-i", filePath, "-map", "0:a:0", "-f", "null", "-"], { encoding: "utf8", maxBuffer: 16 * 1024 * 1024, timeout: 300000 });
  base.decode_ok = dr.status === 0;
  const stderr = String(dr.stderr || "").trim();
  if (!base.decode_ok) {
    base.decode_error = (stderr || `ffmpeg exit ${dr.status}`).slice(0, 400);
  } else if (stderr) {
    base.decode_warnings = stderr.slice(0, 400);
  }
  return base;
}

// ---------------------------------------------------------------- 本地样本

const LOCAL_SAMPLES = [
  { file: "tmp_audit_ielts/audio/maslow_b01_t1_p1.mp3", audio_id: audioIdFor(partIdentity(1, 1, 1), AUDIO_SCOPE.PART), url: MASLOW.raw + "ielts_listening/book_01/test_1_part_1.mp3", via: "raw" },
  { file: "tmp_audit_ielts/cam21/audio_T1_Section_1.mp3", audio_id: audioIdFor(partIdentity(21, 1, 1), AUDIO_SCOPE.PART), url: CAM21.raw + "audio/C21T1_Section_1.mp3", via: "raw" },
  { file: "tmp_audit_ielts/cam21/audio_T3_Section_4.mp3", audio_id: audioIdFor(partIdentity(21, 3, 4), AUDIO_SCOPE.PART), url: CAM21.raw + "audio/C21T3_Section_4.mp3", via: "raw" },
  { file: "tmp_audit_ielts/raw_audio.mp3", audio_id: audioIdFor(partIdentity(21, 1, 1), AUDIO_SCOPE.PART), url: null, via: "local" },
  { file: "tmp_audit_ielts/cdn_audio.mp3", audio_id: audioIdFor(partIdentity(21, 1, 1), AUDIO_SCOPE.PART), url: null, via: "local" },
];

function localSamplesFor(audioId) {
  return LOCAL_SAMPLES.filter((s) => s.audio_id === audioId);
}

// ---------------------------------------------------------------- 覆盖提取

function extractMaslowCoverage(treePath) {
  const raw = JSON.parse(fs.readFileSync(treePath, "utf8"));
  const items = [];
  const walk = (nodes) => {
    for (const n of nodes || []) {
      if (n.type === "blob") items.push({ path: n.path, size: n.size });
      walk(n.tree);
    }
  };
  walk(raw.tree);
  const mp3 = items.filter((i) => i.path.endsWith(".mp3"));
  const parts = [];
  const full = [];
  for (const i of mp3) {
    let m = /^ielts_listening\/book_(\d+)\/test_(\d+)_part_(\d+)\.mp3$/.exec(i.path);
    if (m) { parts.push({ book: +m[1], test: +m[2], part: +m[3], path: i.path, bytes: i.size }); continue; }
    m = /^ielts_listening\/book_(\d+)\/test_(\d+)\.mp3$/.exec(i.path);
    if (m) full.push({ book: +m[1], test: +m[2], path: i.path, bytes: i.size });
  }
  const present = new Set(parts.map((p) => `${p.book}:${p.test}:${p.part}`));
  const missing_parts = [];
  for (let b = 1; b <= 20; b++) for (let t = 1; t <= 4; t++) for (let p = 1; p <= 4; p++) {
    if (!present.has(`${b}:${t}:${p}`)) missing_parts.push({ book: b, test: t, part: p });
  }
  const presentFull = new Set(full.map((p) => `${p.book}:${p.test}`));
  const missing_full = [];
  for (let b = 1; b <= 20; b++) for (let t = 1; t <= 4; t++) {
    if (!presentFull.has(`${b}:${t}`)) missing_full.push({ book: b, test: t });
  }
  return { raw, parts, full, missing_parts, missing_full };
}

// ---------------------------------------------------------------- 选中展开

function expandPriority(tokens) {
  const ids = [];
  for (const tk of tokens) {
    const m = /^book(\d+)t(\d+)(?:p(\d+))?$/i.exec(tk);
    if (!m) throw new Error("bad priority token (expect bookNtT / bookNtTpP): " + tk);
    const book = +m[1];
    const test = +m[2];
    const parts = m[3] ? [+m[3]] : [1, 2, 3, 4];
    for (const p of parts) ids.push(audioIdFor(partIdentity(book, test, p), AUDIO_SCOPE.PART));
  }
  return [...new Set(ids)];
}

// ---------------------------------------------------------------- tree / 绑定辅助

function sha256File(filePath) {
  const h = crypto.createHash("sha256");
  const fd = fs.openSync(filePath, "r");
  const buf = Buffer.alloc(1 << 20);
  try {
    for (;;) {
      const n = fs.readSync(fd, buf, 0, buf.length, null);
      if (!n) break;
      h.update(buf.subarray(0, n));
    }
  } finally { fs.closeSync(fd); }
  return h.digest("hex");
}

function relTo(root, p) {
  return path.relative(root, p).replace(/\\/g, "/");
}

/** 由记录推导仓库路径（用于 tree blob 比对） */
function sourcePathForRecord(rec) {
  const m = /^cambridge:(\d+):shared:listening:(\d+)(?::P(\d+))?$/.exec(rec.identity);
  if (!m) return null;
  const book = +m[1];
  const test = +m[2];
  const part = m[3] ? +m[3] : null;
  if (rec.source === "maslow") {
    return part
      ? { source: "maslow", path: `ielts_listening/book_${pad2(book)}/test_${test}_part_${part}.mp3` }
      : { source: "maslow", path: `ielts_listening/book_${pad2(book)}/test_${test}.mp3` };
  }
  if (rec.source === "cam21") {
    return part ? { source: "cam21", path: `audio/C21T${test}_Section_${part}.mp3` } : null;
  }
  return null;
}

function loadTreeIndex(treePath) {
  const raw = JSON.parse(fs.readFileSync(treePath, "utf8"));
  const map = new Map();
  const walk = (nodes) => {
    for (const n of nodes || []) {
      if (n.type === "blob") map.set(n.path, { sha: n.sha, size: n.size });
      walk(n.tree);
    }
  };
  walk(raw.tree);
  return { map, sha: raw.sha || null, truncated: !!raw.truncated, file: relTo(WORKSPACE_ROOT, treePath) };
}

const MASLOW_TREE = path.join(WORKSPACE_ROOT, "tmp_audit_ielts", "maslow_tree.json");
const CAM21_TREE = path.join(WORKSPACE_ROOT, "tmp_audit_ielts", "cam21", "tree.json");
const CAM21_LOCAL_PAGES = path.join(WORKSPACE_ROOT, "tmp_audit_ielts", "cam21");

// ---------------------------------------------------------------- 模式：cam21 页面绑定

async function runFetchCam21Pages({ fetcher, catalog, dataRoot, audioDir, writeCheckpointSummary, reuseStored = false }) {
  const bindingsPath = path.join(audioDir, "cam21-page-bindings.json");
  const transcriptsPath = path.join(audioDir, "cam21-transcripts.json");
  const prevBindings = reuseStored && fs.existsSync(bindingsPath) ? readJson(bindingsPath) : null;

  let treeIndex = null;
  if (fs.existsSync(CAM21_TREE)) treeIndex = loadTreeIndex(CAM21_TREE);
  else console.error("WARN: 缺少 " + CAM21_TREE + "，repo_blob 比对将记 null");

  const durByPart = new Map();
  for (const r of catalog.records) {
    if (r.source !== "cam21" || r.scope !== AUDIO_SCOPE.PART) continue;
    const m = /:listening:(\d+):P(\d+)$/.exec(r.identity);
    if (m) durByPart.set(`${+m[1]}:${+m[2]}`, r.duration_sec ?? null);
  }

  const pages = {};
  const transcriptsOut = {
    schema: "ielts.cam21-transcripts/1",
    generated_at: new Date().toISOString(),
    timestamp_status: "candidate_unvalidated",
    note: "页面内嵌转录的 t 字段仅为候选时间戳；必须经 S10 时钟校验/对齐后才可用于题级区间",
    source: CAM21.name,
    pages: {},
  };

  for (let t = 1; t <= 4; t++) {
    const rel = `t${t}-listening.html`;
    const url = CAM21.raw + rel;
    let stored;
    const prev = prevBindings && prevBindings.pages && prevBindings.pages[String(t)];
    const prevBody = prev && prev.body_path ? path.join(dataRoot, prev.body_path) : null;
    if (reuseStored && prevBody && fs.existsSync(prevBody)) {
      const actualSha = sha256File(prevBody);
      if (actualSha !== prev.stored_sha256) throw new Error(`reuse integrity failed for ${rel}: ${actualSha} != ${prev.stored_sha256}`);
      stored = { sha256: prev.stored_sha256, bodyPath: prevBody, metaPath: prev.meta_path ? path.join(dataRoot, prev.meta_path) : null, bytes: fs.statSync(prevBody).size, status: prev.status ?? null, deduped: true, reused_local: true };
      console.error(`page t${t}: reuse stored raw ${prev.body_path} (sha=${prev.stored_sha256.slice(0, 12)})`);
    } else {
      stored = await fetcher.fetchToRaw({ source: "cam21", url, parserVersion: "cam21-listening-page/1" });
    }
    const bodyBuf = fs.readFileSync(stored.bodyPath);
    const parsed = parseCam21ListeningPage(bodyBuf.toString("utf8"));

    const localPath = path.join(CAM21_LOCAL_PAGES, rel);
    let local_sha256 = null;
    let local_match = null;
    if (fs.existsSync(localPath)) {
      local_sha256 = sha256File(localPath);
      local_match = local_sha256 === stored.sha256;
    }

    const repoExpected = treeIndex ? treeIndex.map.get(rel) : null;
    const repoComputed = gitBlobSha1Buffer(bodyBuf);
    const sections = {};
    for (const [k, s] of Object.entries(parsed.sections || {})) {
      const dur = durByPart.get(`${t}:${+k}`) ?? null;
      sections[k] = {
        ...s,
        catalog_duration_sec: dur,
        clock_delta_sec: dur != null && s.last_t != null ? Math.round((dur - s.last_t) * 1000) / 1000 : null,
        clock_sane: dur != null && s.last_t != null ? s.last_t <= dur + 2 : null,
      };
    }
    pages[t] = {
      url,
      status: stored.status ?? null,
      bytes: stored.bytes,
      stored_sha256: stored.sha256,
      body_path: relTo(dataRoot, stored.bodyPath),
      meta_path: relTo(dataRoot, stored.metaPath),
      deduped: !!stored.deduped,
      local_copy: relTo(WORKSPACE_ROOT, localPath),
      local_sha256,
      local_match,
      repo_blob_expected_sha1: repoExpected ? repoExpected.sha : null,
      repo_blob_expected_size: repoExpected ? repoExpected.size : null,
      repo_blob_computed_sha1: repoComputed,
      repo_blob_match: repoExpected ? (repoComputed === repoExpected.sha && stored.bytes === repoExpected.size) : null,
      tree_sha: treeIndex ? treeIndex.sha : null,
      audio_tracks: parsed.audio_tracks,
      sections,
      warnings: parsed.warnings,
    };
    transcriptsOut.pages[t] = { page_sha256: stored.sha256, sections: {} };
    for (const [k, lines] of Object.entries(parsed.transcripts || {})) {
      transcriptsOut.pages[t].sections[k] = (lines || []).map((l) => ({
        sp: l.sp || "",
        t: typeof l.t === "number" ? l.t : null,
        text: transcriptPlainText(l.h),
        q: transcriptQNums(l.h),
      }));
    }
    const secKeys = Object.keys(parsed.sections || {});
    console.log(`page t${t}: bytes=${stored.bytes} sha=${stored.sha256.slice(0, 12)} local_match=${local_match} repo_blob_match=${pages[t].repo_blob_match} sections=[${secKeys.join(",")}] warnings=${parsed.warnings.join(";") || "-"}`);
    for (const k of secKeys) {
      const s = sections[k];
      console.log(`  s${k}: lines=${s.lines} last_t=${s.last_t} dur=${s.catalog_duration_sec} clock_delta=${s.clock_delta_sec} q=[${s.q_numbers.join(",")}]`);
    }
  }

  writeJsonAtomic(bindingsPath, {
    schema: "ielts.cam21-page-bindings/1",
    generated_at: new Date().toISOString(),
    source: CAM21.name,
    tree: relTo(WORKSPACE_ROOT, CAM21_TREE),
    tree_sha: treeIndex ? treeIndex.sha : null,
    note: "页面 audioTracks 为官方题本绑定；repo_blob_match 表示页面字节与仓库 tree blob sha 一致",
    pages,
  });
  writeJsonAtomic(transcriptsPath, transcriptsOut);
  writeCheckpointSummary("fetch-cam21-pages", {
    cam21_pages: Object.fromEntries(Object.entries(pages).map(([t, p]) => [t, { sha256: p.stored_sha256, local_match: p.local_match, repo_blob_match: p.repo_blob_match }])),
  });
  console.log("bindings:    " + bindingsPath);
  console.log("transcripts: " + transcriptsPath);
}

// ---------------------------------------------------------------- 模式：tree blob 比对

function runTreeCheck({ catalog, catalogPath, writeCheckpointSummary }) {
  const trees = {};
  for (const [label, tp] of [["maslow", MASLOW_TREE], ["cam21", CAM21_TREE]]) {
    if (!fs.existsSync(tp)) throw new Error("missing tree file: " + tp);
    trees[label] = loadTreeIndex(tp);
  }
  const stats = { checked: 0, matched: 0, mismatched: 0, missing_file: 0, no_tree_entry: 0, not_applicable: 0 };
  catalog.issues = (catalog.issues || []).filter((i) => i.kind !== "tree_blob_mismatch");
  for (const rec of catalog.records) {
    if (rec.status !== AUDIO_STATUS.AVAILABLE && rec.status !== AUDIO_STATUS.VERIFIED) { stats.not_applicable++; continue; }
    const src = sourcePathForRecord(rec);
    const tree = src ? trees[src.source] : null;
    const entry = src && tree ? tree.map.get(src.path) : null;
    if (!src || !tree) { stats.no_tree_entry++; rec.tree_blob = { note: "no_source_path", checked_at: new Date().toISOString() }; continue; }
    if (!entry) {
      stats.no_tree_entry++;
      rec.tree_blob = { source_path: src.path, tree: tree.file, expected_sha: null, computed_sha: null, match: null, note: "no_tree_entry", checked_at: new Date().toISOString() };
      continue;
    }
    if (!rec.file_path || !fs.existsSync(rec.file_path)) {
      stats.missing_file++;
      rec.tree_blob = { source_path: src.path, tree: tree.file, expected_sha: entry.sha, expected_size: entry.size, computed_sha: null, match: null, note: "file_missing", checked_at: new Date().toISOString() };
      continue;
    }
    const buf = fs.readFileSync(rec.file_path);
    const computed = gitBlobSha1Buffer(buf);
    const match = computed === entry.sha && buf.length === entry.size;
    rec.tree_blob = {
      source_path: src.path,
      tree: tree.file,
      tree_sha: tree.sha,
      expected_sha: entry.sha,
      expected_size: entry.size,
      computed_sha: computed,
      computed_size: buf.length,
      match,
      checked_at: new Date().toISOString(),
    };
    stats.checked++;
    if (match) stats.matched++;
    else {
      stats.mismatched++;
      catalog.issues.push({ kind: "tree_blob_mismatch", severity: "high", audio_id: rec.audio_id, source_path: src.path, expected_sha: entry.sha, expected_size: entry.size, computed_sha: computed, computed_size: buf.length });
    }
  }
  catalog.meta = catalog.meta || {};
  catalog.meta.tree_check = {
    at: new Date().toISOString(),
    trees: { maslow: trees.maslow.sha, maslow_truncated: trees.maslow.truncated, cam21: trees.cam21.sha, cam21_truncated: trees.cam21.truncated },
    stats,
  };
  writeJsonAtomic(catalogPath, catalog);
  writeCheckpointSummary("tree-check", { tree_check: stats });
  console.log("tree-check: " + JSON.stringify(stats));
  if (stats.mismatched) process.exit(4);
}

// ---------------------------------------------------------------- 模式：cam21 verified

function runMarkCam21({ catalog, catalogPath, audioDir, writeCheckpointSummary }) {
  const bindingsPath = path.join(audioDir, "cam21-page-bindings.json");
  if (!fs.existsSync(bindingsPath)) {
    console.error("FATAL: 缺少 " + bindingsPath + "，先运行 --fetch-cam21-pages");
    process.exit(2);
  }
  const bindings = readJson(bindingsPath);
  const outcomes = [];
  for (const rec of catalog.records) {
    if (rec.source !== "cam21" || rec.scope !== AUDIO_SCOPE.PART) continue;
    const m = /:listening:(\d+):P(\d+)$/.exec(rec.identity);
    const test = +m[1];
    const section = +m[2];
    const expectedPath = `audio/C21T${test}_Section_${section}.mp3`;
    const reasons = [];
    if (rec.status !== AUDIO_STATUS.AVAILABLE && rec.status !== AUDIO_STATUS.VERIFIED) reasons.push("not_available:" + rec.status);
    const tb = rec.tree_blob;
    if (!tb || tb.match !== true) reasons.push("tree_blob_not_matched");
    else if (tb.source_path !== expectedPath) reasons.push("tree_blob_path_mismatch");
    const page = bindings.pages && bindings.pages[String(test)];
    if (!page) reasons.push("no_page_binding");
    else {
      if (!page.audio_tracks || page.audio_tracks[String(section)] !== expectedPath) reasons.push("page_track_mismatch");
      if (page.repo_blob_match !== true) reasons.push("page_repo_blob_mismatch");
    }
    if (reasons.length) {
      outcomes.push({ audio_id: rec.audio_id, ok: false, reasons });
      continue;
    }
    const sec = page.sections && page.sections[String(section)];
    const res = markVerified(catalog, rec.audio_id, {
      refs: [
        {
          kind: "official_binding",
          ref: `cam21-page:t${test}-listening.html#audioTracks.${section}`,
          note: `page sha256=${page.stored_sha256} local_match=${page.local_match} repo_blob_match=${page.repo_blob_match} transcript_last_t=${sec ? sec.last_t : null} catalog_dur=${sec ? sec.catalog_duration_sec : null} (内容级 ASR 抽查留 S10)`,
        },
        {
          kind: "official_binding",
          ref: `cam21-tree:${expectedPath}@${tb.tree_sha || "unknown"}`,
          note: `git blob sha1=${tb.expected_sha} 下载字节 computed sha1 匹配`,
        },
      ],
    });
    outcomes.push({ audio_id: rec.audio_id, ok: res.ok, status: res.ok ? res.record.status : null, reasons: res.ok ? [] : [res.error] });
  }
  writeJsonAtomic(catalogPath, catalog);
  const okCount = outcomes.filter((o) => o.ok).length;
  writeCheckpointSummary("mark-cam21", { mark_cam21: { ok: okCount, skipped: outcomes.length - okCount, total: outcomes.length } });
  console.log(`mark-cam21: ok=${okCount} skipped=${outcomes.length - okCount} of ${outcomes.length}`);
  for (const o of outcomes) console.log(`${o.ok ? "OK  " : "SKIP"} ${o.audio_id}${o.reasons.length ? " " + o.reasons.join(",") : ""}`);
}

// ---------------------------------------------------------------- main

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (opts.help) { usage(); return; }

  const dataRoot = resolveDataDir();
  const rDir = runDir(dataRoot, opts.runId);
  const audioDir = path.join(rDir, "audio");
  fs.mkdirSync(audioDir, { recursive: true });
  const catalogPath = opts.catalog || path.join(audioDir, "audio-catalog.json");
  const cpPath = path.join(audioDir, "verify-checkpoint.json");
  const coveragePath = path.join(audioDir, "maslow-audio-coverage.json");
  const rangeProbesPath = path.join(audioDir, "range-probes.jsonl");

  const fetcher = createFetcher({ root: dataRoot, runId: opts.runId });
  console.error(`data root: ${dataRoot}`);
  console.error(`catalog:   ${catalogPath}`);

  // ---------- range probe 模式 ----------
  if (opts.rangeProbe) {
    const url = opts.rangeProbe;
    const source = /EnglishLearning/i.test(url) ? "maslow" : /cambridge-21/i.test(url) ? "cam21" : "probe";
    const r = await fetcher.request({ source, url, headers: { Range: "bytes=0-299" } });
    const cr = r.headers["content-range"] || r.headers["Content-Range"] || null;
    const validation = validateRangeProbe({ status: r.status, content_range: cr, bytes_len: r.body.length });
    const sniff = sniffAudio(r.body.subarray(0, 64));
    const entry = {
      at: new Date().toISOString(), url, source, status: r.status,
      content_type: r.content_type || null, content_range: cr,
      bytes_len: r.body.length, validation, sniff,
    };
    fs.appendFileSync(rangeProbesPath, JSON.stringify(entry) + "\n");
    console.log(JSON.stringify(entry, null, 2));
    if (!validation.ok) process.exit(4);
    return;
  }

  // ---------- build ----------
  let catalog = readJson(catalogPath);
  if (opts.build || !catalog) {
    if (catalog && !opts.rebuild && opts.build) {
      console.error("catalog 已存在；--build 未加 --rebuild，保持现有进度不动。");
    } else {
      const treePath = path.join(WORKSPACE_ROOT, "tmp_audit_ielts", "maslow_tree.json");
      if (!fs.existsSync(treePath)) {
        console.error(`FATAL: 缺少 ${treePath}，无法提取 maslow 覆盖。`);
        process.exit(2);
      }
      const cov = extractMaslowCoverage(treePath);
      const cam21List = [];
      for (let t = 1; t <= 4; t++) for (let s = 1; s <= 4; s++) cam21List.push({ test: t, section: s });
      catalog = buildAudioCatalog({
        maslowParts: cov.parts.map((p) => ({ book: p.book, test: p.test, part: p.part })),
        maslowFull: cov.full.map((p) => ({ book: p.book, test: p.test })),
        cam21: cam21List,
        meta: {
          run_id: opts.runId,
          built_at: new Date().toISOString(),
          maslow_tree: "tmp_audit_ielts/maslow_tree.json",
          maslow_tree_sha: cov.raw.sha || null,
          maslow_tree_truncated: !!cov.raw.truncated,
          sources: { maslow: MASLOW.name, cam21: CAM21.name },
          note: "book21 听力由 cam21 仓库提供；maslow 覆盖 book 1–20",
        },
      });
      writeJsonAtomic(catalogPath, catalog);
      const coverage = {
        schema: "ielts.audio-source-coverage/1",
        extracted_from: "tmp_audit_ielts/maslow_tree.json",
        extracted_at: new Date().toISOString(),
        tree_sha: cov.raw.sha || null,
        tree_truncated: !!cov.raw.truncated,
        maslow: {
          parts_present: cov.parts.length,
          full_present: cov.full.length,
          missing_parts: cov.missing_parts,
          missing_full: cov.missing_full,
          parts: cov.parts,
          full: cov.full,
        },
        cam21: {
          source: CAM21.name,
          candidates: cam21List,
          note: "候选模式 audio/C21T{test}_Section_{section}.mp3；存在性由下载探测确认",
        },
        book_21_note: "maslow 无 book_21；剑21 听力音频来源为 cam21 仓库",
      };
      writeJsonAtomic(coveragePath, coverage);
      const s = summarizeAudioCatalog(catalog);
      console.log(`built catalog: records=${s.records} by_source=${JSON.stringify(s.by_source)}`);
      console.log(`maslow parts=${cov.parts.length} (missing ${cov.missing_parts.length}) full=${cov.full.length} cam21 candidates=${cam21List.length}`);
      console.log(`coverage: ${coveragePath}`);
    }
  }

  if (!catalog) {
    console.error("FATAL: 无目录可用。先运行 --build。");
    process.exit(2);
  }

  // ---------- 目录级 checkpoint 摘要（供身份核验模式使用） ----------
  function writeCheckpointSummary(mode, extra = {}) {
    const s = summarizeAudioCatalog(catalog);
    const cp = {
      schema: CHECKPOINT_SCHEMA,
      run_id: opts.runId,
      updated_at: new Date().toISOString(),
      catalog_path: path.relative(dataRoot, catalogPath).replace(/\\/g, "/"),
      mode,
      summary: { records: s.records, by_status: s.by_status, derived_parts: s.derived_parts, issues: s.issues, issue_kinds: s.issue_kinds },
      records: Object.fromEntries(
        catalog.records
          .filter((r) => r.status !== AUDIO_STATUS.CANDIDATE)
          .map((r) => [r.audio_id, { status: r.status, sha256: r.content_sha256, bytes: r.bytes, duration_sec: r.duration_sec, at: r.fetched_at, local_samples: r.local_samples.map((x) => x.path) }])
      ),
      ...extra,
    };
    writeJsonAtomic(cpPath, cp);
    return cp;
  }

  // ---------- 身份核验模式（不需要 ffmpeg） ----------
  if (opts.fetchCam21Pages) {
    await runFetchCam21Pages({ fetcher, catalog, dataRoot, audioDir, writeCheckpointSummary, reuseStored: opts.reusePages });
    return;
  }
  if (opts.treeCheck) {
    runTreeCheck({ catalog, catalogPath, writeCheckpointSummary });
    return;
  }
  if (opts.markCam21) {
    runMarkCam21({ catalog, catalogPath, audioDir, writeCheckpointSummary });
    return;
  }

  // ---------- 下载/探测模式需要 ffmpeg ----------
  const bins = findFfmpeg();
  if (!bins) {
    console.error("FATAL: 找不到 ffprobe/ffmpeg（设置 EXAMDATA_FFMPEG_DIR 或安装 FFmpeg）。不能在没有解码器的前提下推进 available。");
    process.exit(2);
  }
  console.error(`ffmpeg: ${bins.ffprobe} (${bins.dir})`);

  // ---------- 选中 ----------
  const explicit = opts.ids.length > 0;
  const selectedIds = explicit ? opts.ids : (opts.priority.length ? expandPriority(opts.priority) : null);
  const terminal = new Set([AUDIO_STATUS.AVAILABLE, AUDIO_STATUS.VERIFIED]);

  let queue = catalog.records.filter((r) => r.scope === AUDIO_SCOPE.PART);
  if (selectedIds) {
    const missing = [];
    queue = selectedIds.map((id) => {
      const rec = catalog.records.find((r) => r.audio_id === id);
      if (!rec) missing.push(id);
      return rec;
    }).filter(Boolean);
    if (missing.length) console.error(`WARN: 选中但目录中不存在（跳过）: ${missing.join(", ")}`);
  } else if (!opts.download) {
    queue = queue.filter((r) => localSamplesFor(r.audio_id).length > 0);
  }
  const skippedTerminal = queue.filter((r) => terminal.has(r.status) && !opts.reprobe).length;
  queue = queue.filter((r) => opts.reprobe || !terminal.has(r.status));
  if (opts.limit) queue = queue.slice(0, opts.limit);

  console.log(`selection: ${selectedIds ? (explicit ? opts.ids.length + " ids" : opts.priority.join(",")) : opts.download ? "ALL parts" : "local-samples only"}`);
  console.log(`queue=${queue.length} skipped_terminal=${skippedTerminal} download=${opts.download} concurrency=${opts.concurrency}`);

  if (!queue.length) {
    const s = summarizeAudioCatalog(catalog);
    console.log("nothing to process. by_status=" + JSON.stringify(s.by_status));
    return;
  }

  let processedCount = 0;
  let stop = false;
  const outcomes = [];

  function saveState() {
    writeJsonAtomic(catalogPath, catalog);
    writeCheckpointSummary("download", {
      selection: selectedIds ? selectedIds.join(",") : (opts.download ? "ALL" : "local-samples"),
      processed_this_run: processedCount,
      queue_remaining: queue.length,
    });
  }

  async function processRecord(rec) {
    const attempts = [];
    let got = false;

    // 1) 本地样本（优先复用，不耗网络预算）
    for (const s of localSamplesFor(rec.audio_id)) {
      const abs = path.join(WORKSPACE_ROOT, s.file);
      if (!fs.existsSync(abs)) { attempts.push({ local: s.file, error: { kind: "local_missing" } }); continue; }
      const stored = fetcher.reuseLocalBinary({ kind: "audio", filePath: abs, ext: "mp3" });
      const probe = probeAudioFile(stored.path, bins);
      const probeArg = {
        audio_id: rec.audio_id, sha256: stored.sha256, bytes: stored.bytes,
        file_path: stored.path, fetched_at: new Date().toISOString(), local_sample: s.file, ...probe,
      };
      if (s.url) { probeArg.url = s.url; probeArg.via = s.via; }
      const applied = applyProbe(catalog, probeArg);
      attempts.push({ local: s.file, sha256: stored.sha256, status: applied.record ? applied.record.status : null, decode_ok: probe.decode_ok, duration_sec: probe.duration_sec });
      got = true;
    }

    // 2) 网络下载（逐 URL 回退）
    if (!got && opts.download) {
      for (const u of rec.urls) {
        try {
          const stored = await fetcher.fetchToBinary({
            source: rec.source, url: u.url, kind: "audio", ext: "mp3",
            expect: { rejectHtml: true, minBytes: 50 * 1024 },
          });
          const probe = probeAudioFile(stored.path, bins);
          const applied = applyProbe(catalog, {
            audio_id: rec.audio_id, url: u.url, via: u.via, sha256: stored.sha256,
            bytes: stored.bytes, file_path: stored.path, fetched_at: new Date().toISOString(), ...probe,
          });
          attempts.push({ url: u.url, sha256: stored.sha256, status: applied.record ? applied.record.status : null, decode_ok: probe.decode_ok, duration_sec: probe.duration_sec, bytes: stored.bytes });
          got = true;
          break;
        } catch (e) {
          const err = { kind: e.kind || e.name || "error", message: String(e.message || e).slice(0, 300), status: e.status ?? null };
          applyProbe(catalog, { audio_id: rec.audio_id, url: u.url, error: err });
          attempts.push({ url: u.url, error: err });
          if (e instanceof BudgetExceededError) { stop = true; break; }
          if (e instanceof SourceBlockedError) break;
        }
      }
    }

    if (!got && !opts.download && !localSamplesFor(rec.audio_id).length) {
      attempts.push({ skipped: "no_local_sample_and_no_download" });
    }
    return { audio_id: rec.audio_id, attempts };
  }

  async function worker() {
    while (queue.length && !stop) {
      const rec = queue.shift();
      const out = await processRecord(rec);
      processedCount++;
      outcomes.push(out);
      saveState();
      const last = out.attempts[out.attempts.length - 1] || {};
      const tag = last.error ? `FAIL ${last.error.kind}` : last.skipped ? "skip" : `${last.status || "?"} ${last.duration_sec ? Math.round(last.duration_sec) + "s" : ""} ${last.sha256 ? last.sha256.slice(0, 12) : ""}`;
      console.log(`[${processedCount}/${processedCount + queue.length}] ${rec.audio_id} → ${tag}`);
    }
  }

  const nWorkers = Math.max(1, Math.min(opts.concurrency || 2, 2));
  await Promise.all(Array.from({ length: nWorkers }, () => worker()));
  saveState();

  const s = summarizeAudioCatalog(catalog);
  console.log("---- summary ----");
  console.log("by_status: " + JSON.stringify(s.by_status));
  console.log("issues: " + s.issues + " " + JSON.stringify(s.issue_kinds));
  console.log("checkpoint: " + cpPath);
  if (stop) {
    console.error("STOPPED: 预算/来源阻断，未完成全部队列。重新运行可续跑。");
    process.exit(3);
  }
}

main().catch((e) => {
  console.error("FATAL: " + (e && e.stack || e));
  process.exit(1);
});
