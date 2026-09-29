"""Cambridge Mark Scheme 解析器。

实测版式（research/cambridge.md，0580/11 June 2024）：
  - 前若干页为 Generic Marking Principles / MARK SCHEME NOTES（无评分表）
  - 评分表为 4 列：Question | Answer | Marks | Partial Marks
  - 题目编号形如 1(a) / 3(b) / 7，与试卷题目树可直接对齐

解析依赖表格网格还原（parsing.tables），不依赖文本流顺序。
"""

from __future__ import annotations

import re
from typing import Any, Optional

import pymupdf

from ..parsing.pdfdoc import PdfDocument
from ..parsing.tables import detect_grid, fill_cells
from .base import MarkSchemeDraft, MarkSchemeEntryDraft

# 表格表头（用于定位评分表起始与列语义）
_HEADER_TOKENS = ("question", "answer", "marks", "partial marks", "guidance")
_NUMBER = re.compile(r"^\s*(\d{1,2})\s*(?:\(([a-z])\))?\s*(?:\(([ivx]+)\))?\s*$", re.I)
_MARKS_INT = re.compile(r"^\s*(\d{1,2})\s*$")

# Cambridge 使用符号字体，部分字符落在私有区，需要归一化
_CHAR_FIXES = {
    "\uf02d": "-",
    "\uf02b": "+",
    "\uf03d": "=",
    "\uf0b4": "x",
    "\uf0b7": ".",
    "\uf0a3": "<=",
    "\uf0b3": ">=",
    "\uf0e2": "->",
    "\uf0ae": "-",
}


def normalize_chars(text: str) -> str:
    for bad, good in _CHAR_FIXES.items():
        text = text.replace(bad, good)
    return text


def normalize_number_path(label: str) -> str:
    """把 Mark Scheme 的题号规范化为与试卷题目树一致的路径。

    "1 (a)" -> "1(a)"，"3(b)" -> "3(b)"，"2" -> "2"
    """
    s = normalize_chars(label).strip()
    s = re.sub(r"\s+", "", s)
    s = s.replace("（", "(").replace("）", ")")
    return s


def _parse_marks(text: str) -> Optional[int]:
    if not text:
        return None
    m = _MARKS_INT.match(text.strip())
    if m:
        return int(m.group(1))
    return None


