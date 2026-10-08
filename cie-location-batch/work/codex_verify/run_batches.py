"""Run codex vision batches over one volume's rendered sheets.

Usage: python run_batches.py <subject/year/season/paper> [--batch-size 4] [--max-batches N]

- Reads work/codex_verify/<slug>-manifest.json (sheets, each with its region ids).
- Splits sheets into batches of --batch-size in manifest order.
- Skips batches whose result JSON exists and matches the sheet set + expected ids
  (idempotent resume). A .FAILED.json batch is retried fresh on the next run.
- Each batch: codex exec (ephemeral, read-only sandbox) with the sheet PNGs and
  prompt_final.txt on stdin; the reply must be one JSON array covering every
  expected id exactly once. One retry on failure, then <slug>-batch-<nn>.FAILED.json
  and exit 3. A quota / rate-limit reply exits 4 immediately (stop the worker).
- Artifacts: work/codex_verify/<slug>-batch-<nn>.json and
  work/codex_verify/logs/<slug>-batch-<nn>[.retry].{out,err}.txt
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import batchlib as B

OUT_DIR = B.WORK / "codex_verify"
LOG_DIR = OUT_DIR / "logs"
CODEX = Path("C:/Users/weo/.local/bin/codex.exe")
PROMPT = OUT_DIR / "prompt_final.txt"
CALL_TIMEOUT = 280
QUOTA_MARKERS = ("usage limit", "rate limit", "quota", "too many requests",
                 "http 429", "try again later")


def load_manifest(key: str) -> tuple[str, dict]:
    slug = key.replace("/", "-")
    path = OUT_DIR / f"{slug}-manifest.json"
    if not path.is_file():
        raise SystemExit(f"manifest missing: {path}")
    return slug, json.loads(path.read_text(encoding="utf-8"))


def sheet_set(batch: list[dict]) -> list[str]:
    return [str(s["path"]) for s in batch]


def valid_result(path: Path, batch: list[dict], expected: list[str]) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        return None
    if data.get("sheets") != sheet_set(batch):
        return None
    got = [r.get("id") for r in data["records"] if isinstance(r, dict)]
    if len(got) != len(set(got)) or sorted(got) != sorted(expected):
        return None
    return data


def parse_reply(stdout: str) -> list[dict] | None:
    start, end = stdout.find("["), stdout.rfind("]")
    if start < 0 or end <= start:
        return None
    try:
        arr = json.loads(stdout[start:end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(arr, list):
        return None
    out: list[dict] = []
    for item in arr:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            return None
        out.append(item)
    return out


def run_call(sheet_paths: list[str]) -> tuple[int, bytes, bytes, float]:
    cmd = [str(CODEX), "exec", "--ignore-user-config", "--skip-git-repo-check",
           "--ephemeral", "-s", "read-only", "-i", *sheet_paths]
    prompt = PROMPT.read_text(encoding="utf-8")
    t0 = time.time()
    proc = subprocess.run(cmd, input=prompt.encode("utf-8"), capture_output=True,
                          cwd=str(OUT_DIR), timeout=CALL_TIMEOUT)
    return proc.returncode, proc.stdout, proc.stderr, time.time() - t0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--max-batches", type=int, default=0,
                    help="stop after N newly finished batches (0 = all)")
    args = ap.parse_args()

    slug, manifest = load_manifest(args.key)
    sheets = manifest["sheets"]
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    batches = [sheets[i:i + args.batch_size]
               for i in range(0, len(sheets), args.batch_size)]
    print(f"{slug}: {len(sheets)} sheets -> {len(batches)} batches "
          f"(size {args.batch_size})", flush=True)
    done_new = 0
    for bi, batch in enumerate(batches, 1):
        expected = [i for s in batch for i in s["ids"]]
        rpath = OUT_DIR / f"{slug}-batch-{bi:02d}.json"
        fpath = OUT_DIR / f"{slug}-batch-{bi:02d}.FAILED.json"
        if valid_result(rpath, batch, expected):
            print(f"batch {bi:02d}: already done ({len(expected)} ids)", flush=True)
            continue
        if args.max_batches and done_new >= args.max_batches:
            print("max-batches reached; stopping", flush=True)
            break
        ok = False
        last_err = ""
        for attempt, suffix in ((1, ""), (2, ".retry")):
            out_log = LOG_DIR / f"{slug}-batch-{bi:02d}{suffix}.out.txt"
            err_log = LOG_DIR / f"{slug}-batch-{bi:02d}{suffix}.err.txt"
            print(f"batch {bi:02d} attempt {attempt}: {len(batch)} sheets, "
                  f"{len(expected)} ids", flush=True)
            t0 = time.time()
            try:
                code, out_b, err_b, dt = run_call(sheet_set(batch))
            except subprocess.TimeoutExpired as exc:
                code, dt = 124, time.time() - t0
                out_b = exc.stdout if isinstance(exc.stdout, bytes) else b""
                err_b = exc.stderr if isinstance(exc.stderr, bytes) else b""
            out = (out_b or b"").decode("utf-8", "replace")
            err = (err_b or b"").decode("utf-8", "replace")
            out_log.write_text(out, encoding="utf-8")
            err_log.write_text(err, encoding="utf-8")
            last_err = err[-2000:]
            if any(m in err.lower() for m in QUOTA_MARKERS):
                print(f"batch {bi:02d}: quota/rate-limit marker; stop (exit 4)",
                      flush=True)
                return 4
            records = parse_reply(out) if code == 0 else None
            if records is not None:
                got = [r["id"] for r in records]
                if sorted(got) == sorted(expected) and len(set(got)) == len(got):
                    payload = {"batch": bi, "slug": slug, "key": args.key,
                               "sheets": sheet_set(batch), "expected_ids": expected,
                               "records": records, "attempt": attempt,
                               "codex_exit": code, "duration_s": round(dt, 1),
                               "finished_at": B.now_iso(), "prompt": str(PROMPT)}
                    B.atomic_write_json(rpath, payload)
                    if fpath.exists():
                        fpath.unlink()
                    print(f"batch {bi:02d}: ok ({len(records)} records, "
                          f"{dt:.0f}s)", flush=True)
                    ok = True
                    break
                miss = sorted(set(expected) - set(got))
                extra = sorted(set(got) - set(expected))
                print(f"batch {bi:02d}: coverage mismatch missing={miss} "
                      f"extra={extra}", flush=True)
            else:
                print(f"batch {bi:02d}: unusable reply (exit={code}, {dt:.0f}s)",
                      flush=True)
        if not ok:
            B.atomic_write_json(fpath, {"batch": bi, "slug": slug, "key": args.key,
                                        "sheets": sheet_set(batch),
                                        "expected_ids": expected,
                                        "at": B.now_iso(),
                                        "stderr_tail": last_err})
            print(f"batch {bi:02d}: FAILED after retry (exit 3)", flush=True)
            return 3
        done_new += 1
    print(f"{slug}: batches complete", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
