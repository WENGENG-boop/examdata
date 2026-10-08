"""缺口 1 补证：10 个「仍无任何系列清单记录」科目 syllabus 页的定向句子提取。

背景：June 2024 国际版清单覆盖 23 码中的 13 个；剩余 10 码
（0265/0266/0479/0715/0716/8101/8102/8293/9981/9982）需要从 syllabus 页
确认「首考时间 / 可用系列与 zones」，以解释其缺席系列清单的原因。

- 输入：syllabuses.json 的 source_url（仅这 10 码）
- 定向提取句子：first examination / examination from / available in / series /
  withdraw / last ... series / zones 等，按类别落盘
- 只走仓库 Fetcher（robots/限速/单线程）；原文本不留存，只保留短句证据

输出：evidence/gap1_syllabus_sentences.json
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

ROOT = Path(r"C:/Users/weo/Desktop/api")
OUT = ROOT / "tmp_materials_probe" / "evidence"
CODES = ["0265", "0266", "0479", "0715", "0716", "8101", "8102", "8293", "9981", "9982"]

TAGS = {
    "first_examination": r"[^.]*\b[Ff]irst examination[^.]*\.",
    "examination_from": r"[^.]*\bexamination from\b[^.]*\.",
    "syllabus_availability": r"[^.]*\bSyllabus availability\b[^.]*\.",
    "available_in": r"[^.]*\bavailable (?:in|from)\b[^.]*\.",
    "withdrawal": r"[^.]*\b[Ww]ithdraw(?:al|n|ing)?\b[^.]*\.",
    "last_series": r"[^.]*\blast [A-Za-z]+ (?:exam )?series[^.]*\.",
    "zone": r"[^.]*\b[Zz]one[s]? [0-9][^.]*\.",
    "not_available": r"[^.]*\bnot available\b[^.]*\.",
}


def main() -> None:
    syll = json.loads((ROOT / "examdata" / ".data" / "syllabuses.json").read_text(encoding="utf-8"))
    by_code = {str(s.get("code")): s for s in syll}
    fetcher = Fetcher(Settings())
    out = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "method_zh": "逐页抓取 syllabus 页原文，按关键词抽取完整句子；不保存整页文本",
           "codes": {}}
    for code in CODES:
        s = by_code.get(code)
        if not s:
            out["codes"][code] = {"error": "not in syllabuses.json"}
            continue
        url = s.get("source_url")
        rec = {"title": s.get("title"), "source_url": url}
        r = fetcher.get(url)
        rec["http"] = getattr(r, "status", None)
        rec["error"] = r.error
        if not (r.ok and r.text):
            out["codes"][code] = rec
            print(code, "FAILED", r.error)
            continue
        # 去标签/压缩空白
        text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", r.text, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&nbsp;?", " ", text)
        text = re.sub(r"&#\d+;", " ", text)
        text = re.sub(r"\s+", " ", text)
        rec["text_chars"] = len(text)
        for tag, pat in TAGS.items():
            hits = []
            for m in re.finditer(pat, text):
                sent = m.group(0).strip()
                if 8 <= len(sent) <= 320 and sent not in hits:
                    hits.append(sent)
            # 去噪：导航样板
            hits = [h for h in hits if "Support and guidance for digital exams" not in h]
            if hits:
                rec[tag] = hits[:6]
        out["codes"][code] = rec
        print(code, rec["title"], "| chars:", rec["text_chars"], "| tags:", [k for k in TAGS if k in rec])
    OUT.joinpath("gap1_syllabus_sentences.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    fetcher.close()
    print("wrote gap1_syllabus_sentences.json")


if __name__ == "__main__":
    main()