class CambridgeMarkSchemeParser:
    key = "cambridge"

    def parse(self, doc: PdfDocument, *, pdf_path: str | None = None) -> MarkSchemeDraft:
        draft = MarkSchemeDraft()
        path = pdf_path or str(doc.path)
        pdf = pymupdf.open(path)
        try:
            for page_info in doc.pages:
                page = pdf[page_info.number - 1]
                grid = detect_grid(page, page_info)
                if len(grid.column_ranges) < 3 or len(grid.row_ranges) < 2:
                    continue
                matrix = fill_cells(page_info, grid)
                if not matrix:
                    continue
                self._consume_matrix(matrix, draft, page_number=page_info.number)
        finally:
            pdf.close()

        self._finalize(draft)
        return draft

    # -- 内部 -----------------------------------------------------------

    def _consume_matrix(self, matrix, draft: MarkSchemeDraft, *, page_number: int) -> None:
        header_cols = self._find_header(matrix)
        if header_cols is None:
            return
        q_col, a_col, m_col, g_col = header_cols

        # 2025 specimen 的版式是"横排"的：表头 Question/Answer/Marks/Partial Marks
        # 不是列名，而是**行名**，每个题号占一列。此时按列解析会把 "Question"
        # 当成题号、把整页内容塞进一条条目。先检测并转置成常规竖排表。
        matrix = self._maybe_transpose(matrix)
        header_cols = self._find_header(matrix)
        if header_cols is None:
            return
        q_col, a_col, m_col, g_col = header_cols
        started = False

        # 当前条目累积的行（含续行）。多行 Marks 单元必须累加：
        # 例如 Q14 = M1(本行) + A1(续行) = 2 分，Q22 = M1 + A1 + A1 = 3 分。
        pending: Optional[MarkSchemeEntryDraft] = None
        pending_rows: list[dict[str, str]] = []

        def flush() -> None:
            nonlocal pending, pending_rows
            if pending is not None:
                pending.marks = self._resolve_marks(pending_rows)
                self._extract_marking_vocabulary(pending)
                pending.raw["rows"] = pending_rows
                # 分值解析成功应提升置信度（跨续行累加后才知道真实分值）
                if pending.marks is not None:
                    pending.parse_confidence = round(
                        min(pending.parse_confidence + 0.15, 1.0), 3
                    )
                draft.entries.append(pending)
            pending = None
            pending_rows = []

        for r, row in enumerate(matrix):
            cells = [normalize_chars(c.text).strip() for c in row]
            if not any(cells):
                continue
            first = cells[q_col].lower() if q_col < len(cells) else ""
            if not started:
                if first.startswith("question"):
                    started = True
                continue

            label = cells[q_col] if q_col < len(cells) else ""
            answer = cells[a_col] if a_col < len(cells) else ""
            marks_txt = cells[m_col] if m_col < len(cells) else ""
            guide = cells[g_col] if g_col < len(cells) and g_col >= 0 else ""

            if not label:
                # 续行：并入当前条目（答案、说明、分值都要累积）
                if pending is not None:
                    if answer:
                        pending.answer_text = ((pending.answer_text or "") + " " + answer).strip()
                    if guide:
                        pending.partial_marks = (
                            ((pending.partial_marks or "") + " " + guide).strip()
                        )
                        pending.guidance = pending.partial_marks
                    pending_rows.append({"marks": marks_txt, "partial": guide})
                continue

            if not _NUMBER.match(label):
                continue

            # 新条目：先结算上一条
            flush()
            path = normalize_number_path(label)
            pending = MarkSchemeEntryDraft(
                number_label=label.strip(),
                number_path=path,
                answer_text=answer or None,
                partial_marks=guide or None,
                guidance=guide or None,
                raw={"page": page_number, "row": r, "cells": cells},
                parse_confidence=self._entry_confidence(label, answer, marks_txt),
            )
            pending_rows = [{"marks": marks_txt, "partial": guide}]

        flush()

    @staticmethod
    def _resolve_marks(rows: list[dict[str, str]]) -> Optional[int]:
        """由条目所有行（含续行）解析分值。

        优先级：
        1. Marks 列出现纯整数 -> 取该整数（如 "1"、"2"、"3"）。
        2. Partial Marks 列以数字开头 -> 取该数字（如 "2 B1 for ..."）。
        3. 否则统计 M/A/B 记号的个数（如 M1 + A1 = 2 分）。
        """
        for row in rows:
            val = _parse_marks(row.get("marks", ""))
            if val is not None:
                return val

        for row in rows:
            m = re.match(r"^\s*(\d{1,2})\b", row.get("partial", "") or "")
            if m:
                return int(m.group(1))

        total = 0
        for row in rows:
            blob = (row.get("marks", "") or "") + " " + (row.get("partial", "") or "")
            for tok in re.findall(r"\b([MAB])(\d)\b", blob):
                total += int(tok[1])
        return total or None

    @staticmethod
    def _row_labels(matrix) -> list[str]:
        """取矩阵第一列的文字（转置后的行名）。"""
        labels = []
        for row in matrix:
            if not row:
                continue
            labels.append(normalize_chars(row[0].text).strip().lower())
        return labels

    @classmethod
    def _is_transposed(cls, matrix) -> bool:
        """判断表格是否为"表头在行、题号在列"的横排版式。

        特征：第一列从上到下依次出现 Question / Answer / Marks / Partial Marks，
        而题号散落在各列上。
        """
        labels = [l for l in cls._row_labels(matrix) if l]
        if not labels:
            return False
        first_col_blob = " | ".join(labels[:6])
        has_rows = (
            "question" in first_col_blob
            and "answer" in first_col_blob
            and "mark" in first_col_blob
        )
        if not has_rows:
            return False
        # 横排表的第 0 行是 "Partial Marks" 之类的列名，而不是表头本身
        return labels[0].startswith("partial") or not labels[0].startswith("question")

    @classmethod
    def _maybe_transpose(cls, matrix):
        """横排表 -> 竖排表。

        PDF 里这份表格是"每个题号占一列"，且行序自上而下为
        Partial Marks / Marks / Answer / Question。要还原成常规表格，
        需要**转置 + 行序翻转**：转置让每个题号成为一行，翻转让
        Question 排在 Answer、Marks 之前，这样表头才在数据行上方。
        """
        if not matrix or not cls._is_transposed(matrix):
            return matrix
        from ..parsing.tables import TableCell

        n_rows = len(matrix)
        n_cols = max(len(r) for r in matrix)
        out: list[list[TableCell]] = []
        for t in range(n_cols):
            row: list[TableCell] = []
            for c, k in enumerate(range(n_rows - 1, -1, -1)):
                cell = matrix[k][t] if t < len(matrix[k]) else None
                row.append(
                    TableCell(
                        column=c,
                        row=t,
                        text=cell.text if cell is not None else "",
                        bbox=cell.bbox if cell is not None else (0.0, 0.0, 0.0, 0.0),
                    )
                )
            out.append(row)
        return out

    @staticmethod
    def _find_header(matrix) -> Optional[tuple[int, int, int, int]]:
        """定位表头行并返回 (question_col, answer_col, marks_col, guidance_col)。

        表头可能出现在任意一列（横排表转置后 Question 不在第 0 列），
        因此按内容定位而不是写死列号。
        """
        for row in matrix:
            cells = [normalize_chars(c.text).strip().lower() for c in row]
            if not any(cells):
                continue
            q_col = next((i for i, c in enumerate(cells) if c.startswith("question")), None)
            if q_col is None:
                continue
            a_col = next(
                (i for i, c in enumerate(cells) if c.startswith("answer")), q_col + 1
            )
            m_col = next((i for i, c in enumerate(cells) if c.startswith("mark")), a_col + 1)
            g_col = next(
                (i for i, c in enumerate(cells) if "partial" in c or "guidance" in c), -1
            )
            return q_col, a_col, m_col, g_col
        return None

    @staticmethod
    def _entry_confidence(label: str, answer: str, marks_txt: str) -> float:
        conf = 0.6
        if _NUMBER.match(label):
            conf += 0.2
        if _MARKS_INT.match(marks_txt.strip()):
            conf += 0.15
        if answer:
            conf += 0.05
        return round(min(conf, 1.0), 3)

    @staticmethod
    def _extract_marking_vocabulary(entry: MarkSchemeEntryDraft) -> None:
        """识别 M/A/B 等评分语汇。

        Cambridge 记法：M=method, A=accuracy, B=independent, FT/ECF=follow through。
        """
        text = (entry.answer_text or "") + " " + (entry.guidance or "")
        if not text:
            return
        entry.method_marks = len(re.findall(r"\bM\d?", text))
        entry.accuracy_marks = len(re.findall(r"\bA\d?", text))
        entry.independent_marks = len(re.findall(r"\bB\d?", text))
        if re.search(r"\b(FT|ECF)\b", text, re.I):
            entry.ecf = True
        # 可接受答案：常见于 "oe"（or equivalent）、"or"、"accept"
        accepts: list[str] = []
        for m in re.finditer(r"\b(?:oe|or|accept)\b\s*([^;.]{1,80})", text, re.I):
            cand = m.group(1).strip()
            if cand:
                accepts.append(cand)
        entry.acceptable_answers = accepts[:6]

    @staticmethod
    def _finalize(draft: MarkSchemeDraft) -> None:
        if not draft.entries:
            draft.findings.append(
                {
                    "rule": "ms_no_entries",
                    "severity": "critical",
                    "message": "未从 Mark Scheme 中解析出任何评分条目",
                }
            )
            return
        # 题号连续性
        seen: list[str] = []
        for e in draft.entries:
            if e.number_path not in seen:
                seen.append(e.number_path)
        draft.metadata["entry_count"] = len(draft.entries)
        draft.metadata["distinct_numbers"] = len(seen)
        draft.metadata["total_marks"] = sum(e.marks or 0 for e in draft.entries)

        dupes = {n for n in seen if seen.count(n) > 1}
        if dupes:
            draft.findings.append(
                {
                    "rule": "ms_duplicate_numbers",
                    "severity": "warning",
                    "message": f"重复题号: {sorted(dupes)[:20]}",
                }
            )


