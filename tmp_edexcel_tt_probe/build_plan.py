"""构建 Edexcel 下载计划 v2（权威版）。

输入：
  evidence/cdx_full_{root,intgcse,ukgcse,ial}.json  全量 CDX 捕获（header+rows）
  evidence/landing.html                             live 落地页（live 候选）
  evidence/content_check.json                       已核验样本
输出：
  evidence/download_plan_v2.json
"""

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

EV = Path(r"C:/Users/weo/Desktop/api/tmp_edexcel_tt_probe/evidence")

MONTH_WORDS = {"january": 1, "jan": 1, "june": 6, "jun": 6, "summer": 6,
               "april": 6, "apr": 6, "may": 6, "october": 10, "oct": 10,
               "november": 11, "nov": 11}
MONTH_RE = re.compile(r"(?<![a-z])(january|jan|june|jun|summer|april|apr|may|october|oct|november|nov)(?![a-z])")

EXCLUDE_RE = re.compile(
    r"btec|lcci|plsc|ipls|awards?[-_]|certificate|t[-_ ]levels?|functional|extended[-_ ]maths|"
    r"l2[-_]|l3[-_]|core[-_]maths|pamphlet|updates[-_]pearson|start[-_]times|post[-_]results|"
    r"results[-_]|entry[-_]|guidance|notice|faq|overview|swj|inset", re.I)

R_CODE_RE = re.compile(
    r"(?<![a-z])r[-_ ]?code(?![a-z])|(?<![a-z])r[-_ ]?paper(?![a-z])|intgcser|igcse[-_ ]?r(?![a-z])|"
    r"gcse[-_ ]?r(?![a-z])|[-_ ]r[-_ .)]|[-_ ]r$", re.I)

FOLDERS = {"root": "Examination-timetables",
           "intgcse": "Examination-timetables-for-Edexcel-International-GCSE",
           "ukgcse": "Examination-timetables-for-UK-Edexcel-GCSE",
           "ial": "Examination-timetables-for-International-Advanced-Levels"}


def norm_url(u):
    u = u.replace(":80/", "/")
    u = re.sub(r"^http://", "https://", u)
    return u


def load_cdx_rows():
    rows = []
    for key in ("root", "intgcse", "ukgcse", "ial"):
        p = EV / f"cdx_full_{key}.json"
        if not p.exists():
            continue
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not raw:
            continue
        if isinstance(raw[0], list):
            header = raw[0]
            for r in raw[1:]:
                d = dict(zip(header, r))
                d["_folder"] = key
                rows.append(d)
        elif isinstance(raw[0], dict):
            for r in raw:
                d = dict(r)
                d.setdefault("_folder", key)
                rows.append(d)
    return rows


def group_captures(rows):
    """按 (归一 URL, digest) 去重，每个 digest 选最佳捕获。"""
    by_url = defaultdict(lambda: defaultdict(list))
    for r in rows:
        url = norm_url(r["original"])
        digest = r.get("digest") or ""
        by_url[url][digest].append(r)

    out = []
    for url, digests in by_url.items():
        caps = []
        for digest, rs in digests.items():
            best = None
            for r in rs:
                st = str(r.get("statuscode"))
                try:
                    ln = int(r.get("length") or 0)
                except (TypeError, ValueError):
                    ln = 0
                key = (st == "200", ln)
                if best is None or key > best[0]:
                    best = (key, r, st, ln)
            _, r, st, ln = best
            caps.append({"url": url, "digest": digest, "timestamp": r["timestamp"],
                         "status": st, "length": ln, "folder": r.get("_folder"),
                         "cap_years": sorted({x["timestamp"][:4] for x in rs})})
        caps.sort(key=lambda c: (c["status"] != "200", -c["length"]))
        out.extend(caps[:4])
    return out


def month_of(name):
    m = MONTH_RE.search(name)
    return MONTH_WORDS[m.group(1)] if m else None


