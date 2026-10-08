"""为一份试卷生成「题目定位」提案。

做三件事：
1. 把 QP / MS 的每一页按 PAGE_ZOOM 渲染到 tmp/<subject>/<year>-<season>-<paper>/pages/
2. 从 QP 文字层抽取题号候选（顶层 1..99 / (a) / (i)）与分值、题干范围
3. 从 MS 文字层抽取 Question 列的行标签，并给出该行的矩形带

本工具只提出候选与边界框，不做任何视觉识别；判定交给渲染图。
坐标一律是「未旋转 PDF、左上原点、points」，page 从 1 起。
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path

import batchlib as B
import paperlib as P

if (getattr(sys.stdout, "encoding", "") or "").replace("-", "").lower() != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PAD = 4.0
MARGIN_TOP = 50.0
MARGIN_BOTTOM = 47.0

QP_TOP_X_MAX = 95.0
QP_SUB_X = (90.0, 110.0)
QP_SSUB_X_MIN = 110.0
QP_MARK_X_MIN = 480.0

MS_COL_PAD = 8.0
MS_COL_FALLBACK = (677.0, 733.5)
MS_ROW_PAD = 6.0
MS_ROW_RULE_MAX_W = 2.5
MS_H_RULE_MIN_W = 10.0
MS_LABEL_X_MAX = 110.0
MS_HEADER_WORD = "Question"
MS_TABLE_WORDS = ("Question", "Answer", "Marks", "Guidance")

QP_QUESTION_RE = re.compile(r"^[1-9]\d{0,2}(?:\([a-z]\)(?:\([ivx]+\))?)?$")
QP_TOP_RE = re.compile(r"^(\d{1,2})(?:\s|$)")
QP_SUB_RE = re.compile(r"^\(([a-z])\)")
QP_SSUB_RE = re.compile(r"^\(([ivx]+)\)")
QP_MARK_RE = re.compile(r"^\[(\d{1,3})\]$")
QP_TOTAL_RE = re.compile(r"The total mark for this paper is (\d+)")

MS_LABEL_RE = re.compile(r"^\d{1,2}(?:\([a-z]\))?$")
ROMAN_LOOKALIKE = {"i", "v", "x"}

DOT_LINE_RE = re.compile(r"^[.\s_·]+$")
FOOTER_CODE_RE = re.compile(r"^\d{4}/\d{1,2}[A-Z]?/")
BARE_INT_RE = re.compile(r"^\d{1,3}$")

ROW_OVERLAP_RATIO = 0.5

QP_BOILERPLATE_RE = (
    re.compile(r"^Additional page$"),
    re.compile(r"^If you use the following page to complete the answer"),
    re.compile(r"^Permission to reproduce items"),
    re.compile(r"^reasonable effort has been made by the publisher"),
    re.compile(r"^publisher will be pleased to make amends"),
    re.compile(r"^To avoid the issue of disclosure of answer-related information"),
    re.compile(r"^Assessment International Education Copyright"),
    re.compile(r"^at www\.cambridgeinternational\.org"),
    re.compile(r"^Cambridge Assessment International Education is part of"),
    re.compile(r"^Local Examinations Syndicate \(UCLES\)"),
)


def group_words(words) -> list[dict]:
    grouped: dict[tuple[int, int], list] = {}
    for w in words:
        grouped.setdefault((w[5], w[6]), []).append(w)
    lines = []
    for (block, line), items in sorted(grouped.items()):
        items.sort(key=lambda w: w[0])
        lines.append({
            "block": block, "line": line,
            "text": " ".join(w[4] for w in items),
            "x0": min(w[0] for w in items), "y0": min(w[1] for w in items),
            "x1": max(w[2] for w in items), "y1": max(w[3] for w in items),
            "words": items,
        })
    lines.sort(key=lambda l: (round(l["y0"], 1), l["x0"]))
    return lines


def thin_rules(page) -> tuple[list[dict], list[dict]]:
    v_rules, h_rules = [], []
    for drawing in page.get_drawings():
        rect = drawing["rect"]
        width = rect.x1 - rect.x0
        height = rect.y1 - rect.y0
        if width < MS_ROW_RULE_MAX_W:
            v_rules.append({"x": (rect.x0 + rect.x1) / 2, "y0": rect.y0, "y1": rect.y1})
        elif height < MS_ROW_RULE_MAX_W and width >= MS_H_RULE_MIN_W:
            h_rules.append({"y": (rect.y0 + rect.y1) / 2, "x0": rect.x0, "x1": rect.x1})
    v_rules.sort(key=lambda r: (round(r["x"], 1), r["y0"]))
    h_rules.sort(key=lambda r: (round(r["y"], 1), r["x0"]))
    return v_rules, h_rules


def read_doc(path: Path) -> dict:
    import pymupdf
    pages = []
    with pymupdf.open(path) as pdf:
        for i, page in enumerate(pdf):
            bounds = P.analysis_bounds(page)
            v_rules, h_rules = thin_rules(page)
            pages.append({
                "page": i + 1,
                "rotation": page.rotation,
                "rect": [page.rect.x0, page.rect.y0, page.rect.x1, page.rect.y1],
                "bounds": bounds,
                "lines": group_words(page.get_text("words")),
                "rules": v_rules,
                "h_rules": h_rules,
            })
    return {"pages": pages}


def is_decorative(line: dict, bounds) -> bool:
    text = line["text"].strip()
    if not text:
        return True
    if DOT_LINE_RE.match(text):
        return True
    if text.startswith("©"):
        return True
    if FOOTER_CODE_RE.match(text):
        return True
    if "BLANK PAGE" in text.upper():
        return True
    if text.startswith("[Turn over") or text.startswith("Turn over"):
        return True
    if BARE_INT_RE.match(text) and (line["y0"] < bounds[1] + MARGIN_TOP
                                    or line["y1"] > bounds[3] - MARGIN_BOTTOM):
        return True
    return False


def content_lines(page: dict) -> list[dict]:
    boiler = {l["block"] for l in page["lines"]
              if any(rx.match(l["text"].strip()) for rx in QP_BOILERPLATE_RE)}
    return [l for l in page["lines"]
            if l["block"] not in boiler and not is_decorative(l, page["bounds"])]


def ordered_rows(doc: dict) -> list[dict]:
    out: list[dict] = []
    for page in doc["pages"]:
        rows: list[dict] = []
        for line in content_lines(page):
            item = dict(line, page=page["page"])
            for row in rows:
                overlap = min(row["y1"], item["y1"]) - max(row["y0"], item["y0"])
                shorter = min(row["y1"] - row["y0"], item["y1"] - item["y0"])
                if shorter > 0 and overlap >= shorter * ROW_OVERLAP_RATIO:
                    row["lines"].append(item)
                    row["y0"] = min(row["y0"], item["y0"])
                    row["y1"] = max(row["y1"], item["y1"])
                    break
            else:
                rows.append({"page": page["page"], "y0": item["y0"], "y1": item["y1"],
                             "lines": [item]})
        rows.sort(key=lambda r: (r["y0"], min(l["x0"] for l in r["lines"])))
        for row in rows:
            row["lines"].sort(key=lambda l: l["x0"])
            row["x0"] = min(l["x0"] for l in row["lines"])
            row["x1"] = max(l["x1"] for l in row["lines"])
        out.extend(rows)
    for index, row in enumerate(out):
        row["index"] = index
        row["text"] = re.sub(r"\s+", " ", " ".join(l["text"] for l in row["lines"])).strip()
    return out


def qp_marker(line: dict) -> tuple[int, str] | None:
    text = line["text"].strip()
    x0 = line["x0"]
    if x0 < QP_TOP_X_MAX:
        m = QP_TOP_RE.match(text)
        if m and 1 <= int(m.group(1)) <= 99:
            return 0, str(int(m.group(1)))
    if QP_SUB_X[0] <= x0 < QP_SUB_X[1]:
        m = QP_SUB_RE.match(text)
        if m:
            return 1, m.group(1)
    if x0 >= QP_SSUB_X_MIN:
        m = QP_SSUB_RE.match(text)
        if m:
            return 2, m.group(1)
    return None


def _merged_sub_marker(line: dict) -> tuple[str, tuple] | None:
    words = line.get("words") or []
    if len(words) < 2 or not re.fullmatch(r"\d{1,2}", words[0][4]):
        return None
    match = re.fullmatch(r"\(([a-z])\)", words[1][4])
    if match is None or words[1][0] >= QP_SUB_X[1]:
        return None
    return match.group(1), words[1]


def qp_questions(doc: dict, warnings: list[str]) -> list[dict]:
    rows = ordered_rows(doc)
    markers: list[dict] = []
    for row in rows:
        for line in row["lines"]:
            found = qp_marker(line)
            if not found:
                continue
            markers.append({"level": found[0], "label": found[1],
                            "line": line, "row": row, "word": None})
            if found[0] == 0:
                merged = _merged_sub_marker(line)
                if merged is not None:
                    markers[-1]["word"] = line["words"][0]
                    markers.append({"level": 1, "label": merged[0],
                                    "line": line, "row": row, "word": merged[1]})

    out: list[dict] = []
    stack: list[tuple[int, str]] = []
    for marker in markers:
        level = marker["level"]
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, marker["label"]))
        parts = [lb if lv == 0 else f"({lb})" for lv, lb in stack]
        out.append({
            "question": "".join(parts),
            "parent": "".join(parts[:-1]) if len(parts) > 1 else None,
            "level": level,
            "marker": marker,
        })

    for i, item in enumerate(out):
        level = item["level"]
        start = item["marker"]["row"]["index"]
        end = len(rows)
        for later in out[i + 1:]:
            if later["level"] <= level:
                end = max(later["marker"]["row"]["index"], start + 1)
                break
        span_rows = rows[start:end]
        span = [line for row in span_rows for line in row["lines"]]
        marker_line = item["marker"]["line"]
        item["span"] = span
        item["span_rows"] = len(span_rows)
        regions = _regions(span, doc)
        item["regions"] = regions
        item["bbox"] = regions[0]["bbox"] if len(regions) == 1 else None
        item["marks"] = _span_marks(span)
        word = item["marker"].get("word")
        if word is None:
            item["marker_bbox"] = [round(marker_line["x0"], 1), round(marker_line["y0"], 1),
                                   round(marker_line["x1"], 1), round(marker_line["y1"], 1)]
        else:
            item["marker_bbox"] = [round(word[0], 1), round(word[1], 1),
                                   round(word[2], 1), round(word[3], 1)]
        item["text"] = re.sub(r"\s+", " ", " ".join(l["text"] for l in span)).strip()

    _qp_warnings(out, warnings)
    return out


def _regions(span: list[dict], doc: dict) -> list[dict]:
    bounds = {p["page"]: p["bounds"] for p in doc["pages"]}
    by_page: dict[int, list[dict]] = {}
    for line in span:
        by_page.setdefault(line["page"], []).append(line)
    regions = []
    for page_no in sorted(by_page):
        group = by_page[page_no]
        box = bounds[page_no]
        x0 = max(min(l["x0"] for l in group) - PAD, box[0])
        y0 = max(min(l["y0"] for l in group) - PAD, box[1])
        x1 = min(max(l["x1"] for l in group) + PAD, box[2])
        y1 = min(max(l["y1"] for l in group) + PAD, box[3])
        regions.append({"page": page_no,
                        "bbox": [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)]})
    return regions


def _span_mark_values(span: list[dict]) -> list[int]:
    values = []
    for line in span:
        for word in line.get("words") or ():
            m = QP_MARK_RE.match(word[4])
            if m and word[0] > QP_MARK_X_MIN:
                values.append(int(m.group(1)))
    return values


def _span_marks(span: list[dict]) -> int | None:
    values = _span_mark_values(span)
    return values[-1] if values else None


def _children(candidates: list[dict], name: str) -> list[dict]:
    return [c for c in candidates if c["parent"] == name]


def leaf_total_marks(candidates: list[dict]) -> int | None:
    leaves = [c for c in candidates if not _children(candidates, c["question"])]
    if not leaves or any(c["marks"] is None for c in leaves):
        return None
    return sum(c["marks"] for c in leaves)


_ROMAN_NUMERALS = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"]


def _self_checks(candidates: list[dict], rows: list[dict], total: int | None,
                 warnings: list[str]) -> list[dict]:
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            warnings.append(f"自检未过 [{name}]：{detail}")

    leaves = [c for c in candidates if not _children(candidates, c["question"])]
    leaf_total = leaf_total_marks(candidates)
    if total is None or leaf_total is None:
        missing = "、".join(c["question"] for c in leaves if c["marks"] is None)
        add("leaf_marks_sum", False,
            f"无法校验：声明总分 {total}，叶子合计 {leaf_total}，未取到分值的叶子：{missing or '无'}")
    else:
        add("leaf_marks_sum", leaf_total == total,
            f"叶子题合计 {leaf_total} vs 首页声明 {total}")

    tops = [c for c in candidates if c["level"] == 0]
    labels = [int(c["question"]) for c in tops]
    expected = list(range(1, len(tops) + 1))
    add("top_numbering", labels == expected, f"顶层题号 {labels} vs 期望 {expected}")

    bad_parents: list[str] = []
    for parent in candidates:
        kids = _children(candidates, parent["question"])
        if not kids:
            continue
        got = [k["marker"]["label"] for k in kids]
        if kids[0]["level"] == 1:
            want = [chr(ord("a") + i) for i in range(len(got))]
        elif kids[0]["level"] == 2:
            want = [_ROMAN_NUMERALS[i] if i < len(_ROMAN_NUMERALS) else str(i + 1)
                    for i in range(len(got))]
        else:
            bad_parents.append(f"{parent['question']} 子题层级异常 {kids[0]['level']}")
            continue
        if got != want:
            bad_parents.append(f"{parent['question']} 子题 {got} != {want}")
    add("sub_lettering", not bad_parents, "；".join(bad_parents) or "各父题子题字母连续")

    leaf_names = {c["question"] for c in leaves}
    orphans = sorted({r["label"] for r in rows} - leaf_names)
    add("ms_labels_within_leaves", not orphans,
        f"MS 标签无对应叶子题：{'、'.join(orphans)}" if orphans
        else f"{len({r['label'] for r in rows})} 个 MS 标签均落在叶子题内")

    ordered = True
    ordered_detail = "MS 行按（页, y）升序"
    prev: tuple | None = None
    for row in rows:
        key = (row["page"], row["row_bbox"][1])
        if prev is not None and key <= prev:
            ordered = False
            ordered_detail = f"MS 行顺序异常：{prev} → {key}（标签 {row['label']}）"
            break
        prev = key
    add("ms_rows_ordered", ordered, ordered_detail)

    bad_regions = []
    for c in candidates:
        pages = [r["page"] for r in c["regions"]]
        if pages != sorted(set(pages)):
            bad_regions.append(f"{c['question']}{pages}")
    add("regions_page_order", not bad_regions,
        "；".join(bad_regions) or "各题区间跨页顺序正常")

    bad_marks = [(c["question"], len(_span_mark_values(c["span"]))) for c in leaves]
    bad_marks = [(q, n) for q, n in bad_marks if n != 1]
    add("leaf_single_mark", not bad_marks,
        "叶子题区间 [n] 个数异常：" + "、".join(f"{q}×{n}" for q, n in bad_marks[:10])
        if bad_marks else f"{len(leaves)} 个叶子题区间内各恰 1 个 [n]")

    return checks


def _qp_warnings(out: list[dict], warnings: list[str]) -> None:
    for item in out:
        name = item["question"]
        if not QP_QUESTION_RE.match(name):
            warnings.append(f"QP 题号 {name!r} 不匹配索引 schema 的题号模式，需人工修正")
        if item["level"] == 1 and item["marker"]["label"] in ROMAN_LOOKALIKE:
            warnings.append(
                f"QP 第 {item['marker']['line']['page']} 页的 ({item['marker']['label']}) "
                f"x0={item['marker']['line']['x0']:.1f} 落在子题区间，但看起来像罗马数字，"
                f"可能被误判层级")

    for item in out:
        kids = _children(out, item["question"])
        marks = [k["marks"] for k in kids]
        item["marks_children_sum"] = (
            sum(marks) if kids and all(m is not None for m in marks) else None)

    missing = [c["question"] for c in out if c["marks"] is None]
    if missing:
        shown = "、".join(missing[:8]) + ("…" if len(missing) > 8 else "")
        warnings.append(f"QP 有 {len(missing)} 个题号未在其区间内找到右栏分值 [n]：{shown}")

    if any(item["level"] == 0 and _children(out, item["question"]) for item in out):
        warnings.append(
            "约定：候选的 marks 取该题区间内最后一个右栏 [n]，对顶层题即其最后一小题的分值，"
            "不等于子题合计（子题合计见 marks_children_sum）；总分校验用叶子题合计")


def qp_total_marks(doc: dict) -> int | None:
    if not doc["pages"]:
        return None
    for line in doc["pages"][0]["lines"]:
        m = QP_TOTAL_RE.search(line["text"])
        if m:
            return int(m.group(1))
    return None


def ms_column_band(page: dict) -> tuple[float, float] | None:
    for line in page["lines"]:
        if line["text"].strip() == MS_HEADER_WORD and line["x0"] < 100:
            return line["y0"] - MS_COL_PAD, line["y1"] + MS_COL_PAD
    return None


def ms_table_words(page: dict) -> list[str]:
    present = {l["text"].strip() for l in page["lines"] if l["x0"] < 100}
    return [w for w in MS_TABLE_WORDS if w in present]


def _column_bounds(page: dict, band: tuple[float, float]) -> list[float]:
    crossing = [r for r in page["rules"]
                if r["y1"] > band[0] and r["y0"] < band[1]]
    bounds_list: list[float] = []
    for rule in crossing:
        if not bounds_list or abs(bounds_list[-1] - rule["x"]) > 0.6:
            bounds_list.append(rule["x"])
    bounds_list.sort()
    return bounds_list


def _row_x_range(bounds_list: list[float], label: dict, page: dict) -> tuple[float, float, str]:
    if len(bounds_list) >= 2:
        return bounds_list[0], bounds_list[-1], "rule"
    box = page["bounds"]
    x0 = max(label["x0"] - MS_ROW_PAD, box[0])
    x1 = min(label["x1"] + MS_ROW_PAD, box[2])
    return x0, x1, "fallback"


def _row_y_range(page: dict, label: dict, labels: list[dict], index: int,
                 band: tuple[float, float]) -> tuple[float, float, str]:
    header_y1 = band[1] - MS_COL_PAD
    cx = (label["x0"] + label["x1"]) / 2
    segs = [r["y"] for r in page["h_rules"] if r["x0"] - 1 <= cx <= r["x1"] + 1]
    top = [y for y in segs if header_y1 - 2 <= y <= label["y0"] + 1]
    bottom = [y for y in segs if y >= label["y1"] - 1]
    source = "rule"
    y0 = max(top) if top else None
    y1 = min(bottom) if bottom else None
    if y0 is None:
        prev = labels[index - 1]["y1"] if index > 0 else None
        y0 = (prev + label["y0"]) / 2 if prev is not None else label["y0"] - MS_ROW_PAD
        source = "fallback"
    if y1 is None:
        nxt = labels[index + 1]["y0"] if index + 1 < len(labels) else None
        y1 = (label["y1"] + nxt) / 2 if nxt is not None else label["y1"] + MS_ROW_PAD
        source = "fallback"
    box = page["bounds"]
    y0 = max(y0, box[1])
    y1 = min(y1, box[3])
    if y1 <= y0:
        y1 = y0 + MS_ROW_PAD
    return y0, y1, source


def ms_rows(doc: dict, warnings: list[str]) -> list[dict]:
    out: list[dict] = []
    for page in doc["pages"]:
        if page["rotation"] % 180 != 0:
            out.extend(_ms_rows_rotated(page, warnings))
            continue
        band = ms_column_band(page)
        if band is None:
            suspects = [l for l in content_lines(page)
                        if MS_LABEL_RE.match(l["text"].strip())
                        and l["x0"] < MS_LABEL_X_MAX]
            if suspects:
                warnings.append(
                    f"MS 第 {page['page']} 页没有 {MS_HEADER_WORD!r} 表头，"
                    f"{len(suspects)} 个疑似编号未纳入（说明性编号列表）")
            continue
        band_words = ms_table_words(page)
        bounds_list = _column_bounds(page, band)
        x_max = bounds_list[1] if len(bounds_list) >= 2 else MS_LABEL_X_MAX
        labels = [l for l in content_lines(page)
                  if MS_LABEL_RE.match(l["text"].strip())
                  and l["y0"] > band[1] - MS_COL_PAD + 1 and l["x0"] < x_max]
        labels.sort(key=lambda l: (round(l["y0"], 1), l["x0"]))
        for i, label in enumerate(labels):
            x0, x1, x_source = _row_x_range(bounds_list, label, page)
            y0, y1, y_source = _row_y_range(page, label, labels, i, band)
            out.append({
                "label": label["text"].strip(),
                "page": page["page"],
                "row": [round(x0, 1), round(x1, 1)],
                "row_bbox": [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)],
                "row_source": "rule" if x_source == "rule" and y_source == "rule" else "fallback",
                "column_band": [round(band[0], 1), round(band[1], 1)],
                "page_has_table_header": True,
                "page_table_words": band_words,
                "label_bbox": [round(label["x0"], 1), round(label["y0"], 1),
                               round(label["x1"], 1), round(label["y1"], 1)],
            })
    return out


def _ms_rows_rotated(page: dict, warnings: list[str]) -> list[dict]:
    band = ms_column_band(page)
    header = band is not None
    if band is None:
        band = MS_COL_FALLBACK
    band_words = ms_table_words(page)
    labels = [l for l in content_lines(page)
              if MS_LABEL_RE.match(l["text"].strip())
              and l["y0"] >= band[0] - 1 and l["y1"] <= band[1] + 1]
    if not header and labels:
        warnings.append(
            f"MS 第 {page['page']} 页（rotation={page['rotation']}）没有 {MS_HEADER_WORD!r} 表头，"
            f"但按固定列带 {band} 命中 {len(labels)} 个疑似标签，已保留并标记")
    if not labels:
        return []
    labels.sort(key=lambda l: l["x0"])
    bounds_list = _column_bounds(page, band)
    out: list[dict] = []
    for label in labels:
        x0 = x1 = None
        source = "rule"
        for j in range(len(bounds_list) - 1):
            if bounds_list[j] <= label["x0"] < bounds_list[j + 1]:
                x0, x1 = bounds_list[j], bounds_list[j + 1]
                break
        if x0 is None:
            source = "fallback"
            x0 = label["x0"] - MS_ROW_PAD
            nxt = [l["x0"] for l in labels if l["x0"] > label["x0"]]
            x1 = (nxt[0] - MS_ROW_PAD if nxt else page["bounds"][2])
        y0, y1 = _rotated_row_y_range(page, x0, x1, source)
        out.append({
            "label": label["text"].strip(),
            "page": page["page"],
            "row": [round(x0, 1), round(x1, 1)],
            "row_bbox": [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)],
            "row_source": source,
            "column_band": [round(band[0], 1), round(band[1], 1)],
            "page_has_table_header": header,
            "page_table_words": band_words,
            "label_bbox": [round(label["x0"], 1), round(label["y0"], 1),
                           round(label["x1"], 1), round(label["y1"], 1)],
        })
    return out


def _rotated_row_y_range(page: dict, x0: float, x1: float, source: str) -> tuple[float, float]:
    if source == "rule":
        ys = [(r["y0"], r["y1"]) for r in page["rules"]
              if abs(r["x"] - x0) <= 0.6 or abs(r["x"] - x1) <= 0.6]
        if ys:
            lo = min(a for a, _ in ys)
            hi = max(b for _, b in ys)
            box = page["bounds"]
            return max(lo, box[1]), min(hi, box[3])
    lines = content_lines(page)
    box = page["bounds"]
    if not lines:
        return box[1], box[3]
    lo = max(min(l["y0"] for l in lines) - 2.0, box[1])
    hi = min(max(l["y1"] for l in lines) + 2.0, box[3])
    return lo, hi


def find_pdfs(tmp_dir: Path) -> tuple[Path | None, Path | None]:
    def pick(*patterns):
        for pattern in patterns:
            hits = sorted(tmp_dir.glob(pattern))
            if hits:
                return hits[0]
        return None
    return pick("*_qp_*.pdf", "*qp*.pdf"), pick("*_ms_*.pdf", "*ms*.pdf")


def render_doc(path: Path, out_dir: Path, prefix: str, pages: int, force: bool) -> list[dict]:
    import pymupdf
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = path.stat().st_mtime
    rendered, reused = 0, 0
    with pymupdf.open(path) as pdf:
        for i, page in enumerate(pdf):
            dest = out_dir / f"{prefix}-p{i + 1:03d}.png"
            if not force and dest.exists() and dest.stat().st_mtime >= stamp:
                reused += 1
                continue
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(P.PAGE_ZOOM, P.PAGE_ZOOM),
                                     alpha=False)
            pixmap.save(str(dest))
            pixmap = None
            rendered += 1
    return [{"page": i + 1, "path": f"pages/{prefix}-p{i + 1:03d}.png"}
            for i in range(pages)], rendered, reused


def _line_out(line: dict) -> dict:
    return {k: v for k, v in line.items() if k != "words"}


def build(key: str, force: bool) -> int:
    subject, year, season, paper = key.split("/")
    tmp_dir = P.paper_tmp(key)
    if not tmp_dir.is_dir():
        print(f"[失败] 没有临时目录 {tmp_dir}")
        return 1
    qp_path, ms_path = find_pdfs(tmp_dir)
    if qp_path is None:
        print(f"[失败] {tmp_dir} 下找不到 QP PDF")
        return 1

    warnings: list[str] = []
    qp_doc = read_doc(qp_path)
    ms_doc = read_doc(ms_path) if ms_path else None

    pages_dir = tmp_dir / "pages"
    qp_images, qp_rendered, qp_reused = render_doc(qp_path, pages_dir, "qp",
                                                   len(qp_doc["pages"]), force)
    ms_images, ms_rendered, ms_reused = ([], 0, 0)
    if ms_doc is not None:
        ms_images, ms_rendered, ms_reused = render_doc(ms_path, pages_dir, "ms",
                                                       len(ms_doc["pages"]), force)

    candidates = qp_questions(qp_doc, warnings)
    rows = ms_rows(ms_doc, warnings) if ms_doc is not None else []

    total = qp_total_marks(qp_doc)
    top = [c for c in candidates if c["level"] == 0]
    leaf_total = leaf_total_marks(candidates)
    checks = _self_checks(candidates, rows, total, warnings)

    payload = {
        "key": key,
        "identity": {"subject": subject, "year": int(year), "season": season,
                     "paper": paper},
        "generated_at": B.now_iso(),
        "coordinate_system": "unrotated_pdf_points_top_left",
        "page_base": 1,
        "note": "候选与边界框来自 PDF 文字层与矢量表格线；判定以 pages/ 下的渲染图为准",
        "qp_sha256": B.sha256_file(qp_path),
        "ms_sha256": None if ms_path is None else B.sha256_file(ms_path),
        "qp_pages": len(qp_doc["pages"]),
        "ms_pages": None if ms_doc is None else len(ms_doc["pages"]),
        "page_meta": {"qp": P.page_meta(qp_path),
                      "ms": None if ms_path is None else P.page_meta(ms_path)},
        "qp_pages_detail": [{"page": p["page"], "rotation": p["rotation"],
                             "analysis_bounds": p["bounds"],
                             "lines": [_line_out(l) for l in p["lines"]]}
                            for p in qp_doc["pages"]],
        "ms_pages_detail": [] if ms_doc is None else [
            {"page": p["page"], "rotation": p["rotation"],
             "analysis_bounds": p["bounds"],
             "lines": [_line_out(l) for l in p["lines"]]}
            for p in ms_doc["pages"]],
        "render": {"zoom": P.PAGE_ZOOM, "pages_dir": str(pages_dir),
                   "qp": qp_images, "ms": ms_images,
                   "qp_rendered": qp_rendered, "qp_reused": qp_reused,
                   "ms_rendered": ms_rendered, "ms_reused": ms_reused},
        "documents": {
            "qp": {"filename": qp_path.name, "sha256": B.sha256_file(qp_path),
                   "pages": len(qp_doc["pages"]),
                   "rotations": sorted({p["rotation"] for p in qp_doc["pages"]}),
                   "bounds": qp_doc["pages"][0]["bounds"]},
            "ms": None if ms_doc is None else {
                "filename": ms_path.name, "sha256": B.sha256_file(ms_path),
                "pages": len(ms_doc["pages"]),
                "rotations": sorted({p["rotation"] for p in ms_doc["pages"]}),
                "bounds": ms_doc["pages"][0]["bounds"]},
        },
        "qp_total_marks": total,
        "qp_leaf_marks_total": leaf_total,
        "question_candidates": [
            {**{k: v for k, v in c.items() if k not in ("span", "span_rows", "marker")},
             "marker_line": c["marker"]["line"]["text"],
             "needs_review": True, "text_source": "text_layer"}
            for c in candidates],
        "ms_candidates": rows,
        "checks": checks,
        "stats": {
            "question_candidates": len(candidates),
            "top_level": len(top),
            "ms_candidates": len(rows),
            "ms_pages_with_labels": len({r["page"] for r in rows}),
            "warnings": len(warnings),
            "checks_failed": sum(1 for c in checks if not c["ok"]),
        },
        "warnings": warnings,
    }

    dest = B.WORK / "proposals" / subject / f"{year}-{season}-{paper}.json"
    B.atomic_write_json(dest, payload)

    print(f"提案 {key}")
    print(f"  QP {qp_path.name} {len(qp_doc['pages'])} 页 "
          f"渲染 {qp_rendered} 复用 {qp_reused}")
    if ms_doc is not None:
        print(f"  MS {ms_path.name} {len(ms_doc['pages'])} 页 "
              f"渲染 {ms_rendered} 复用 {ms_reused}")
    else:
        print("  MS 缺失，跳过 MS 行带")
    print(f"  题目候选 {len(candidates)}（顶层 {len(top)}）  MS 行带 {len(rows)}")
    print(f"  分值：首页声明 {total}  叶子题合计 {leaf_total}")
    print(f"  自检 {sum(1 for c in checks if c['ok'])}/{len(checks)} 通过")
    print(f"  警告 {len(warnings)}")
    for item in warnings:
        print(f"    ~ {item}")
    print(f"  写出 {dest}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="生成题目定位提案并渲染页面")
    parser.add_argument("key", help="subject/year/season/paper，如 9709/2024/Jun/11")
    parser.add_argument("--force", action="store_true", help="强制重新渲染所有页面")
    args = parser.parse_args()
    return build(args.key, args.force)


if __name__ == "__main__":
    raise SystemExit(main())
