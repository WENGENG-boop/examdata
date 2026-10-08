"""Test URL style variants for spaced-family QP/MS URLs."""
import json
import time
from pathlib import Path

import httpx

UA = "ExamDataBot/0.1 (+https://example.invalid/examdata; contact=ops@example.invalid)"
ORIGIN = "https://qualifications.pearson.com"
data = json.loads(Path("tmp_edxprobe/urls.json").read_text(encoding="utf-8"))

def variant_dashed(url: str) -> str:
    return url.replace("International Advanced Level", "International-Advanced-Level")

with httpx.Client(timeout=60, headers={"User-Agent": UA}, follow_redirects=False) as client:
    for item in data["spaced"]:
        url = ORIGIN + item["url"]
        for label, u in (("as-is", url), ("dashed", variant_dashed(url))):
            try:
                r = client.get(u)
                ct = r.headers.get("content-type", "")
                loc = r.headers.get("location", "")
                magic = r.content[:5] == b"%PDF-" if r.status_code == 200 else b""
                print(f"{item['series']:14s} {label:6s} {r.status_code} {ct[:30]:30s} bytes={len(r.content)} pdf={bool(magic)} loc={loc[:70]}")
            except Exception as exc:
                print(f"{item['series']:14s} {label:6s} ERROR {exc!r}")
            time.sleep(0.6)
    for item in data["dashed"]:
        try:
            r = client.get(ORIGIN + item["url"])
            ct = r.headers.get("content-type", "")
            magic = r.content[:5] == b"%PDF-" if r.status_code == 200 else b""
            print(f"{item['series']:14s} dashed {r.status_code} {ct[:30]:30s} bytes={len(r.content)} pdf={bool(magic)}")
        except Exception as exc:
            print(f"{item['series']:14s} dashed ERROR {exc!r}")
        time.sleep(0.6)
