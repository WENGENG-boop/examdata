"""题目定位与裁剪（纯 PyMuPDF，无 OCR 依赖）。

思路是"左栏编号 + 层级 + 单调序列"，全部依据实测版式：

- 大题号是左栏的独立 token（Edexcel QP 实测 x0≈43/595），
  子题标记 `(a)`/`(i)` 是**另一个**独立 token（x0≈60），两者在 PDF 里
  从不合成 `12(a)` 一个词——按 `^(\\d+)([a-z])$` 去匹配永远匹配不上。
- 大题号候选按页码/纵坐标排序后做**单调非降**过滤（从 1 开始贪心保留），
  这样答案页重复出现的 `12` 不会截断整题，而 Mark Scheme 表格内部的
  数字（实测落在 x0=88~121）会被同一规则剔除；整行几乎全是数字的统计
  表行（如卡方临界值表的 df 列）同样不是题号，在候选阶段直接剔除。
- 区域终点 = 之后第一个"层级不深于起点、且编号不同"的锚点；
  整题（depth 0）因此会越过重复的 `12` 一直延伸到 `13`，
  子题 `12(a)` 则在 `(b)` 处结束。
- 终点还有一个更准的候选：QP 每题都印的
  `(Total for Question N = X marks)`。它总是落在下一个题号锚点之前，
  取两者靠前的那个——整题因此收在总分行上，子题则取"下一个同级锚点"
  与"父题总分行"中靠前的那个。
- 每页的裁剪框会再收紧到该题**实际内容**的包围盒（word bbox ∪
  drawing bbox）外扩 `_PAD`。图没有文字，所以 drawing 必须计入，
  否则带图题的图会被裁掉。
- 页眉/页脚/水印逐项识别，不再整页按 0.04/0.9 硬切：左右页边的竖排水印
  `DO NOT WRITE IN THIS AREA`、页脚条码 `*P75888A0328*`、`P75888A`、
  页码、`©2024 Pearson Education Ltd.`、`Turn over` 按"窄位置带 + 正则族"
  判定（条码每页都变，所以不做整串匹配）；页顶的 `SECTION A/B/C` 横幅
  还要求同行右侧跟一个单字母区号，免得误伤正文里的
  `TOTAL FOR SECTION A = 6 MARKS`。跨页续页因此从该页真正的第一行内容
  起步，而不是从 0.04 页高起步。

**为什么不用 OCR 兜底**：本机没有 Pillow/pytesseract/tesseract，模块顶层
import 会让整包不可用；而且扫描件本来就无可靠编号。所以扫描版 PDF 明确
抛 `LocationError`，不猜。
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

import pymupdf

from .errors import LocationError


# 版式常量：按真实 Edexcel 试卷（QP 为 A4 595x842，MS 为 Letter 612x792）
# 实测得到，全部写成页面尺寸的比例，换纸张大小不用改。
_MARGIN_X = 0.055    # 左右页边竖排水印所在的窄带
_HEADER_Y = 0.045    # 页眉带（页高比例）
_FOOTER_Y = 0.94     # 页脚带起点（页高比例）
_BANNER_Y = 0.15     # SECTION 横幅只可能落在页顶这一带
_FRAME = 0.85        # 宽、高同时超过页面的这个比例 → 整页外框，不是内容
_PAD = 5.0           # 内容包围盒统一外扩量


def _page_bounds(page: pymupdf.Page) -> pymupdf.Rect:
    """Return the unrotated coordinate space used by text, drawings, and images."""
    return page.rect * page.derotation_matrix


def _render_clip(page: pymupdf.Page, clip: pymupdf.Rect) -> pymupdf.Rect:
    """Transform an analysis-space clip into the page's rotated render space."""
    return pymupdf.Rect(clip) * page.rotation_matrix


_CIPHER_SHIFT = 0x1D


def decode_cipher_text(text: str) -> str:
    """密码字体卷（GID = 真实字符 − 0x1D）的解码；空白码与范围外字符原样保留。"""
    out = []
    for char in text:
        code = ord(char)
        if code in (0x09, 0x0A, 0x0D, 0x20) or code < 0x03 or code > 0x61:
            out.append(char)
        else:
            out.append(chr(code + _CIPHER_SHIFT))
    return "".join(out)


