// S10: alignment provider — wires the pure matcher (audio-matcher.mjs) to the
// local Python alignment tool (tools/align-audio.py) and the model environment
// under `ielts-data/tools/`.
//
// Boundaries enforced here:
//   * the tool is invoked through spawn with an argument array, never a shell;
//   * the tool must run fully offline from local model dirs (model-lock.json);
//   * audio identity is re-checked via sha256 before any ASR result is merged;
//   * when the environment is missing the result is `alignment_setup_blocked`,
//     never a fabricated alignment.

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { spawn, spawnSync } from "node:child_process";
import { resolveDataDir } from "./data-store.mjs";
import {
  ALIGN_STATUS,
  MATCHER_VERSION,
  THRESHOLD_VERSION,
  alignQuestions,
  composeConfidence,
  gateNeedsReview,
} from "./audio-matcher.mjs";

export const ALIGNMENT_SCHEMA = "ielts.alignment/1";
export const MODEL_LOCK_SCHEMA = "ielts.alignment-model-lock/1";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export function alignmentPaths({ dataDir, toolPath } = {}) {
  const root = dataDir || resolveDataDir();
  const isWin = process.platform === "win32";
  const venvPython = isWin
    ? path.join(root, "tools", "alignment-venv", "Scripts", "python.exe")
    : path.join(root, "tools", "alignment-venv", "bin", "python3");
  return {
    dataDir: root,
    python: venvPython,
    // The tool script lives next to this module; `toolPath` exists so tests
    // can point setup checks at a sandbox copy instead of the real script.
    tool: toolPath || path.join(__dirname, "tools", "align-audio.py"),
    modelsDir: path.join(root, "tools", "alignment-models"),
    modelLock: path.join(root, "tools", "alignment-models", "model-lock.json"),
    venvDir: path.join(root, "tools", "alignment-venv"),
  };
}

// ---------------------------------------------------------------------------
// Setup check
// ---------------------------------------------------------------------------

export function checkAlignmentSetup({ dataDir, verifyHashes = false, toolPath } = {}) {
  const paths = alignmentPaths({ dataDir, toolPath });
  const checks = [];
  const push = (name, ok, detail) => checks.push({ name, ok, detail });

  push("venv_python", fs.existsSync(paths.python), paths.python);
  push("tool_script", fs.existsSync(paths.tool), paths.tool);
  let toolSha256 = null;
  if (fs.existsSync(paths.tool)) {
    // A zero-byte script exits 0 silently and produces no output — treat it
    // as a blocked environment instead of a mysterious tool failure.
    const toolSize = fs.statSync(paths.tool).size;
    push("tool_script_nonempty", toolSize > 0, `size=${toolSize}`);
    if (toolSize > 0) {
      try {
        toolSha256 = sha256FileSync(paths.tool);
      } catch (err) {
        push("tool_script_readable", false, `unreadable: ${err.message}`);
      }
    }
  }

  let lock = null;
  if (fs.existsSync(paths.modelLock)) {
    try {
      lock = JSON.parse(fs.readFileSync(paths.modelLock, "utf8"));
      push("model_lock", lock?.schema === MODEL_LOCK_SCHEMA, `${paths.modelLock} schema=${lock?.schema}`);
    } catch (err) {
      push("model_lock", false, `unreadable: ${err.message}`);
    }
  } else {
    push("model_lock", false, `${paths.modelLock} missing`);
  }

  const modelCheck = (key, requiredFile) => {
    const entry = lock?.models?.[key];
    if (!entry?.dir) {
      push(`${key}_model`, false, "no entry in model-lock.json");
      return;
    }
    const dir = path.isAbsolute(entry.dir) ? entry.dir : path.join(paths.modelsDir, entry.dir);
    if (!fs.existsSync(dir)) {
      push(`${key}_model`, false, `dir missing: ${dir}`);
      return;
    }
    if (requiredFile && !fs.existsSync(path.join(dir, requiredFile))) {
      push(`${key}_model`, false, `missing ${requiredFile} in ${dir}`);
      return;
    }
    if (verifyHashes && entry.files_sha256) {
      for (const [file, sha] of Object.entries(entry.files_sha256)) {
        const fp = path.join(dir, file);
        if (!fs.existsSync(fp)) {
          push(`${key}_model`, false, `missing hashed file ${fp}`);
          return;
        }
        const actual = sha256FileSync(fp);
        if (actual !== sha) {
          push(`${key}_model`, false, `sha256 mismatch for ${fp}`);
          return;
        }
      }
    }
    push(`${key}_model`, true, dir);
  };
  modelCheck("whisper", "model.bin");
  modelCheck("align", null);

  const ok = checks.every((c) => c.ok);
  return {
    status: ok ? "ready" : "alignment_setup_blocked",
    reason: ok ? "ok" : checks.filter((c) => !c.ok).map((c) => `${c.name}: ${c.detail}`).join("; "),
    checks,
    paths,
    model_lock: lock,
    tool_sha256: toolSha256,
  };
}

