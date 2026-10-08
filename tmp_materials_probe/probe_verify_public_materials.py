"""验证：官网公开发布的 Confidential Instructions / Pre-Release 文件可实测取回。

只走仓库 Fetcher（robots、限速、单线程）。结果落 evidence/verify_public_materials.json。
"""

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

OUT = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe/evidence")
DOWNLOADS = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe/downloads")

URLS = {
    "0620_ci_51_june2024": "https://www.cambridgeinternational.org/Images/649924-june-2024-confidential-instructions-paper-51.pdf",
    "0411_pre_release_p11_june2024": "https://www.cambridgeinternational.org/Images/521274-june-2024-paper-11-pre-release-material.pdf",
    "9701_ci_31_june2024": "https://www.cambridgeinternational.org/Images/567187-june-2024-confidential-instructions-paper-31.pdf",
}

results = {}
fetcher = Fetcher(Settings())
try:
    for name, url in URLS.items():
        r = fetcher.get(url, expect_binary=True)
        rec = {
            "url": url,
            "http": r.status,
            "error": r.error,
            "robots_blocked": r.robots_blocked,
            "content_type": r.content_type,
        }
        if r.ok and r.content:
            rec["bytes"] = len(r.content)
            rec["sha256"] = hashlib.sha256(r.content).hexdigest()
            rec["magic"] = r.content[:8].decode("latin-1", "replace")
            path = DOWNLOADS / f"{name}.pdf"
            path.write_bytes(r.content)
            rec["saved"] = str(path)
        results[name] = rec
        print(name, rec.get("http"), rec.get("bytes"), rec.get("sha256"))
finally:
    fetcher.close()

(OUT / "verify_public_materials.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("written", OUT / "verify_public_materials.json")
