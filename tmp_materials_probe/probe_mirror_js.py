"""拿镜像站前端 JS，找接口名/资料区线索。"""

import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

ORIGIN = "https://cie.fraft.cn"
OUT = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe/evidence")
fetcher = Fetcher(Settings())

for name in ["static/pc/definitions.js", "static/pc/modules.js", "static/common/modules.js",
             "static/pc/tabs/search.html", "static/pc/tabs/help.html"]:
    r = fetcher.get_text(f"{ORIGIN}/{name}")
    fn = name.replace("/", "__")
    (OUT / fn).write_text(r.text or "", encoding="utf-8")
    print("==", name, r.status, len(r.text or ""))

import re
combined = ""
for f in OUT.glob("static__*"):
    combined += f.read_text(encoding="utf-8", errors="replace")
urls = sorted(set(re.findall(r"[\"'`]([A-Za-z0-9_./-]*?(?:Fetch|obj|api|list|List|fetch)[A-Za-z0-9_./-]*)[\"'`]", combined)))
print("candidate endpoints:", urls[:60])
kw = sorted(set(re.findall(r"[\u4e00-\u9fff]{2,8}", combined)))
print("chinese keywords:", " / ".join(kw[:80]))