def link_entries_to_questions(
    entries: list[MarkSchemeEntryDraft],
    questions: list[Any],
    *,
    fuzzy: bool = True,
) -> tuple[list[tuple[int, int]], list[str], list[str]]:
    """把评分条目按题号路径挂到题目。

    先精确匹配 number_path；未命中的条目再尝试"父题回退"（挂到最近的祖先题），
    仍无法匹配的记为 unmatched，交由校验层转人工。
    """
    by_path = {q.number_path: q for q in questions}
    linked: list[tuple[int, int]] = []
    unmatched: list[str] = []
    matched_qids: set[int] = set()

    for i, e in enumerate(entries):
        q = by_path.get(e.number_path)
        if q is not None:
            linked.append((i, q.id if hasattr(q, "id") else id(q)))
            matched_qids.add(q.id if hasattr(q, "id") else id(q))
            continue

        if fuzzy:
            # 父题回退：如 MS 给出 "3(b)(ii)" 而题目树只有 "3(b)"
            found = None
            path = e.number_path
            while "(" in path:
                path = path[: path.rfind("(")]
                if path in by_path:
                    found = by_path[path]
                    break
            if found is None:
                # 顶层题号回退
                m = re.match(r"^(\d+)", e.number_path)
                if m and m.group(1) in by_path:
                    found = by_path[m.group(1)]
            if found is not None:
                qid = found.id if hasattr(found, "id") else id(found)
                linked.append((i, qid))
                matched_qids.add(qid)
                continue

        unmatched.append(e.number_path)

    qid_all = {q.id if hasattr(q, "id") else id(q) for q in questions}
    without = [q.number_path for q in questions
               if (q.id if hasattr(q, "id") else id(q)) not in matched_qids]
    return linked, unmatched, without
