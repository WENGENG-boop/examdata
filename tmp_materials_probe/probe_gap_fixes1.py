"""缺口 1/4/5 补证：

1) 抓取 23 个无材料证据科目（no_material_evidence）的 syllabus 页，提取"可用系列/首考年份"片段。
2) 下载并解析 Nov 2026 早考卷与 pre-release 清单 xlsx（公共管理文档），列出含 pre-release 的科目。
3) 实测下载 Supplementary Multiple Choice Answer Sheet (Exam Day - Form 2a) PDF 的字节/sha256，随后删除原件。

输出：
  evidence/gap1_syllabus_availability.json
  evidence/gap4_pre_release_xlsx.json
  evidence/gap5_mc_answer_sheet.json
"""

import hashlib
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

OUT = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe/evidence")
DOWNLOADS = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe/downloads")
DOWNLOADS.mkdir(parents=True, exist_ok=True)

CODES = ["0262", "0265", "0266", "0444", "0472", "0479", "0480", "0499", "0523", "0539", "0544",
         "0547", "0715", "0716", "0772", "0989", "0995", "7164", "8101", "8102", "8293", "9981", "9982"]

syl = json.load(open(r"C:/Users/weo/Desktop/api/examdata/.data/syllabuses.json", encoding="utf-8"))
by_code = {str(e.get("code")): e for e in syl}

fetcher = Fetcher(Settings())
now = datetime.now(timezone.utc).isoformat(timespec="seconds")


def strip_html(html: str) -> str:
    body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    body = re.sub(r"<[^>]+>", " ", body)
    return re.sub(r"\s+", " ", body).strip()


# ---------- 1) 23 个 syllabus 页 ----------
PATTERNS = {
    "first_examination": r"[Ff]irst examination[^.]{0,160}",
    "examination_from": r"[Ee]xamination from \d{4}[^.]{0,160}",
    "teaching_from": r"[Tt]eaching from \d{4}[^.]{0,160}",
    "available_series": r"[Aa]vailable in the [^.]{0,160}",
    "series_mention": r"[^.]{0,120}\b(?:June|November|March)\b[^.]{0,120}series[^.]{0,160}",
    "last_examination": r"[Ll]ast examination[^.]{0,160}",
    "withdrawal": r"[Ww]ithdrawn?[^.]{0,160}",
    "availability_heading": r"[Aa]vailability[^.]{0,200}",
}

syl_out = {"generated_at": now, "method_zh": "抓取 syllabuses.json 的 source_url 页面，提取可用系列/首考片段；只走仓库 Fetcher（robots/限速/单线程）", "codes": {}}
for code in CODES:
    e = by_code.get(code)
    rec = {"title": e.get("title") if e else None, "source_url": e.get("source_url") if e else None,
           "error": "no syllabus entry", "snippets": {}}
    if e and e.get("source_url"):
        r = fetcher.get_text(e["source_url"])
        rec["error"] = r.error
        rec["final_url"] = getattr(r, "url", None) or getattr(r, "final_url", None)
        if r.text:
            body = strip_html(r.text)
            rec["chars"] = len(body)
            snippets = {}
            for name, pat in PATTERNS.items():
                hits = []
                for m in re.finditer(pat, body):
                    hits.append(m.group(0).strip())
                    if len(hits) >= 2:
                        break
                if hits:
                    snippets[name] = hits
            rec["snippets"] = snippets
    syl_out["codes"][code] = rec
    print(f"syllabus {code}: err={rec['error']} chars={rec.get('chars')} snips={list(rec.get('snippets', {}).keys())}")

(OUT / "gap1_syllabus_availability.json").write_text(
    json.dumps(syl_out, ensure_ascii=False, indent=1), encoding="utf-8")
print("wrote gap1_syllabus_availability.json")