def is_ciphered(pdf: pymupdf.Document) -> bool:
    """前 3 页非空白控制字符 ≥ 200 → 密码字体卷（实测密文卷 700+，正常卷 ≤ 16）。"""
    count = 0
    for index in range(min(3, len(pdf))):
        for char in pdf[index].get_text():
            code = ord(char)
            if code < 0x20 and code not in (0x09, 0x0A, 0x0D):
                count += 1
                if count >= 200:
                    return True
    return False


def _decoded_words(page: pymupdf.Page) -> list:
    """密码字体页的 word 列表：逐字符解码、按解码后空白切词、bbox 取并集。"""
    words = []
    for block in page.get_text("rawdict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            current = None
            for span in line["spans"]:
                for char in span["chars"]:
                    decoded = decode_cipher_text(char["c"])
                    if decoded.isspace():
                        if current is not None:
                            words.append(current)
                            current = None
                        continue
                    box = char["bbox"]
                    if current is None:
                        current = [box[0], box[1], box[2], box[3], decoded]
                    else:
                        current[0] = min(current[0], box[0])
                        current[1] = min(current[1], box[1])
                        current[2] = max(current[2], box[2])
                        current[3] = max(current[3], box[3])
                        current[4] += decoded
            if current is not None:
                words.append(current)
    return [(w[0], w[1], w[2], w[3], w[4], 0, 0, 0) for w in words]


def _page_words(page: pymupdf.Page, ciphered: bool) -> list:
    return _decoded_words(page) if ciphered else page.get_text("words")


def _decode_if(text: str, ciphered: bool) -> str:
    return decode_cipher_text(text) if ciphered else text


_BARCODE = re.compile(r"^\*[A-Z0-9]{6,}\*$")
_PAPER_CODE = re.compile(r"^P\d{5}[A-Z]?$")
_PRINT_CODE = re.compile(r"^F:[\d/]+$")
_PAGE_NUMBER = re.compile(r"^\d{1,3}$")
_TURN_OVER = re.compile(r"^(?:turn|over)$", re.I)
_COPYRIGHT = re.compile(r"©|pearson education", re.I)
_SYMBOL = re.compile(r"^[\uf000-\uf8ff]+$")
_SECTION = re.compile(r"^section$", re.I)
_SECTION_MARK = re.compile(r"^[A-D]$")
_TOTAL_HEAD = "(Total"
_ACKNOWLEDGEMENTS = re.compile(r"acknowledg(e)?ments", re.I)


def _is_furniture(text: str, box: tuple[float, float, float, float], page: pymupdf.Rect) -> bool:
    """页眉/页脚/页边水印一类的版式噪声，不是题目内容。"""
    x0, y0, x1, y1 = box
    if x1 <= page.width * _MARGIN_X or x0 >= page.width * (1 - _MARGIN_X):
        return True  # 左右页边竖排的 "DO NOT WRITE IN THIS AREA"
    if y1 <= page.height * _HEADER_Y or y0 >= page.height * _FOOTER_Y:
        return True  # 页眉带 / 页脚带
    if _SYMBOL.match(text):
        return True  # 装饰用的私有区字形
    if _BARCODE.match(text) or _PAPER_CODE.match(text) or _PRINT_CODE.match(text):
        return True  # 条码（每页都变）/ 试卷代码 / 印刷批次号
    if _TURN_OVER.match(text) or _COPYRIGHT.search(text):
        return True  # "Turn over" / "©2024 Pearson Education Ltd."
    return bool(_PAGE_NUMBER.match(text) and y0 >= page.height * 0.9)


def _is_furniture_drawing(rect: pymupdf.Rect, page: pymupdf.Rect) -> bool:
    if rect.width <= 0.5 or rect.height <= 0.5:
        return True  # 退化的点/线，文本已经覆盖同一位置
    if rect.x1 <= page.width * _MARGIN_X or rect.x0 >= page.width * (1 - _MARGIN_X):
        return True
    if rect.y1 <= page.height * _HEADER_Y or rect.y0 >= page.height * _FOOTER_Y:
        return True
    return rect.width >= page.width * _FRAME and rect.height >= page.height * _FRAME


def _banner_rows(words: list, page: pymupdf.Rect) -> set[float]:
    """页顶 `SECTION A/B/C` 横幅所在行的 y；判定要求右侧跟一个单字母区号，
    这样 "TOTAL FOR SECTION A = 6 MARKS" 这类正文不会被误伤。"""
    rows = set()
    for word in words:
        if not _SECTION.match(word[4]) or word[1] >= page.height * _BANNER_Y:
            continue
        if any(other[0] > word[2] and _SECTION_MARK.match(other[4])
               for other in words if abs(other[1] - word[1]) < 4):
            rows.add(round(word[1], 1))
    return rows


def _content_items(page: pymupdf.Page, top: float, bottom: float, *, ciphered: bool = False) -> list[pymupdf.Rect]:
    """窗口 [top, bottom] 内属于题目内容的矩形：文字、矢量与 raster image bbox。

    文字入选判据是"垂直中心落在窗口内"，不是"与窗口有重叠"——相邻题目的
    行只探进窗口零点几磅就会把包围盒拖到窗口外（子题 `(a)` 的下缘正好
    压在上一个窗口的底边上）。
    """
    bounds = _page_bounds(page)
    words = _page_words(page, ciphered)
    banners = _banner_rows(words, bounds)
    items = []
    for word in words:
        x0, y0, x1, y1, text = word[0], word[1], word[2], word[3], word[4]
        if not top <= (y0 + y1) / 2 <= bottom:
            continue
        if any(abs(y0 - row) < 4 for row in banners):
            continue
        if _is_furniture(text, (x0, y0, x1, y1), bounds):
            continue
        items.append(pymupdf.Rect(x0, y0, x1, y1))
    for drawing in page.get_drawings():
        rect = pymupdf.Rect(drawing["rect"])
        if not top <= (rect.y0 + rect.y1) / 2 <= bottom:
            continue
        if _is_furniture_drawing(rect, bounds):
            continue
        items.append(pymupdf.Rect(rect.x0, max(rect.y0, top), rect.x1, min(rect.y1, bottom)))
    window = pymupdf.Rect(bounds.x0, top, bounds.x1, bottom)
    for image in page.get_image_info():
        rect = pymupdf.Rect(image["bbox"]) & bounds
        if rect.is_empty or rect.is_infinite:
            continue
        if _is_furniture("", tuple(rect), bounds):
            continue
        rect &= window
        if not rect.is_empty:
            items.append(rect)
    return items


def _tighten(page: pymupdf.Page, top: float, bottom: float, *, ciphered: bool = False) -> pymupdf.Rect:
    """把整页宽的窗口收紧到内容包围盒 + padding；认不出内容时退回窗口本身，
    避免把内容极少的页面裁没。"""
    bounds = _page_bounds(page)
    fallback = pymupdf.Rect(30, max(0.0, top), bounds.width - 30, min(bottom, bounds.height))
    items = _content_items(page, top, bottom, ciphered=ciphered)
    if not items:
        return fallback
    box = pymupdf.Rect(
        min(item.x0 for item in items) - _PAD,
        min(item.y0 for item in items) - _PAD,
        max(item.x1 for item in items) + _PAD,
        max(item.y1 for item in items) + _PAD,
    )
    box &= bounds
    if box.is_empty or box.width < 2 or box.height < 2:
        return fallback
    return box


def _total_markers(page: pymupdf.Page, ciphered: bool = False) -> dict[int, float]:
    """本页 `(Total for Question N = X marks)` 的 N -> 该行底部 y。"""
    words = _page_words(page, ciphered)
    markers: dict[int, float] = {}
    for word in words:
        if word[4] != _TOTAL_HEAD:
            continue
        line = [other for other in words if abs(other[3] - word[3]) < 4]
        numbers = sorted((other for other in line if other[0] > word[2] and _PAGE_NUMBER.match(other[4])),
                         key=lambda other: other[0])
        if not numbers:
            continue
        markers[int(numbers[0][4])] = max(other[3] for other in line)
    return markers


def _total_boundary(pdf: pymupdf.Document, number: int, after: tuple[int, float], ciphered: bool = False):
    """该题总分行（含总分行本身）的结束位置；没有就返回 None。"""
    for index in range(after[0], len(pdf)):
        bottom = _total_markers(pdf[index], ciphered).get(number)
        if bottom is None:
            continue
        candidate = (index, bottom + 2)
        if candidate > after:
            return candidate
    return None


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


def _numeric_row(words: list, y: float, tol: float = 2.0, *, candidate: str = "") -> bool:
    """同一行几乎全是数字 → 统计表行，不是题号行。

    带尾点的题号（数学卷 "4." 排版风格）例外：它们常与题目首行数据列表
    同行，整行看起来像统计表行，但确实是题号，不能丢弃。
    """
    if candidate.endswith("."):
        return False
    row = [w[4] for w in words if abs(w[1] - y) <= tol]
    if len(row) < 3:
        return False
    numeric = sum(1 for t in row if re.fullmatch(r"\d+(?:\.\d+)?", t))
    return numeric >= len(row) * 0.8


def _greek_number_after_question_word(previous, word, bounds: pymupdf.Rect) -> bool:
    """希腊语卷：题号是紧跟 "Ερώτηση" 词后的数字（同排、间隙小、位于左半页）。"""
    if previous is None:
        return False
    if word[0] >= bounds.width * .25:
        return False
    if abs(word[1] - previous[1]) >= 4:
        return False
    if not 0 <= word[0] - previous[2] < 25:
        return False
    return unicodedata.normalize("NFC", previous[4]) == unicodedata.normalize("NFC", "Ερώτηση")


def _total_for_paper_bottom(words: list) -> float | None:
    """解码词表里 "TOTAL FOR PAPER" 行的顶部 y；没有返回 None。"""
    for head in (w for w in words if w[4] == "TOTAL"):
        line = sorted((w for w in words if abs(w[1] - head[1]) < 4), key=lambda w: w[0])
        texts = [w[4] for w in line]
        for index in range(len(texts) - 2):
            if texts[index] == "TOTAL" and texts[index + 1] == "FOR" and texts[index + 2] == "PAPER":
                return min(line[index][1], line[index + 1][1], line[index + 2][1])
    return None


def _dot_answer_digit(words: list, word) -> bool:
    """答题空行的编号行（"1 .........."）不是题号：同视觉行右侧紧跟一段点线（文本）。"""
    x, y, x1, y1, text, *_ = word
    for other in words:
        if other is word:
            continue
        wx0, wy0, wx1, wy1, wtext, *_ = other
        if wx0 >= x1 - 2 and wx0 - x1 < 24 and wy0 < y1 and wy1 > y and re.fullmatch(r"[.\ufffd]{4,}", wtext):
            # 点线字符：'.' 正常映射；U+FFFD 是 PDF 字体映射缺失时点线被替换成的字符
            return True
    return False


def _anchors(pdf: pymupdf.Document, role: str, *, ciphered=None):
    if ciphered is None:
        ciphered = is_ciphered(pdf)
    anchors: list[Anchor] = []
    main = 0
    section_at, section_top = None, 0.0
    sub = ""
    end = (len(pdf) - 1, _page_bounds(pdf[-1]).height * .9)
    for index, page in enumerate(pdf):
        if index == 0:
            continue
        bounds = _page_bounds(page)
        words = sorted(_page_words(page, ciphered), key=lambda w: (round(w[1] / 3), w[0]))
        banners = _banner_rows(words, bounds)
        if banners:
            section_at, section_top = index, min(banners)
        stop = False
        previous = None
        for word in words:
            prev = previous
            previous = word
            x, y, _, _, text, *_ = word
            if _ACKNOWLEDGEMENTS.match(text):
                if not anchors:
                    # 合订本（Source Booklet 排在题目之前）的 Acknowledgements
                    # 出现在任何题号之前，不是题目区的结束，继续扫描。
                    continue
                end = (index, max(0, y - 8))
                stop = True
                break
            if not bounds.height * .04 < y < bounds.height * .9:
                continue
            if (x < bounds.width * .125 or _greek_number_after_question_word(prev, word, bounds)) and re.fullmatch(r"[1-9]\d{0,2}\.{0,2}", text.lstrip("*")) and not _numeric_row(words, y, candidate=text.lstrip("*")) and not _dot_answer_digit(words, word):  # 星号前缀（*20）是联题标记；双点题号（"1.."）与希腊卷 "Ερώτηση N" 的紧跟数字都算题号；整行几乎全数值的统计表行不是题号（带尾点题号除外，见 _numeric_row）
                number = int(text.lstrip("*").rstrip("."))
                if section_at is not None and (index == section_at + 1 or (index == section_at and y > section_top)):
                    section_at = None
                    if number == 1 and main >= 2:
                        # 分节横幅后题号重新从 1 开始：横幅前收集的多是来源文章内部编号，清掉重来
                        anchors.clear()
                        main = 0
                        sub = ""
                if number == main + 1 or (main and number == main):
                    main = number
                    sub = ""
                    anchors.append(Anchor(str(main), index, y))
            elif main and x < bounds.width * .20:
                match = re.fullmatch(r"\(([a-z]+)\)", text)
                if not match:
                    continue
                part = match.group(1)
                if len(part) == 1 and (part not in {"i", "v", "x"} or not sub or ord(part) == ord(sub) + 1):
                    sub = part
                    anchors.append(Anchor(f"{main}({part})", index, y))
                elif sub and re.fullmatch(r"[ivx]+", part):
                    anchors.append(Anchor(f"{main}({sub})({part})", index, y))
        totals = page.search_for("TOTAL FOR PAPER") if role == "qp" and not ciphered else []
        if role == "qp" and ciphered:
            bottom = _total_for_paper_bottom(words)
            if bottom is not None:
                end = (index, bottom - 4)
                break
        if totals:
            end = (index, min(rect.y0 for rect in totals) - 4)
            break
        if stop:
            break
    if not anchors or main < 1:
        raise LocationError("No reliable left-column question numbering; scanned/unsupported PDF layout")
    return anchors, end


def locate(pdf: pymupdf.Document, question: str, role: str, *, ciphered=None) -> list[tuple[int, pymupdf.Rect]]:
    if ciphered is None:
        ciphered = is_ciphered(pdf)
    anchors, end = _anchors(pdf, role, ciphered=ciphered)
    if role == "qp":
        summary_pages = set()
        for a in anchors:
            if a.depth != 1:
                continue
            siblings = {b.path for b in anchors if b.page == a.page and b.depth == 1 and b.path.split('(')[0] == a.path.split('(')[0]}
            if len(siblings) >= 3 and any(b.path == a.path and b.page > a.page for b in anchors):
                summary_pages.add(a.page)
        if "(" in question:
            filtered = [a for a in anchors if a.page not in summary_pages]
            if any(a.path == question for a in filtered):
                anchors = filtered
    matches = [a for a in anchors if a.path == question]
    if not matches:
        raise LocationError(f"Question {question} could not be located reliably")
    start = matches[0]
    stop_at = end
    for a in anchors[anchors.index(start) + 1:]:
        if a.path == question or a.path == question.split("(")[0]:
            continue
        if a.depth <= start.depth and not a.path.startswith(question + "("):
            if a.page > start.page and a.y < _page_bounds(pdf[a.page]).height * .25:
                candidate = (a.page - 1, _page_bounds(pdf[a.page - 1]).height * .9)
            else:
                candidate = (a.page, max(0, a.y - 5))
            if candidate <= (start.page, start.y):
                continue
            stop_at = candidate
            break
    # 总分行比"下一个锚点"更准：整题收在它上面，子题取两者靠前的那个
    # （最后一个子题的父题总分行就在它后面，正好当终点）。
    total = _total_boundary(pdf, int(question.split("(")[0]), (start.page, start.y), ciphered)
    if total is not None and total < stop_at:
        stop_at = total
    if stop_at <= (start.page, start.y):
        raise LocationError("Invalid question boundaries")
    clips = []
    for index in range(start.page, stop_at[0] + 1):
        page = pdf[index]
        # 起始页从题号锚点起步（锚点上方是上一题的答题区）；续页从 0 起步，
        # 上边界交给内容包围盒——页顶横幅、页脚条码/页码、页边竖排水印
        # 都在 _content_items 里被剔除，续页因此不会带上页眉带或页脚带。
        top = max(0, start.y - _PAD) if index == start.page else 0
        bottom = stop_at[1] if index == stop_at[0] else _page_bounds(page).height
        if bottom - top > 4:
            clips.append((index, _tighten(page, top, bottom, ciphered=ciphered)))
    if not clips:
        raise LocationError("Question span is empty")
    return clips


def index_questions(data: bytes, role: str) -> list[dict]:
    """Index detected question paths without rendering or inventing missing anchors."""
    if role not in {"qp", "ms"}:
        raise LocationError("Unsupported document role")
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        if not 1 <= len(pdf) <= 400:
            raise LocationError("PDF page limit exceeded")
        ciphered = is_ciphered(pdf)
        anchors, _ = _anchors(pdf, role, ciphered=ciphered)
        paths = list(dict.fromkeys(a.path for a in anchors))
        if len(paths) > 1000:
            raise LocationError("Question index limit exceeded")
        result = []
        for path in paths:
            clips = locate(pdf, path, role, ciphered=ciphered)
            if len(clips) > 25:
                raise LocationError("Question spans too many pages")
            result.append({"question": path, "regions": [
                {"page": page + 1, "bbox": list(rect)} for page, rect in clips
            ]})
        return result


def crop_question(data: bytes, question: str, role: str, *, budget=None) -> list[Crop]:
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        ciphered = is_ciphered(pdf)
        clips = locate(pdf, question, role, ciphered=ciphered)
        text = " ".join(_decode_if(pdf[page].get_text(clip=clip), ciphered) for page, clip in clips)
        if role == "qp" and re.search(r"\b(?:Extract|Figure)\s+[A-Z0-9]", text):
            covers = [i for i, p in enumerate(pdf) if "Source Booklet" in _decode_if(p.get_text(), ciphered)
                      and "Do not return this Booklet" in _decode_if(p.get_text(), ciphered)]
            booklet_start = covers[-1] if covers else len(pdf)
            included = {page for page, _ in clips}
            for index in range(booklet_start + 1, len(pdf)):
                page = pdf[index]
                if index in included:
                    continue
                if ciphered:
                    acknowledgements = [pymupdf.Rect(w[:4]) for w in _decoded_words(page)
                                        if _ACKNOWLEDGEMENTS.match(w[4])]
                else:
                    acknowledgements = page.search_for("Acknowledgements")
                bottom = min(r.y0 for r in acknowledgements) - 5 if acknowledgements else _page_bounds(page).height * .9
                context_clip = _tighten(page, 0, bottom)
                context_text = _decode_if(page.get_text(clip=context_clip), ciphered)
                if context_clip.height > 4 and (not acknowledgements or re.search(r"\b(?:Extract|Figure)\s+[A-Z0-9]", context_text)):
                    clips.append((index, context_clip))
                if acknowledgements:
                    break
        # 上限检查放在 booklet 上下文页追加之后：这些页同样要渲染 PNG，
        # 只限制 locate 的结果挡不住最终列表膨胀。
        if len(clips) > 25:
            raise LocationError("Question span is implausibly large")
        from .budget import RequestBudget
        import math
        budget = budget or RequestBudget()
        crops = []
        for page, clip in clips:
            render_clip = _render_clip(pdf[page], clip)
            pixels = math.ceil(render_clip.width * 1.5) * math.ceil(render_clip.height * 1.5) * 4
            budget.charge(pixels, "raster rendering")
            pixmap = pdf[page].get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), clip=render_clip)
            png = pixmap.tobytes("png")
            budget.charge(len(png), "PNG output")
            crops.append(Crop(page + 1, (clip.x0, clip.y0, clip.x1, clip.y1), png))
            del pixmap
        return crops
