"""Edexcel 时间表下载器：按 download_plan_v4.json 逐季下载、核验、落盘。

策略：
  - 每季按候选序尝试（wayback id_ 或 live CDN），最多 6 次请求；
    命中 1 final（或 final+provisional）且核验通过即停
  - 核验：%PDF 魔数 + pymupdf 页数>0 + family/month 词 + R 卷代码；
    无文本层（扫描件）作为安全阀放行并记录 text_light
  - 全部失败 → 用最佳候选原始 URL 直抓 live CDN 一次 → 仍失败记 unobtainable
  - 落盘 downloads/edexcel/{family}/{YYYY-MM}[-r][-provisional].pdf
  - manifest 增量写 downloads/edexcel_manifest.json（支持断点续跑）

用法：
  python edexcel_download.py                     # 全量（断点续跑）
  python edexcel_download.py --seasons a,b       # 指定考季
  python edexcel_download.py --force             # 重下已完成的
"""

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher
import pymupdf

BASE = Path(r"C:/Users/weo/Desktop/api/tmp_edexcel_tt_probe")
EV = BASE / "evidence"
DL = BASE / "downloads"
STAGE = DL / "edexcel_stage"
OUT = DL / "edexcel"
MANIFEST = DL / "edexcel_manifest.json"
PLAN = EV / "download_plan_v4.json"

WAYBACK = "https://web.archive.org/web/{ts}id_/{url}"

FAMILY_RX = {
    "gcse": [re.compile(r"(?<![a-z])gcse(?![a-z])", re.I)],
    "gce": [re.compile(r"(?<![a-z])gce(?![a-z])|a[- ]?level|advanced level", re.I)],
    "intgcse": [re.compile(r"international\s+gcse|igcse|int[- ]?gcse|international general certificate of secondary education", re.I)],
    "ial": [re.compile(r"international\s+advanced\s+level|international\s+a[- ]?level|(?<![a-z])ial(?![a-z])", re.I)],
}
FAMILY_ANTI = {
    "gcse": re.compile(r"international\s+gcse|igcse|international general certificate of secondary education", re.I),
    "gce": re.compile(r"international\s+advanced\s+level|international\s+a[- ]?level|(?<![a-z])ial(?![a-z])", re.I),
    "intgcse": None,
    "ial": None,
}
MONTH_RX = {
    1: re.compile(r"january|(?<![a-z])jan(?![a-z])", re.I),
    6: re.compile(r"june|summer|april|may", re.I),
    10: re.compile(r"october|(?<![a-z])oct(?![a-z])", re.I),
    11: re.compile(r"november|(?<![a-z])nov(?![a-z])", re.I),
}
R_TOKEN_RX = re.compile(r"\b[0-9A-Z]{4,5}\s?\d{2}R\b")
R_PHRASE_RX = re.compile(r"r[-_ ]?paper", re.I)
UNSEEN_RX = re.compile(r"unseen content", re.I)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def key_to_dir(key):
    parts = key.split("|")
    fam, y, m = parts[0], parts[1], parts[2]
    suffix = "-r" if len(parts) > 3 else ""
    return f"{fam}_{y}-{m}{suffix}"


def rel(p):
    return str(Path(p).relative_to(BASE)).replace("\\", "/")


def verify_pdf(path, fam, month, variant, year):
    try:
        doc = pymupdf.open(str(path))
    except Exception as e:
        return {"pass": False, "error": repr(e)}
    pages = doc.page_count
    if pages <= 0:
        doc.close()
        return {"pass": False, "error": "0 pages"}
    text_parts = []
    for i in range(min(4, pages)):
        text_parts.append(doc[i].get_text())
    doc.close()
    text = "\n".join(text_parts)
    flat = " ".join(text.split())
    if len(flat) < 50:
        return {"pass": True, "text_light": True, "pages": pages, "head": flat[:220]}
    fam_ok = any(rx.search(flat) for rx in FAMILY_RX[fam])
    anti = FAMILY_ANTI[fam]
    if anti and anti.search(flat):
        fam_ok = False
    month_ok = bool(MONTH_RX[month].search(flat))
    r_tokens = len(R_TOKEN_RX.findall(text))
    r_phrase = bool(R_PHRASE_RX.search(flat))
    r_ok = None
    if variant == "R":
        r_ok = r_tokens >= 3 or r_phrase
    year_seen = str(year) in flat
    special = "unseen-content-assessment" if UNSEEN_RX.search(flat) else None
    content_label = None
    if re.search(r"provisional", flat, re.I):
        content_label = "provisional"
    elif re.search(r"\bfinal\b", flat, re.I):
        content_label = "final"
    passed = bool(fam_ok and month_ok and (r_ok is not False))
    return {"pass": passed, "family_ok": fam_ok, "month_ok": month_ok, "r_ok": r_ok,
            "r_tokens": r_tokens, "year_seen": year_seen, "special": special,
            "content_label": content_label, "pages": pages, "head": flat[:220]}


