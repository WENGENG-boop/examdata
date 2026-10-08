"""Build coverage-matrix.csv: 31 provinces x channels x evidence.

Inputs:
  logs/eol-article-index2.csv   (EOL article index: year, section, regions, url)
  logs/inventory.csv            (GitHub files: repo, year, subject, path, size, url)
  samples/manifest.csv          (downloaded samples)
Output:
  coverage-matrix.csv
"""
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PROVINCES = [
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江", "上海",
    "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南",
    "广东", "广西", "海南", "重庆", "四川", "贵州", "云南", "西藏", "陕西",
    "甘肃", "青海", "宁夏", "新疆",
]

ABBR = {
    "黑吉辽蒙": ["黑龙江", "吉林", "辽宁", "内蒙古"],
    "黑吉辽": ["黑龙江", "吉林", "辽宁"],
    "陕晋宁青": ["陕西", "山西", "宁夏", "青海"],
    "陕晋青宁": ["陕西", "山西", "青海", "宁夏"],
    "西北": ["陕西", "甘肃", "青海", "宁夏", "新疆"],
    "京津冀": ["北京", "天津", "河北"],
}


def provinces_in_text(text):
    """All provinces mentioned in text (incl. abbreviations)."""
    found = []
    for ab, ps in ABBR.items():
        if ab in text:
            found += ps
    for p in PROVINCES:
        if p in text and p not in found:
            found.append(p)
    return found


def eol_province_counts():
    """province -> {year: linked-article count} from EOL index."""
    rows = list(csv.DictReader(open(ROOT / "logs" / "eol-article-index2.csv", encoding="utf-8")))
    counts = defaultdict(lambda: defaultdict(int))
    for r in rows:
        if not r.get("url"):
            continue
        name, regions, year = r["section_name"], r["regions"], r["year"]
        prov = None
        m = re.fullmatch(r"(.+?)卷", name)
        if m and m.group(1) in PROVINCES:
            prov = [m.group(1)]
        if prov is None:
            prov = provinces_in_text(regions or "")
        if prov is None:
            prov = provinces_in_text(name)
        for p in prov or []:
            counts[p][year] += 1
    return counts


def github_province_counts():
    """province -> (count, kinds) from GitHub inventory."""
    rows = list(csv.DictReader(open(ROOT / "logs" / "inventory.csv", encoding="utf-8")))
    cnt = Counter()
    kinds = defaultdict(set)
    for r in rows:
        path = r["path"]
        fname = path.split("/")[-1]
        prov = provinces_in_text(fname) or provinces_in_text(path)
        if not prov:
            # qingshuo region-code dirs
            seg = path.split("/")
            code = None
            for i, s in enumerate(seg):
                if s in ("2024", "2025", "2026", "supplements", "partials") and i + 1 < len(seg):
                    code = seg[i + 1]
                    break
            CODE = {"BJ": "北京", "TJ": "天津", "SH": "上海", "ZJ": "浙江", "JS": "江苏",
                    "SD": "山东", "GD": "广东", "HB": "湖北", "HN": "湖南", "HA": "河南",
                    "HE": "河北", "FJ": "福建", "AH": "安徽", "JX": "江西", "SC": "四川",
                    "GZ": "贵州", "YN": "云南", "HI": "海南", "CQ": "重庆", "GX": "广西",
                    "GS": "甘肃", "LN": "辽宁"}
            if code in CODE:
                prov = [CODE[code]]
        if not prov and "2026全国理综" in fname:
            prov = ["西藏", "新疆"]
        if prov:
            for p in prov:
                cnt[p] += 1
                shared = ("全国" in fname or "全国" in path
                          or any(ab in fname for ab in ABBR)
                          or len(provinces_in_text(fname)) >= 2)
                kinds[p].add("共享" if shared else "专属")
        elif "全国" in path:
            pass  # national-only file without province list
    return cnt, kinds


def main():
    eol = eol_province_counts()
    gh, ghk = github_province_counts()

    # sample dirs
    samp = {}
    for d in sorted((ROOT / "samples" / "by-province").glob("*")):
        if d.is_dir():
            samp[d.name] = len([f for f in d.iterdir() if f.is_file()])
    shared_cover = {
        "吉林": "黑吉辽蒙物理(2025/2026)", "黑龙江": "黑吉辽蒙物理(2025/2026)",
        "内蒙古": "黑吉辽蒙物理(2025/2026)",
        "山西": "陕晋宁青物理(2025)+陕晋青宁(2026)", "陕西": "陕晋宁青物理(2025)+陕晋青宁(2026)",
        "青海": "陕晋宁青物理(2025)+陕晋青宁(2026)", "宁夏": "陕晋宁青物理(2025)+陕晋青宁(2026)",
        "西藏": "2025全国理综(西藏,新疆)", "新疆": "2025全国理综(西藏,新疆)",
    }

    out = []
    for p in PROVINCES:
        e23, e24, e25, e26 = (eol[p].get(y, 0) for y in ("2023", "2024", "2025", "2026"))
        eol_level = "L1图片" if (e23 + e24 + e25) > 0 else "L5"
        gh_n = gh.get(p, 0)
        gh_kind = "+".join(sorted(ghk.get(p, []))) or "-"
        gh_level = "L1" if gh_n > 0 else "L5"
        smp = f"by-province/{p}/×{samp[p]}" if p in samp else shared_cover.get(p, "")
        overall = "L1" if (gh_level == "L1" or eol_level.startswith("L1")) else "L5"
        notes = []
        if gh_kind == "-" or gh_n == 0:
            notes.append("GitHub无直接文件")
        if p in shared_cover:
            notes.append("样本经共享卷覆盖")
        out.append({
            "province": p,
            "eol_2023": e23, "eol_2024": e24, "eol_2025": e25, "eol_2026": e26,
            "eol_level": eol_level,
            "github_files": gh_n, "github_kind": gh_kind, "github_level": gh_level,
            "commercial_level": "L3", "pan_level": "L3(下载需账号)", "hf_level": "L1题目级",
            "official_level": "L5", "overall_level": overall,
            "samples": smp, "notes": ";".join(notes),
        })

    with open(ROOT / "coverage-matrix.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    print("wrote coverage-matrix.csv:", len(out), "provinces")
    for r in out:
        print(r["province"], "| EOL", r["eol_2023"], r["eol_2024"], r["eol_2025"], r["eol_2026"],
              "| GH", r["github_files"], r["github_kind"], "| samples:", r["samples"], "|", r["overall_level"])


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    main()
