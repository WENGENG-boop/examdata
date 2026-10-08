#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pdf-answer-values.py — 剑桥雅思 PDF 答案页逐题答案值提取（S18）。

目的: 从本地剑桥雅思真题 PDF 的"答案页"提取**逐题答案值**（区别于 S02
pdf_answer_keys.py 只提取题号范围），产出可直接作为 compare-official.mjs
`--pdf` 候选文件的逐 cell JSON，用于与我方答案逐题核验。

用法（在 C:/Users/weo/Desktop/api 下，用含 pymupdf 的 python 运行）:
  python ielts-api/tools/pdf-answer-values.py \
    --book 10 \
    --keys  ielts-data/runs/20261003T140007Z-repair/evidence/pdf-answer-keys.json \
    --ocr   <该册 OCR 缓存.json>        # s06_ocr.py 400dpi 输出（含该册 key pages）
    --outdir <输出目录> \
    [--pdf tmp_audit_ielts/downloads/book_10.pdf] \
    [--tests 1,2] [--limit-pages 145] [--gold-merge <gold.json>] \
    [--visual-fix <fixes.json>]

  --visual-fix JSON 形状: {"<book>": {"<test>/<skill>": {"<number>":
      {"value": "...", "method": "...", "evidence": "..."}}}}
  用于字形级目检已定案的条目（坏字体/低置信）：覆盖值并标 visual_verified，
  旧值留档于 text_layer_value。

算法:
  1. 每页取 OCR words（s06 格式）与文本层 rawdict tokens；各自按 y 聚类成行、
     按 x 间隔（>40pt）切成"段"。
  2. 段中识别节标题 "Section N, Questions a-b" / "Reading Passage N, Questions a-b"
     （OCR 变体归一化）；标题 x0 聚类成列（间隔 >80pt 分列）。
  3. 行: 值列 x∈[列x+10, 列x+200]；OCR 行与文本层行按 |dy|<=5.5 合并（保留两值）；
     文本层单源行要求含字母数字且字号<=20（过滤 "。" 等噪声）。
  4. 题号锚点: 位于 [列x-10, 列x+16] 且解析为 1..45 的 token；文本层锚点按
     y 序求 LIS（最长严格递增子序列）过滤：<=3 个锚点退回严格递增；否则要求
     LIS 长度 >=3 且 >=60% 锚点数，只保留 LIS 内锚点（防坏字体把题号渲染成
     别的数字，同时容忍个别拼接噪声 token）；
     同列内锚点与行做全局最小距离配对（|dy|<=7，双向唯一）。
  5. 节内赋值: 锚点行取锚点题号；未锚定行仅在"锚点间缺口数==未锚定行数"时
     按 y 序填充；"N&N IN EITHER ORDER" 标签行被识别后（题号可来自相邻锚点
     带 token），两数字按 y 序对到标签最近两行并记录 either-order 组
     （listed_values/ordered=false/allow_reuse=false）；无法配对时记 anomaly，
     不猜、不按数组长度补位。
  6. 值: OCR 为主值；与文本层不一致时文本层读法进 allowed_variants（两值都保留）。
     单字符值（字母/罗马数字）为文本层单源条目。
  7. 视觉修正: --visual-fix 提供的字形级目检结论按 cell/题号覆盖值，旧值存
     text_layer_value，条目标 visual_verified=true（未改值标 visual_confirm）。
  8. 输出: 每 cell 一个 JSON（compare-official --pdf 输入形状）:
     {source, identity, pdf, pdf_sha256, entries:[{number,value,allowed_variants,
      page,sha256,ocr,visual_verified,alt_value,agreement,number_source,y,ocr_conf}],
      sections, anomalies, stats}

边界: 不猜测、不补位；提取不到的题号不产出条目，记入 anomalies。
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import re
import sys
from pathlib import Path

import pymupdf

SECTION_RE = re.compile(r"(?:^|\b)(?:Section|Part)\s*([1-9]|I{1,3}|IV|V)\b", re.I)
PASSAGE_RE = re.compile(r"Reading\s+Passage\s*([1-9]|I{1,3})\b", re.I)
RANGE_RE = re.compile(r"Questions?\s*(\d{1,2})\s*-\s*(\d{1,2})", re.I)
NUM_RE = re.compile(r"^(\d{1,2})[.,;:]?$")
FOOTER_RE = re.compile(
    r"if\s+you\s+score|you\s+are\s+unlikely|you\s+may\s+get|you\s+are\s+likely"
    r"|acceptable\s+score|more\s+practice|improving\s+your"
    r"|if\s+you\s+sc|examination\s+conditions|score\s+under|before\s+you\s+take",
    re.I,
)
SKILL_PAGE = {
    "listening": re.compile(r"^LISTENING$", re.I),
    "reading": re.compile(r"^(?:ACADEMIC\s+READING|GENERAL\s+TRAINING\s+READING|READING)$", re.I),
}
EITHER_PAIR_RE = re.compile(r"(?:Q\s*)?(\d{1,2})\s*(?:&|\+|and|-)\s*(?:Q\s*)?(\d{1,2})", re.I)
EITHER_ORDER_RE = re.compile(r"in\s+(?:either|any)\s+order", re.I)


def either_pair(text: str):
    """识别 'N&N IN EITHER ORDER' 标签行；返回 (n1, n2) 或 None。"""
    if not EITHER_ORDER_RE.search(text):
        return None
    m = EITHER_PAIR_RE.search(text)
    if not m:
        return None
    n1, n2 = int(m.group(1)), int(m.group(2))
    if n2 != n1 + 1 or not (1 <= n1 <= 45):
        return None
    return (n1, n2)


