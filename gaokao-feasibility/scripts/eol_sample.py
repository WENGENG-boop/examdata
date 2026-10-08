"""EOL per-province sampling: fetch article page 0, parse _PAGE_COUNT + first image,
then probe the last image in the sequence. Saves a couple of sample images.

Output: logs/eol-sample.csv
"""
import csv
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def curl(url, out=None, head=False):
    cmd = ["curl", "-s", "-A", UA, "--max-time", "30"]
    if head:
        cmd += ["-o", "/dev/null", "-w", "%{http_code} %{size_download} %{content_type}"]
    else:
        cmd += ["-o", str(out), "-w", "%{http_code}"]
    cmd.append(url)
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.stdout.strip()


def parse_first_page(html):
    pm = re.search(r'_PAGE_COUNT\s*=\s*"(\d+)"', html)
    count = int(pm.group(1)) if pm else None
    im = re.search(r'src="(https?://img\d?\.eol\.cn/e_images/gk/[^"]*st/[^"]+?\.(?:jpg|jpeg|png))"', html)
    img = im.group(1) if im else None
    return count, img


def next_image(img):
    """Return (base, number, ext) for an image URL like .../sx01.jpg"""
    m = re.match(r"(.*?)(\d+)(\.(?:jpg|jpeg|png))$", img)
    if not m:
        return None
    return m.group(1), int(m.group(2)), m.group(3)


def main():
    rows = list(csv.DictReader(open(ROOT / "logs" / "eol-article-index2.csv", encoding="utf-8")))
    # pick one qp article per (year, section, subject) for selected years
    want = []
    seen = set()
    for r in rows:
        if r["kind"] != "qp" or not r["url"]:
            continue
        y = int(r["year"])
        if y not in (2023, 2024, 2025):
            continue
        key = (y, r["section_name"], r["subject"])
        if key in seen:
            continue
        seen.add(key)
        want.append(r)

    # limit: for 2023/2024 take a handful; for 2025 take all sections (per-province), prefer 数学/英语 then first available
    out_rows = []
    sample_dir = ROOT / "samples" / "eol"
    sample_dir.mkdir(parents=True, exist_ok=True)

    def do_one(r, save=None):
        url = r["url"]
        tmp = ROOT / "logs" / "eol" / "_tmp_article.html"
        code = curl(url, tmp)
        if code != "200":
            out_rows.append(dict(year=r["year"], section=r["section_name"], subject=r["subject"], url=url, page_count="", first_img="", last_img="", last_status=f"article_http_{code}", last_bytes=""))
            return
        html = tmp.read_text(encoding="utf-8", errors="replace")
        count, img = parse_first_page(html)
        if not img:
            out_rows.append(dict(year=r["year"], section=r["section_name"], subject=r["subject"], url=url, page_count=count or "", first_img="", last_img="", last_status="no_image", last_bytes=""))
            return
        nb = next_image(img)
        last_status = ""
        last_img = ""
        last_bytes = ""
        if nb and count:
            base, num, ext = nb
            last_num = num + count - 1
            last_img = f"{base}{last_num:02d}{ext}"
            st = curl(last_img, head=True)
            parts = st.split()
            last_status = parts[0] if parts else "?"
            last_bytes = parts[1] if len(parts) > 1 else ""
        if save and nb:
            base, num, ext = nb
            for i, n in enumerate(range(num, num + min(2, count or 2))):
                fn = sample_dir / f"{r['year']}_{r['section_name']}_{r['subject']}_{n:02d}{ext}"
                curl(f"{base}{n:02d}{ext}", fn)
        out_rows.append(dict(year=r["year"], section=r["section_name"], subject=r["subject"], url=url, page_count=count or "", first_img=img, last_img=last_img, last_status=last_status, last_bytes=last_bytes))

    # 2025: per section pick up to 2 subjects (数学 preferred, then 英语, then first)
    by_sec = {}
    for r in want:
        if r["year"] != "2025":
            continue
        by_sec.setdefault(r["section_name"], []).append(r)
    for sec, items in by_sec.items():
        pref = [x for x in items if x["subject"] in ("数学", "英语")]
        pref = pref[:2] if pref else items[:1]
        for r in pref:
            do_one(r, save=(sec in ("北京卷", "上海卷", "山东卷", "四川卷")))
            print("done", r["year"], sec, r["subject"], flush=True)

    # 2024: sample 6 sections x 1 subject (数学 preferred)
    by_sec24 = {}
    for r in want:
        if r["year"] != "2024":
            continue
        by_sec24.setdefault(r["section_name"], []).append(r)
    picked = 0
    for sec, items in by_sec24.items():
        if picked >= 6:
            break
        pref = [x for x in items if x["subject"] == "数学"] or items[:1]
        do_one(pref[0])
        print("done 2024", sec, pref[0]["subject"], flush=True)
        picked += 1

    # 2023: sample 4
    by_sec23 = {}
    for r in want:
        if r["year"] != "2023":
            continue
        by_sec23.setdefault(r["section_name"], []).append(r)
    picked = 0
    for sec, items in by_sec23.items():
        if picked >= 4:
            break
        pref = [x for x in items if x["subject"] == "数学"] or items[:1]
        do_one(pref[0])
        print("done 2023", sec, pref[0]["subject"], flush=True)
        picked += 1

    out = ROOT / "logs" / "eol-sample.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["year", "section", "subject", "url", "page_count", "first_img", "last_img", "last_status", "last_bytes"])
        w.writeheader()
        w.writerows(out_rows)
    print("wrote", out, len(out_rows))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
