"""Download a per-province sample pack from the GitHub inventory.

Reads logs/inventory.csv for URLs, downloads ~55 files:
  - samples/_shared/            shared national papers (全国卷)
  - samples/by-province/<省>/   province-specific papers
Writes samples/manifest.csv with url/bytes/sha256/status.

Fallback: raw.githubusercontent.com -> cdn.jsdelivr.net
"""
import csv
import hashlib
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

# (dest_group, repo, path)  dest_group = "_shared" or province name
PICKS = [
    # ---- shared national papers ----
    ("_shared", "qingshuo/China-Gaokao-Papers-Collection", "papers/2024/全国/数学/2024新高考1(山东,广东,湖南,湖北,河北,江苏,福建,浙江,河南,江西,安徽).pdf"),
    ("_shared", "qingshuo/China-Gaokao-Papers-Collection", "papers/2024/全国/语文/新课标Ⅰ语文-试题-p.pdf"),
    ("_shared", "qingshuo/China-Gaokao-Papers-Collection", "papers/2024/全国/英语/新课标Ⅰ英语-试题-p.pdf"),
    ("_shared", "qingshuo/China-Gaokao-Papers-Collection", "papers/2024/全国/数学/2024新高考2(辽宁,重庆,海南,吉林,黑龙江,山西,云南,广西,甘肃,贵州,新疆).pdf"),
    ("_shared", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/全国/数学/2025全国1(山东,广东,湖南,湖北,河北,江苏,福建,浙江,河南,江西,安徽).pdf"),
    ("_shared", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/全国/数学/2025全国2(辽宁,重庆,海南,吉林,黑龙江,山西,云南,广西,甘肃,贵州,新疆,四川,内蒙古,陕西,青海,宁夏,西藏).pdf"),
    ("_shared", "qingshuo/China-Gaokao-Papers-Collection", "papers/2026/全国/数学/2026全国1(山东,广东,湖南,湖北,河北,江苏,福建,浙江,河南,江西,安徽).pdf"),
    ("_shared", "qingshuo/China-Gaokao-Papers-Collection", "papers/2026/全国/数学/2026全国2(辽宁,重庆,海南,吉林,黑龙江,山西,云南,广西,甘肃,贵州,新疆,四川,内蒙古,陕西,青海,宁夏,西藏).pdf"),
    ("_shared", "deekur/gaokaophysics", "普通高考/2025/2025黑吉辽蒙.pdf"),
    ("_shared", "deekur/gaokaophysics", "普通高考/2025/2025陕晋宁青.pdf"),
    ("_shared", "deekur/gaokaophysics", "普通高考/2026/2026黑吉辽蒙.pdf"),
    ("_shared", "deekur/gaokaophysics", "普通高考/2026/2026陕晋青宁.pdf"),
    ("_shared", "deekur/gaokaophysics", "普通高考/2025/2025全国理综(西藏,新疆).pdf"),
    ("_shared", "qingshuo/China-Gaokao-Papers-Collection", "papers/supplements/2025/全国/化学/2025年高考化学答案解析（黑龙江、吉林、辽宁、内蒙古）.pdf"),
    ("_shared", "qingshuo/China-Gaokao-Papers-Collection", "papers/2026/全国/历史/2026西北高考历史.docx"),
    # ---- 北京 ----
    ("北京", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/BJ/数学/北京数学.pdf"),
    ("北京", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/BJ/化学/2025年高考北京化学.pdf"),
    ("北京", "qingshuo/China-Gaokao-Papers-Collection", "papers/2026/BJ/数学/数学（北京卷）.pdf"),
    # ---- 天津 ----
    ("天津", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/TJ/数学/2025天津.pdf"),
    ("天津", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/TJ/物理/2025天津.pdf"),
    # ---- 上海 ----
    ("上海", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/SH/数学/2025上海.pdf"),
    ("上海", "qingshuo/China-Gaokao-Papers-Collection", "papers/2024/SH/化学/上海化学-试题-p.pdf"),
    ("上海", "qingshuo/China-Gaokao-Papers-Collection", "papers/2026/SH/物理/物理上海.pdf"),
    # ---- 浙江 ----
    ("浙江", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/ZJ/物理/2025浙江1月.pdf"),
    ("浙江", "qingshuo/China-Gaokao-Papers-Collection", "papers/2024/ZJ/英语/浙江英语-1月-试题-p.pdf"),
    ("浙江", "qingshuo/China-Gaokao-Papers-Collection", "papers/2026/ZJ/物理/2026浙江6月.pdf"),
    # ---- 江苏 ----
    ("江苏", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/JS/化学/2025年高考江苏化学.pdf"),
    ("江苏", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/JS/历史/2025年高考江苏历史.pdf"),
    ("江苏", "qingshuo/China-Gaokao-Papers-Collection", "papers/2026/JS/物理/2026江苏.pdf"),
    # ---- 山东 ----
    ("山东", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/SD/化学/2025年高考山东化学.pdf"),
    ("山东", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/SD/地理/2025年高考山东地理.pdf"),
    ("山东", "qingshuo/China-Gaokao-Papers-Collection", "papers/2026/SD/物理/2026山东.pdf"),
    # ---- 广东 ----
    ("广东", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/GD/化学/2025年高考广东化学卷.pdf"),
    ("广东", "qingshuo/China-Gaokao-Papers-Collection", "papers/2026/GD/地理/广东地理.pdf"),
    ("广东", "qingshuo/China-Gaokao-Papers-Collection", "papers/2026/GD/物理/2026广东.pdf"),
    # ---- 湖北 ----
    ("湖北", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/HB/生物/2025高考湖北卷生物真题试卷.pdf"),
    ("湖北", "qingshuo/China-Gaokao-Papers-Collection", "papers/2026/HB/物理/2026湖北.pdf"),
    # ---- 湖南 ----
    ("湖南", "qingshuo/China-Gaokao-Papers-Collection", "papers/2026/HN/物理/2026湖南.pdf"),
    ("湖南", "deekur/gaokaomath", "普通高考/2025/2025全国1(山东,广东,湖南,湖北,河北,江苏,福建,浙江,河南,江西,安徽).pdf"),
    # ---- 河南 ----
    ("河南", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/HA/化学/2025年高考河南化学卷完整版.pdf"),
    ("河南", "qingshuo/China-Gaokao-Papers-Collection", "papers/2026/HA/物理/2026河南.pdf"),
    # ---- 河北 ----
    ("河北", "qingshuo/China-Gaokao-Papers-Collection", "papers/2026/HE/物理/2026河北.pdf"),
    ("河北", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/HE/化学/2025高考河北化学卷.docx"),
    # ---- 福建 ----
    ("福建", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/FJ/物理/2025年高考福建物理1.pdf"),
    ("福建", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/FJ/化学/2025年高考福建化学卷.pdf"),
    # ---- 安徽 ----
    ("安徽", "qingshuo/China-Gaokao-Papers-Collection", "papers/2026/AH/生物/2026年安徽高考生物试卷.pdf"),
    ("安徽", "qingshuo/China-Gaokao-Papers-Collection", "papers/supplements/2025/AH/物理/2025安徽.pdf"),
    # ---- 江西 ----
    ("江西", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/JX/物理/江西省 2025 年普通高中学业水平选择性考试-物理试题.pdf"),
    # ---- 四川 ----
    ("四川", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/SC/地理/2025年高考四川地理.docx"),
    ("四川", "qingshuo/China-Gaokao-Papers-Collection", "papers/2026/SC/物理/2026四川.pdf"),
    # ---- 贵州 ----
    ("贵州", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/GZ/地理/2025年高考贵州地理.docx"),
    ("贵州", "qingshuo/China-Gaokao-Papers-Collection", "papers/2026/GZ/物理/2026贵州.pdf"),
    # ---- 云南 ----
    ("云南", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/YN/物理/2025年高考云南物理.pdf"),
    ("云南", "qingshuo/China-Gaokao-Papers-Collection", "papers/2026/YN/物理/2026云南.pdf"),
    # ---- 海南 ----
    ("海南", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/HI/物理/2025年高考海南卷物理真题.pdf"),
    # ---- 重庆 ----
    ("重庆", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/CQ/物理/2025重庆.pdf"),
    # ---- 广西 ----
    ("广西", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/GX/物理/2025广西.pdf"),
    # ---- 甘肃 ----
    ("甘肃", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/GS/化学/2025年高考甘肃化学.pdf"),
    ("甘肃", "deekur/gaokaophysics", "普通高考/2026/2026甘肃.pdf"),
    # ---- 辽宁 ----
    ("辽宁", "qingshuo/China-Gaokao-Papers-Collection", "papers/2025/LN/化学/2025年高考化学黑吉辽蒙.pdf"),
    # ---- 吉林 / 黑龙江 / 内蒙古 -> shared 黑吉辽蒙 + 全国2 ----
    # ---- 山西 / 陕西 / 青海 / 宁夏 -> shared 陕晋宁青 ----
    # ---- 西藏 / 新疆 -> shared 2025全国理综 ----
    # ---- docx samples from Zaxaerith ----
    ("_shared", "Zaxaerith/GaokaoCHN", "2024/2024年新课标I卷语文.docx"),
    ("_shared", "Zaxaerith/GaokaoENG", "2024/2024年甲卷英语.docx"),
    ("_shared", "Zaxaerith/GaokaoGEO", "2024/2024年山东地理.docx"),
    ("_shared", "Zaxaerith/GaokaoGEO", "2024/2024年湖北地理.docx"),
]


def build_url(repo, path):
    enc = "/".join(urllib_quote(p) for p in path.split("/"))
    return f"https://raw.githubusercontent.com/{repo}/main/{enc}"


def urllib_quote(s):
    from urllib.parse import quote
    return quote(s, safe="")


def jsdelivr(repo, path):
    enc = "/".join(urllib_quote(p) for p in path.split("/"))
    return f"https://cdn.jsdelivr.net/gh/{repo}@main/{enc}"


def fetch(url, dest):
    p = subprocess.run(
        ["curl", "-sL", "-A", UA, "--max-time", "120", "-o", str(dest), "-w", "%{http_code}", url],
        capture_output=True, text=True)
    return p.stdout.strip()


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def header_ok(path):
    with open(path, "rb") as f:
        head = f.read(8)
    if head[:4] == b"%PDF":
        return "pdf"
    if head[:2] == b"PK":
        return "zip/docx"
    return "?"


def main():
    inv = {}
    with open(ROOT / "logs" / "inventory.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            inv[(r["repo"], r["path"])] = r

    base_count = Counter()
    for group, repo, path in PICKS:
        if (repo, path) in inv:
            base_count[(group, path.split("/")[-1])] += 1

    rows = []
    jobs = []
    for group, repo, path in PICKS:
        key = (repo, path)
        if key not in inv:
            rows.append(dict(group=group, repo=repo, path=path, url="", bytes="", sha256="", status="NOT_IN_INVENTORY", header=""))
            continue
        url = inv[key]["url"]
        if group == "_shared":
            dest_dir = ROOT / "samples" / "_shared"
        else:
            dest_dir = ROOT / "samples" / "by-province" / group
        dest_dir.mkdir(parents=True, exist_ok=True)
        base = path.split("/")[-1]
        if base_count[(group, base)] > 1:
            base = f"{path.split('/')[-2]}-{base}"
        dest = dest_dir / base
        jobs.append((group, repo, path, url, dest))

    def work(job):
        group, repo, path, url, dest = job
        code = fetch(url, dest)
        status = f"http_{code}"
        if code != "200" or not dest.exists() or dest.stat().st_size == 0:
            alt = jsdelivr(repo, path)
            code2 = fetch(alt, dest)
            status += f"/fallback_{code2}"
            url_used = alt if code2 == "200" else url
        else:
            url_used = url
        size = dest.stat().st_size if dest.exists() else 0
        hdr = header_ok(dest) if size > 0 else ""
        sha = sha256(dest) if size > 0 else ""
        return dict(group=group, repo=repo, path=path, url=url_used, bytes=size, sha256=sha, status=status, header=hdr)

    with ThreadPoolExecutor(max_workers=6) as ex:
        for r in ex.map(work, jobs):
            rows.append(r)
            print(r["status"], r["header"], r["bytes"], r["group"], r["path"].split("/")[-1], flush=True)

    out = ROOT / "samples" / "manifest.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["group", "repo", "path", "url", "bytes", "sha256", "status", "header"])
        w.writeheader()
        w.writerows(rows)
    ok = sum(1 for r in rows if r["status"].startswith("http_200"))
    tot_bytes = sum(int(r["bytes"] or 0) for r in rows)
    print(f"\nwrote {out}: {ok}/{len(rows)} ok, {tot_bytes/1e6:.1f} MB")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