def fetch_candidate(f, c):
    if c["kind"] == "live":
        url = c["url"]
    else:
        url = WAYBACK.format(ts=c["timestamp"], url=c["url"])
    try:
        r = f.get(url, expect_binary=True, follow_redirects=True)
    except Exception as e:
        return None, {"url": url, "result": "error", "error": repr(e)}
    return r, {"url": url}


def process_season(f, key, meta, manifest, force=False):
    rec = manifest["seasons"].get(key)
    if rec and rec.get("status") == "ok" and not force:
        return "skip"
    fam = meta["family"]
    year = meta["year"]
    month = meta["month"]
    variant = meta["variant"]
    stage_dir = STAGE / key_to_dir(key)
    stage_dir.mkdir(parents=True, exist_ok=True)
    attempts = []
    accepted = []
    seen = set()
    n_req = 0
    fail_after_accept = 0
    used_fallback = False

    for idx, c in enumerate(meta["candidates"]):
        if n_req >= 6:
            break
        sig = (c.get("name"), c.get("label"), c.get("timestamp"))
        if sig in seen:
            continue
        seen.add(sig)
        if accepted and fail_after_accept >= 3:
            break
        n_req += 1
        r, info = fetch_candidate(f, c)
        info.update({"kind": c["kind"], "ts": c.get("timestamp"), "label": c.get("label"),
                     "name": c.get("name"), "verified_cdx": bool(c.get("verified"))})
        if r is None:
            attempts.append(info)
            if accepted:
                fail_after_accept += 1
            continue
        body = r.content or b""
        info["status"] = r.status
        info["bytes"] = len(body)
        if body[:4] != b"%PDF":
            info["result"] = "not-pdf"
            attempts.append(info)
            if accepted:
                fail_after_accept += 1
            continue
        dest = stage_dir / f"cand{idx:02d}.pdf"
        dest.write_bytes(body)
        info["result"] = "pdf"
        info["sha256"] = hashlib.sha256(body).hexdigest()
        v = verify_pdf(dest, fam, month, variant, year)
        info["verify"] = v
        attempts.append(info)
        eff_label = v.get("content_label") or c.get("label") or "unknown"
        info["eff_label"] = eff_label
        if v.get("pass"):
            accepted.append({
                "stage": str(dest),
                "source": {"kind": c["kind"], "url": c["url"], "fetch_url": info["url"],
                           "timestamp": c.get("timestamp"), "label": eff_label,
                           "name": c.get("name"), "sha256": info["sha256"],
                           "bytes": len(body), "pages": v.get("pages"),
                           "verified_cdx": bool(c.get("verified"))},
                "verify": v})
            if eff_label == "final":
                break
        else:
            if accepted:
                fail_after_accept += 1

    # 兜底：直抓 live CDN 一次
    if not accepted and meta["candidates"]:
        best = meta["candidates"][0]
        used_fallback = True
        info = {"url": best["url"], "kind": "live-direct", "name": best.get("name"),
                "label": best.get("label"), "result": "error"}
        try:
            r = f.get(best["url"], expect_binary=True, follow_redirects=True)
            body = r.content or b""
            info["status"] = r.status
            info["bytes"] = len(body)
            if body[:4] == b"%PDF":
                dest = stage_dir / "fallback.pdf"
                dest.write_bytes(body)
                info["result"] = "pdf"
                info["sha256"] = hashlib.sha256(body).hexdigest()
                v = verify_pdf(dest, fam, month, variant, year)
                info["verify"] = v
                if v.get("pass"):
                    accepted.append({
                        "stage": str(dest),
                        "source": {"kind": "live-direct", "url": best["url"],
                                   "fetch_url": best["url"], "timestamp": None,
                                   "label": v.get("content_label") or best.get("label") or "unknown",
                                   "name": best.get("name"),
                                   "sha256": info["sha256"], "bytes": len(body),
                                   "pages": v.get("pages"),
                                   "verified_cdx": bool(best.get("verified"))},
                        "verify": v})
            else:
                info["result"] = "not-pdf"
        except Exception as e:
            info["error"] = repr(e)
        attempts.append(info)

    finished = now_iso()
    base = {"family": fam, "year": year, "month": month, "variant": variant,
            "attempts": attempts, "requests": n_req + (1 if used_fallback else 0),
            "finished_at": finished}
    if accepted:
        final = next((a for a in accepted if a["source"]["label"] == "final"), None)
        main = final or accepted[0]
        extra = None
        if final and len(accepted) > 1:
            extra = next((a for a in accepted if a is not final), None)
        ym = f"{year:04d}-{month:02d}" + ("-r" if variant == "R" else "")
        fam_dir = OUT / fam
        fam_dir.mkdir(parents=True, exist_ok=True)
        main_path = fam_dir / f"{ym}.pdf"
        shutil.copyfile(main["stage"], main_path)
        rec = dict(base)
        rec.update({"status": "ok", "file": rel(main_path), "label": main["source"]["label"],
                    "source": main["source"], "verify": main["verify"], "extra": None})
        if extra:
            extra_path = fam_dir / f"{ym}-provisional.pdf"
            shutil.copyfile(extra["stage"], extra_path)
            rec["extra"] = {"file": rel(extra_path), "label": extra["source"]["label"],
                            "source": extra["source"], "verify": extra["verify"]}
        manifest["seasons"][key] = rec
        return f"ok [{rec['label']}] {rec['file']}"
    rec = dict(base)
    rec.update({"status": "unobtainable",
                "reason": "all candidates failed (not pdf / verify failed)"})
    manifest["seasons"][key] = rec
    return "unobtainable"


