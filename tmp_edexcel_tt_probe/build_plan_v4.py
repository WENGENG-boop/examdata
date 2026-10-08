"""构建 Edexcel 下载计划 v4（在 v3 基础上加入 COVID-19 取消考季分类）。

相对 v3 的变化：
  1. CANCELLED 分类：6 个考季（2020/2021 夏考，因 COVID-19 取消）从 plan 移出，
     记录 reason/evidence 与候选文件；下载器跳过；构建/API 记为 cancelled
  2. gaps 判定排除 cancelled 考季；一致性检查覆盖 cancelled

输入：
  evidence/cdx_full_{root,intgcse,ukgcse,ial}.json
  evidence/landing.html
  evidence/content_check.json
  evidence/manual_verify.json
输出：
  evidence/download_plan_v4.json
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
    r"l2[-_]|l3[-_]|core[-_ ]maths|pamphlet|updates[-_]pearson|start[-_]times|post[-_]results|"
    r"results[-_]|entry[-_]|guidance|notice|faq|overview|swj|inset", re.I)

R_CODE_RE = re.compile(
    r"(?<![a-z])r[-_ ]?code(?![a-z])|(?<![a-z])r[-_ ]?paper(?![a-z])|intgcser|igcse[-_ ]?r(?![a-z])|"
    r"gcse[-_ ]?r(?![a-z])|[-_ ]r[-_ .)]|[-_ ]r$", re.I)

FOLDERS = {"root": "Examination-timetables",
           "intgcse": "Examination-timetables-for-Edexcel-International-GCSE",
           "ukgcse": "Examination-timetables-for-UK-Edexcel-GCSE",
           "ial": "Examination-timetables-for-International-Advanced-Levels"}

# 手动映射（basename 已 decode/lower；key 为考季键）
MANUAL = [
    {"rx": r"^8088-gcse-final-timetable-2017\.pdf$", "key": "gcse|2017|06", "label": "final",
     "note": "content-verified: UK GCSE May-June 2017 FINAL"},
    {"rx": r"^8088-gcse-provisional-timetable-2017\.pdf$", "key": "gcse|2017|06", "label": "provisional",
     "note": "content-verified: UK GCSE May-June 2017 PROVISIONAL"},
    {"rx": r"^ial_provisional_examination_dates\.pdf$", "key": "ial|2017|06", "label": "final",
     "note": "content-verified: IAL May-June 2017 FINAL"},
    {"rx": r"^ial-\s?timetable-2018-international\.pdf$", "key": "ial|2018|06", "label": "final",
     "note": "content-verified: IAL June 2018 FINAL v6"},
    {"rx": r"^international_gcse_timetable\.pdf$", "key": "intgcse|2017|01", "label": "final",
     "note": "content-verified: IntGCSE January 2017 FINAL"},
    {"rx": r"^int-advanced-levels-oct-2017-provisional-timetable\.pdf$", "key": "ial|2017|10", "label": "final",
     "note": "content-verified: IAL October 2017 FINAL (filename says provisional)"},
    {"rx": r"^october-2019-timetable-provisional\.pdf$", "key": "ial|2019|10", "label": "provisional",
     "note": "content-verified: IAL October 2019 PROVISIONAL"},
    {"rx": r"^a-level-timetable-2018-provisional\.pdf$", "key": "gce|2018|06", "label": "provisional",
     "note": "content-verified: GCE May-June 2018 PROVISIONAL"},
    {"rx": r"^a-level-timetable-2018-int-provisional\.pdf$", "key": "gce|2018|06", "label": "provisional",
     "note": "content-verified: GCE May-June 2018 PROVISIONAL (int copy)"},
]

# 经多轮 CDX 扫描确认不可得的考季（含 R 卷），带证据说明
UNOBTAINABLE = {
    "gcse|2016|01": {"reason": "no archived timetable file for UK GCSE January 2016 in any scanned CDX folder"},
    "gcse|2017|01": {"reason": "no archived timetable file for UK GCSE January 2017 in any scanned CDX folder"},
    "gcse|2018|11": {"reason": "no archived timetable file for UK GCSE November 2018 (2015/2017/2019+ exist; 2016 only 302)"},
    "intgcse|2015|01": {"reason": "only the R-paper file was archived; standard IntGCSE January 2015 file not captured",
                        "evidence": ["7201 IGCSE January 2015 R paper Timetable Final v1_DTP.pdf (200)"]},
    "intgcse|2022|11": {"reason": "series not offered (no November IntGCSE series that year)"},
}

R_UNOBTAINABLE = {
    "intgcse|2016|06|R": {"reason": "R-paper file seen in snapshots (7741_IGCSE_R_Paper_June_2016) but no CDX capture"},
    "intgcse|2017|01|R": {"reason": "R-paper file seen in snapshots (iGCSE-R-paper-Final-Timetable-January-2017) but no CDX capture"},
    "intgcse|2017|06|R": {"reason": "R-paper file seen in snapshots (International_GCSE_June_2017_final_timetable_R_code) but no CDX capture"},
    "intgcse|2019|01|R": {"reason": "R-paper file seen in snapshots (1901_intGCSER_final) but no CDX capture"},
    "intgcse|2019|06|R": {"reason": "no R file captured (standard 1906IntGCSE itself only 302)"},
    "intgcse|2021|01|R": {"reason": "only an xlsx 302 capture; no PDF archived"},
    "intgcse|2023|06|R": {"reason": "v1/v2 R files only 302 captures (int-gcse-r-paper-summer-2023-final-v2.pdf)"},
}

# COVID-19 取消考季：文件（可能）存在于档案中，但考试未举行
CANCELLED = {
    "gcse|2020|06": {
        "reason": "UK GCSE summer 2020 series cancelled (COVID-19); grades awarded by centre assessment",
        "evidence": ["UK government announcement 2020-03-18: all summer 2020 exams cancelled"],
    },
    "gce|2020|06": {
        "reason": "UK GCE A-level summer 2020 series cancelled (COVID-19); grades awarded by centre assessment",
        "evidence": ["UK government announcement 2020-03-18: all summer 2020 exams cancelled"],
    },
    "gcse|2021|06": {
        "reason": "UK GCSE summer 2021 series cancelled (COVID-19); teacher-assessed grades",
        "evidence": ["UK government announcement 2021-01-04: summer 2021 exams cancelled"],
    },
    "gce|2021|06": {
        "reason": "UK GCE A-level summer 2021 series cancelled (COVID-19); teacher-assessed grades",
        "evidence": ["UK government announcement 2021-01-04: summer 2021 exams cancelled"],
    },
    "ial|2020|06": {
        "reason": "International A Level May/June 2020 series cancelled (COVID-19)",
        "evidence": ["HKEAA announcement 2020-03-25; Pearson international May/June 2020 cancellation"],
    },
    "intgcse|2020|06": {
        "reason": "International GCSE May/June 2020 series cancelled (COVID-19)",
        "evidence": ["HKEAA announcement 2020-03-25; Pearson international May/June 2020 cancellation"],
    },
}


def norm_url(u):
    u = u.replace(":80/", "/")
    u = re.sub(r"^http://", "https://", u)
    return u


def orig_url(u):
    m = re.search(r"id_/(https?://.+)$", u)
    return m.group(1) if m else u


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

    # 内容核验标记（修正：wayback URL → 原始 URL）
    verified = {}
    for fname in ("content_check.json", "manual_verify.json"):
        vp = EV / fname
        if not vp.exists():
            continue
        for rec in json.loads(vp.read_text(encoding="utf-8")):
            if rec.get("url") and rec.get("ts") and rec.get("status") != 302:
                verified[(norm_url(orig_url(rec["url"])), rec["ts"])] = rec

    plan = defaultdict(list)
    unclassified = []
    excluded = []
    manual_mapped = []

    def manual_match(base):
        for m in MANUAL:
            if re.match(m["rx"], base):
                return m
        return None

    for c in caps:
        raw_name = c["url"].rsplit("/", 1)[-1].lower()
        base = raw_name.replace("%20", " ")
        ext = base.rsplit(".", 1)[-1]
        mm = manual_match(base)
        if mm:
            if ext != "pdf":
                excluded.append({"url": c["url"], "reason": f"ext {ext}"})
                continue
            key = mm["key"]
            v = verified.get((c["url"], c["timestamp"]))
            cand = {"url": c["url"], "kind": "wayback", "timestamp": c["timestamp"],
                    "status": c["status"], "length": c["length"], "digest": c["digest"],
                    "label": mm["label"], "confidence": "high",
                    "name": c["url"].rsplit("/", 1)[-1], "manual": mm["note"]}
            if v:
                cand["verified"] = {"season_words": v.get("season_words"), "years": v.get("years"),
                                    "pages": v.get("pages"), "file": v.get("file"),
                                    "head": (v.get("head") or "")[:200]}
            plan[key].append(cand)
            manual_mapped.append({"key": key, "name": raw_name, "ts": c["timestamp"], "note": mm["note"]})
            continue
        name = re.sub(r"\.(pdf|xlsx)$", "", raw_name).replace("%20", " ")
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
                                "pages": v.get("pages"), "file": v.get("file"),
                                "head": (v.get("head") or "")[:200]}
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
                         "viable": any(c["status"] == "200" or c["kind"] == "live" for c in cands),
                         "candidates": cands}

    # COVID-19 取消考季：从 plan 移出，保留候选与原因
    cancelled_out = {}
    for key, meta in CANCELLED.items():
        rec = dict(meta)
        rec["candidates"] = plan_out.pop(key, {}).get("candidates", [])
        cancelled_out[key] = rec

    # 缺口（网格修正版；排除 cancelled）
    GRID = {
        "gcse": {6: range(2015, 2028), 11: range(2015, 2027), 1: [2016, 2017, 2018]},
        "intgcse": {6: range(2015, 2028), 1: range(2015, 2024), 11: range(2020, 2027)},
        "ial": {1: range(2016, 2028), 6: range(2016, 2028), 10: range(2016, 2027)},
        "gce": {6: range(2015, 2028), 10: [2020], 11: [2021]},
    }
    gaps = []
    for fam, months in GRID.items():
        for month, years in months.items():
            for y in years:
                key = f"{fam}|{y}|{month:02d}"
                if key not in plan_out and key not in cancelled_out:
                    gaps.append(key)
    r_keys = sorted(k for k in plan_out if k.endswith("|R"))

    known_unobtainable = dict(UNOBTAINABLE)
    r_unobtainable = dict(R_UNOBTAINABLE)
    # 一致性检查：gaps 应全部有不可得证据；已知不可得/取消不应出现在 plan
    unexplained = [g for g in gaps if g not in known_unobtainable and g not in r_unobtainable]
    overlap = [k for k in list(known_unobtainable) + list(r_unobtainable) if k in plan_out]
    cancelled_overlap = [k for k in cancelled_out if k in plan_out]

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_rows": len(rows),
        "plan": plan_out,
        "gaps": gaps,
        "known_unobtainable": known_unobtainable,
        "r_unobtainable": r_unobtainable,
        "cancelled": cancelled_out,
        "r_variants": r_keys,
        "manual_mapped": manual_mapped,
        "unclassified": unclassified,
        "excluded": excluded,
        "live_extra": live_extra,
        "consistency": {"unexplained_gaps": unexplained, "unobtainable_overlap": overlap,
                        "cancelled_overlap": cancelled_overlap},
    }
    (EV / "download_plan_v4.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\nseasons in plan: {len(plan_out)}")
    for key in sorted(plan_out):
        cands = plan_out[key]["candidates"]
        best = cands[0]
        vf = "V" if best.get("verified") else " "
        print(f"  {key:20s} {len(cands)}c viable={str(plan_out[key]['viable']):5s} best[{vf}]: "
              f"{best['kind']:7s} {best['status']} {best['length']:>8} {best['label']:11s} {best['name'][:52]}")
    print(f"\ncancelled ({len(cancelled_out)}):")
    for key, rec in sorted(cancelled_out.items()):
        print(f"    {key:20s} cands={len(rec['candidates'])}  {rec['reason']}")
    print(f"\ngaps ({len(gaps)}):")
    for g in gaps:
        print("   ", g, "->", "KNOWN" if (g in known_unobtainable or g in r_unobtainable) else "!! UNEXPLAINED")
    print(f"\nr_variants ({len(r_keys)}): {r_keys}")
    print(f"r_unobtainable: {sorted(r_unobtainable)}")
    print(f"manual_mapped: {len(manual_mapped)}")
    print(f"unclassified: {len(unclassified)}  excluded: {len(excluded)}  live_extra: {len(live_extra)}")
    print(f"consistency: unexplained={unexplained} overlap={overlap} cancelled_overlap={cancelled_overlap}")
    print("\nsaved download_plan_v4.json")


if __name__ == "__main__":
    main()
