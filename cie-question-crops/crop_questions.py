"""纯几何算法把 CIE QP 按题切图成 PNG；乱码文字层可用（不 OCR、不调模型）。

定位依据全部是文字层 span 的坐标与字形结构，与文字内容无关：
- 题号 token：左栏 x0≈72、页顶 y0<82 的 1-3 字形 span（乱码字形照样按位置找到）
- 小题标记：x0≈94 的 3 字形 span，用「首尾字形成对出现 ≥2 次」过滤噪声
  （乱码是一致替换，同一标记在整卷重复出现，字形对计数不受影响）
- 答题点线：x0≈94/115 的长重复行 —— 题目续页；卷尾附加页的点线整栏起（x0≈72）
- 裁剪框：内容区左右各留 10pt；上界在页顶条码/页码行下、首题号上；下界在页脚行上

输出（默认 <本文件目录>/out/<pdf 文件名>/）：
- crops/qNN.png       整题合成图；多页题按页纵向拼接
- crops/qNN-pNN.png   多页题的逐页分图
- crops/manifest.json 每题页码、y 区间、小题标记与自检结果
- viewer.html         查看页（--no-viewer 关闭）

用法：
  <venv-python> crop_questions.py --pdf <QP.pdf> [--out <dir>] [--zoom 3.0] [--strict]

设计文档见同目录 DESIGN.md；本文件自包含（仅依赖 pymupdf + 标准库）。
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

# ---- 版面常量（9709/2026/Mar/12 实测；换版式时由自检兜底报警，而不是静默切错）----
TOKEN_X0 = (70.0, 76.0)      # 题号列 x0
TOKEN_X1_MAX = 92.0
TOKEN_Y_MAX = 82.0           # 题号只在页顶
TOKEN_GLYPHS = (1, 3)        # 剥掉尾随空格字形后的长度

MARKER_X0 = (92.0, 97.0)     # 小题标记列 x0
MARKER_X1_MAX = 118.0
MARKER_GLYPHS = 3            # "(a)" 类 3 字形
MARKER_PAIR_MIN = 2          # 首尾字形成对至少出现几次才算真标记

CONTENT_Y = (50.0, 735.0)    # 内容区 y 范围；页顶条码/页码与页脚都在其外
CROP_PAD_X = 10.0
BOTTOM_GAP = 0.7             # 下界与页脚顶的间隙
TOP_FLOOR = 56.5             # 上界不低于页顶行（条码/页码）下沿
TOP_GAP = 2.0                # 上界与首题号 y0 的间隙

DOT_MIN_GLYPHS = 30          # 长重复行（答题点线）判定
DOT_MAX_KINDS = 3
DOT_X0_INDENT = (88.0, 132.0)  # 题内答题区缩进列（实测 93.7 / 115.1）
DOT_X0_FULLWIDTH = 80.0        # 附加页点线整栏起（实测 72.4）
DOT_ROWS_MIN = 5

EDGE_PX = 9                  # 四边无墨自检的像素带宽（渲染分辨率下）
INK_DARK = 200
INK_RANGE = (0.0005, 0.20)   # 整图墨迹占比合理区间

ARTIFACT_X = (55.0, 556.0)   # 印刷标记/灰色条带所在的页边带，不算内容图形
ARTIFACT_Y = (50.0, 745.0)

MAX_PAGE_PT = 14000.0        # PyMuPDF 单页尺寸上限附近；超过则不拼合成图

QUESTION_RE = re.compile(r"^q(\d{2})(?:-p(\d{2}))?\.png$")


def _fix_stdout() -> None:
    if (getattr(sys.stdout, "encoding", "") or "").replace("-", "").lower() != "utf8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


# ---------------------------------------------------------------- 几何分析（纯函数）

def load_spans(doc) -> list[list[tuple[float, float, float, float, str]]]:
    """每页的非旋转文字 span：(x0, y0, x1, y1, text)；纯空格 span 跳过。"""
    pages = []
    for page in doc:
        spans = []
        for block in page.get_text("dict")["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                dx, dy = line["dir"]
                if abs(dx - 1) > 1e-3 or abs(dy) > 1e-3:
                    continue
                for span in line["spans"]:
                    if not span["text"].strip("~ "):
                        continue
                    bbox = span["bbox"]
                    spans.append((bbox[0], bbox[1], bbox[2], bbox[3], span["text"]))
        pages.append(spans)
    return pages


def find_tokens(page_spans) -> list[dict]:
    """题号 token：左栏页顶的 1-3 字形 span。"""
    tokens = []
    for pno, spans in enumerate(page_spans):
        for x0, y0, x1, y1, text in spans:
            core = text.strip("~ ")
            if (TOKEN_X0[0] <= x0 <= TOKEN_X0[1] and y0 < TOKEN_Y_MAX
                    and x1 <= TOKEN_X1_MAX and TOKEN_GLYPHS[0] <= len(core) <= TOKEN_GLYPHS[1]):
                tokens.append({"page": pno, "y0": y0, "x0": x0, "x1": x1, "raw": text})
    tokens.sort(key=lambda t: (t["page"], t["y0"]))
    return tokens


def find_markers(page_spans) -> tuple[list[dict], dict, collections.Counter]:
    """小题标记：3 字形候选 + 首尾字形成对 ≥2 次过滤；返回 (保留, 字形→字母, 全部计数)。"""
    cands = []
    for pno, spans in enumerate(page_spans):
        for x0, y0, x1, y1, text in spans:
            core = text.rstrip("~ ")
            if (MARKER_X0[0] <= x0 <= MARKER_X0[1] and x1 <= MARKER_X1_MAX
                    and len(core) == MARKER_GLYPHS):
                cands.append({"page": pno, "y0": y0, "x0": x0, "x1": x1,
                              "raw": text, "core": core})
    pairs = collections.Counter((c["core"][0], c["core"][-1]) for c in cands)
    kept = [c for c in cands if pairs[(c["core"][0], c["core"][-1])] >= MARKER_PAIR_MIN]
    kept.sort(key=lambda c: (c["page"], c["y0"]))
    label_of: dict[str, str] = {}
    for c in kept:
        if c["core"] not in label_of:
            label_of[c["core"]] = "abcdefghijklmnopqrstuvwxyz"[len(label_of)]
        c["label"] = label_of[c["core"]]
    return kept, label_of, pairs


def dot_rows(spans) -> list[tuple[float, float]]:
    """长重复行（答题点线）：(y0, x0)。"""
    rows = []
    for x0, y0, x1, y1, text in spans:
        core = text.strip("~ ")
        if (len(core) >= DOT_MIN_GLYPHS and len(set(core)) <= DOT_MAX_KINDS
                and CONTENT_Y[0] < y0 < CONTENT_Y[1]):
            rows.append((y0, x0))
    return rows


def page_signature(spans) -> dict:
    rows = dot_rows(spans)
    return {
        "dot_rows": len(rows),
        "indented": sum(1 for _, x0 in rows if DOT_X0_INDENT[0] <= x0 <= DOT_X0_INDENT[1]),
        "fullwidth": sum(1 for _, x0 in rows if x0 <= DOT_X0_FULLWIDTH),
    }


def crop_box(page_spans, tokens) -> tuple[float, float, float, float, dict]:
    """裁剪框：内容区 + 页顶行 + 页脚（页脚扫描从首题页起）。"""
    p0 = tokens[0]["page"]
    content = [s for spans in page_spans[p0:] for s in spans
               if CONTENT_Y[0] < s[1] < CONTENT_Y[1]]
    xs0 = min(s[0] for s in content)
    xs1 = max(s[2] for s in content)
    ys1 = max(s[3] for s in content)
    top_spans = [s for spans in page_spans for s in spans if s[1] < 55.0]
    top_y1 = max((s[3] for s in top_spans), default=57.0)
    foot_spans = [s for spans in page_spans[p0:] for s in spans if s[1] > 730.0]
    foot_y0 = min((s[1] for s in foot_spans), default=None)
    tmin = min(t["y0"] for t in tokens)
    top = min(max(top_y1 + 0.8, TOP_FLOOR), tmin - TOP_GAP)
    bot = min(ys1 + 0.8, foot_y0 - BOTTOM_GAP) if foot_y0 is not None else ys1 + 0.8
    left = xs0 - CROP_PAD_X
    right = xs1 + CROP_PAD_X
    detail = {"content_x": [round(xs0, 1), round(xs1, 1)], "content_y1": round(ys1, 1),
              "top_line_y1": round(top_y1, 1), "footer_y0": foot_y0,
              "token_ymin": round(tmin, 1)}
    return left, top, right, bot, detail


def question_segments(tokens, markers, sigs, npages, top, bot) -> list[dict]:
    """每题 -> (segments[(page, y0, y1)], end_page, subparts[dict])。page 为 0 基。"""
    out = []
    for i, token in enumerate(tokens):
        p0 = token["page"]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if nxt is not None and nxt["page"] == p0:
            end = p0
            segs = [(p0, top, max(nxt["y0"] - TOP_GAP, top + 10.0))]
        else:
            if nxt is not None:
                end = nxt["page"] - 1
            else:
                end = p0
                for m in markers:
                    if m["page"] >= p0:
                        end = max(end, m["page"])
                while end + 1 < npages and sigs[end + 1]["indented"] >= DOT_ROWS_MIN:
                    end += 1
            segs = [(p, top, bot) for p in range(p0, end + 1)]
        subs = [{"label": m["label"], "page": m["page"] + 1, "y0": round(m["y0"], 1)}
                for m in markers
                if (m["page"], m["y0"]) >= (p0, token["y0"])
                and (nxt is None or (m["page"], m["y0"]) < (nxt["page"], nxt["y0"]))]
        out.append({"segs": segs, "end": end, "subparts": subs})
    return out


def analyze(doc) -> dict:
    """纯几何分析（不写文件）：span、题号、标记、裁剪框、页面签名、题目分段。"""
    npages = len(doc)
    rotations = sorted({p.rotation for p in doc})
    page_spans = load_spans(doc)
    tokens = find_tokens(page_spans)
    markers, label_of, pairs = find_markers(page_spans)
    sigs = [page_signature(spans) for spans in page_spans]
    out = {"npages": npages, "rotations": rotations, "page_spans": page_spans,
           "tokens": tokens, "markers": markers, "label_of": label_of, "pairs": pairs,
           "sigs": sigs, "box": None, "box_detail": {}, "questions": []}
    if not tokens:
        return out
    left, top, right, bot, detail = crop_box(page_spans, tokens)
    out["box"] = (left, top, right, bot)
    out["box_detail"] = detail
    out["questions"] = question_segments(tokens, markers, sigs, npages, top, bot)
    return out


# ---------------------------------------------------------------- 渲染与图像自检

def render_clip(page, bbox):
    import pymupdf
    return pymupdf.Rect(bbox) * page.rotation_matrix


def render_composite(doc, segs, box, zoom: float, dest: Path):
    """把一道题的各页区间拼成一张图；返回 (px_w, px_h, checks)。"""
    import pymupdf
    left, _top, right, _bot = box
    width = right - left
    height = sum(y1 - y0 for _, y0, y1 in segs)
    nd = pymupdf.open()
    page = nd.new_page(width=round(width, 2), height=round(height, 2))
    yy = 0.0
    for pno, y0, y1 in segs:
        rect = pymupdf.Rect(0, yy, width, yy + (y1 - y0))
        page.show_pdf_page(rect, doc, pno, clip=pymupdf.Rect(left, y0, right, y1))
        yy += y1 - y0
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    pix.save(str(dest))
    checks = image_checks(page, zoom)
    nd.close()
    return pix.width, pix.height, checks


def render_segment(doc, pno, box, zoom: float, dest: Path):
    import pymupdf
    left, top, right, bot = box
    page = doc[pno]
    clip = render_clip(page, (left, top, right, bot))
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip)
    pix.save(str(dest))
    return pix.width, pix.height


def image_checks(page, zoom: float) -> dict:
    """四边无墨 + 整图墨迹占比；在 0.5x 灰度图上做，够灵敏且便宜。"""
    import pymupdf
    gray = page.get_pixmap(matrix=pymupdf.Matrix(zoom * 0.5, zoom * 0.5),
                           colorspace=pymupdf.csGRAY)
    w, h, samples = gray.width, gray.height, gray.samples
    band = max(2, int(round(EDGE_PX * 0.5)))
    edge_dark = 0
    for y in range(h):
        row = samples[y * w:(y + 1) * w]
        if y < band or y >= h - band:
            edge_dark += sum(1 for b in row if b < INK_DARK)
        else:
            for x in list(range(band)) + list(range(w - band, w)):
                if row[x] < INK_DARK:
                    edge_dark += 1
    ink = sum(1 for b in samples if b < INK_DARK) / max(1, w * h)
    return {"edge_dark_px": edge_dark, "ink_frac": round(ink, 5)}


def drawing_warnings(doc, box, npages) -> list[str]:
    """内容图形（图表等矢量）必须完整落在裁剪框内；页边带的印刷标记/灰条不算。"""
    left, top, right, bot = box
    out = []
    for pno in range(npages):
        for d in doc[pno].get_drawings():
            r = d["rect"]
            if (r.x0 < ARTIFACT_X[0] or r.x1 > ARTIFACT_X[1]
                    or r.y0 < ARTIFACT_Y[0] or r.y1 > ARTIFACT_Y[1]):
                continue
            if not (left <= r.x0 and r.x1 <= right and top <= r.y0 and r.y1 <= bot):
                out.append(f"p{pno + 1} 内容图形 ({r.x0:.1f},{r.y0:.1f},{r.x1:.1f},{r.y1:.1f})"
                           f" 超出裁剪框，可能被裁掉")
    return out


# ---------------------------------------------------------------- 文件小工具

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def atomic_write_json(path: Path, payload, *, attempts: int = 60) -> None:
    """Windows 上 os.replace 可能因目标被短暂打开而抛 PermissionError，退避重试。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".part")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        for i in range(attempts):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if i == attempts - 1:
                    raise
                time.sleep(min(0.05 * (i + 1), 0.5))
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def viewer_html(paths: list[str], title: str, width: int = 1200) -> str:
    """查看页：把若干 PNG 按给定宽度依次排列，便于浏览器目视。"""
    imgs = "\n".join(
        f'<figure><figcaption>{p}</figcaption>'
        f'<img src="{p}" style="width:{width}px;display:block"></figure>' for p in paths)
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title>"
            "<style>body{margin:0;background:#fff;font:12px sans-serif}"
            "figure{margin:0 0 8px 0}figcaption{background:#eee;padding:2px 6px}"
            "img{image-rendering:auto}</style></head><body>" + imgs + "</body></html>")