def normalize(t: str) -> str:
    t = t.replace("\u00a0", " ")
    t = re.sub(r"(?<=\d)[·．](?=\d)", "", t)
    t = re.sub(r"(?<=\d)\s*[–—~一+]\s*(?=\d)", "-", t)
    t = re.sub(r"(?<=[0-9A-Za-z])[Çç](?=[A-Za-z])", ",", t)
    t = re.sub(r"\bQ\s*uestions?", "Questions", t)
    t = re.sub(r"\bQues\s*tions?", "Questions", t)
    t = re.sub(r"\bQuesti[o。0]ns?", "Questions", t)
    t = re.sub(r"Sectio\s*n", "Section", t, flags=re.I)
    t = re.sub(r"Passag\s*e", "Passage", t, flags=re.I)
    t = re.sub(r"Questio11s", "Questions", t, flags=re.I)
    t = re.sub(r"(Questions?\s*)[Il|]\s+(\d)", r"\g<1>1\g<2>", t)
    t = re.sub(r"(Questions?\s*)[Il|]{2}(?=[\s\d-])", r"\g<1>11", t)
    t = re.sub(r"\b[A-Z]{1,2}\b(?:\s+[A-Z]{1,2}\b){2,}",
               lambda m: m.group(0).replace(" ", ""), t)
    return t


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def lis_indices(nums: list) -> list:
    """最长严格递增子序列的下标（bisect O(n log n)，返回原序列下标升序）。"""
    if not nums:
        return []
    tails = []       # tails[k] = 长度 k+1 的递增子序列的最小尾值
    tails_idx = []   # 对应尾值在原序列中的下标
    prev = [-1] * len(nums)
    for i, x in enumerate(nums):
        j = bisect.bisect_left(tails, x)
        if j == len(tails):
            tails.append(x)
            tails_idx.append(i)
        else:
            tails[j] = x
            tails_idx[j] = i
        prev[i] = tails_idx[j - 1] if j > 0 else -1
    out = []
    k = tails_idx[-1]
    while k != -1:
        out.append(k)
        k = prev[k]
    return out[::-1]


def raw_tokens(pg) -> list:
    """rawdict -> y 行 + x 间隔分词（gap>4.5 切分）。"""
    d = pg.get_text("rawdict")
    chars = []
    for blk in d["blocks"]:
        if blk.get("type") != 0:
            continue
        for ln in blk["lines"]:
            for sp in ln["spans"]:
                for ch in sp["chars"]:
                    x0, y0, x1, y1 = ch["bbox"]
                    chars.append((y0, x0, x1, y1, ch["c"], sp["font"], round(sp["size"], 1)))
    chars.sort(key=lambda t: (t[0], t[1]))
    lines = []
    for c in chars:
        if lines and c[0] - lines[-1][-1][0] <= 3.5:
            lines[-1].append(c)
        else:
            lines.append([c])
    toks = []
    for ln in lines:
        ln.sort(key=lambda t: t[1])
        cur = [ln[0]]
        for prev, c in zip(ln, ln[1:]):
            if c[1] - prev[2] > 4.5:
                toks.append(cur)
                cur = [c]
            else:
                cur.append(c)
        toks.append(cur)
    out = []
    for t in toks:
        text = "".join(x[4] for x in t)
        if not text.strip():
            continue
        out.append({
            "text": text,
            "x0": min(x[1] for x in t), "x1": max(x[2] for x in t),
            "y0": min(x[0] for x in t), "y1": max(x[3] for x in t),
            "font": t[0][5], "size": max(x[6] for x in t),
            "kind": "raw",
        })
    return out


def build_segments(items: list, ytol: float = 4.0, xgap: float = 40.0) -> list:
    """行内按 x 间隔切段（phrase），段文本用空格连接。"""
    if not items:
        return []
    items = sorted(items, key=lambda w: (w["y0"], w["x0"]))
    lines = []
    for it in items:
        for ln in lines:
            if abs(it["y0"] - ln["y"]) <= ytol:
                ln["items"].append(it)
                break
        else:
            lines.append({"y": it["y0"], "items": [it]})
    segs = []
    for ln in lines:
        ln["items"].sort(key=lambda w: w["x0"])
        cur = [ln["items"][0]]
        for prev, it in zip(ln["items"], ln["items"][1:]):
            if it["x0"] - prev["x1"] > xgap:
                segs.append(cur)
                cur = [it]
            else:
                cur.append(it)
        segs.append(cur)
    out = []
    for s in segs:
        text = " ".join((x.get("text") or "").strip() for x in s)
        out.append({
            "text": text,
            "x0": min(x["x0"] for x in s), "x1": max(x["x1"] for x in s),
            "y0": min(x["y0"] for x in s), "y1": max(x["y1"] for x in s),
        })
    return out


def parse_range(text: str):
    m = RANGE_RE.search(text)
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    return (a, b) if 1 <= a < b <= 45 else None


def detect_headers(segs: list, source: str) -> list:
    out = []
    for s in segs:
        t = normalize(s["text"])
        m1 = SECTION_RE.search(t)
        m2 = PASSAGE_RE.search(t)
        if not (m1 or m2):
            continue
        if len(t) > 90:
            continue
        rng = parse_range(t)
        skill = "reading" if m2 else "listening"
        out.append({
            "text": t.strip()[:90], "x0": s["x0"], "y0": s["y0"], "y1": s["y1"],
            "range": list(rng) if rng else None, "skill": skill, "source": source,
        })
    return out


def cluster_columns(xs: list, gap: float = 80.0) -> list:
    """把 x0 聚成列，返回列代表 x（升序）。"""
    xs = sorted(set(round(x, 1) for x in xs))
    if not xs:
        return []
    cols = [[xs[0]]]
    for x in xs[1:]:
        if x - cols[-1][-1] > gap:
            cols.append([x])
        else:
            cols[-1].append(x)
    return [min(c) for c in cols]


def col_of(x: float, cols: list):
    best = None
    for c in cols:
        if x >= c - 12:
            best = c
    return best


def join_raw_row(items: list) -> str:
    """文本层行内 token 拼接：间隔<=1.2 直接相连，否则空格；再修 / 旁空格。"""
    items = sorted(items, key=lambda w: w["x0"])
    parts = []
    prev = None
    for it in items:
        if prev is not None and it["x0"] - prev["x1"] > 1.2:
            parts.append(" ")
        parts.append(it["text"])
        prev = it
    t = "".join(parts)
    t = re.sub(r"\s*/\s*", "/", t)
    return t.strip()