def extract_season(name, cap_years):
    """返回 (year, month, confidence)。confidence: high/medium/low。"""
    mword = month_of(name)
    years = [int(y) for y in re.findall(r"(?<!\d)(20[1-2]\d)(?!\d)", name)]
    years = [y for y in years if 2015 <= y <= 2027]
    yymm = []
    for m in re.finditer(r"(?<!\d)(\d{2})(01|06|10|11)(?!\d)", name):
        yy, mm = int(m.group(1)), int(m.group(2))
        if 15 <= yy <= 27:
            yymm.append((2000 + yy, mm))
    if years and mword:
        return years[0], mword, "high"
    if years:
        return years[0], None, "medium"
    if yymm:
        y, mm = yymm[0]
        conf = "high"
        # 捕获年份合理性检查：文件捕获应发生在考季前 1-2 年至之后 3 年内
        if cap_years:
            cy = [int(c) for c in cap_years]
            if not any(y - 2 <= c <= y + 3 for c in cy):
                conf = "low"
        return y, mm, conf
    return None, None, None


def family_of(name, folder):
    if folder == "intgcse":
        return "intgcse"
    if folder == "ukgcse":
        return "gcse"
    if folder == "ial":
        return "ial"
    n = name
    if re.search(r"international[-_ ]?gcse|int[-_ ]?gcse|intgcse|igcse", n):
        return "intgcse"
    if re.search(r"international[-_ ]?advanced[-_ ]?level|int[-_ ]?a[-_ ]?level|(?<![a-z])ial(?![a-z])", n):
        return "ial"
    if re.search(r"(?<![a-z])gcse(?![a-z])", n):
        return "intgcse" if "international" in n else "gcse"
    if re.search(r"(?<![a-z])gce(?![a-z])|a[-_ ]?level", n):
        return "gce"
    return None


def label_of(name):
    if re.search(r"provisional|(?<![a-z])prov(?![a-z])", name):
        return "provisional"
    if "final" in name:
        return "final"
    return "unknown"


def variant_of(name):
    return "R" if R_CODE_RE.search(name) else "standard"


def classify(name, folder, cap_years):
    fam = family_of(name, folder)
    if fam is None:
        return None
    if EXCLUDE_RE.search(name):
        return {"excluded": True, "family": fam}
    year, month, conf = extract_season(name, cap_years)
    return {"excluded": False, "family": fam, "year": year, "month": month,
            "confidence": conf, "label": label_of(name), "variant": variant_of(name)}


def parse_live_links():
    p = EV / "landing.html"
    if not p.exists():
        return []
    html = p.read_text(encoding="utf-8", errors="replace")
    found = set()
    for m in re.finditer(r"/content/dam/pdf/Support/([A-Za-z0-9%\-_/. ]+?\.(?:pdf|xlsx))", html):
        found.add("/content/dam/pdf/Support/" + m.group(1).strip())
    out = []
    for path in sorted(found):
        url = "https://qualifications.pearson.com" + path.replace(" ", "%20")
        folder = None
        for k, f in FOLDERS.items():
            if f"/{f}/" in path:
                folder = k
        name = path.rsplit("/", 1)[-1].lower()
        out.append({"url": url, "name": name, "folder": folder, "ext": name.rsplit(".", 1)[-1]})
    return out


