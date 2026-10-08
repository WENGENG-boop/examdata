"""内容级文件类型识别。

规格要求"文件类型判断不能只依赖文件名，还需要能够结合官方页面信息、
文件本身信息以及文档内容进行判断"。

现有 classify.py 只用了**锚文本 + URL slug** 两个信号，都属于"页面信息"。
这里补上第三类信号：**文档内容**。

做法：读取 PDF 首页文本，与各类别特有的措辞做匹配。
每个类别的证据词按判别力加权——"mark scheme" 出现在首页几乎是决定性的，
而 "question" 单独出现判别力很低（mark scheme 里也满是 question）。

输出的是**独立证据**，不直接改 doc_type：由调用方决定如何与
锚文本判定融合（见 reconcile）。这样任何单点判断失误都能被追溯。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..parsing.pdfdoc import load_pdf


# 每个类别：(正则, 权重)。权重反映该措辞在首页出现时对该类别的判别力。
_PATTERNS: dict[str, list[tuple[re.Pattern[str], float]]] = {
    "mark_scheme": [
        (re.compile(r"mark scheme", re.I), 1.00),
        (re.compile(r"maximum mark\s*:", re.I), 0.60),
        (re.compile(r"published as an aid to teachers", re.I), 0.80),
        (re.compile(r"\bpartial marks\b", re.I), 0.50),
        (re.compile(r"\bquestion\b\s+\banswer\b\s+\bmarks\b", re.I), 0.45),
        (re.compile(r"how the marks should be awarded", re.I), 0.70),
        (re.compile(r"\bM1\b|\bA1\b|\bB1\b", re.I), 0.25),
    ],
    "specimen_mark_scheme": [
        (re.compile(r"specimen", re.I), 0.45),
        (re.compile(r"mark scheme", re.I), 0.80),
        (re.compile(r"for examination from\s+\d{4}", re.I), 0.60),
    ],
    "question_paper": [
        (re.compile(r"question paper", re.I), 0.95),
        (re.compile(r"answer all questions", re.I), 0.70),
        (re.compile(r"write your answer", re.I), 0.50),
        (re.compile(r"you must answer on the question paper", re.I), 0.75),
        (re.compile(r"time allowed", re.I), 0.45),
        (re.compile(r"\[\s*\d+\s*\]", re.I), 0.20),
        # Edexcel 封面措辞（新旧两代封面 + 教师/考生版说明）。全库实测
        # 只命中 question_paper，mark scheme 一份未命中。
        (re.compile(r"before entering your candidate information", re.I), 0.85),
        (re.compile(r"write your name here", re.I), 0.55),
        (re.compile(r"you do not need any other materials", re.I), 0.45),
        (re.compile(r"instructions to (?:the )?(?:teacher/examiner|candidate)\b", re.I), 0.40),
        (re.compile(r"paper reference", re.I), 0.35),
        # 听力文字稿：类型词表里没有 transcript，官方页面把它们归在
        # question paper 下（全库 10 份皆然）。此模式同时压过文字稿里
        # "(M1)" 说话人标记对 mark_scheme 的假阳性。
        (re.compile(r"transcript of (?:the )?listening test", re.I), 0.65),
        # 部分文字稿封面只写 "Transcript"（如 WSP04 2020），单独给一个
        # 弱权重，避免被 "(M1)" 假阳性压过去。全库实测只命中文字稿。
        (re.compile(r"\btranscript\b", re.I), 0.50),
        # 封面 "Total Marks" 框；用于压过少数 QP 里 "Insert"/"clean copy"
        # 对 source_material 的误命中（全库实测 1564 行皆 question_paper）。
        (re.compile(r"\btotal marks\b", re.I), 0.30),
    ],
    "specimen_paper": [
        (re.compile(r"specimen", re.I), 0.50),
        (re.compile(r"question paper", re.I), 0.80),
        (re.compile(r"for examination from\s+\d{4}", re.I), 0.55),
    ],
    "examiner_report": [
        (re.compile(r"examiner report", re.I), 1.00),
        (re.compile(r"principal examiner", re.I), 0.80),
        (re.compile(r"general comments", re.I), 0.55),
        (re.compile(r"candidates?\s+(?:were|did|found|often)", re.I), 0.35),
        (re.compile(r"common misconceptions", re.I), 0.60),
    ],
    "scoring_guideline": [
        (re.compile(r"scoring guideline", re.I), 1.00),
        (re.compile(r"rubric", re.I), 0.55),
        (re.compile(r"free[- ]response", re.I), 0.40),
    ],
    "sample_response": [
        (re.compile(r"sample response", re.I), 1.00),
        (re.compile(r"exemplar", re.I), 0.70),
        (re.compile(r"candidate response", re.I), 0.60),
    ],
    "formula_booklet": [
        (re.compile(r"formula (?:booklet|sheet|list)", re.I), 1.00),
        (re.compile(r"list of formulae", re.I), 0.85),
        (re.compile(r"mathematical formulae", re.I), 0.70),
    ],
    "data_booklet": [
        (re.compile(r"data booklet", re.I), 1.00),
        (re.compile(r"periodic table", re.I), 0.55),
        (re.compile(r"data sheet", re.I), 0.70),
    ],
    "source_material": [
        (re.compile(r"source material", re.I), 1.00),
        (re.compile(r"insert", re.I), 0.55),
        (re.compile(r"clean copy", re.I), 0.45),
    ],
    # 非考试材料类官方文件。把它们显式判为 other，
    # 而不是返回 None——"这是教学大纲，不是试题"比"我不知道这是什么"
    # 对下游更有用，也能和"文件读不出来"区分开。
    "other": [
        (re.compile(r"scheme of work", re.I), 1.00),
        (re.compile(r"specification\b", re.I), 0.60),
        (re.compile(r"qualification guide", re.I), 0.80),
        (re.compile(r"getting started guide", re.I), 0.80),
        (re.compile(r"\bnotice\b", re.I), 0.40),
        (re.compile(r"past training|training content", re.I), 0.60),
        (re.compile(r"accredited specification", re.I), 0.70),
    ],
}

# 分类只读前几页：封面信息足以判定，且避免把题目正文里的词当证据。
SCAN_PAGES = 2
MAX_CHARS = 6000


@dataclass
class ContentEvidence:
    doc_type: Optional[str]
    confidence: float
    scores: dict[str, float] = field(default_factory=dict)
    matched: dict[str, list[str]] = field(default_factory=dict)
    pages_scanned: int = 0
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_type": self.doc_type,
            "confidence": round(self.confidence, 4),
            "scores": {k: round(v, 4) for k, v in self.scores.items()},
            "matched": self.matched,
            "pages_scanned": self.pages_scanned,
            "error": self.error,
        }


def classify_content(path: Path | str) -> ContentEvidence:
    """读 PDF 前几页文本，给出内容级类型判定。"""
    try:
        # 分类只看前 SCAN_PAGES 页；解析整本 PDF 在大库下代价显著且无收益。
        doc = load_pdf(Path(path), max_pages=SCAN_PAGES)
    except Exception as exc:  # 损坏文件 / 加密文件
        return ContentEvidence(doc_type=None, confidence=0.0, error=f"{type(exc).__name__}: {exc}")

    text_parts: list[str] = []
    pages = 0
    for page in doc.pages[:SCAN_PAGES]:
        pages += 1
        for line in page.lines:
            text_parts.append(line.text)
            if sum(len(p) for p in text_parts) > MAX_CHARS:
                break
    text = "\n".join(text_parts)[:MAX_CHARS]

    # 文本层不可用（纯扫描件、字体编码损坏）时如实报错，与"读得出但判不出"
    # 区分开：前者再补规则也读不出来，后者说明规则还需要补。
    normalized = re.sub(r"\s+", " ", text)
    ctrl_ratio = len(re.findall(r"[\x00-\x08\x0b-\x1f\x7f]", text)) / max(1, len(text))
    if len(re.findall(r"[A-Za-z]{3,}", normalized)) < 5 or ctrl_ratio > 0.10:
        error = "no_text_layer" if not normalized.strip() else "text_layer_unreadable"
        return ContentEvidence(doc_type=None, confidence=0.0, pages_scanned=pages, error=error)

    scores: dict[str, float] = {}
    matched: dict[str, list[str]] = {}
    for doc_type, patterns in _PATTERNS.items():
        total = 0.0
        hits: list[str] = []
        for pat, weight in patterns:
            # 空白归一化后匹配："Mark\nScheme" 这类跨行排版不归一化会漏掉。
            m = pat.search(normalized)
            if m:
                total += weight
                hits.append(m.group(0)[:40])
        if total > 0:
            scores[doc_type] = total
            matched[doc_type] = hits

    if not scores:
        return ContentEvidence(doc_type=None, confidence=0.0, pages_scanned=pages)

    best = max(scores, key=lambda k: scores[k])
    best_score = scores[best]
    runner = max((v for k, v in scores.items() if k != best), default=0.0)
    # 置信度同时看绝对分与相对优势：两个类别得分接近时，判定不可信
    confidence = min(1.0, best_score / 1.5) * (1.0 if best_score == 0 else best_score / (best_score + runner))
    # 归一化到 0-1 且让"首页出现 mark scheme"这种强证据接近 1
    confidence = min(1.0, best_score / 1.5)
    if runner > 0:
        confidence *= best_score / (best_score + runner)
    return ContentEvidence(
        doc_type=best,
        confidence=round(confidence, 4),
        scores=scores,
        matched=matched,
        pages_scanned=pages,
    )


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """置信度必须落在 [0,1]。融合时会取 max，不钳制就会溢出。"""
    return max(low, min(high, float(value)))


# 更具体的类型 -> 它所属的泛化类型。
# 内容判定只能看出"这是一份试卷"，看不出"这是样卷"——样卷身份来自
# 官方页面标注（"Specimen"）。这类差异是**具体化**，不是冲突。
_SPECIALIZES: dict[str, str] = {
    "specimen_paper": "question_paper",
    "specimen_mark_scheme": "mark_scheme",
}


def reconcile(label_type: Optional[str], content: ContentEvidence) -> tuple[str, float, str]:
    """把锚文本判定与内容判定融合成一个最终类型。

    规则（保守优先，冲突不静默）：
    - 两者一致：高置信度采纳。
    - 标签是内容的**具体化**（如 specimen_paper 之于 question_paper）：
      采纳更具体的标签，置信度按内容证据给分——这不是冲突。
    - 只有内容有判定：采纳内容判定，置信度按内容证据打折（没有页面佐证）。
    - 只有锚文本有判定：保留锚文本判定，置信度中等。
    - 真正冲突：**不自动裁决**。保留锚文本判定（页面信息是权威来源），
      置信度压到 0.4 以下，让这份文件进入待检查队列。
    返回 (doc_type, confidence, method)。
    """
    ctype = content.doc_type
    if label_type and ctype:
        if label_type == ctype or _SPECIALIZES.get(label_type) == ctype:
            return label_type, _clamp(max(0.9, content.confidence)), "label+content"
        return label_type, 0.35, "conflict"
    if ctype:
        return ctype, _clamp(min(0.75, content.confidence)), "content"
    if label_type:
        return label_type, 0.6, "label"
    return "other", 0.2, "none"