def build_rows(items: list, ytol: float) -> list:
    """按 y 聚成行。items 需含 text/x0/x1/y0/y1。"""
    if not items:
        return []
    items = sorted(items, key=lambda w: (w["y0"], w["x0"]))
    lines = []
    for it in items:
        for ln in lines:
            if abs(it["y0"] - ln["y"]) <= ytol:
                ln["items"].append(it)
                break
        else:
            lines.append({"y": it["y0"], "items": [it]})
    out = []
    for ln in lines:
        ln["items"].sort(key=lambda w: w["x0"])
        out.append({
            "y": min(x["y0"] for x in ln["items"]),
            "y1": max(x["y1"] for x in ln["items"]),
            "x0": min(x["x0"] for x in ln["items"]),
            "items": ln["items"],
        })
    return out


def norm_cmp(t: str) -> str:
    t = (t or "").lower()
    t = re.sub(r"[\s\u00a0]+", "", t)
    t = t.strip(".,;:")
    return t


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", type=int, required=True)
    ap.add_argument("--keys", default="ielts-data/runs/20261003T140007Z-repair/evidence/pdf-answer-keys.json")
    ap.add_argument("--pdf", default=None)
    ap.add_argument("--ocr", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--tests", default=None)
    ap.add_argument("--limit-pages", default=None)
    ap.add_argument("--gold-merge", default=None)
    ap.add_argument("--visual-fix", default=None,
                    help="字形级目检修正 JSON（形状见文件头 docstring）")
    args = ap.parse_args()

    keys = json.loads(Path(args.keys).read_text(encoding="utf-8"))
    bk = keys.get(str(args.book))
    if not bk:
        print(json.dumps({"error": f"book {args.book} not in keys json"}, ensure_ascii=False))
        return 1

    page_tests = {}
    for tkey, tv in (bk.get("tests") or {}).items():
        for skill in ("listening", "reading"):
            for pg in ((tv.get(skill) or {}).get("pages") or []):
                page_tests.setdefault(int(pg), set()).add(tkey)

    pages = sorted(page_tests)
    if args.limit_pages:
        want = {int(x) for x in args.limit_pages.split(",")}
        pages = [p for p in pages if p in want]
    if args.tests:
        want_t = {x.strip() for x in args.tests.split(",")}
        pages = [p for p in pages if page_tests.get(p, set()) & want_t]

    pdf_path = Path(args.pdf) if args.pdf else Path(f"tmp_audit_ielts/downloads/book_{args.book}.pdf")
    doc = pymupdf.open(pdf_path)
    sha = sha256_file(pdf_path)

    ocr = json.loads(Path(args.ocr).read_text(encoding="utf-8"))
    ocr_pages = {int(p["file_page"]): p.get("words") or [] for p in ocr.get("pages", [])}

    cells = {}          # key -> {entries:{num:entry}, sections:[...], anomalies:[...], pages:set}
    page_reports = []

    for pno in pages:
        if pno not in ocr_pages:
            page_reports.append({"page": pno, "reason": "no_ocr_cache"})
            continue
        pg = doc[pno - 1]
        ocr_words = ocr_pages[pno]
        rawt = raw_tokens(pg)
        ocr_segs = build_segments(ocr_words)
        raw_segs = build_segments(rawt)

        # 页级技能标记
        page_skills = set()
        for s in ocr_segs + raw_segs:
            t = normalize(s["text"]).strip()
            for sk, rx in SKILL_PAGE.items():
                if rx.match(t):
                    page_skills.add(sk)

        # 节标题（OCR 优先，文本层补充）
        headers = []
        for h in detect_headers(ocr_segs, "ocr") + detect_headers(raw_segs, "raw"):
            dup = False
            for e in headers:
                if abs(e["y0"] - h["y0"]) <= 6 and abs(e["x0"] - h["x0"]) <= 15 and e["range"] == h["range"]:
                    dup = True
                    if h["source"] == "ocr" and e["source"] != "ocr":
                        e.update(h)
                    break
            if not dup:
                headers.append(h)

        # 列聚类（无标题时用锚点 x）
        col_xs = [h["x0"] for h in headers]
        if not col_xs:
            for w in ocr_words:
                if NUM_RE.match((w.get("text") or "").strip()):
                    col_xs.append(w["x0"])
        cols = cluster_columns(col_xs)
        for h in headers:
            h["col"] = col_of(h["x0"], cols)

        # 值行（分列）
        rows_by_col = {c: [] for c in cols}
        for c in cols:
            band = (c + 10, c + 200)
            o_items = [w for w in ocr_words if band[0] <= w["x0"] <= band[1]]
            r_items = [t for t in rawt if band[0] <= t["x0"] <= band[1]]
            orows = build_rows(o_items, 5.0)
            rrows = build_rows(r_items, 4.0)
            # 过滤文本层噪声行
            rrows = [r for r in rrows
                     if re.search(r"[A-Za-z0-9]", join_raw_row(r["items"]))
                     and max(x["size"] for x in r["items"]) <= 20]
            merged = []
            used_r = set()
            for orow in orows:
                orow["text"] = " ".join((w.get("text") or "").strip() for w in orow["items"]).strip()
                orow["conf"] = min((w.get("conf") if w.get("conf") is not None else 1.0) for w in orow["items"])
                best = None
                for ri, rrow in enumerate(rrows):
                    if ri in used_r:
                        continue
                    dy = abs(rrow["y"] - orow["y"])
                    if dy <= 5.5 and (best is None or dy < best[1]):
                        best = (ri, dy)
                if best is not None:
                    used_r.add(best[0])
                    rtext = join_raw_row(rrows[best[0]]["items"])
                    orow["raw_text"] = rtext
                merged.append(orow)
            for ri, rrow in enumerate(rrows):
                if ri in used_r:
                    continue
                merged.append({
                    "y": rrow["y"], "y1": rrow["y1"], "x0": rrow["x0"],
                    "items": rrow["items"], "text": None, "conf": None,
                    "raw_text": join_raw_row(rrow["items"]),
                })
            merged.sort(key=lambda r: r["y"])
            rows_by_col[c] = merged

        # 锚点（分列）
        anchors_by_col = {}
        for c in cols:
            band = (c - 10, c + 16)
            anch = []
            for w in ocr_words:
                t = (w.get("text") or "").strip()
                m = NUM_RE.match(t)
                if m and band[0] <= w["x0"] <= band[1]:
                    n = int(m.group(1))
                    if 1 <= n <= 45:
                        anch.append({"num": n, "y": w["y0"], "x0": w["x0"], "src": "ocr"})
            raw_anch = []
            for t in rawt:
                m = NUM_RE.match((t.get("text") or "").strip())
                if m and band[0] <= t["x0"] <= band[1]:
                    n = int(m.group(1))
                    if 1 <= n <= 45:
                        raw_anch.append({"num": n, "y": t["y0"], "x0": t["x0"], "src": "raw"})
            # 文本层锚点：按 y 序求 LIS（容忍个别坏 token 拼出的伪题号）；
            # 序列较短（<=3）时退回严格递增；LIS 占比过低说明整列字体不可信，整列拒收。
            raw_sorted = sorted(raw_anch, key=lambda a: a["y"])
            raw_seq = [a["num"] for a in raw_sorted]
            if len(raw_seq) <= 3:
                raw_ok = bool(raw_seq) and all(b > a for a, b in zip(raw_seq, raw_seq[1:]))
                raw_keep = raw_sorted if raw_ok else []
            else:
                lis = lis_indices(raw_seq)
                raw_ok = len(lis) >= 3 and len(lis) >= 0.6 * len(raw_seq)
                raw_keep = [raw_sorted[i] for i in lis] if raw_ok else []
            raw_dropped = len(raw_sorted) - len(raw_keep)
            anch_all = anch + raw_keep
            # 去重：同 num 且 |dy|<6 只留一个（OCR 优先）
            anch_all.sort(key=lambda a: (a["y"], 0 if a["src"] == "ocr" else 1))
            dedup = []
            for a in anch_all:
                dup = False
                for d in dedup:
                    if d["num"] == a["num"] and abs(d["y"] - a["y"]) < 6:
                        dup = True
                        break
                if not dup:
                    dedup.append(a)
            anchors_by_col[c] = {"anchors": dedup, "raw_accepted": raw_ok,
                                 "raw_rejected": (not raw_ok) and bool(raw_anch),
                                 "raw_total": len(raw_sorted), "raw_kept": len(raw_keep),
                                 "raw_dropped": raw_dropped}

        # 全局配对（同列，|dy|<=7，双向唯一，最小距离优先）
        pairs_by_col = {}
        for c in cols:
            rows = rows_by_col[c]
            anch = anchors_by_col[c]["anchors"]
            cands = []
            for ai, a in enumerate(anch):
                for ri, r in enumerate(rows):
                    dy = abs(r["y"] - a["y"])
                    if dy <= 7.0:
                        cands.append((dy, ai, ri))
            cands.sort()
            a_used, r_used, pairs = set(), set(), {}
            for dy, ai, ri in cands:
                if ai in a_used or ri in r_used:
                    continue
                a_used.add(ai)
                r_used.add(ri)
                pairs[ri] = {"num": anch[ai]["num"], "src": anch[ai]["src"], "dy": round(dy, 2)}
            pairs_by_col[c] = pairs

        # 节内赋值（行先按列 y 区间分派到节；节标题行/页脚行排除在外）
        page_entries = []
        anomalies = []
        outside_count = 0
        outside_samples = []

        # footer_y: 全页所有行中匹配 FOOTER_RE 的最小 y - 3
        footer_y = None
        for c0 in cols:
            for r in rows_by_col.get(c0, []):
                t = normalize(r.get("text") or r.get("raw_text") or "")
                if FOOTER_RE.search(t):
                    if footer_y is None or r["y"] < footer_y:
                        footer_y = r["y"]
        if footer_y is not None:
            footer_y -= 3

        def note_outside(r, col):
            nonlocal outside_count
            outside_count += 1
            if len(outside_samples) < 3:
                outside_samples.append({"page": pno, "col": col, "y": round(r["y"], 1),
                                        "text": (r.get("text") or r.get("raw_text") or "")[:60]})

        # 行 → 节 分派（按列，以节标题 y 为界）
        section_rows = {}   # header_idx -> [row_idx...]
        cont_candidates = {}   # col -> [row_idx...] 列首标题之上的行（上一列节流续接候选）
        cont_min_y = {}        # col -> 列首标题 y0-3
        for c in cols:
            col_headers = [(hi, h) for hi, h in enumerate(headers)
                           if h.get("col") == c and h.get("range")]
            col_headers.sort(key=lambda t: t[1]["y0"])
            crows = rows_by_col.get(c, [])
            if not col_headers:
                if crows:
                    anomalies.append({"page": pno, "kind": "column_no_section",
                                      "col": c, "rows": len(crows)})
                continue
            min_h_y = col_headers[0][1]["y0"] - 3
            cont_min_y[c] = min_h_y
            for ri, r in enumerate(crows):
                y = r["y"]
                if y < min_h_y and (footer_y is None or y < footer_y):
                    cont_candidates.setdefault(c, []).append(ri)
                    continue
                if y < min_h_y or (footer_y is not None and y >= footer_y):
                    note_outside(r, c)
                    continue
                rtext = normalize(r.get("text") or r.get("raw_text") or "")
                if any(abs(y - h["y0"]) <= 5 and (SECTION_RE.search(rtext)
                                                  or PASSAGE_RE.search(rtext)
                                                  or re.search(r"Questions?\s*\d", rtext))
                       for _hi, h in col_headers):
                    continue    # 节标题行本身
                sec = None
                for hi, h in col_headers:
                    if y >= h["y0"] - 3:
                        sec = hi
                    else:
                        break
                if sec is None:
                    note_outside(r, c)
                    continue
                section_rows.setdefault(sec, []).append(ri)

        if pno == int(__import__("os").environ.get("DBG_PAGE", "0")):
            import sys as _sys
            _sys.stderr.write("=== DBG page %d ===\n" % pno)
            _sys.stderr.write("headers: %s\n" % json.dumps(
                [{"text": h["text"], "range": h.get("range"), "col": h.get("col"),
                  "y0": round(h.get("y0", -1), 1), "source": h.get("source")} for h in headers],
                ensure_ascii=False))
            for _c in cols:
                _sys.stderr.write("col %s rows:\n" % _c)
                for _ri, _r in enumerate(rows_by_col.get(_c, [])):
                    _sys.stderr.write("  [%d] y=%7.1f ocr=%r raw=%r\n" % (
                        _ri, _r["y"], (_r.get("text") or "")[:70], (_r.get("raw_text") or "")[:70]))
                _sys.stderr.write("col %s anchors: %s\n" % (_c, json.dumps(
                    [{"num": a["num"], "y": round(a["y"], 1), "src": a["src"]}
                     for a in anchors_by_col.get(_c, {}).get("anchors", [])], ensure_ascii=False)))
                _sys.stderr.write("col %s pairs: %s\n" % (_c, json.dumps(
                    {str(k): v for k, v in sorted(pairs_by_col.get(_c, {}).items())}, ensure_ascii=False)))
            _sys.stderr.write("section_rows: %s\n" % json.dumps(
                {str(k): v for k, v in sorted(section_rows.items())}, ensure_ascii=False))
            _sys.stderr.write("cont_candidates: %s\n" % json.dumps(
                {str(k): v for k, v in cont_candidates.items()}, ensure_ascii=False))
            _sys.stderr.write("cont_min_y: %s\n" % json.dumps(
                {str(k): v for k, v in cont_min_y.items()}, ensure_ascii=False))
            _sys.stderr.write("footer_y: %s\n" % footer_y)

        # either-order 支持: 页级容器 + 标签 token（题号可能在锚点带内，不在值行里）
        label_tokens = [((w.get("text") or "").strip(), w["y0"], w["x0"]) for w in ocr_words]
        label_tokens += [((t.get("text") or "").strip(), t["y0"], t["x0"]) for t in rawt]
        consumed_labels = set()     # 被识别为 either-order 标签的行（不再记 unassigned）
        page_groups_raw = []        # gid 列表（发现顺序）
        page_group_meta = {}        # gid -> {numbers,label,label_y,where,section_range}

        def _make_entry(rows_list, ri, n, src, gid, rng, htext, cval):
            """由行产出条目（主循环与列流续接共用）。返回 None 表示空值。"""
            row = rows_list[ri]
            text_ocr = row.get("text")
            text_raw = row.get("raw_text")
            agreement = "both" if (text_ocr and text_raw) else ("ocr_only" if text_ocr else "raw_only")
            alt = None
            if text_ocr and text_raw and norm_cmp(text_ocr) != norm_cmp(text_raw):
                agreement = "conflict"
                if len(text_raw) <= 40 and text_raw.isprintable():
                    alt = text_raw
            primary = text_ocr or text_raw
            if primary is None or not primary.strip():
                return None
            return {
                "number": n,
                "value": primary.strip(),
                "alt_value": alt,
                "allowed_variants": [alt] if alt else [],
                "agreement": agreement,
                "number_source": src,
                "value_source": "ocr" if text_ocr else "raw",
                "ocr": bool(text_ocr),
                "ocr_conf": round(row["conf"], 3) if row.get("conf") is not None else None,
                "page": pno,
                "sha256": sha,
                "visual_verified": False,
                "section": rng,
                "section_header": htext,
                "y": round(row["y"], 2),
                "col": cval,
                "either_order": page_group_meta[gid]["numbers"] if gid else None,
                "group_ids": [gid] if gid else [],
            }

        for hi, h in enumerate(headers):
            if not h.get("range"):
                anomalies.append({"page": pno, "kind": "header_no_range", "text": h["text"],
                                  "x0": round(h["x0"], 1), "y0": round(h["y0"], 1)})
                continue
            a, b = h["range"]
            c = h["col"]
            rows = rows_by_col.get(c, [])
            pairs = pairs_by_col.get(c, {})
            sec_rows = section_rows.get(hi, [])
            anchored = []   # (row_idx, num, src)
            unanchored = []
            for ri in sec_rows:
                p = pairs.get(ri)
                if p is None:
                    unanchored.append(ri)
                elif a <= p["num"] <= b:
                    rtxt = normalize(rows[ri].get("text") or rows[ri].get("raw_text") or "")
                    if EITHER_ORDER_RE.search(rtxt):
                        unanchored.append(ri)   # either-order 标签行不参与锚定
                    else:
                        anchored.append((ri, p["num"], p["src"]))
                else:
                    anomalies.append({"page": pno, "kind": "anchor_out_of_section",
                                      "number": p["num"], "range": [a, b],
                                      "y": round(rows[ri]["y"], 1)})
                    unanchored.append(ri)
            anchored.sort(key=lambda t: rows[t[0]]["y"])
            assign = {}     # row_idx -> (num, source, gid)
            for ri, n, src in anchored:
                assign[ri] = (n, "anchor_" + src, None)

            def _label_of(ri):
                """行文本（含邻近锚点带 token 拼合）中的 either-order 标签题号。"""
                t = normalize(rows[ri].get("text") or rows[ri].get("raw_text") or "")
                if not EITHER_ORDER_RE.search(t):
                    return None
                found = []
                p = either_pair(t)
                if p:
                    found.append(p)
                y = rows[ri]["y"]
                extra = " ".join(tx for tx, ty, txx in label_tokens
                                 if abs(ty - y) <= 5 and (c - 20) <= txx <= (c + 40))
                if extra:
                    p = either_pair(normalize(extra + " " + t))
                    if p and p not in found:
                        found.append(p)
                return found[0] if len(found) == 1 else None

            def _fill(cand, missing, kind, rng):
                """用候选行按 missing 数字填充；支持 either-order 标签行。返回 True 表示已写入。"""
                if not cand or not missing:
                    return False
                label_rows = []
                for ri in cand:
                    lp = _label_of(ri)
                    if lp:
                        label_rows.append((ri, lp))
                if len(label_rows) > 1:
                    return False
                label_ids = {lr[0] for lr in label_rows}
                value_rows = [ri for ri in cand if ri not in label_ids]
                if len(value_rows) != len(missing):
                    return False
                if not label_rows:
                    for ri, n in zip(sorted(value_rows, key=lambda i: rows[i]["y"]),
                                     sorted(missing)):
                        assign[ri] = (n, kind, None)
                    return True
                lri, (n1, n2) = label_rows[0]
                if n1 not in missing or n2 not in missing:
                    return False
                ly = rows[lri]["y"]
                after = sorted((ri for ri in value_rows if rows[ri]["y"] > ly),
                               key=lambda i: rows[i]["y"])
                before = sorted((ri for ri in value_rows if rows[ri]["y"] < ly),
                                key=lambda i: -rows[i]["y"])
                pair_rows = (after + before)[:2]
                pair_rows.sort(key=lambda i: rows[i]["y"])
                gid = f"either_order:{n1}&{n2}"
                assign[pair_rows[0]] = (n1, kind + "_either", gid)
                assign[pair_rows[1]] = (n2, kind + "_either", gid)
                rest_rows = [ri for ri in sorted(value_rows, key=lambda i: rows[i]["y"])
                             if ri not in pair_rows]
                rest_missing = [n for n in sorted(missing) if n not in (n1, n2)]
                for ri, n in zip(rest_rows, rest_missing):
                    assign[ri] = (n, kind, None)
                consumed_labels.add(lri)
                page_group_meta[gid] = {
                    "numbers": [n1, n2],
                    "label": (rows[lri].get("text") or rows[lri].get("raw_text") or "").strip(),
                    "label_y": round(ly, 2),
                    "where": kind.replace("fill_", ""),
                    "section_range": rng,
                }
                page_groups_raw.append(gid)
                return True

            # 缺口填充（仅当缺口数 == 行数；标签行先被消费）
            pts = [(rows[ri]["y"], n) for ri, n, _s in anchored]
            if pts:
                # 锚点之前
                y0a, n0a = pts[0]
                pre = [ri for ri in unanchored if rows[ri]["y"] < y0a]
                gap = n0a - a
                if pre and not _fill(pre, list(range(a, n0a)), "fill_head", [a, b]):
                    anomalies.append({"page": pno, "kind": "gap_mismatch_head", "range": [a, b],
                                      "rows": len(pre), "gap": gap, "y": round(rows[pre[0]]["y"], 1)})
                # 锚点之间
                for (y1, n1), (y2, n2) in zip(pts, pts[1:]):
                    mid = [ri for ri in unanchored if y1 < rows[ri]["y"] < y2]
                    gap = n2 - n1 - 1
                    if mid and not _fill(mid, list(range(n1 + 1, n2)), "fill_between", [a, b]):
                        anomalies.append({"page": pno, "kind": "gap_mismatch_between",
                                          "range": [a, b], "rows": len(mid), "gap": gap,
                                          "between": [n1, n2], "y": round(rows[mid[0]]["y"], 1)})
                # 锚点之后
                ylast, nlast = pts[-1]
                post = [ri for ri in unanchored if rows[ri]["y"] > ylast]
                gap = b - nlast
                if post and not _fill(post, list(range(nlast + 1, b + 1)), "fill_tail", [a, b]):
                    anomalies.append({"page": pno, "kind": "gap_mismatch_tail", "range": [a, b],
                                      "rows": len(post), "gap": gap, "y": round(rows[post[0]]["y"], 1)})
            else:
                if sec_rows:
                    anomalies.append({"page": pno, "kind": "section_no_anchor", "range": [a, b],
                                      "rows": len(sec_rows)})
            # 产出条目
            for ri, (n, src, gid) in sorted(assign.items(), key=lambda kv: kv[1][0]):
                entry = _make_entry(rows, ri, n, src, gid, [a, b], h["text"], c)
                if entry is None:
                    anomalies.append({"page": pno, "kind": "empty_value", "number": n})
                    continue
                page_entries.append(entry)
            # 未赋值行 → anomaly（either-order 标签行除外）
            for ri in unanchored:
                if ri not in assign and ri not in consumed_labels:
                    anomalies.append({"page": pno, "kind": "unassigned_row", "range": [a, b],
                                      "y": round(rows[ri]["y"], 1),
                                      "text": (rows[ri].get("text") or rows[ri].get("raw_text") or "")[:60]})

        # —— 列流续接：值行从上一列流到本列顶部（行位于列首标题之上）——
        # 用锚点题号定位"开放节"（本列之前、range 覆盖全部锚点的最后一个节），
        # 再按缺口填充把续接行分配给该节题号。
        for c in cols:
            cand_ris = cont_candidates.get(c)
            if not cand_ris:
                continue
            crows = rows_by_col.get(c, [])
            pairs = pairs_by_col.get(c, {})
            min_y = cont_min_y.get(c)
            cand_ris = sorted(cand_ris, key=lambda ri: crows[ri]["y"])
            anch_rows = []      # (row_idx, num, src) —— 本列顶部带锚点的行
            paired_nums = set()
            for ri in cand_ris:
                p = pairs.get(ri)
                if p is not None:
                    anch_rows.append((ri, p["num"], p["src"]))
                    paired_nums.add(p["num"])
            top_unpaired = []   # 锚点带内无对应值行的锚点（如浅灰字）
            for a in anchors_by_col.get(c, {}).get("anchors", []):
                if min_y is not None and a["y"] < min_y and a["num"] not in paired_nums:
                    top_unpaired.append(a["num"])
            nums = [n for _ri, n, _s in anch_rows]
            open_sec = None
            if nums:
                prev = [(hi, h) for hi, h in enumerate(headers)
                        if h.get("range") and h.get("col") is not None and h["col"] < c - 0.5]
                prev.sort(key=lambda t: (t[1]["col"], t[1]["y0"]))
                for hi, h in reversed(prev):
                    ra0, rb0 = h["range"]
                    if all(ra0 <= n <= rb0 for n in nums):
                        open_sec = (hi, h)
                        break
            if open_sec is None:
                if anch_rows:
                    anomalies.append({"page": pno, "kind": "continuation_no_section",
                                      "col": round(c, 1), "numbers": nums})
                for ri in cand_ris:
                    note_outside(crows[ri], c)
                for n in top_unpaired:
                    anomalies.append({"page": pno, "kind": "continuation_anchor_no_row",
                                      "number": n, "col": round(c, 1)})
                continue
            hi, h = open_sec
            ra, rb = h["range"]
            have = {e["number"] for e in page_entries}
            used = {n for n in have if ra <= n <= rb}
            assign = {}         # row_idx -> (num, kind)
            dup_notes = []
            for ri, n, src in anch_rows:
                if n in used:
                    dup_notes.append(n)
                    continue
                assign[ri] = (n, "cont_anchor_" + src)
                used.add(n)
            if dup_notes:
                anomalies.append({"page": pno, "kind": "continuation_duplicate_numbers",
                                  "col": round(c, 1), "range": [ra, rb], "numbers": dup_notes})

            def _fill_range(row_ids, lo, hi_, kind):
                """续接段的精确计数填充：行数 == 缺口数才赋值，否则记 anomaly。"""
                if not row_ids:
                    return
                miss = [n for n in range(lo, hi_ + 1) if n not in used]
                if len(row_ids) == len(miss):
                    for ri, n in zip(sorted(row_ids, key=lambda i: crows[i]["y"]), miss):
                        assign[ri] = (n, kind)
                        used.add(n)
                else:
                    anomalies.append({"page": pno, "kind": "continuation_gap_mismatch",
                                      "col": round(c, 1), "range": [ra, rb],
                                      "segment": [lo, hi_], "rows": len(row_ids),
                                      "gap": len(miss),
                                      "y": round(crows[row_ids[0]]["y"], 1)})

            anch_sorted = sorted((crows[ri]["y"], ri, n) for ri, (n, _k) in assign.items())
            if anch_sorted:
                y_first, _ri_first, n_first = anch_sorted[0]
                _fill_range([ri for ri in cand_ris
                             if ri not in assign and crows[ri]["y"] < y_first],
                            ra, n_first - 1, "cont_fill_head")
                for (y1, _ri1, n1), (y2, _ri2, n2) in zip(anch_sorted, anch_sorted[1:]):
                    _fill_range([ri for ri in cand_ris
                                 if ri not in assign and y1 < crows[ri]["y"] < y2],
                                n1 + 1, n2 - 1, "cont_fill_between")
                y_last, _ri_last, n_last = anch_sorted[-1]
                _fill_range([ri for ri in cand_ris
                             if ri not in assign and crows[ri]["y"] > y_last],
                            n_last + 1, rb, "cont_fill_tail")

            for ri, (n, kind) in sorted(assign.items(), key=lambda kv: kv[1][0]):
                entry = _make_entry(crows, ri, n, kind, None, [ra, rb], h["text"], c)
                if entry is None:
                    anomalies.append({"page": pno, "kind": "empty_value", "number": n})
                    continue
                page_entries.append(entry)
            for ri in cand_ris:
                if ri not in assign:
                    anomalies.append({"page": pno, "kind": "continuation_unassigned_row",
                                      "col": round(c, 1), "y": round(crows[ri]["y"], 1),
                                      "text": (crows[ri].get("text")
                                               or crows[ri].get("raw_text") or "")[:60]})
            for n in top_unpaired:
                anomalies.append({"page": pno, "kind": "continuation_anchor_no_row",
                                  "number": n, "col": round(c, 1)})
            have2 = {e["number"] for e in page_entries}
            unfilled = [n for n in range(ra, rb + 1) if n not in have2]
            if unfilled:
                anomalies.append({"page": pno, "kind": "continuation_unfilled",
                                  "col": round(c, 1), "range": [ra, rb], "numbers": unfilled})

        # either-order 组记录（供题目—答案连接与后续比较使用）
        entry_by_num = {e["number"]: e for e in page_entries}
        page_groups = []
        for gid in page_groups_raw:
            meta = page_group_meta[gid]
            n1, n2 = meta["numbers"]
            e1, e2 = entry_by_num.get(n1), entry_by_num.get(n2)
            if e1 is None or e2 is None:
                anomalies.append({"page": pno, "kind": "either_order_group_incomplete",
                                  "group_id": gid, "numbers": meta["numbers"]})
                continue
            page_groups.append({
                "group_id": gid,
                "kind": "either_order",
                "input_numbers": [n1, n2],
                "listed_values": [e1["value"], e2["value"]],
                "ordered": False,
                "allow_reuse": False,
                "required_count": 2,
                "label": meta["label"],
                "where": meta["where"],
                "section_range": meta["section_range"],
                "page": pno,
                "sha256": sha,
            })

        # 落在所有节区间外的行（聚合一条）
        if outside_count:
            anomalies.append({"page": pno, "kind": "rows_outside_sections",
                              "count": outside_count, "samples": outside_samples})

        # 未落入任何节的锚定行（loose）
        in_ranges = set()
        for h in headers:
            if h.get("range"):
                in_ranges.update(range(h["range"][0], h["range"][1] + 1))
        for c in cols:
            for ri, p in pairs_by_col.get(c, {}).items():
                if p["num"] not in in_ranges:
                    row = rows_by_col[c][ri]
                    anomalies.append({"page": pno, "kind": "loose_anchor_row", "number": p["num"],
                                      "y": round(row["y"], 1),
                                      "text": (row.get("text") or row.get("raw_text") or "")[:60]})

        page_reports.append({
            "page": pno, "tests": sorted(page_tests.get(pno, set())),
            "skills": sorted(page_skills),
            "headers": [{"text": h["text"], "range": h["range"], "skill": h["skill"],
                         "col": h["col"], "source": h["source"]} for h in headers],
            "columns": cols,
            "anchors": {str(c): {"count": len(anchors_by_col[c]["anchors"]),
                                 "raw_accepted": anchors_by_col[c]["raw_accepted"],
                                 "raw_rejected": anchors_by_col[c]["raw_rejected"],
                                 "raw_total": anchors_by_col[c]["raw_total"],
                                 "raw_kept": anchors_by_col[c]["raw_kept"],
                                 "raw_dropped": anchors_by_col[c]["raw_dropped"]}
                        for c in cols},
            "entries": len(page_entries), "groups": page_groups, "anomalies": anomalies,
        })

        # 归入 cells
        tests = page_tests.get(pno, set())
        for e in page_entries:
            sec_skill = None
            for h in headers:
                if h.get("range") and h["range"][0] <= e["number"] <= h["range"][1] \
                        and h["skill"] and h["col"] == e["col"]:
                    sec_skill = h["skill"]
                    break
            skill = sec_skill or (sorted(page_skills)[0] if page_skills else None)
            if not skill:
                anomalies.append({"page": pno, "kind": "entry_no_skill", "number": e["number"]})
                continue
            if len(tests) != 1:
                anomalies.append({"page": pno, "kind": "entry_ambiguous_test", "number": e["number"],
                                  "tests": sorted(tests)})
                if not tests:
                    continue
            tkey = sorted(tests)[0]
            ck = f"{tkey}/{skill}"
            cell = cells.setdefault(ck, {"entries": {}, "sections": [], "anomalies": [], "pages": set(),
                                         "test": tkey, "skill": skill, "groups": []})
            cell["pages"].add(pno)
            if e["number"] in cell["entries"]:
                prev = cell["entries"][e["number"]]
                if norm_cmp(prev["value"]) != norm_cmp(e["value"]):
                    cell["anomalies"].append({"kind": "duplicate_number_conflict",
                                              "number": e["number"], "page": pno,
                                              "kept": prev["value"], "dropped": e["value"],
                                              "kept_page": prev["page"]})
                    continue
            cell["entries"][e["number"]] = e
            for g in page_groups:
                if g["group_id"] in (e.get("group_ids") or []) \
                        and all(x["group_id"] != g["group_id"] for x in cell.setdefault("groups", [])):
                    cell["groups"].append(g)

    # 字形级目检修正（--visual-fix）: 覆盖 OCR/文本层值，旧值留档。
    # 先于金标合并执行：金标校验针对修正后的最终提取状态。
    vf_report = None
    if args.visual_fix:
        vfix = json.loads(Path(args.visual_fix).read_text(encoding="utf-8"))
        book_fix = vfix.get(str(args.book)) or {}
        vf_report = {"applied": []}
        for ck, fixes in sorted(book_fix.items()):
            cell = cells.get(ck)
            if cell is None:
                tkey, skill = ck.split("/", 1)
                cell = cells.setdefault(ck, {"entries": {}, "sections": [], "anomalies": [],
                                             "pages": set(), "test": tkey, "skill": skill,
                                             "groups": []})
            for n_str, fx in sorted(fixes.items(), key=lambda kv: int(kv[0])):
                n = int(n_str)
                newv = (fx.get("value") or "").strip()
                if not newv:
                    continue
                cur = cell["entries"].get(n)
                old = (cur.get("value") if cur else None)
                if cur is None:
                    cur = {"number": n, "value": newv, "alt_value": None, "allowed_variants": [],
                           "agreement": "visual_new", "number_source": "visual_fix",
                           "value_source": "visual", "ocr": False, "ocr_conf": None,
                           "page": None, "sha256": sha, "section": None, "section_header": None,
                           "y": None, "col": None, "either_order": None, "group_ids": []}
                    cell["entries"][n] = cur
                else:
                    if old != newv:
                        cur["text_layer_value"] = old
                        cur["agreement"] = "visual_override"
                        cur["value_source"] = "visual"
                        if cur.get("alt_value") and norm_cmp(str(cur["alt_value"])) == norm_cmp(newv):
                            cur["alt_value"] = None
                            cur["allowed_variants"] = []
                    else:
                        cur["agreement"] = "visual_confirm"
                cur["value"] = newv
                cur["visual_verified"] = True
                cur["visual_method"] = fx.get("method")
                vf_report["applied"].append({"cell": ck, "number": n, "value": newv,
                                             "prev": old, "agreement": cur["agreement"],
                                             "evidence": fx.get("evidence")})

    # 金标合并（对修正后的提取结果校验/补录）
    gold_report = None
    if args.gold_merge:
        gold = json.loads(Path(args.gold_merge).read_text(encoding="utf-8"))
        gold_report = {"match": [], "conflict": [], "added": []}
        gid = gold.get("identity") or {}
        gk = f"{gid.get('test')}/{gid.get('skill')}" if gid else None
        if gk and gk in cells:
            cell = cells[gk]
            for ge in gold.get("entries", []):
                n = ge.get("number")
                gv = ge.get("value")
                if n is None:
                    continue
                cur = cell["entries"].get(n)
                if cur is None or not str(cur.get("value") or "").strip():
                    cell["entries"][n] = {
                        "number": n, "value": gv, "alt_value": None, "allowed_variants": [],
                        "agreement": "gold", "number_source": "gold_merge",
                        "value_source": "s06_gold", "ocr": False, "ocr_conf": None,
                        "page": ge.get("page"), "sha256": ge.get("sha256") or sha,
                        "visual_verified": bool(ge.get("visual_verified")),
                        "section": None, "section_header": None, "y": None, "col": None,
                    }
                    gold_report["added"].append({"number": n, "value": gv})
                elif norm_cmp(cur["value"]) == norm_cmp(str(gv)):
                    gold_report["match"].append(n)
                else:
                    gold_report["conflict"].append({"number": n, "extracted": cur["value"],
                                                    "gold": gv, "extracted_page": cur["page"]})

    # 输出
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    written = []
    for ck, cell in sorted(cells.items()):
        tkey, skill = ck.split("/", 1)
        entries = [cell["entries"][n] for n in sorted(cell["entries"])]
        obj = {
            "source": f"book{args.book}_answer_key_page",
            "identity": {"book": args.book, "test": tkey, "skill": skill},
            "pdf": str(pdf_path).replace("\\", "/"),
            "pdf_sha256": sha,
            "extraction": {
                "tool": "pdf-answer-values.py",
                "method": "ocr+rawdict",
                "pages": sorted(cell["pages"]),
                "gold_merge": (gold_report if (args.gold_merge and gold_report
                                               and gk == ck) else None),
                "visual_fixes": ([x for x in vf_report["applied"] if x["cell"] == ck]
                                 if vf_report else None),
            },
            "entries": entries,
            "groups": cell.get("groups", []),
            "anomalies": cell["anomalies"],
            "stats": {
                "entries": len(entries),
                "numbers": [entries[0]["number"], entries[-1]["number"]] if entries else None,
                "agreement_counts": {
                    k: sum(1 for e in entries if e["agreement"] == k)
                    for k in sorted({e["agreement"] for e in entries})
                },
            },
        }
        fname = outdir / f"test_{tkey}_{skill}.json"
        fname.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
        written.append(str(fname).replace("\\", "/"))

    (outdir / "_pages.json").write_text(json.dumps({
        "book": args.book, "pdf": str(pdf_path).replace("\\", "/"), "pdf_sha256": sha,
        "pages": page_reports,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    summary = {
        "book": args.book,
        "cells": {ck: {"entries": len(c["entries"]), "groups": len(c.get("groups") or []),
                       "pages": sorted(c["pages"]),
                       "anomalies": len(c["anomalies"])} for ck, c in sorted(cells.items())},
        "written": written,
        "gold_report": gold_report,
        "visual_fixes": vf_report,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
