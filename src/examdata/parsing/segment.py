"""题目切分：把试卷 PDF 转成题目树。

核心约束（需求文档）：
- 严禁按 PDF 页切题。题目持续到出现同级或更高级的下一个题号为止。
- 跨页题目必须正确合并，并记录 page_from / page_to。
- 题目层级（大题 -> 小问 -> 子小问）必须正确恢复。
- 非文本内容（图片/图表）必须随题目保留，且不因拆分丢失。

切分策略（三层过滤，缺一不可）：
1. **前置页剔除**：封面/指令页含固定标记，不参与题号识别。
2. **数字占比过滤**：坐标轴标签、答题格、条形码等数字密集块不是题目。
3. **单调性约束**：试卷大题号必然形如 1..N 递增。用最长递增子序列(LIS)筛选候选，
   这是压制"图表刻度被误判为题号"最有力的信号。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from .numbering import (
    NumberMatch,
    extract_marks,
    is_ambiguous_sub_label,
    is_noise,
    match_numbers,
    roman_to_int,
)
from .pdfdoc import ImageBlock, PdfDocument, TextBlock, TextLine

# 封面/指令页标记。Cambridge 试卷首页固定出现这些措辞。
_FRONT_MATTER_MARKERS = [
    "you must answer on the question paper",
    "read these instructions",
    "you will need:",
    "time allowed",
    "answer all questions",
    "this document has",
    "do not use an erasable pen",
    "information",
    "advice",
]
_FRONT_MATTER_MIN_HITS = 2

# 题目正文至少要有一个 3 个字母以上的单词，否则视为噪声块
_HAS_WORD = re.compile(r"[A-Za-z]{3,}")
_DIGIT = re.compile(r"\d")
_ALPHA = re.compile(r"[A-Za-z]")

MAX_TOP_NUMBER = 60

# 页眉页脚边距：占页高比例。题号不会出现在这些区域。
MARGIN_FRACTION = 0.06

# 顶层题号的最小字号比例（相对正文基线）。
# 图表内的刻度、单位标注比正文小得多，低于此比例的行不可能是题号。
NUMBER_SIZE_RATIO = 0.95

# 左边距锚定容差（磅）。顶层题号独占页面最左侧一列，题干与小问都向右缩进，
# 因此"是否落在最左列"是比字号、粗体都更稳定的几何约束。
# 实测 9709 整卷只有 36 行粗体（低于粗体信号启用阈值），粗体会失效；
# 但题号在最左列这一点在所有考试局、所有题型上都成立。
LEFT_COLUMN_TOLERANCE = 6.0

# 左边距取值的分位点。个别文档会在更靠左的位置出现装饰性文字
# （如 specimen 01 第 10 页的图表轴标签 "Time to complete the swimming race"，
# x=39.7 而正文最左列是 49.6；0478 的 "Limit" 表头 x=37.4 而题号在 49.6），
# 直接取最小值会被这类离群点带偏。取 3% 分位即可稳定命中真正的题号列，
# 实测 0580 / 9709 / 0620 / 0478 共 16 份试卷全部命中。
LEFT_COLUMN_PERCENTILE = 0.03


# 图片扩展名 -> MIME。落库时 Asset.mime 需要真实类型，而不是留空。
_EXT_MIME = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "webp": "image/webp",
    "jp2": "image/jp2",
    "jpx": "image/jpx",
}


def _mime_for_ext(ext: str) -> str:
    """由扩展名推导 MIME；未知类型退化为二进制流。"""
    return _EXT_MIME.get((ext or "").lower().lstrip("."), "application/octet-stream")


@dataclass
class AssetRef:
    """题目关联的资产。"""

    page: int
    bbox: tuple[float, float, float, float]
    width: int
    height: int
    ext: str
    data: bytes
    role: str = "figure"
    reading_order: int = 0
    # figure / table / diagram / graph / chem / photo
    kind: str = "figure"
    mime: str = ""


@dataclass
class QuestionNode:
    """题目树节点。"""

    label: str
    number_path: str
    depth: int
    kind: str
    order: int
    marks: Optional[int] = None
    page_from: Optional[int] = None
    page_to: Optional[int] = None
    text_parts: list[str] = field(default_factory=list)
    assets: list[AssetRef] = field(default_factory=list)
    children: list["QuestionNode"] = field(default_factory=list)
    confidence: float = 0.0
    bbox_from: Optional[dict[str, Any]] = None
    bbox_to: Optional[dict[str, Any]] = None
    # 父节点反向引用。repr/compare 必须排除，否则父子互指会让 repr 无限递归。
    parent: Optional["QuestionNode"] = field(default=None, repr=False, compare=False)

    @property
    def text(self) -> str:
        return "\n".join(self.text_parts).strip()

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    def to_dict(self, *, with_text: bool = True) -> dict[str, Any]:
        d: dict[str, Any] = {
            "label": self.label,
            "number_path": self.number_path,
            "depth": self.depth,
            "kind": self.kind,
            "order": self.order,
            "marks": self.marks,
            "page_from": self.page_from,
            "page_to": self.page_to,
            "asset_count": len(self.assets),
            "confidence": self.confidence,
        }
        if with_text:
            d["text"] = self.text
        if self.children:
            d["children"] = [c.to_dict(with_text=with_text) for c in self.children]
        return d


@dataclass
class QuestionTree:
    """一份试卷的题目树与切分统计。"""

    roots: list[QuestionNode] = field(default_factory=list)
    page_count: int = 0
    total_marks: Optional[int] = None
    front_matter_pages: list[int] = field(default_factory=list)
    # 前置页（封面/说明页）上的资产：校徽、版权标识等文档级图形，
    # 不属于任何题目，单独留存以备溯源。
    front_assets: list[AssetRef] = field(default_factory=list)
    top_number_sequence: list[int] = field(default_factory=list)
    bold_signal_available: bool = False
    rejected_number_candidates: int = 0
    findings: list[dict[str, Any]] = field(default_factory=list)

    def walk(self):
        for root in self.roots:
            yield from root.walk()

    def flat(self) -> list[QuestionNode]:
        return list(self.walk())

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_count": self.page_count,
            "total_marks": self.total_marks,
            "question_count": len(self.roots),
            "node_count": len(self.flat()),
            "front_matter_pages": self.front_matter_pages,
            "front_asset_count": len(self.front_assets),
            "top_number_sequence": self.top_number_sequence,
            "bold_signal_available": self.bold_signal_available,
            "rejected_number_candidates": self.rejected_number_candidates,
            "findings": self.findings,
            "questions": [r.to_dict() for r in self.roots],
        }


# --------------------------------------------------------------------------
# 过滤辅助
# --------------------------------------------------------------------------


def detect_front_matter(doc: PdfDocument) -> set[int]:
    """识别封面/指令页。这些页不参与题号识别。"""
    pages: set[int] = set()
    for page in doc.pages:
        low = page.text.lower()
        hits = sum(1 for marker in _FRONT_MATTER_MARKERS if marker in low)
        if hits >= _FRONT_MATTER_MIN_HITS:
            pages.add(page.number)
    return pages


def _digit_ratio(text: str) -> float:
    stripped = re.sub(r"\s", "", text)
    if not stripped:
        return 1.0
    return len(_DIGIT.findall(stripped)) / len(stripped)


def _looks_like_stem(text: str) -> bool:
    """题目块至少要有实义单词，或本身是极短的纯题号行。"""
    if _HAS_WORD.search(text):
        return True
    # 允许 "2" 或 "2 (a)" 这类独立题号行
    return len(text.strip()) <= 8


def _unit_sort_key(line: TextLine) -> tuple[int, int, int]:
    """阅读顺序：页 -> 块序 -> 行序。

    保留 PyMuPDF 的块顺序（对分栏比纯坐标排序更稳），块内按行序。
    """
    return (line.page, line.block_no, line.line_no)


def _path_for(parent_path: str, label: str) -> str:
    if not parent_path:
        return label
    if label.startswith("("):
        return f"{parent_path}{label}"
    return f"{parent_path} {label}"


def _candidate_score(line: TextLine) -> int:
    """候选优先级：含实义单词的行更可能是真正的题目开头。

    纯数字行（如坐标轴刻度 14、16）在同等条件下排后。
    """
    return 1 if _HAS_WORD.search(line.text) else 0


def select_consecutive_questions(
    candidates: list[tuple[int, int]],
    units: list[TextLine],
) -> dict[int, int]:
    """从候选中选出真实的 1..N 连续题号序列。

    试卷大题号必然是 1..N 连续递增的，这是压制图表刻度误判最有力的约束。
    返回 {block_index: question_number}。

    对每个题号，若有多个候选块，优先取含实义单词的块（真题目开头），
    其次取最早出现的块。
    """
    if not candidates:
        return {}

    by_value: dict[int, list[int]] = {}
    for idx, value in candidates:
        by_value.setdefault(value, []).append(idx)

    for value, idxs in by_value.items():
        idxs.sort(key=lambda i: (-_candidate_score(units[i]), i))

    best: dict[int, int] = {}
    for start_value, start_idxs in sorted(by_value.items()):
        # 只在 1 或 2 起头（部分试卷首页题号被切掉）
        if start_value > 2:
            continue
        for start_idx in start_idxs[:3]:
            chain: dict[int, int] = {start_idx: start_value}
            last_idx = start_idx
            value = start_value
            while True:
                nxt = value + 1
                chosen = None
                for cand_idx in by_value.get(nxt, []):
                    if cand_idx > last_idx:
                        chosen = cand_idx
                        break
                if chosen is None:
                    break
                chain[chosen] = nxt
                last_idx = chosen
                value = nxt
            if len(chain) > len(best):
                best = chain
    return best


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------


def build_question_tree(
    doc: PdfDocument,
    *,
    expected_total_marks: Optional[int] = None,
    max_depth: int = 3,
) -> QuestionTree:
    """把 PDF 文本块切分为题目树。"""
    tree = QuestionTree(page_count=doc.page_count)
    front_matter = detect_front_matter(doc)
    tree.front_matter_pages = sorted(front_matter)

    # 以行作为切分单位：块级检测会漏掉与答题点线行合并在一起的小问号。
    # 同时剔除页眉页脚区域，避免页码被当成题号。
    units: list[TextLine] = []
    for page in doc.pages:
        if page.number in front_matter:
            continue
        top_limit = page.height * MARGIN_FRACTION
        bottom_limit = page.height * (1.0 - MARGIN_FRACTION)
        for line in page.lines:
            if line.bbox[1] < top_limit or line.bbox[3] > bottom_limit:
                continue
            units.append(line)
    units.sort(key=_unit_sort_key)

    # 粗体可用性：试卷题号通常是粗体（实测 Cambridge 全部如此）。
    # 若整份文档几乎没有粗体，则不启用该信号，退回连续性约束。
    bold_lines = sum(1 for u in units if u.bold)
    bold_available = bold_lines >= max(5, len(units) // 20)

    # 字号基线：题号用正文字号，图表刻度/标注通常明显更小。
    # 用"最短的 20% 行"的中位字号作基线，避免把图内小字当成题号。
    sizes = sorted(u.size for u in units if u.size > 0)
    if sizes:
        low_band = sizes[: max(1, len(sizes) // 5)]
        body_size = low_band[len(low_band) // 2]
    else:
        body_size = 0.0
    min_number_size = body_size * NUMBER_SIZE_RATIO if body_size else 0.0

    # 左边距锚定：顶层题号独占页面最左侧一列，题干与小问都向右缩进。
    # 坐标轴刻度、公式片段、答题格、分值标注都不会落在最左列。
    left_xs = sorted(u.bbox[0] for u in units)
    if left_xs:
        anchor_idx = max(0, int(len(left_xs) * LEFT_COLUMN_PERCENTILE) - 1)
        left_edge = left_xs[anchor_idx]
    else:
        left_edge = 0.0
    max_left_x = left_edge + LEFT_COLUMN_TOLERANCE

    # --- 第 1 遍：收集顶层题号候选 ---
    # 注意：独立成行的题号（如 "1"）数字占比为 1.0，不能因此被丢弃，
    # 否则会整题丢失。因此数字占比过滤只作用于较长的块（>6 字符）。
    candidates: list[tuple[int, int]] = []  # (unit_idx, value)
    for idx, block in enumerate(units):
        text = block.text.strip()
        if is_noise(text):
            continue
        if block.bbox[0] > max_left_x:
            # 不在一列上的数字都不是题号
            continue
        if bold_available and not block.bold:
            # 非粗体的数字行几乎都是坐标轴刻度、公式片段或答题格
            continue
        # 图表内的坐标轴刻度（如 "9 cm"、"14"）字号明显小于正文，
        # 是压不住的误判源；用字号下限先筛掉。
        if min_number_size and block.size and block.size < min_number_size:
            continue
        chain = match_numbers(text)
        if not chain or chain[0].depth != 0:
            continue
        # 数字占比过滤只对较长的块生效：独立题号行（如 "12"）占比为 1.0 也必须保留。
        # 注意这里**不能**再要求"含实义单词"：题号行后可能直接跟公式
        # （如 "18  f(x) = 3 – 2x  g(x) = 2x + 3"），那仍然是合法题号。
        if len(text) > 6 and _digit_ratio(text) > 0.5 and not _HAS_WORD.search(text):
            continue
        try:
            value = int(chain[0].label)
        except ValueError:
            continue
        if not (1 <= value <= MAX_TOP_NUMBER):
            continue
        candidates.append((idx, value))

    # --- 第 2 遍：连续性约束（1..N 递增）---
    selected = select_consecutive_questions(candidates, units)
    kept_block_idx = set(selected)
    tree.rejected_number_candidates = len(candidates) - len(kept_block_idx)
    tree.top_number_sequence = [selected[i] for i in sorted(selected)]
    tree.bold_signal_available = bold_available

    # --- 第 3 遍：按保留的候选构建题目树 ---
    stack: list[QuestionNode] = []
    order = 0
    page_assigned: set[int] = set()
    last_node: Optional[QuestionNode] = None

    for idx, block in enumerate(units):
        text = block.text.strip()
        if is_noise(text):
            continue

        is_top = idx in kept_block_idx
        chain: list[NumberMatch] = []
        if is_top:
            chain = match_numbers(text)
        else:
            # 未被顶层题号占用时，才尝试识别小问；且必须已有打开的题目
            sub_chain = match_numbers(text)
            if (
                sub_chain
                and sub_chain[0].depth > 0
                and stack
                and _looks_like_stem(text)
                and (not bold_available or block.bold)
            ):
                chain = sub_chain

        if not chain:
            if last_node is not None:
                last_node.text_parts.append(text)
                last_node.page_to = block.page
                last_node.bbox_to = {"page": block.page, "bbox": list(block.bbox)}
                # 分值常单独占一行（"\n[2]"），与题号不在同一个文本块里。
                # 这类行没有题号，必须在这里把分值补挂到当前题目上，
                # 否则整份卷子的分值合计会系统性偏低。
                if last_node.marks is None:
                    tail_marks, _ = extract_marks(text)
                    if tail_marks is not None:
                        last_node.marks = tail_marks
            continue

        # 分值可能出现在本块任何位置，先整体抽取，赋给链中最后一个节点
        block_marks, _frag = extract_marks(text)

        for pos, match in enumerate(chain):
            depth = min(match.depth, max_depth)
            label = match.label
            kind = match.kind

            # (i)/(v)/(x) 既是字母表的第 9/22/24 个字母，也是罗马数字 1/5/10。
            # Cambridge 数学卷的小问只到 (a)..(d) 左右，子小问才用罗马数字，
            # 因此默认按罗马数字（depth 2）解析；只有当前一个同级标签正好是
            # 紧邻的前一个字母 (h)/(u)/(w) 时，才判定为字母小问。
            if is_ambiguous_sub_label(label):
                prev = _last_sibling_label(stack, depth)
                if prev is not None and _is_preceding_letter(prev, label):
                    kind = "sub"
                    depth = min(1, max_depth)
                else:
                    kind = "part"
                    depth = min(2, max_depth)

            while stack and stack[-1].depth >= depth:
                closed = stack.pop()
                if closed.page_to is None:
                    closed.page_to = block.page
            parent = stack[-1] if stack else None

            order += 1
            node = QuestionNode(
                label=label,
                number_path=_path_for(parent.number_path if parent else "", label),
                depth=depth,
                kind=kind,
                order=order,
                page_from=block.page,
                page_to=block.page,
                confidence=match.confidence,
                bbox_from={"page": block.page, "bbox": list(block.bbox)},
            )
            if match.rest:
                node.text_parts.append(match.rest)

            if parent is not None:
                node.parent = parent
                parent.children.append(node)
            else:
                tree.roots.append(node)

            stack.append(node)
            last_node = node

            # 分值归属链中最后一个节点（小问优先）
            if pos == len(chain) - 1 and block_marks is not None:
                node.marks = block_marks

        page_assigned.add(block.page)

    for node in tree.walk():
        if node.page_to is None:
            node.page_to = node.page_from
        if node.marks is None:
            for part in node.text_parts:
                m, _ = extract_marks(part)
                if m is not None:
                    node.marks = m
                    break

    # 父题的页码范围必须覆盖其所有子题（题目跨页时父题页尾要跟到最后一页）
    _propagate_page_ranges(tree)

    # 图形资产归属到题目
    tree.asset_stats = attach_assets(tree, doc)

    _validate(tree, doc, page_assigned, expected_total_marks)
    return tree


def _last_sibling_label(stack: list[QuestionNode], depth: int) -> Optional[str]:
    """取当前栈中最近的同级标签（用于 (i)/(v)/(x) 消歧）。"""
    for node in reversed(stack):
        if node.depth < depth:
            return None
        if node.depth == depth:
            return node.label
    return None


# 歧义标签 -> 紧邻的前一个字母。出现 (h) 之后的 (i) 才真的是字母小问。
_AMBIGUOUS_PREDECESSOR = {"i": "h", "v": "u", "x": "w"}


def _is_preceding_letter(prev_label: str, label: str) -> bool:
    """前一个同级标签是否正好是歧义标签的前一个字母。

    如 (h) 后的 (i) -> 字母小问；(a) 后的 (i) -> 罗马数字子小问。
    """
    if not (len(prev_label) == 3 and prev_label.startswith("(") and prev_label.endswith(")")):
        return False
    ch = label[1]
    return prev_label[1].lower() == _AMBIGUOUS_PREDECESSOR.get(ch)


def _looks_roman(label: str) -> bool:
    """标签是否为罗马数字（i/ii/iii/iv/v/...）。"""
    if not (label.startswith("(") and label.endswith(")")):
        return False
    return roman_to_int(label[1:-1]) is not None


def _propagate_page_ranges(tree: QuestionTree) -> None:
    """自底向上把子题的页码范围合并到父题。

    题目可能跨页：Q25 起于 p10，其小问 25(b) 延伸到 p12，
    因此 Q25 的 page_to 必须是 12，而不是它自身题号所在页。
    """

    def visit(node: QuestionNode) -> tuple[int, int]:
        lo = node.page_from or 0
        hi = node.page_to or node.page_from or 0
        for child in node.children:
            clo, chi = visit(child)
            if clo:
                lo = min(lo, clo) if lo else clo
            if chi:
                hi = max(hi, chi)
        if lo:
            node.page_from = lo
        if hi:
            node.page_to = hi
        return lo, hi

    for root in tree.roots:
        visit(root)


def _validate(
    tree: QuestionTree,
    doc: PdfDocument,
    page_assigned: set[int],
    expected_total_marks: Optional[int],
) -> None:
    findings = tree.findings

    top_numbers: list[int] = []
    for root in tree.roots:
        try:
            top_numbers.append(int(root.label))
        except ValueError:
            findings.append(
                {
                    "rule": "top_level_number_not_integer",
                    "severity": "warning",
                    "message": f"顶层题号非整数: {root.label}",
                }
            )
    for a, b in zip(top_numbers, top_numbers[1:]):
        if b != a + 1:
            findings.append(
                {
                    "rule": "numbering_gap",
                    "severity": "error",
                    "message": f"顶层题号不连续: {a} -> {b}",
                }
            )
    if top_numbers and top_numbers[0] != 1:
        findings.append(
            {
                "rule": "numbering_not_start_at_one",
                "severity": "error",
                "message": f"首个顶层题号为 {top_numbers[0]}，应为 1",
            }
        )

    leaf_marks = 0
    has_marks = False
    for node in tree.walk():
        if not node.children and node.marks is not None:
            leaf_marks += node.marks
            has_marks = True
    if has_marks:
        tree.total_marks = leaf_marks
        if expected_total_marks is not None and leaf_marks != expected_total_marks:
            findings.append(
                {
                    "rule": "marks_total_mismatch",
                    "severity": "error",
                    "message": f"分值合计 {leaf_marks} != 试卷总分 {expected_total_marks}",
                    "evidence": {"computed": leaf_marks, "expected": expected_total_marks},
                }
            )
    else:
        findings.append(
            {"rule": "no_marks_found", "severity": "warning", "message": "未抽取到任何分值"}
        )

    if not tree.roots:
        findings.append(
            {"rule": "no_questions", "severity": "critical", "message": "未识别出任何题目"}
        )

    uncovered = sorted(
        set(range(1, doc.page_count + 1)) - page_assigned - set(tree.front_matter_pages)
    )
    if uncovered:
        findings.append(
            {
                "rule": "pages_uncovered",
                "severity": "warning",
                "message": f"{len(uncovered)} 页未归属任何题目（可能为空白页/版权页）",
                "evidence": {"pages": uncovered[:50]},
            }
        )

    for node in tree.walk():
        for child in node.children:
            if child.depth > node.depth + 1:
                findings.append(
                    {
                        "rule": "depth_skip",
                        "severity": "warning",
                        "message": f"{child.number_path} 层级跳级（{node.depth} -> {child.depth}）",
                    }
                )


def attach_assets(tree: QuestionTree, doc: PdfDocument) -> dict[str, Any]:
    """把页面上的视觉资产归属到题目。

    三类页面分开处理，避免把封面校徽、版权页图形误当成"未归属的题目插图"：
      1. 前置页（封面/说明页）上的资产：文档级资产，记在 tree.front_assets；
      2. 题目页上的资产：按页面与纵向位置挂到最贴近的题目；
      3. 页面上没有题目覆盖但资产存在：才计为 orphan，转人工确认。
    """
    assigned = 0
    front = 0
    orphan_pages: set[int] = set()
    nodes = [n for n in tree.walk()]
    front_matter = set(tree.front_matter_pages or [])

    for page in doc.pages:
        if page.number in front_matter:
            for img in page.images:
                tree.front_assets.append(_asset_ref(img))
                front += 1
            continue

        page_nodes = [
            n
            for n in nodes
            if n.page_from is not None
            and n.page_from <= page.number <= (n.page_to or n.page_from)
        ]
        for img in page.images:
            ref = _asset_ref(img)
            owner = _owner_for(page_nodes, page.number, img.bbox[1]) if page_nodes else None
            if owner is None:
                orphan_pages.add(page.number)
                continue
            owner.assets.append(ref)
            assigned += 1

    total_images = sum(len(p.images) for p in doc.pages)
    stats = {
        "images_total": total_images,
        "images_assigned": assigned,
        "images_front_matter": front,
        "images_orphan": total_images - assigned - front,
        "orphan_pages": sorted(orphan_pages),
    }

    if stats["images_orphan"] > 0:
        tree.findings.append(
            {
                "rule": "orphan_assets",
                "severity": "warning",
                "message": f"{stats['images_orphan']} 个图片未能归属到题目",
                "evidence": {"pages": stats["orphan_pages"][:50]},
            }
        )
    return stats


def _asset_ref(img) -> AssetRef:
    """ImageBlock -> AssetRef。矢量图形与位图共用同一条落库路径。"""
    return AssetRef(
        page=img.page,
        bbox=tuple(img.bbox),  # type: ignore[arg-type]
        width=img.width,
        height=img.height,
        ext=img.ext,
        data=img.data,
        reading_order=img.block_no,
        kind="figure",
        mime=_mime_for_ext(img.ext),
    )


def _owner_for(nodes: list[QuestionNode], page: int, y: float) -> Optional[QuestionNode]:
    """选择覆盖该纵坐标且最贴近图片上方的题目节点。"""
    if not nodes:
        return None
    started = [n for n in nodes if (n.bbox_from or {}).get("page") == page]
    if started:
        started.sort(key=lambda n: (n.bbox_from or {}).get("bbox", [0, 0, 0, 0])[1])
        chosen = None
        for n in started:
            y0 = (n.bbox_from or {}).get("bbox", [0, 0, 0, 0])[1]
            if y0 <= y + 1:
                chosen = n
        if chosen is not None:
            return chosen
        return started[0]
    candidates = sorted(nodes, key=lambda n: -n.depth)
    return candidates[0] if candidates else None