# ---------- 2) pre-release xlsx ----------
xlsx_url = "https://www.cambridgeinternational.org/Images/761208-early-question-papers-and-pre-release-material-november-2026.xlsx"
r = fetcher.get(xlsx_url, expect_binary=True)
pre = {"url": xlsx_url, "http": getattr(r, "status", None), "error": r.error}
if r.ok and r.content:
    pre["bytes"] = len(r.content)
    pre["sha256"] = hashlib.sha256(r.content).hexdigest()
    pre["magic"] = r.content[:8].decode("latin-1", "replace")
    try:
        zf = zipfile.ZipFile(BytesIO(r.content))
        names = zf.namelist()
        pre["zip_entries"] = names[:30]
        # 共享字符串表
        shared = []
        if "xl/sharedStrings.xml" in names:
            ss = zf.read("xl/sharedStrings.xml").decode("utf-8", "replace")
            shared = re.findall(r"<t[^>]*>(.*?)</t>", ss, flags=re.S)
            shared = [re.sub(r"<[^>]+>", "", s) for s in shared]
        pre["shared_strings_count"] = len(shared)
        pre["shared_strings_sample"] = shared[:80]
        # 工作表：按行拼接文本，找 pre-release 行
        sheet_names = [n for n in names if re.match(r"xl/worksheets/sheet\d+\.xml$", n)]
        rows_text = []
        if sheet_names:
            sx = zf.read(sorted(sheet_names)[0]).decode("utf-8", "replace")
            # 每个 <row ...>...</row> 转成单元格文本
            for rm in re.finditer(r"<row[^>]*>(.*?)</row>", sx, flags=re.S):
                cells = re.findall(r"<c[^>]*?(?:t=\"(\w+)\")?[^>]*>(?:<v>(.*?)</v>|<is><t[^>]*>(.*?)</t></is>)?</c>", rm.group(1), flags=re.S)
                vals = []
                for t, v, inline in cells:
                    if t == "s" and v is not None and v.isdigit():
                        idx = int(v)
                        vals.append(shared[idx] if idx < len(shared) else "")
                    elif inline:
                        vals.append(inline)
                    elif v is not None:
                        vals.append(v)
                rows_text.append(vals)
        pre["rows"] = rows_text
    except Exception as exc:  # noqa: BLE001
        pre["parse_error"] = f"{type(exc).__name__}: {exc}"
(OUT / "gap4_pre_release_xlsx.json").write_text(json.dumps(pre, ensure_ascii=False, indent=1), encoding="utf-8")
print("wrote gap4_pre_release_xlsx.json  bytes=", pre.get("bytes"), "rows=", len(pre.get("rows") or []))

# ---------- 3) MC answer sheet PDF ----------
mc_url = "https://www.cambridgeinternational.org/Images/86445-supplementary-multiple-choice-answer-sheet-exam-day-form-2a.pdf"
r2 = fetcher.get(mc_url, expect_binary=True)
mc = {"url": mc_url, "http": getattr(r2, "status", None), "error": r2.error,
      "content_type": getattr(r2, "content_type", None), "robots_blocked": getattr(r2, "robots_blocked", None)}
if r2.ok and r2.content:
    mc["bytes"] = len(r2.content)
    mc["sha256"] = hashlib.sha256(r2.content).hexdigest()
    mc["magic"] = r2.content[:8].decode("latin-1", "replace")
    # 提取 PDF 内可见文本片段（若未压缩），确认标题
    txt = r2.content.decode("latin-1", "replace")
    mc_meta = re.findall(r"/Title\s*\(([^)]{0,120})\)", txt)
    if mc_meta:
        mc["pdf_title"] = mc_meta[0]
    p = DOWNLOADS / "cie_mc_answer_sheet_form2a.pdf"
    p.write_bytes(r2.content)
    mc["saved_then_deleted"] = str(p)
(OUT / "gap5_mc_answer_sheet.json").write_text(json.dumps(mc, ensure_ascii=False, indent=1), encoding="utf-8")
print("wrote gap5_mc_answer_sheet.json  bytes=", mc.get("bytes"), "sha=", mc.get("sha256"))

# 清理下载原件（版权原件不留存）
for f in [DOWNLOADS / "cie_mc_answer_sheet_form2a.pdf"]:
    if f.exists():
        f.unlink()
        print("deleted", f)

fetcher.close()
