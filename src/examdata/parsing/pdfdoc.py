"""PDF 读取与版式块抽取。

使用 PyMuPDF 获取文本块、图片块与页面几何信息。
解析器版本化：输出中记录 parser_version，派生数据可据此重建。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pymupdf


@dataclass
class TextBlock:
    """一个文本块。"""

    page: int
    bbox: tuple[float, float, float, float]
    text: str
    # 块内第一行的字号与是否粗体，用于题号识别
    first_span_size: float = 0.0
    first_span_bold: bool = False
    block_no: int = 0

    @property
    def y0(self) -> float:
        return self.bbox[1]

    @property
    def x0(self) -> float:
        return self.bbox[0]


@dataclass
class TextLine:
    """一行文本。

    切分以**行**为单位而非文本块：PyMuPDF 常把相邻内容（如答题点线行与下一小问号）
    合并进同一个块，若只检查块首就会漏掉小问号。
    """

    page: int
    bbox: tuple[float, float, float, float]
    text: str
    block_no: int
    line_no: int
    size: float = 0.0
    bold: bool = False

    @property
    def y0(self) -> float:
        return self.bbox[1]

    @property
    def x0(self) -> float:
        return self.bbox[0]


@dataclass
class ImageBlock:
    """页面上的一个视觉资产。

    source="image"：PDF 内嵌位图，data 是原始字节。
    source="vector"：由矢量绘图指令构成的图形（坐标系、几何图、函数图像等）。
    Cambridge 试卷的图形绝大多数是矢量，内嵌位图几乎为零，因此必须两者都抽。
    """

    page: int
    bbox: tuple[float, float, float, float]
    width: int
    height: int
    ext: str
    data: bytes
    block_no: int = 0
    source: str = "image"
    item_count: int = 0


@dataclass
class PageInfo:
    number: int
    width: float
    height: float
    text: str
    text_coverage: float
    blocks: list[TextBlock] = field(default_factory=list)
    lines: list[TextLine] = field(default_factory=list)
    images: list[ImageBlock] = field(default_factory=list)


@dataclass
class PdfDocument:
    path: Path
    page_count: int
    pages: list[PageInfo] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def chars_per_page(self) -> float:
        """平均每页字符数 —— 判断是否为扫描件的主指标。"""
        if not self.pages:
            return 0.0
        return sum(len(p.text) for p in self.pages) / len(self.pages)

    @property
    def is_text_native(self) -> bool:
        """是否文本型 PDF（非扫描件）。

        按每页字符数判断：扫描件即使有 OCR 层，字符数也远低于文本型试卷。
        """
        return self.chars_per_page >= 200.0

    @property
    def text_coverage(self) -> float:
        if not self.pages:
            return 0.0
        return sum(p.text_coverage for p in self.pages) / len(self.pages)


# --- 矢量图形抽取参数 ---------------------------------------------------
# Cambridge 试卷的"图"由大量绘图指令拼成：坐标轴、网格线、曲线、标注框。
# 需要先把碎指令聚合成"一个图"，再按尺寸筛掉表格线、下划线、装饰框。
VECTOR_CLUSTER_GAP = 8.0        # pt：相距小于此值的绘图指令视为同一图形
VECTOR_MIN_WIDTH = 30.0         # pt：图形最小宽
VECTOR_MIN_HEIGHT = 20.0        # pt：图形最小高
VECTOR_MIN_AREA = 1500.0        # pt²：图形最小面积
VECTOR_PAGE_RULE_RATIO = 0.6    # 长度超过页面尺寸此比例的直线判定为表格/分栏线
VECTOR_MAX_PAGE_AREA_RATIO = 0.8  # 占页面面积超过此比例的多半是背景框，不是图形
VECTOR_RENDER_ZOOM = 2.0        # 渲染倍率，保证图内文字可读


def _rect_near(a: list[float], b: list[float], gap: float) -> bool:
    """两个矩形是否相交或间距小于 gap。"""
    return not (
        a[2] + gap < b[0] or b[2] + gap < a[0] or a[3] + gap < b[1] or b[3] + gap < a[1]
    )


def _rect_union(a: list[float], b: list[float]) -> list[float]:
    return [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]


def _cluster_rects(rects: list[list[float]], gap: float) -> list[list[float]]:
    """把彼此邻近的矩形聚成若干簇（贪心合并直到稳定）。

    一条曲线会被 PDF 拆成几十段，坐标轴又是另外几段；只有先聚类，
    才能得到"一个图"的整体包围盒。
    """
    boxes = [list(r) for r in rects]
    changed = True
    while changed:
        changed = False
        out: list[list[float]] = []
        while boxes:
            cur = boxes.pop()
            i = 0
            while i < len(boxes):
                if _rect_near(cur, boxes[i], gap):
                    cur = _rect_union(cur, boxes[i])
                    boxes.pop(i)
                    changed = True
                else:
                    i += 1
            out.append(cur)
        boxes = out
    return boxes


def _vector_figures(page, pno: int) -> list[ImageBlock]:
    """把页面的矢量绘图指令聚合成图形，并渲染成 PNG。

    返回的每个 ImageBlock 都是一块可以脱离 PDF 独立使用的图片。
    """
    try:
        drawings = page.get_drawings()
    except Exception:
        return []
    if not drawings:
        return []

    pw, ph = float(page.rect.width), float(page.rect.height)
    page_area = max(pw * ph, 1.0)

    rects: list[list[float]] = []
    for d in drawings:
        r = d.get("rect")
        if r is None:
            continue
        x0, y0, x1, y1 = float(r.x0), float(r.y0), float(r.x1), float(r.y1)
        w, h = x1 - x0, y1 - y0
        # 表格线/分栏线：退化成一条贯穿页面的大直线
        if w <= 0.01 and h > ph * VECTOR_PAGE_RULE_RATIO:
            continue
        if h <= 0.01 and w > pw * VECTOR_PAGE_RULE_RATIO:
            continue
        rects.append([x0, y0, x1, y1])

    if not rects:
        return []

    figures: list[ImageBlock] = []
    for box in _cluster_rects(rects, VECTOR_CLUSTER_GAP):
        x0, y0, x1, y1 = box
        w, h = x1 - x0, y1 - y0
        if w < VECTOR_MIN_WIDTH or h < VECTOR_MIN_HEIGHT:
            continue
        if w * h < VECTOR_MIN_AREA:
            continue
        if w * h > page_area * VECTOR_MAX_PAGE_AREA_RATIO:
            continue

        # 稍微外扩，避免裁掉坐标轴刻度和紧贴图形的标注
        pad = 4.0
        clip = pymupdf.Rect(
            max(x0 - pad, 0.0), max(y0 - pad, 0.0),
            min(x1 + pad, pw), min(y1 + pad, ph),
        )
        try:
            pix = page.get_pixmap(
                clip=clip, matrix=pymupdf.Matrix(VECTOR_RENDER_ZOOM, VECTOR_RENDER_ZOOM)
            )
            data = pix.tobytes("png")
        except Exception:
            continue
        if not data:
            continue

        figures.append(
            ImageBlock(
                page=pno + 1,
                bbox=(clip.x0, clip.y0, clip.x1, clip.y1),
                width=pix.width,
                height=pix.height,
                ext="png",
                data=data,
                block_no=len(figures),
                source="vector",
                item_count=len(rects),
            )
        )
    return figures


def _span_info(block: dict) -> tuple[float, bool]:
    """取块内第一个 span 的字号与粗体标记。"""
    try:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                size = float(span.get("size", 0.0))
                flags = int(span.get("flags", 0))
                bold = bool(flags & 2**4)  # PyMuPDF flag bit 4 = bold
                font = str(span.get("font", "")).lower()
                if "bold" in font or "black" in font:
                    bold = True
                return size, bold
    except Exception:
        pass
    return 0.0, False


def load_pdf(path: Path | str, *, max_pages: Optional[int] = None) -> PdfDocument:
    """读取 PDF 并抽取版式块。"""
    path = Path(path)
    doc = pymupdf.open(path)
    pages: list[PageInfo] = []

    try:
        limit = doc.page_count if max_pages is None else min(max_pages, doc.page_count)
        for pno in range(limit):
            page = doc[pno]
            rect = page.rect
            text = page.get_text("text") or ""
            area = max(rect.width * rect.height, 1.0)

            text_blocks: list[TextBlock] = []
            text_lines: list[TextLine] = []
            raw = page.get_text("dict")
            for bno, block in enumerate(raw.get("blocks", [])):
                if block.get("type") != 0:  # 0 = 文本块
                    continue
                btext = "\n".join(
                    "".join(span.get("text", "") for span in line.get("spans", []))
                    for line in block.get("lines", [])
                ).strip()
                if not btext:
                    continue
                size, bold = _span_info(block)
                text_blocks.append(
                    TextBlock(
                        page=pno + 1,
                        bbox=tuple(block.get("bbox", (0, 0, 0, 0))),  # type: ignore[arg-type]
                        text=btext,
                        first_span_size=size,
                        first_span_bold=bold,
                        block_no=bno,
                    )
                )

                # 逐行展开，保留行级几何信息用于精确的题号识别
                for lno, line in enumerate(block.get("lines", [])):
                    ltext = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
                    if not ltext:
                        continue
                    lsize = 0.0
                    lbold = False
                    for span in line.get("spans", []):
                        lsize = max(lsize, float(span.get("size", 0.0)))
                        if int(span.get("flags", 0)) & 2**4:
                            lbold = True
                        if "bold" in str(span.get("font", "")).lower():
                            lbold = True
                    text_lines.append(
                        TextLine(
                            page=pno + 1,
                            bbox=tuple(line.get("bbox", block.get("bbox", (0, 0, 0, 0)))),  # type: ignore[arg-type]
                            text=ltext,
                            block_no=bno,
                            line_no=lno,
                            size=lsize,
                            bold=lbold,
                        )
                    )

            # 位图：用 PyMuPDF 自己的解码器（无 Pillow 依赖），
            # 尺寸直接用块 bbox，避免为了读宽高引入图像库。
            images: list[ImageBlock] = []
            for bno, block in enumerate(raw.get("blocks", [])):
                if block.get("type") != 1:  # 1 = 图片块
                    continue
                try:
                    img = block.get("image")
                    if not img:
                        continue
                    ext = str(block.get("ext") or "png").lower()
                    if ext == "jpeg":
                        ext = "jpg"
                    x0, y0, x1, y1 = block.get("bbox", (0, 0, 0, 0))
                    images.append(
                        ImageBlock(
                            page=pno + 1,
                            bbox=(float(x0), float(y0), float(x1), float(y1)),
                            width=int(round(float(x1) - float(x0))),
                            height=int(round(float(y1) - float(y0))),
                            ext=ext,
                            data=img,
                            block_no=bno,
                            source="image",
                        )
                    )
                except Exception:
                    continue

            # 矢量图形：Cambridge 试卷的主力，必须与位图一起抽取
            images.extend(_vector_figures(page, pno))

            coverage = min(1.0, len(text) / area)
            pages.append(
                PageInfo(
                    number=pno + 1,
                    width=rect.width,
                    height=rect.height,
                    text=text,
                    text_coverage=coverage,
                    blocks=text_blocks,
                    lines=text_lines,
                    images=images,
                )
            )
    finally:
        doc.close()

    return PdfDocument(path=path, page_count=len(pages), pages=pages)