function sha256FileSync(filePath) {
  const h = createHash("sha256");
  const fd = fs.openSync(filePath, "r");
  const buf = Buffer.alloc(1024 * 1024);
  try {
    for (;;) {
      const n = fs.readSync(fd, buf, 0, buf.length, null);
      if (!n) break;
      h.update(buf.subarray(0, n));
    }
  } finally {
    fs.closeSync(fd);
  }
  return h.digest("hex");
}

// ---------------------------------------------------------------------------
// Tool invocation (spawn, argument array, no shell)
// ---------------------------------------------------------------------------

export function runAligner({ pythonPath, toolPath, input, timeoutMs = 30 * 60 * 1000, tmpDir = os.tmpdir() } = {}) {
  const stamp = `${process.pid}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const inPath = path.join(tmpDir, `align-in-${stamp}.json`);
  const outPath = path.join(tmpDir, `align-out-${stamp}.json`);
  fs.writeFileSync(inPath, JSON.stringify(input, null, 1), "utf8");
  try {
    const res = spawnSync(pythonPath, [toolPath, "--input", inPath, "--out", outPath], {
      encoding: "utf8",
      timeout: timeoutMs,
      maxBuffer: 64 * 1024 * 1024,
      windowsHide: true,
    });
    const result = { exit_code: res.status, signal: res.signal, stderr: (res.stderr || "").slice(0, 4000), stdout: (res.stdout || "").slice(0, 2000) };
    if (fs.existsSync(outPath)) {
      try {
        result.output = JSON.parse(fs.readFileSync(outPath, "utf8"));
      } catch (err) {
        result.parse_error = err.message;
      }
    }
    if (res.error) result.spawn_error = String(res.error.message || res.error);
    result.ok = Boolean(result.output?.ok);
    return result;
  } finally {
    try { fs.unlinkSync(inPath); } catch { /* ignore */ }
    // outPath intentionally left for callers; callers should remove it.
  }
}

export function runAlignerAsync({ pythonPath, toolPath, input, timeoutMs = 60 * 60 * 1000, tmpDir = os.tmpdir() }) {
  const stamp = `${process.pid}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const inPath = path.join(tmpDir, `align-in-${stamp}.json`);
  const outPath = path.join(tmpDir, `align-out-${stamp}.json`);
  fs.writeFileSync(inPath, JSON.stringify(input, null, 1), "utf8");
  return new Promise((resolve) => {
    const child = spawn(pythonPath, [toolPath, "--input", inPath, "--out", outPath], {
      windowsHide: true,
    });
    let stderr = "";
    child.stderr.on("data", (d) => { stderr += d.toString(); });
    const timer = setTimeout(() => {
      try { child.kill(); } catch { /* ignore */ }
    }, timeoutMs);
    child.on("close", (code) => {
      clearTimeout(timer);
      const result = { exit_code: code, stderr: stderr.slice(0, 4000), ok: false };
      if (fs.existsSync(outPath)) {
        try {
          result.output = JSON.parse(fs.readFileSync(outPath, "utf8"));
          result.ok = Boolean(result.output?.ok);
        } catch (err) {
          result.parse_error = err.message;
        }
      }
      try { fs.unlinkSync(inPath); } catch { /* ignore */ }
      resolve(result);
    });
    child.on("error", (err) => {
      clearTimeout(timer);
      resolve({ ok: false, spawn_error: String(err.message || err), exit_code: null });
    });
  });
}

// ---------------------------------------------------------------------------
// ASR merge
// ---------------------------------------------------------------------------

