"""题目定位与裁剪（纯 PyMuPDF，无 OCR 依赖）。

思路是"左栏编号 + 层级 + 单调序列"，全部依据实测版式：

- 大题号是左栏的独立 token（Edexcel QP 实测 x0≈43/595），
  子题标记 `(a)`/`(i)` 是**另一个**独立 token（x0≈60），两者在 PDF 里
  从不合成 `12(a)` 一个词——按 `^(\\d+)([a-z])$` 去匹配永远匹配不上。
- 大题号候选按页码/纵坐标排序后做**单调非降**过滤（从 1 开始贪心保留），
  这样答案页重复出现的 `12` 不会截断整题，而 Mark Scheme 表格内部的
  数字（实测落在 x0=88~121）会被同一规则剔除。
- 区域终点 = 之后第一个"层级不深于起点、且编号不同"的锚点；
  整题（depth 0）因此会越过重复的 `12` 一直延伸到 `13`，
  子题 `12(a)` 则在 `(b)` 处结束。

**为什么不用 OCR 兜底**：本机没有 Pillow/pytesseract/tesseract，模块顶层
import 会让整包不可用；而且扫描件本来就无可靠编号。所以扫描版 PDF 明确
抛 `LocationError`，不猜。
"""

from __future__ import annotations

from dataclasses import dataclass
import re

import pymupdf

from examdata.paperqa.errors import LocationError


@dataclass(frozen=True)
class Anchor:
    path: str
    page: int
    y: float

    @property
    def depth(self):
        return self.path.count("(")


@dataclass(frozen=True)
class Crop:
    """一页的裁剪结果。

    `page` 从 1 开始（给人看的页码），`bbox` 是 PDF 用户空间坐标
    (x0, y0, x1, y1)，`png` 是渲染后的字节。解包为 `(page, png)`
    以兼容早期只关心页码与图片的调用方。
    """

    page: int
    bbox: tuple[float, float, float, float]
    png: bytes

    def __iter__(self):
        return iter((self.page, self.png))


def locate(pdf: pymupdf.Document, question: str, role: str) -> list[tuple[int, pymupdf.Rect]]:
    anchors: list[Anchor] = []
    main = 0
    sub = ""
    end = (len(pdf) - 1, pdf[-1].rect.height * .9)
    for index, page in enumerate(pdf):
        if index == 0:
            continue
        words = sorted(page.get_text("words"), key=lambda w: (round(w[1] / 3), w[0]))
        stop = False
        for word in words:
            x, y, _, _, text, *_ = word
            if re.match(r"acknowledg(e)?ments", text, re.I):
                end = (index, max(0, y - 8))
                stop = True
                break
            if not page.rect.height * .04 < y < page.rect.height * .9:
                continue
            if x < page.rect.width * .125 and re.fullmatch(r"[1-9]\d{0,2}", text):
                number = int(text)
                if number == main + 1 or (main and number == main):
                    main = number
                    sub = ""
                    anchors.append(Anchor(str(main), index, y))
            elif main and x < page.rect.width * .20:
                match = re.fullmatch(r"\(([a-z]+)\)", text)
                if not match:
                    continue
                part = match.group(1)
                if len(part) == 1 and (part not in {"i", "v", "x"} or not sub or ord(part) == ord(sub) + 1):
                    sub = part
                    anchors.append(Anchor(f"{main}({part})", index, y))
                elif sub and re.fullmatch(r"[ivx]+", part):
                    anchors.append(Anchor(f"{main}({sub})({part})", index, y))
        totals = page.search_for("TOTAL FOR PAPER") if role == "qp" else []
        if totals:
            end = (index, min(rect.y0 for rect in totals) - 4)
            break
        if stop:
            break
    if not anchors or main < 1:
        raise LocationError("No reliable left-column question numbering; scanned/unsupported PDF layout")
    if role == "qp":
        summary_pages = set()
        for a in anchors:
            if a.depth != 1:
                continue
            siblings = {b.path for b in anchors if b.page == a.page and b.depth == 1 and b.path.split('(')[0] == a.path.split('(')[0]}
            if len(siblings) >= 3 and any(b.path == a.path and b.page > a.page for b in anchors):
                summary_pages.add(a.page)
        if "(" in question:
            anchors = [a for a in anchors if a.page not in summary_pages]
    matches = [a for a in anchors if a.path == question]
    if not matches:
        raise LocationError(f"Question {question} could not be located reliably")
    start = matches[0]
    stop_at = end
    for a in anchors[anchors.index(start) + 1:]:
        if a.path == question or a.path == question.split("(")[0]:
            continue
        if a.depth <= start.depth and not a.path.startswith(question + "("):
            if a.page > start.page and a.y < pdf[a.page].rect.height * .25:
                stop_at = (a.page - 1, pdf[a.page - 1].rect.height * .9)
            else:
                stop_at = (a.page, max(0, a.y - 5))
            break
    if stop_at <= (start.page, start.y):
        raise LocationError("Invalid question boundaries")
    clips = []
    for index in range(start.page, stop_at[0] + 1):
        page = pdf[index]
        top = max(0, start.y - 5) if index == start.page else page.rect.height * .04
        bottom = stop_at[1] if index == stop_at[0] else page.rect.height * .9
        if bottom - top > 4:
            clips.append((index, pymupdf.Rect(30, top, page.rect.width - 30, bottom)))
    if not clips or len(clips) > 25:
        raise LocationError("Question span is empty or implausibly large")
    return clips


def crop_question(data: bytes, question: str, role: str) -> list[Crop]:
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        clips = locate(pdf, question, role)
        text = " ".join(pdf[page].get_text(clip=clip) for page, clip in clips)
        if role == "qp" and re.search(r"\b(?:Extract|Figure)\s+[A-Z0-9]", text):
            covers = [i for i, p in enumerate(pdf) if "Source Booklet" in p.get_text()
                      and "Do not return this Booklet" in p.get_text()]
            booklet_start = covers[-1] if covers else len(pdf)
            included = {page for page, _ in clips}
            for index in range(booklet_start + 1, len(pdf)):
                page = pdf[index]
                if index in included:
                    continue
                acknowledgements = page.search_for("Acknowledgements")
                bottom = min(r.y0 for r in acknowledgements) - 5 if acknowledgements else page.rect.height * .9
                context_clip = pymupdf.Rect(30, page.rect.height * .04, page.rect.width - 30, bottom)
                context_text = page.get_text(clip=context_clip)
                if bottom > page.rect.height * .1 and (not acknowledgements or re.search(r"\b(?:Extract|Figure)\s+[A-Z0-9]", context_text)):
                    clips.append((index, context_clip))
                if acknowledgements:
                    break
        return [Crop(page + 1, (clip.x0, clip.y0, clip.x1, clip.y1),
                     pdf[page].get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), clip=clip).tobytes("png"))
                for page, clip in clips]