def save_manifest(manifest):
    manifest["saved_at"] = now_iso()
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", default=None, help="逗号分隔的考季键（默认全量）")
    ap.add_argument("--force", action="store_true", help="重下已完成的考季")
    ap.add_argument("--max-seasons", type=int, default=None)
    args = ap.parse_args()

    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    seasons = plan["plan"]
    keys = sorted(seasons)
    if args.seasons:
        want = [s.strip() for s in args.seasons.split(",") if s.strip()]
        keys = [k for k in want if k in seasons]
        missing = [k for k in want if k not in seasons]
        if missing:
            print(f"WARN: keys not in plan: {missing}")
    if args.max_seasons:
        keys = keys[:args.max_seasons]

    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    else:
        manifest = {"generated_at": now_iso(), "plan_file": rel(PLAN),
                    "plan_generated_at": plan.get("generated_at"), "seasons": {}}
    manifest["cancelled"] = {k: {"reason": v["reason"]} for k, v in plan.get("cancelled", {}).items()}
    manifest["gaps"] = plan.get("gaps", [])
    manifest["known_unobtainable"] = plan.get("known_unobtainable", {})
    manifest["r_unobtainable"] = plan.get("r_unobtainable", {})

    fetcher = Fetcher(Settings())
    print(f"seasons to process: {len(keys)}")
    t0 = time.time()
    done = 0
    for i, key in enumerate(keys, 1):
        meta = seasons[key]
        try:
            res = process_season(fetcher, key, meta, manifest, force=args.force)
        except Exception as e:
            res = f"EXC {e!r}"
        done += 1
        save_manifest(manifest)
        print(f"[{i}/{len(keys)}] {key:22s} {res}  ({time.time()-t0:.0f}s)", flush=True)
    save_manifest(manifest)
    ok = sum(1 for r in manifest["seasons"].values() if r.get("status") == "ok")
    un = sum(1 for r in manifest["seasons"].values() if r.get("status") == "unobtainable")
    print(f"\nDONE: ok={ok} unobtainable={un} processed={done} in {time.time()-t0:.0f}s")
    print(f"manifest: {MANIFEST}")


if __name__ == "__main__":
    main()