export function wordsInWindow(words, startSec, endSec, pad = 0.25) {
  const lo = startSec - pad;
  const hi = endSec + pad;
  return (words ?? []).filter((w) => {
    const mid = (w.start + w.end) / 2;
    return mid >= lo && mid <= hi;
  });
}

export function windowWordStats(words, startSec, endSec) {
  const inWin = wordsInWindow(words, startSec, endSec);
  if (!inWin.length) return { count: 0, mean_confidence: null, text: "", words: [] };
  const scored = inWin.filter((w) => Number.isFinite(w.confidence));
  const mean = scored.length ? scored.reduce((s, w) => s + w.confidence, 0) / scored.length : null;
  return {
    count: inWin.length,
    mean_confidence: mean,
    text: inWin.map((w) => w.word).join(" ").trim(),
    words: inWin.map((w) => ({ word: w.word, start: w.start, end: w.end, confidence: w.confidence })),
  };
}

// Recomputes confidence/gating for each question window using ASR word
// statistics, upgrading `unverified` -> `needs_review` only when every gate
// passes. `verified` is never produced here.
export function mergeAsrIntoAlignment(result, asr, { thresholds } = {}) {
  // `asr.words` is the word count in the provider summary; the full word list
  // (when present) is `asr.words_full`. Tests may pass an array directly.
  const words = Array.isArray(asr?.words_full) ? asr.words_full : (Array.isArray(asr?.words) ? asr.words : null);
  if (!asr || asr.status !== "ok" || !words?.length) return { ...result, asr_merge: { applied: false, reason: asr?.status ?? "no_asr" } };
  const questions = result.questions.map((q) => {
    const next = { ...q, intervals: q.intervals.map((iv) => ({ ...iv })) };
    let best = { count: 0, mean_confidence: null, text: "", words: [] };
    for (const iv of next.intervals) {
      const stats = windowWordStats(words, iv.start_sec, iv.end_sec);
      iv.asr = { word_count: stats.count, mean_confidence: stats.mean_confidence, text: stats.text };
      if (stats.count > best.count) best = stats;
    }
    const parts = { ...next.confidence.parts };
    if (best.count > 0) parts.aligner_word_confidence = best.mean_confidence;
    const conf = composeConfidence(parts);
    next.confidence = conf;
    const gate = gateNeedsReview(conf, "asr_forced_align", thresholds);
    next.asr_gate = gate;
    if (next.status === ALIGN_STATUS.NEEDS_REVIEW) {
      // stays; evidence updated
    } else if (next.status === ALIGN_STATUS.UNVERIFIED && next.intervals.length && gate.passes) {
      next.status = ALIGN_STATUS.NEEDS_REVIEW;
      next.reasons = (next.reasons ?? []).filter((r) => !r.includes("below_threshold"));
      next.reasons.push("asr_gate_passed");
    }
    if (next.status === ALIGN_STATUS.UNVERIFIED && next.intervals.length && !gate.passes) {
      next.reasons = [...new Set([...(next.reasons ?? []), ...gate.failures])];
    }
    return next;
  });
  const counts = {};
  for (const q of questions) counts[q.status] = (counts[q.status] ?? 0) + 1;
  return {
    ...result,
    method: "asr_forced_align",
    model_version: asr.model_version ?? result.model_version,
    questions,
    coverage: { ...result.coverage, ...counts, questions_total: questions.length },
    asr_merge: { applied: true, words_total: words.length, audio_sha256: asr.audio_sha256 ?? null },
  };
}

// ---------------------------------------------------------------------------
// High-level pipeline
// ---------------------------------------------------------------------------

