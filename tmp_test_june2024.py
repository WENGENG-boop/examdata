"""Focused test: June-2024 biology files, both URL styles + cross-subject sample."""
import json
import time
from pathlib import Path

import httpx

from examdata.core.fetch import Fetcher
from examdata.adapters.edexcel import servlet

UA = "ExamDataBot/0.1 (+https://example.invalid/examdata; contact=ops@example.invalid)"
ORIGIN = "https://qualifications.pearson.com"

fetcher = Fetcher()
records = servlet.fetch_records(
    fetcher,
    ["Pearson-UK:Specification-Code/ial18-biology", "Pearson-UK:Exam-Series/June-2024"],
)
qpms = []
for rec in records:
    cats = rec.get("category") or []
    raw = None
    for c in cats:
        if c.startswith("Pearson-UK:Document-Type/"):
            raw = c.split("/", 1)[1]
    if raw in {"Question-paper", "Mark-scheme", "Mark-Scheme"}:
        qpms.append((raw, rec["url"]))
print(f"June-2024 qp/ms: {len(qpms)}")
for raw, url in sorted(qpms):
    print(f"  {raw:14s} {url}")

def alt_style(url: str) -> str:
    if "International Advanced Level" in url:
        return url.replace("International Advanced Level", "International-Advanced-Level")
    if "International-Advanced-Level" in url:
        return url.replace("International-Advanced-Level", "International Advanced Level")
    return url

with httpx.Client(timeout=60, headers={"User-Agent": UA}, follow_redirects=False) as client:
    print("\n-- June-2024 files: catalog URL as-is vs alternate style --")
    for raw, url in sorted(qpms):
        for label, u in (("as-is", url), ("alt", alt_style(url))):
            try:
                r = client.get(ORIGIN + u)
                magic = r.content[:5] == b"%PDF-" if r.status_code == 200 else b""
                print(f"  {label:6s} {r.status_code} bytes={len(r.content):8d} pdf={bool(magic)} {url.rsplit('/', 1)[-1]}")
            except Exception as exc:
                print(f"  {label:6s} ERROR {exc!r}")
            time.sleep(0.5)
    print("\n-- cross-subject sample: chemistry + mathematics spaced/dashed --")
    for slug in ("ial18-chemistry", "ial18-mathematics"):
        try:
            recs = servlet.fetch_records(fetcher, [f"Pearson-UK:Specification-Code/{slug}"])
        except servlet.ShardExhausted as exc:
            print(f"  {slug}: ShardExhausted ({exc})")
            continue
        got = {"spaced": None, "dashed": None}
        for rec in recs:
            cats = rec.get("category") or []
            raw = None
            for c in cats:
                if c.startswith("Pearson-UK:Document-Type/"):
                    raw = c.split("/", 1)[1]
            if raw not in {"Question-paper", "Mark-scheme", "Mark-Scheme"}:
                continue
            u = rec["url"]
            if "/secure/" in u:
                continue
            if "International Advanced Level" in u and got["spaced"] is None:
                got["spaced"] = u
            elif "International-Advanced-Level" in u and got["dashed"] is None:
                got["dashed"] = u
            if got["spaced"] and got["dashed"]:
                break
        for style, u in got.items():
            if not u:
                print(f"  {slug}: no {style} sample found")
                continue
            try:
                r = client.get(ORIGIN + u)
                magic = r.content[:5] == b"%PDF-" if r.status_code == 200 else b""
                print(f"  {slug} {style:6s} {r.status_code} bytes={len(r.content):8d} pdf={bool(magic)} {u.rsplit('/', 1)[-1]}")
            except Exception as exc:
                print(f"  {slug} {style:6s} ERROR {exc!r}")
            time.sleep(0.5)