# ---------------------------------------------------------------- 主流程

def build(pdf_path, out_dir, zoom: float = 3.0, viewer: bool = True,
          strict: bool = False, label: str | None = None) -> int:
    import pymupdf
    pdf_path = Path(pdf_path)
    out_dir = Path(out_dir)
    crops_dir = out_dir / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)
    label = label or pdf_path.stem
    warnings: list[str] = []
    checks: list[dict] = []

    def add_check(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            warnings.append(f"自检未过 [{name}]：{detail}")

    if not pdf_path.is_file():
        print(f"[失败] 找不到 PDF：{pdf_path}")
        return 1

    with pymupdf.open(pdf_path) as doc:
        ana = analyze(doc)
        npages = ana["npages"]
        if ana["rotations"] != [0]:
            warnings.append(f"页面旋转 {ana['rotations']}；裁剪按 rotation_matrix 处理，需人工复核")

        tokens = ana["tokens"]
        if not tokens:
            print("[失败] 未找到题号 token；该卷版式可能不适用本工具，需人工检查")
            return 1
        markers = ana["markers"]
        pairs = ana["pairs"]
        left, top, right, bot = ana["box"]
        box_detail = ana["box_detail"]
        if not (left < right and top < bot):
            print(f"[失败] 裁剪框非法：left={left} top={top} right={right} bottom={bot}")
            return 1
        sigs = ana["sigs"]
        questions = ana["questions"]

        # 小题字母连续性（每题的标记应恰好是 a,b,c…）
        bad_subs = []
        for i, q in enumerate(questions):
            labels = [s["label"] for s in q["subparts"]]
            want = [chr(ord("a") + k) for k in range(len(labels))]
            if labels != want:
                bad_subs.append(f"Q{i + 1} 小题 {labels} != {want}")
        add_check("subparts_contiguous", not bad_subs,
                  "；".join(bad_subs) if bad_subs else
                  f"{len(markers)} 个标记，各题字母连续")

        kept_pairs = {k: v for k, v in pairs.items() if v >= MARKER_PAIR_MIN}
        add_check("marker_pair_single", len(kept_pairs) <= 1,
                  f"存活的字形对 {dict(kept_pairs)}" if len(kept_pairs) > 1
                  else f"字形对 {list(kept_pairs)} 唯一，过滤掉 "
                       f"{sum(v for k, v in pairs.items() if v < MARKER_PAIR_MIN)} 个噪声候选")

        # 逐题渲染
        written: list[str] = []
        q_entries = []
        edge_bad, ink_bad = [], []
        for i, q in enumerate(questions):
            num = i + 1
            name = f"q{num:02d}.png"
            segs = q["segs"]
            height = sum(y1 - y0 for _, y0, y1 in segs)
            if height > MAX_PAGE_PT:
                warnings.append(f"Q{num} 合成高度 {height:.0f}pt 超限，只出逐页分图")
                composite = None
            else:
                px_w, px_h, img_checks = render_composite(
                    doc, segs, (left, top, right, bot), zoom, crops_dir / name)
                written.append(name)
                composite = {"image": name, "image_px": [px_w, px_h], **img_checks}
                if img_checks["edge_dark_px"]:
                    edge_bad.append(f"Q{num}×{img_checks['edge_dark_px']}")
                if not (INK_RANGE[0] <= img_checks["ink_frac"] <= INK_RANGE[1]):
                    ink_bad.append(f"Q{num}={img_checks['ink_frac']:.4f}")
            seg_files = []
            if len(segs) > 1:
                for pno, y0, y1 in segs:
                    seg_name = f"q{num:02d}-p{pno + 1:02d}.png"
                    render_segment(doc, pno, (left, y0, right, y1), zoom,
                                   crops_dir / seg_name)
                    written.append(seg_name)
                    seg_files.append(seg_name)
            q_entries.append({
                "number": num,
                "token_raw": tokens[i]["raw"],
                "pages": [segs[0][0] + 1, segs[-1][0] + 1],
                "segments": [{"page": p + 1, "y0": round(y0, 1), "y1": round(y1, 1),
                              "png": f"q{num:02d}-p{p + 1:02d}.png"
                              if len(segs) > 1 else None}
                             for p, y0, y1 in segs],
                "subparts": q["subparts"],
                **({"composite": composite} if composite else {}),
            })
            if composite:
                print(f"  Q{num:<2d} p{segs[0][0] + 1}-{segs[-1][0] + 1}  "
                      f"小题 {len(q['subparts'])}  边墨迹 {img_checks['edge_dark_px']}  "
                      f"墨迹 {img_checks['ink_frac'] * 100:.2f}%  {name} "
                      f"{px_w}x{px_h}")
            else:
                print(f"  Q{num:<2d} p{segs[0][0] + 1}-{segs[-1][0] + 1}  "
                      f"小题 {len(q['subparts'])}  （无合成图）")

        add_check("edges_clean", not edge_bad,
                  "；".join(edge_bad) if edge_bad else f"{len(written)} 张图四边无墨")
        add_check("ink_sane", not ink_bad,
                  "；".join(ink_bad) if ink_bad else
                  f"{len(written)} 张图墨迹占比均在 {INK_RANGE[0]:.2%}–{INK_RANGE[1]:.0%}")

        draw_warns = drawing_warnings(doc, (left, top, right, bot), npages)
        add_check("drawings_within_box", not draw_warns,
                  "；".join(draw_warns) if draw_warns else "内容图形均在裁剪框内")

        # 最后一题之后的页面：附加页（整栏点线）属正常；其它含内容页要人工确认
        last_end = questions[-1]["end"]
        after = []
        for p in range(last_end + 1, npages):
            sig = sigs[p]
            if sig["fullwidth"] >= DOT_ROWS_MIN and sig["indented"] == 0:
                continue
            has_content = any(CONTENT_Y[0] < s[1] < CONTENT_Y[1] and s[0] >= 60
                              for s in ana["page_spans"][p])
            if has_content:
                after.append(p + 1)
        add_check("nothing_after_last", not after,
                  f"最后一题之后仍有含内容页 {after}，未纳入（若为续页需人工确认）"
                  if after else f"最后一题之后仅附加页/空页（共 {npages - last_end - 1} 页）")

        # 清掉旧一轮同名模式（qNN.png / qNN-pNN.png）里本轮没写的文件
        stale = []
        for f in sorted(crops_dir.glob("q*.png")):
            if QUESTION_RE.match(f.name) and f.name not in written:
                f.unlink()
                stale.append(f.name)
        if stale:
            print(f"  清理旧图 {len(stale)} 张：{', '.join(stale[:6])}"
                  + ("…" if len(stale) > 6 else ""))

    manifest = {
        "label": label,
        "source_pdf": str(pdf_path),
        "source_sha256": sha256_file(pdf_path),
        "generated_at": now_iso(),
        "method": "text-layer geometry (no OCR, no ML)",
        "coordinate_space": "unrotated PDF points, top-left origin, page base 1",
        "crop_box": {"left": round(left, 1), "top": round(top, 1),
                     "right": round(right, 1), "bottom": round(bot, 1)},
        "crop_box_detail": box_detail,
        "zoom": zoom,
        "page_count": npages,
        "questions": q_entries,
        "checks": checks,
        "warnings": warnings,
        "stats": {"questions": len(q_entries),
                  "subpart_markers": len(markers),
                  "images": len(written),
                  "checks_failed": sum(1 for c in checks if not c["ok"])},
    }
    atomic_write_json(crops_dir / "manifest.json", manifest)

    viewer_path = None
    if viewer:
        rel = []
        for q in q_entries:
            if q.get("composite"):
                rel.append(os.path.relpath(crops_dir / q["composite"]["image"], out_dir).replace("\\", "/"))
        html = viewer_html(rel, f"{label} 题目切图")
        viewer_path = out_dir / "viewer.html"
        viewer_path.write_text(html, encoding="utf-8")

    print(f"题目切图 {label}")
    print(f"  QP {pdf_path.name} {npages} 页；裁剪框 left={left:.1f} top={top:.1f} "
          f"right={right:.1f} bottom={bot:.1f}（PDF points）")
    print(f"  自检 {sum(1 for c in checks if c['ok'])}/{len(checks)} 通过；"
          f"警告 {len(warnings)}")
    for item in warnings:
        print(f"    ~ {item}")
    print(f"  写出 {crops_dir / 'manifest.json'}（{len(q_entries)} 题 {len(written)} 图）")
    if viewer_path:
        print(f"  查看页 {viewer_path}")
    if strict and warnings:
        return 2
    return 0


def main() -> int:
    _fix_stdout()
    parser = argparse.ArgumentParser(description="纯几何算法按题切图（乱码文字层可用）")
    parser.add_argument("--pdf", required=True, help="QP PDF 路径")
    parser.add_argument("--out", help="输出目录（默认 <本文件目录>/out/<pdf 文件名>/）")
    parser.add_argument("--zoom", type=float, default=3.0, help="渲染缩放（默认 3.0）")
    parser.add_argument("--no-viewer", action="store_true", help="不写查看页 HTML")
    parser.add_argument("--strict", action="store_true", help="自检未过或有警告时返回码 2")
    parser.add_argument("--label", help="manifest 中的卷标签（默认取 PDF 文件名）")
    args = parser.parse_args()
    out_dir = Path(args.out) if args.out else Path(__file__).resolve().parent / "out" / Path(args.pdf).stem
    return build(args.pdf, out_dir, args.zoom, not args.no_viewer, args.strict, args.label)


if __name__ == "__main__":
    raise SystemExit(main())