export async function buildAlignmentWithProvider({
  dataDir,
  identity,
  part,
  questions,
  groups,
  audioRecord,
  transcript,
  candidateTimestamps,
  config = {},
  precomputedAsr = null,
} = {}) {
  const paths = alignmentPaths({ dataDir });
  const base = alignQuestions({
    identity,
    part,
    questions,
    groups,
    audio: audioRecord,
    transcript,
    candidateTimestamps,
    config,
  });
  const out = {
    alignment: base,
    asr: { status: "not_requested" },
    setup: null,
  };
  if (!config.use_asr) return out;

  // Reuse a previous ASR transcript when its audio hash matches the current
  // audio record; ASR is the expensive step and the hash is the identity gate.
  let asrOut = null;
  let asrReused = false;
  const preWords = precomputedAsr ? (precomputedAsr.words_full ?? precomputedAsr.words) : null;
  if (
    precomputedAsr?.status === "ok"
    && Array.isArray(preWords)
    && preWords.length
    && (!precomputedAsr.audio_sha256 || !audioRecord?.content_sha256 || precomputedAsr.audio_sha256 === audioRecord.content_sha256)
  ) {
    asrOut = {
      audio_sha256: precomputedAsr.audio_sha256 ?? null,
      model_version: precomputedAsr.model_version ?? null,
      segments: precomputedAsr.segments_full ?? precomputedAsr.segments ?? [],
      words: preWords,
      duration_sec: precomputedAsr.duration_sec ?? null,
      elapsed_sec: precomputedAsr.elapsed_sec ?? 0,
    };
    asrReused = true;
    out.setup = { status: "reused_asr", reason: null, tool_sha256: null };
  }
  if (!asrOut) {
    const setup = checkAlignmentSetup({ dataDir });
    out.setup = { status: setup.status, reason: setup.reason, tool_sha256: setup.tool_sha256 ?? null };
    if (setup.status !== "ready") {
      out.asr = { status: "alignment_setup_blocked", reason: setup.reason };
      out.alignment.warnings.push("alignment_setup_blocked");
      return out;
    }
    if (!audioRecord?.file_path || !fs.existsSync(audioRecord.file_path)) {
      out.asr = { status: "audio_file_missing", path: audioRecord?.file_path ?? null };
      return out;
    }
    const whisperEntry = setup.model_lock?.models?.whisper;
    const whisperDir = path.isAbsolute(whisperEntry?.dir ?? "") ? whisperEntry.dir : path.join(paths.modelsDir, whisperEntry?.dir ?? "");
    const run = await runAlignerAsync({
      pythonPath: paths.python,
      toolPath: paths.tool,
      input: {
        task: "transcribe",
        audio_path: audioRecord.file_path,
        expected_sha256: audioRecord.content_sha256 ?? undefined,
        language: "en",
        device: "cpu",
        models: {
          whisper_dir: whisperDir,
          compute_type: config.compute_type ?? "int8",
          local_files_only: true,
        },
      },
    });
    if (!run.ok) {
      out.asr = {
        status: run.output?.error === "audio_hash_mismatch" ? "audio_hash_mismatch" : "failed",
        error: run.output?.error ?? run.spawn_error ?? "tool_failed",
        detail: run.output?.detail ?? run.stderr?.slice(0, 500) ?? null,
        exit_code: run.exit_code ?? null,
      };
      return out;
    }
    asrOut = run.output;
  }
  out.asr = {
    status: "ok",
    audio_sha256: asrOut.audio_sha256,
    model_version: asrOut.model_version,
    segments: asrOut.segments?.length ?? 0,
    words: asrOut.words?.length ?? 0,
    words_full: asrOut.words ?? [],
    segments_full: asrOut.segments ?? [],
    duration_sec: asrOut.duration_sec ?? null,
    elapsed_sec: asrOut.elapsed_sec,
  };
  if (asrReused) out.asr.reused = true;
  if (audioRecord.content_sha256 && asrOut.audio_sha256 !== audioRecord.content_sha256) {
    out.asr.status = "audio_hash_mismatch";
    return out;
  }

  const asrTranscript = {
    source: "local_asr",
    sha256: asrOut.audio_sha256,
    segments: (asrOut.segments ?? []).map((s) => ({
      t_sec: s.start,
      end_sec: s.end,
      text: s.text,
      source_ref: `asr@${s.start.toFixed(2)}`,
    })),
  };
  const useAsrTranscript = config.asr_transcript === "prefer" || !base.clock?.valid || !(transcript?.segments?.length);
  let merged = base;
  if (useAsrTranscript) {
    merged = alignQuestions({
      identity,
      part,
      questions,
      groups,
      audio: audioRecord,
      transcript: asrTranscript,
      candidateTimestamps: null,
      config: { ...config, method: "asr_forced_align" },
    });
  }
  out.alignment = mergeAsrIntoAlignment(merged, out.asr);
  out.alignment.method = useAsrTranscript ? "asr_forced_align" : out.alignment.method;
  out.alignment.matcher_version = MATCHER_VERSION;
  out.alignment.threshold_version = THRESHOLD_VERSION;
  return out;
}

export const __internals = { sha256FileSync, alignmentPaths };
