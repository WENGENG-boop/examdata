"""MS 行-区域一致性审计（只读本地索引与本地 MS PDF，不联网）。

对每份卷的 MS PDF 逐页取出「题号行」（以页内 'Question' 表头锚定 Question 列，
文本形如 1 / 1(a) / 3(a)(ii)），换算到显示坐标后与索引里的 ms 区域逐条比对。

缺陷类别：
  row_without_region  真实题号行没有任何 ms 区域覆盖（子题漏建索引）
  region_multi_row    区域条带含非自身/非后代的题号行（叶子区域混入下一题）
  region_wrong_row    区域条带覆盖的是另一分支的题号行（区域挂错题）
  region_without_row_header  区域的纵向条带里没有题号行、且页面无实质正文（悬空区域，通常只剩页眉）
  region_without_row_layout  同上但页面有实质正文（写作卷 level-descriptor 表没有编号行，属版式，需人工判读）
  region_unauditable_no_text 页面无可用文字层（扫描页或工坊乱码页），文本审计无法判定，需视觉核验

覆盖判定区分「祖先或自身区域覆盖」（合法）与「其他分支区域覆盖」（缺陷）。
文字层可用性：扫描页 get_text() 为空，CIE 工坊乱码页的文字层是控制字符，二者都判为不可审计。

用法：ms_row_audit.py KEY [KEY...] [--json OUT] [--all] [--quiet]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pymupdf

BATCH = Path("C:/Users/weo/Desktop/api/cie-location-batch")
TMP = BATCH / "tmp"
INDEXES = BATCH / "indexes"
LBL = re.compile(r"^\d{1,2}(\([a-z]+\))*$")
PART = re.compile(r"\d+|[a-z]+")
HEADERS = {"Question", "Answer", "Marks"}


def parts(q: str) -> list[str]:
    return PART.findall(q)


def is_ancestor_or_self(anc: str, desc: str) -> bool:
    a, d = parts(anc), parts(desc)
    return len(a) <= len(d) and d[: len(a)] == a


def pdf_for(key: str, role: str) -> Path | None:
    subject, year, season, paper = key.split("/")
    d = TMP / subject / f"{year}-{season}-{paper}"
    hits = sorted(d.glob(f"*_{role}_*.pdf"))
    return hits[0] if hits else None


def index_path(key: str) -> Path:
    subject, year, season, paper = key.split("/")
    return INDEXES / subject / f"{year}-{season}-{paper}" / "cie-index.json"


def to_display(bbox, rot, w, h):
    x0, y0, x1, y1 = bbox
    if rot == 0:
        return (x0, y0, x1, y1)
    if rot == 90:
        return (h - y1, x0, h - y0, x1)
    if rot == 180:
        return (w - x1, h - y1, w - x0, h - y0)
    if rot == 270:
        return (y0, w - x1, y1, w - x0)
    raise ValueError(f"unsupported rotation {rot}")


def text_rows(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        for ln in b.get("lines", []):
            t = "".join(s["text"] for s in ln.get("spans", [])).strip()
            if t:
                out.append((tuple(ln["bbox"]), t))
    return out


def audit(key: str, quiet: bool = False) -> dict:
    idx = json.loads(index_path(key).read_text(encoding="utf-8"))
    pdf = pdf_for(key, "ms")
    res = {"key": key, "ms_pdf": str(pdf) if pdf else None, "findings": [],
           "questions_with_empty_ms": [], "skipped": None, "pages_without_question_column": [],
           "pages_text_unauditable": []}
    for q in idx["questions"]:
        if not (q.get("ms") or []):
            res["questions_with_empty_ms"].append(q["question"])
    if pdf is None:
        res["skipped"] = "ms pdf missing in tmp"
        return res

    doc = pymupdf.open(pdf)
    ms_by_page: dict[int, list[tuple[str, list]]] = {}
    for q in idx["questions"]:
        for r in q.get("ms") or []:
            ms_by_page.setdefault(int(r["page"]), []).append((q["question"], list(r["bbox"])))

    for pno in range(1, doc.page_count + 1):
        page = doc[pno - 1]
        rot = page.rotation
        w, h = page.mediabox.width, page.mediabox.height
        rows = text_rows(page)
        cols = [to_display(b, rot, w, h) for b, t in rows if t == "Question"]
        labels = []
        if cols:
            cx0 = min(c[0] for c in cols)
            cx1 = max(c[2] for c in cols)
            cy1 = min(c[3] for c in cols)
            for bbox, text in rows:
                if text in HEADERS or not LBL.match(text):
                    continue
                db = to_display(bbox, rot, w, h)
                if db[0] >= cx0 - 6 and db[2] <= cx1 + 14 and db[1] >= cy1 - 2:
                    labels.append((text, db))
        elif ms_by_page.get(pno):
            # 该页没有可锚定的 Question 列，无法判定行归属；不当作缺陷，单独记账。
            res["pages_without_question_column"].append(pno)
        labels.sort(key=lambda r: (r[1][1], r[1][0]))
        regions = [(qn, to_display(b, rot, w, h)) for qn, b in ms_by_page.get(pno, [])]
        regions.sort(key=lambda r: (r[1][1], r[1][0]))

        def rnd(x):
            return round(x, 1)

        disp_lines = [(to_display(b, rot, w, h), t) for b, t in rows]
        # 逐页留档，供汇总脚本在不开 PDF 的情况下判定悬空区域是否为「首行之前的残带」。
        res.setdefault("page_rows", {})[str(pno)] = [
            [t, [rnd(v) for v in lb]] for t, lb in labels]
        res.setdefault("page_regions", {})[str(pno)] = [
            [qn, [rnd(v) for v in rb]] for qn, rb in regions]

        HEADERISH = re.compile(
            r"^(PUBLISHED|©|Page \d+ of \d+|\d{4}/\d+$|Cambridge International|"
            r"May/June \d{4}$|October/November \d{4}$|Question$|Answer$|Marks$|"
            r"Descriptor$|Guidance$|Task completion$|Range$|Accuracy$|Content$)")
        # 该页文字层是否可用于判定：扫描页无文字，CIE 工坊乱码页的文字层是控制字符垃圾。
        raw = page.get_text()
        bad = sum(1 for c in raw if ord(c) < 32 and c not in "\n\r\t")
        page_text_usable = len(raw) > 20 and bad / max(len(raw), 1) < 0.15
        if not page_text_usable:
            res.setdefault("pages_text_unauditable", []).append(pno)

        SUBST_MIN = 15

        def _inside(db, rb):
            return (db[0] >= rb[0] - 1 and db[1] >= rb[1] - 1
                    and db[2] <= rb[2] + 1 and db[3] <= rb[3] + 1)

        def text_inside(rb, limit=10):
            return [t[:60] for db, t in disp_lines if _inside(db, rb)][:limit]

        def substantive_inside(rb):
            return sum(1 for db, t in disp_lines
                       if _inside(db, rb) and len(t) >= SUBST_MIN and not HEADERISH.match(t))

        # 行归属用「题号行纵向中心落在区域条带内」判定：相邻行的条带首尾相接，
        # 用整行包含会因 0.05pt 的排版误差把末行误判为悬空（9868 答案网格即此例）。
        def owns(lb, rb):
            cy = (lb[1] + lb[3]) / 2
            return rb[1] - 1 <= cy <= rb[3] + 1

        for qn, rb in regions:
            inside = [t for t, lb in labels if owns(lb, rb)]
            if not inside:
                nsub = substantive_inside(rb)
                if not page_text_usable:
                    t = "region_unauditable_no_text"
                elif nsub > 0:
                    t = "region_without_row_layout"
                else:
                    t = "region_without_row_header"
                res["findings"].append(
                    {"type": t, "page": pno, "q": qn, "bbox": [rnd(v) for v in rb], "rotation": rot,
                     "page_text_usable": page_text_usable, "substantive_inside": nsub,
                     "text_inside": text_inside(rb)})
            else:
                foreign = [t for t in inside if not is_ancestor_or_self(qn, t)]
                if foreign:
                    res["findings"].append(
                        {"type": "region_wrong_row" if len(inside) == 1 else "region_multi_row",
                         "page": pno, "q": qn, "bbox": [rnd(v) for v in rb],
                         "labels_inside": inside, "foreign": foreign, "rotation": rot})
        for t, lb in labels:
            covering = [qn for qn, rb in regions if owns(lb, rb)]
            if not covering:
                res["findings"].append({"type": "row_without_region", "page": pno, "label": t,
                                        "disp": [rnd(v) for v in lb], "rotation": rot})
            elif not any(is_ancestor_or_self(qn, t) for qn in covering):
                res["findings"].append(
                    {"type": "row_covered_by_other_branch", "page": pno, "label": t,
                     "disp": [rnd(v) for v in lb], "covering": covering, "rotation": rot})
    doc.close()

    if not quiet:
        print("=" * 100)
        n = len(res["findings"])
        print(f"{key}  ms_pages={doc.page_count if False else ''} findings={n}  "
              f"empty_ms={len(res['questions_with_empty_ms'])}")
        for f in res["findings"]:
            print(f"  [{f['type']:26}] p{f['page']:<3} "
                  f"q={f.get('q') or f.get('label'):12} "
                  f"{f.get('bbox') or f.get('disp')} {f.get('labels_inside') or f.get('covering') or ''}")
    return res


def all_keys() -> list[str]:
    keys = []
    for p in sorted(INDEXES.glob("*/*/cie-index.json")):
        subj = p.parent.parent.name
        stem = p.parent.name
        m = re.match(r"^(\d{4})-(Mar|Jun|Nov)-(.+)$", stem)
        if m:
            keys.append(f"{subj}/{m.group(1)}/{m.group(2)}/{m.group(3)}")
    return keys


if __name__ == "__main__":
    argv = sys.argv[1:]
    keys = [a for a in argv if not a.startswith("--")]
    if "--all" in argv:
        keys = all_keys()
    quiet = "--quiet" in argv
    out = {}
    for k in keys:
        out[k] = audit(k, quiet=quiet)
    if not quiet:
        agg: dict[str, int] = {}
        for r in out.values():
            for f in r["findings"]:
                agg[f["type"]] = agg.get(f["type"], 0) + 1
        print()
        print("汇总:", json.dumps(agg, ensure_ascii=False), " 卷数=", len(out))
    if "--json" in argv:
        dest = Path(argv[argv.index("--json") + 1])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print("written", dest)
