"""核验：抓取若干 PDF URL 的响应体，判断 152114 字节响应是什么；重试已知链接 URL。"""

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

OUT = Path(r"C:/Users/weo/Desktop/api/tmp_edexcel_tt_probe")
EV = OUT / "evidence"
DL = OUT / "downloads"
fetcher = Fetcher(Settings())

ORIGIN = "https://qualifications.pearson.com"

tests = [
    "/content/dam/pdf/Support/Examination-timetables-for-Edexcel-International-GCSE/int-gcse-summer-2026-final.pdf",
    "/content/dam/pdf/Support/Examination-timetables-for-International-Advanced-Levels/ial-summer-2025-final.pdf",
    "/content/dam/pdf/Support/Examination-timetables-for-International-Advanced-Levels/ial-january-2026-final.pdf",
]

for i, path in enumerate(tests):
    url = ORIGIN + path
    r = fetcher.get(url, expect_binary=True, follow_redirects=True)
    body = r.content or b""
    rec = {"url": path, "status": r.status, "ctype": getattr(r, "content_type", None),
           "bytes": len(body), "magic": body[:8].hex(), "error": r.error}
    print(json.dumps(rec, ensure_ascii=False))
    if body[:4] == b"%PDF":
        name = path.split("/")[-1]
        (DL / name).write_bytes(body)
        rec["sha256"] = hashlib.sha256(body).hexdigest()
        rec["saved"] = str(DL / name)
    elif b"<html" in body[:2000].lower() or b"<!doctype" in body[:200].lower():
        # dump error page once
        if not (EV / "error_page.html").exists():
            (EV / "error_page.html").write_text(body.decode("utf-8", "replace"), encoding="utf-8")
        import re
        m = re.search(rb"<title[^>]*>(.*?)</title>", body, re.I | re.S)
        rec["title"] = (m.group(1).decode("utf-8", "replace").strip() if m else None)
        m2 = re.search(rb"<h1[^>]*>(.*?)</h1>", body, re.I | re.S)
        rec["h1"] = (" ".join(m2.group(1).decode("utf-8", "replace").split()) if m2 else None)
        print(json.dumps(rec, ensure_ascii=False))