def main():
    rows = load_cdx_rows()
    print(f"loaded {len(rows)} cdx rows")
    caps = group_captures(rows)
    print(f"distinct (url,digest) candidates: {len(caps)}")

    # 内容核验标记
    verified = {}
    vp = EV / "content_check.json"
    if vp.exists():
        for rec in json.loads(vp.read_text(encoding="utf-8")):
            if rec.get("url") and rec.get("ts") and rec.get("status") != 302:
                verified[(norm_url(rec["url"]), rec["ts"])] = rec

    plan = defaultdict(list)
    unclassified = []
    excluded = []
    for c in caps:
        name = c["url"].rsplit("/", 1)[-1].lower()
        name = re.sub(r"\.(pdf|xlsx)$", "", name).replace("%20", " ")
        ext = c["url"].rsplit(".", 1)[-1].lower()
        cls = classify(name, c.get("folder"), c["cap_years"])
        if cls is None:
            unclassified.append({"url": c["url"], "status": c["status"], "length": c["length"],
                                 "reason": "family unknown"})
            continue
        if cls.get("excluded"):
            excluded.append({"url": c["url"], "reason": "family excluded"})
            continue
        if ext != "pdf":
            excluded.append({"url": c["url"], "reason": f"ext {ext}"})
            continue
        if cls["year"] is None or cls["month"] is None:
            unclassified.append({"url": c["url"], "status": c["status"], "length": c["length"],
                                 "family": cls["family"], "variant": cls["variant"],
                                 "label": cls["label"], "reason": "season unknown",
                                 "cap_years": c["cap_years"]})
            continue
        key = f"{cls['family']}|{cls['year']}|{cls['month']:02d}"
        if cls["variant"] == "R":
            key += "|R"
        v = verified.get((c["url"], c["timestamp"]))
        cand = {"url": c["url"], "kind": "wayback", "timestamp": c["timestamp"],
                "status": c["status"], "length": c["length"], "digest": c["digest"],
                "label": cls["label"], "confidence": cls["confidence"],
                "name": c["url"].rsplit("/", 1)[-1]}
        if v:
            cand["verified"] = {"season_words": v.get("season_words"), "years": v.get("years"),
                                "pages": v.get("pages"), "file": v.get("file")}
        plan[key].append(cand)

    # live 链接
    live_links = parse_live_links()
    live_extra = []
    for l in live_links:
        if l["ext"] != "pdf":
            continue
        cls = classify(l["name"], l["folder"], [])
        if cls is None or cls.get("excluded"):
            continue
        if cls["year"] is None or cls["month"] is None:
            live_extra.append(l)
            continue
        key = f"{cls['family']}|{cls['year']}|{cls['month']:02d}"
        if cls["variant"] == "R":
            key += "|R"
        plan[key].append({"url": l["url"], "kind": "live", "timestamp": None,
                          "status": "200", "length": 0, "digest": None,
                          "label": cls["label"], "confidence": cls["confidence"],
                          "name": l["name"]})

    # 排序候选：verified > live > final > 200 > 大文件
    def score(c):
        s = 0
        if c.get("verified"):
            s += 1000
        if c["kind"] == "live":
            s += 100
        if c["label"] == "final":
            s += 50
        if c["status"] == "200":
            s += 20
        s += min(c["length"], 10**7) / 10**7
        return -s

    plan_out = {}
    for key, cands in sorted(plan.items()):
        fam, year, month, *rest = key.split("|")
        cands.sort(key=score)
        plan_out[key] = {"family": fam, "year": int(year), "month": int(month),
                         "variant": rest[0] if rest else "standard",
                         "candidates": cands}

    # 缺口
    GRID = {
        "gcse": {6: range(2015, 2028), 11: range(2015, 2027), 1: [2016, 2017, 2018]},
        "intgcse": {6: range(2015, 2028), 1: range(2015, 2023), 11: range(2020, 2027)},
        "ial": {1: range(2016, 2028), 6: range(2016, 2028), 10: range(2016, 2027)},
        "gce": {6: range(2015, 2028), 10: [2020, 2021]},
    }
    gaps = []
    for fam, months in GRID.items():
        for month, years in months.items():
            for y in years:
                key = f"{fam}|{y}|{month:02d}"
                if key not in plan_out:
                    gaps.append(key)
    r_keys = sorted(k for k in plan_out if k.endswith("|R"))

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_rows": len(rows),
        "plan": plan_out,
        "gaps": gaps,
        "r_variants": r_keys,
        "unclassified": unclassified,
        "excluded": excluded,
        "live_extra": live_extra,
    }
    (EV / "download_plan_v2.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\nseasons in plan: {len(plan_out)}")
    for key in sorted(plan_out):
        cands = plan_out[key]["candidates"]
        best = cands[0]
        print(f"  {key:18s} {len(cands)} cand  best: {best['kind']:7s} {best['status']} "
              f"{best['length']:>8} {best['label']:11s} {best['name'][:58]}")
    print(f"\ngaps ({len(gaps)}):")
    for g in gaps:
        print("  ", g)
    print(f"\nR variants: {r_keys}")
    print(f"unclassified: {len(unclassified)}  excluded: {len(excluded)}  live_extra: {len(live_extra)}")
    print("\nsaved download_plan_v2.json")


if __name__ == "__main__":
    main()
