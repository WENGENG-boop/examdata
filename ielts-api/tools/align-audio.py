#!/usr/bin/env python3
"""S10 local ASR + forced-alignment tool for IELTS listening audio.

Runs fully offline against the model dirs under
`ielts-data/tools/alignment-models` (see model-lock.json). Invoked by
`alignment-provider.mjs` through spawn with an argument array; never through a
shell.

Usage:
  python align-audio.py --input request.json --out result.json

Request (task="transcribe"):
{
  "task": "transcribe",
  "audio_path": "<local audio file>",
  "expected_sha256": "<hex>" | null,
  "language": "en",
  "device": "cpu",
  "models": {
    "whisper_dir": "<faster-whisper model dir>",
    "align_dir": "<wav2vec2 dir>" | null,   # default: sibling wav2vec2-base-960h
    "compute_type": "int8",
    "local_files_only": true
  }
}

Result (success):
{
  "ok": true,
  "audio_sha256": "...",
  "duration_sec": 467.3,
  "model_version": {...},
  "segments": [{"start": 0.0, "end": 1.2, "text": "..."}],
  "words": [{"word": "...", "start": 0.0, "end": 0.5, "confidence": 0.95}],
  "stats": {"segments_total": N, "words_total": N, "words_dropped_nonfinite": N},
  "elapsed_sec": 123.4
}

Result (failure):
{"ok": false, "error": "<code>", "detail": <json>}

Error codes: bad_request, unknown_task, audio_missing, audio_hash_mismatch,
model_missing, audio_decode_failed, asr_failed, align_failed, internal_error.
Handled errors exit 0 with ok=false written to --out; only an unhandled
crash exits non-zero.
"""

import argparse
import hashlib
import json
import math
import os
import sys
import time
import traceback


def sha256_file(path, chunk=1024 * 1024):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            buf = fh.read(chunk)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def fail(out_path, error, detail=None):
    write_out(out_path, {"ok": False, "error": error, "detail": detail})
    return 0


def write_out(out_path, doc):
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)


def version_of(pkg):
    try:
        import importlib.metadata as im
        return im.version(pkg)
    except Exception:
        return None


def run_transcribe(req, out_path):
    t0 = time.monotonic()
    audio_path = req.get("audio_path")
    if not audio_path or not os.path.isfile(audio_path):
        return fail(out_path, "audio_missing", {"audio_path": audio_path})

    models = req.get("models") or {}
    whisper_dir = models.get("whisper_dir")
    if not whisper_dir or not os.path.isdir(whisper_dir):
        return fail(out_path, "model_missing", {"whisper_dir": whisper_dir})
    align_dir = models.get("align_dir") or os.path.join(os.path.dirname(os.path.abspath(whisper_dir)), "wav2vec2-base-960h")
    if not os.path.isdir(align_dir):
        return fail(out_path, "model_missing", {"align_dir": align_dir})
    compute_type = models.get("compute_type") or "int8"
    language = req.get("language") or "en"
    device = req.get("device") or "cpu"

    actual_sha = sha256_file(audio_path)
    expected = req.get("expected_sha256")
    if expected and expected != actual_sha:
        return fail(out_path, "audio_hash_mismatch", {"expected": expected, "actual": actual_sha})
    log(f"stage=sha256 ok ({actual_sha[:12]}...)")

    try:
        import numpy as np
        from whisperx.audio import load_audio
        audio = load_audio(audio_path)
        duration_sec = float(len(audio)) / 16000.0
    except Exception as exc:
        return fail(out_path, "audio_decode_failed", {"error": str(exc)[:1000]})
    log(f"stage=decode ok duration={duration_sec:.1f}s")

    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(whisper_dir, device=device, compute_type=compute_type, local_files_only=True)
        segments_iter, info = model.transcribe(
            audio,
            language=language,
            beam_size=5,
            vad_filter=True,
            without_timestamps=False,
            condition_on_previous_text=False,
            log_progress=False,
        )
        segments = []
        for s in segments_iter:
            text = (s.text or "").strip()
            if not text:
                continue
            segments.append({"start": round(float(s.start), 3), "end": round(float(s.end), 3), "text": text})
    except Exception as exc:
        return fail(out_path, "asr_failed", {"error": str(exc)[:1000], "trace": traceback.format_exc()[-1500:]})
    log(f"stage=asr ok segments={len(segments)}")

    words = []
    dropped = 0
    try:
        import whisperx
        model_a, metadata = whisperx.load_align_model(
            language_code=language,
            device=device,
            model_name=align_dir,
            model_cache_only=True,
        )
        if segments:
            aligned = whisperx.align(segments, model_a, metadata, audio, device)
            for w in aligned.get("word_segments", []):
                start = w.get("start")
                end = w.get("end")
                if start is None or end is None or not (math.isfinite(start) and math.isfinite(end)):
                    dropped += 1
                    continue
                conf = w.get("score")
                if conf is None or not math.isfinite(conf):
                    conf = None
                words.append({
                    "word": str(w.get("word") or ""),
                    "start": round(float(start), 3),
                    "end": round(float(end), 3),
                    "confidence": round(float(conf), 4) if conf is not None else None,
                })
    except Exception as exc:
        return fail(out_path, "align_failed", {"error": str(exc)[:1000], "trace": traceback.format_exc()[-1500:]})
    log(f"stage=align ok words={len(words)} dropped_nonfinite={dropped}")

    doc = {
        "ok": True,
        "audio_sha256": actual_sha,
        "duration_sec": round(duration_sec, 3),
        "model_version": {
            "whisperx": version_of("whisperx"),
            "faster_whisper": version_of("faster-whisper"),
            "whisper_model": os.path.basename(os.path.abspath(whisper_dir)),
            "align_model": os.path.basename(os.path.abspath(align_dir)),
            "compute_type": compute_type,
            "language": language,
            "device": device,
        },
        "segments": segments,
        "words": words,
        "stats": {
            "segments_total": len(segments),
            "words_total": len(words),
            "words_dropped_nonfinite": dropped,
        },
        "elapsed_sec": round(time.monotonic() - t0, 2),
    }
    write_out(out_path, doc)
    log(f"stage=done elapsed={doc['elapsed_sec']}s")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Local ASR + forced alignment tool (S10)")
    parser.add_argument("--input", required=True, help="request JSON path")
    parser.add_argument("--out", required=True, help="result JSON path")
    args = parser.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as fh:
            req = json.load(fh)
    except Exception as exc:
        return fail(args.out, "bad_request", {"error": str(exc)[:500]})

    task = req.get("task")
    if task == "transcribe":
        return run_transcribe(req, args.out)
    return fail(args.out, "unknown_task", {"task": task})


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.stderr.write(traceback.format_exc())
        sys.exit(1)
