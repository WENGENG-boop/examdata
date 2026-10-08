"""Zone 5 时间表最终整合：规范命名 + 逐季核验 + 矩阵 JSON。"""

import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
import pymupdf

OUT = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe")
EV = OUT / "evidence"
DL = OUT / "downloads"
FINAL = DL / "zone5_final"
FINAL.mkdir(exist_ok=True)

# season -> (localfile, source_kind, source_url, capture_ts)
MAP = {
    "2017-06": ("zone5_2017-06.pdf", "wayback", "http://www.cambridgeinternational.org:80/images/340764-june-2017-timetable-zone-5.pdf", "20171013034848"),
    "2017-11": ("zone5_2017-11.pdf", "wayback", "http://www.cambridgeinternational.org:80/images/373326-november-2017-timetable-zone-5.pdf", "20171013021925"),
    "2018-06": ("zone5_2018-06.pdf", "official", "https://www.cambridgeinternational.org/Images/422448-zone-5-june-2018-timetable.pdf", None),
    "2018-11": ("zone5_2018-11.pdf", "wayback", "http://www.cambridgeinternational.org:80/Images/469286-zone-5-november-2018-timetable.pdf", "20180613164739"),
    "2019-11": ("archive_469286_20190825002103.pdf", "wayback", "https://www.cambridgeinternational.org/Images/469286-zone-5-november-timetable.pdf", "20190825002103"),
    "2020-06": ("zone5_2020-06.pdf", "wayback", "https://www.cambridgeinternational.org/Images/513557-june-2020-timetable-zone-5.pdf", "20201001225904"),
    "2021-06": ("zone5_2021-06.pdf", "official", "https://www.cambridgeinternational.org/Images/513557-june-2021-timetable-zone-5.pdf", None),
    "2021-11": ("archive_469286_20210907154816.pdf", "wayback", "https://www.cambridgeinternational.org/Images/469286-zone-5-november-timetable.pdf", "20210907154816"),
    "2022-06": ("zone5_2022-06.pdf", "wayback", "https://www.cambridgeinternational.org/Images/638139-june-2022-zone-5-time-table.pdf", "20220120031648"),
    "2022-11": ("archive_469286_20221022030922.pdf", "official", "https://www.cambridgeinternational.org/Images/469286-zone-5-november-timetable.pdf", "20221022030922"),
    "2023-06": ("zone5_2023-06.pdf", "wayback", "https://www.cambridgeinternational.org/Images/638139-june-2023-zone-5-time-table.pdf", "20230102142826"),
    "2023-11": ("zone5_2023-11.pdf", "official", "https://www.cambridgeinternational.org/Images/373326-november-2023-timetable-zone-5.pdf", None),
    "2024-06": ("zone5_2024-06.pdf", "wayback", "https://www.cambridgeinternational.org/Images/638139-june-2024-zone-5-time-table.pdf", "20240226202036"),
    "2024-11": ("zone5_2024-11.pdf", "official", "https://www.cambridgeinternational.org/Images/710670-november-2024-zone-5-timetable.pdf", None),
    "2025-06": ("zone5_2025-06.pdf", "official", "https://www.cambridgeinternational.org/Images/722879-june-2025-zone-5-timetable.pdf", None),
    "2025-11": ("zone5_2025-11.pdf", "wayback", "https://www.cambridgeinternational.org/Images/732807-november-2025-zone-5-timetable.pdf", "20250401154935"),
    "2026-06": ("zone5_2026-06.pdf", "official", "https://www.cambridgeinternational.org/Images/745760-june-2026-zone-5-timetable.pdf", None),
    "2026-11": ("zone5_2026-11.pdf", "official", "https://www.cambridgeinternational.org/Images/757650-november-2026-zone-5-timetable.pdf", None),
}

def series_of(b):
    doc = pymupdf.open(stream=b, filetype="pdf")
    txt = "".join(p.get_text() for p in doc[:3])
    t = re.sub(r"\s+", " ", txt)
    m = re.search(r"(?:Final Exam Timetable|Exam Timetable)\s+((?:June|November|March|May|October)\s+20\d\d)", t)
    if not m:
        m = re.search(r"\b((?:June|November|March|May|October)\s+20\d\d)\b", t)
    return (m.group(1) if m else None), len(doc)

matrix = {}
ok = 0
for season, (fname, kind, url, ts) in MAP.items():
    fp = DL / fname
    if not fp.exists():
        matrix[season] = {"error": "file missing", "file": fname}
        print(f"✘ {season}: 缺 {fname}")
        continue
    b = fp.read_bytes()
    s, pages = series_of(b)
    want = ("June " if season.endswith("-06") else "November ") + season[:4]
    match = (s == want)
    shutil.copyfile(fp, FINAL / f"{season}.pdf")
    sha = hashlib.sha256(b).hexdigest()
    matrix[season] = {
        "file": f"zone5_final/{season}.pdf", "bytes": len(b), "sha256": sha,
        "pages": pages, "series_detected": s, "series_expected": want, "match": match,
        "source_kind": kind, "source_url": url, "wayback_ts": ts,
        "wayback_replay_url": (f"https://web.archive.org/web/{ts}id_/{url}" if ts else None),
    }
    ok += int(match)
    print(f"{'✔' if match else '✘'} {season}: {s} pages={pages} bytes={len(b)} [{kind}]")

gaps = {
    "2013-11": "Wayback 仅存 404 记录（2024-07-13 抓取），官网在线 404；文件已下架且从未被存档",
    "2014-06": "同上（152491，2024-07-14 404 记录）",
    "2015-06": "同上（180301，2024-06 两 404 记录）",
    "2015-11": "同上（207027，2024-06-20 404）",
    "2016-06": "同上（267322，2024-08-07 404）",
    "2016-11": "同上（296275，仅 2017 年 301 与 404 记录）",
    "2019-06": "文件 513557-june-2019-timetable-zone-5.pdf 从未被有效存档（CDX 仅 1 条 2024-06-16 404）；同 ID 于 2020/2021 被覆盖",
    "2020-11": "该季文件（469286 无年份命名）在 2020 时点无任何 Wayback 抓取；后续同 URL 内容已被 2021/2022 覆盖；官网无历年归档版",
}
EV.joinpath("zone5_final_matrix.json").write_text(json.dumps({
    "generated_by": "tmp_materials_probe/probe_timetable_final.py",
    "source_of_truth": "https://www.cambridgeinternational.org/exam-administration/cambridge-exams-officers-guide/phase-1-preparation/timetabling-exams/exam-timetables/",
    "seasons": matrix, "unobtainable": gaps,
}, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n可核验 {ok}/{len(MAP)} 季；不可得 {len(gaps)} 季")
print("saved evidence/zone5_final_matrix.json")
