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
        matrix = self._maybe_transpose(matrix)
        pending: Optional[MarkSchemeEntryDraft] = None
        if draft.entries:
            previous = draft.entries[-1]
            pages = previous.raw.get("pages", [previous.raw.get("page")])
            if pages and pages[-1] == page_number - 1:
                pending = previous
        header_cols = self._find_header(matrix)
        started = header_cols is None
        if header_cols is None:
            header_cols = pending.raw.get("columns") if pending is not None else None
        if header_cols is None:
            return
        q_col, a_col, m_col, g_col = header_cols
        if started and any(len(row) <= max(q_col, a_col, m_col, g_col) for row in matrix):
            return
        touched: dict[int, MarkSchemeEntryDraft] = {}

        for r, row in enumerate(matrix):
            cells = [normalize_chars(c.text).strip() for c in row]
            if not any(cells):
                continue
            label = cells[q_col] if q_col < len(cells) else ""
            if label.lower().startswith("question"):
                started = True
                continue
            if not started:
                continue

            answer = cells[a_col] if a_col < len(cells) else ""
            marks_txt = cells[m_col] if m_col < len(cells) else ""
            guide = cells[g_col] if 0 <= g_col < len(cells) else ""
            if label:
                if not _NUMBER.fullmatch(normalize_number_path(label)):
                    continue
                pending = MarkSchemeEntryDraft(
                    number_label=label.strip(),
                    number_path=normalize_number_path(label),
                    raw={
                        "page": page_number,
                        "row": r,
                        "cells": cells,
                        "columns": header_cols,
                        "pages": [],
                        "rows": [],
                        "base_confidence": self._entry_confidence(label, answer, marks_txt),
                    },
                )
                draft.entries.append(pending)
            elif pending is None:
                if answer or marks_txt or guide:
                    draft.findings.append(
                        {
                            "rule": "ms_orphan_continuation",
                            "severity": "warning",
                            "message": "评分续行没有可确认的前页条目",
                            "evidence": {"page": page_number, "row": r, "cells": cells},
                        }
                    )
                continue

            if answer:
                pending.answer_text = ((pending.answer_text or "") + " " + answer).strip()
            if guide:
                pending.partial_marks = ((pending.partial_marks or "") + " " + guide).strip()
                pending.guidance = pending.partial_marks
            pending.raw["rows"].append({"marks": marks_txt, "partial": guide})
            if page_number not in pending.raw["pages"]:
                pending.raw["pages"].append(page_number)
            touched[len(draft.entries) - 1] = pending

        for entry_index, entry in touched.items():
            entry.marks, issue = self._marks_resolution(entry.raw["rows"])
            entry.parse_confidence = round(
                min(entry.raw["base_confidence"] + (0.15 if entry.marks is not None else 0), 1.0),
                3,
            )
            self._extract_marking_vocabulary(entry)
            draft.findings[:] = [
                f for f in draft.findings
                if not (f.get("rule") == "ms_marks_ambiguous"
                        and f.get("evidence", {}).get("entry_index") == entry_index)
            ]
            if issue:
                draft.findings.append(
                    {
                        "rule": "ms_marks_ambiguous",
                        "severity": "error",
                        "message": issue,
                        "evidence": {
                            "entry_index": entry_index,
                            "number_path": entry.number_path,
                            "pages": list(entry.raw["pages"]),
                            "rows": list(entry.raw["rows"]),
                        },
                    }
                )

    @staticmethod
    def _resolve_marks(rows: list[dict[str, str]]) -> Optional[int]:
        return CambridgeMarkSchemeParser._marks_resolution(rows)[0]

    @staticmethod
    def _marks_resolution(rows: list[dict[str, str]]) -> tuple[Optional[int], Optional[str]]:
        numeric: list[int] = []
        marks_tokens: list[int] = []
        for row in rows:
            text = (row.get("marks", "") or "").strip()
            if not text:
                continue
            value = _parse_marks(text)
            if value is not None:
                numeric.append(value)
            elif re.fullmatch(r"[MAB]\d{1,2}(?:[\s+]+[MAB]\d{1,2})*", text):
                marks_tokens.extend(int(v) for v in re.findall(r"[MAB](\d{1,2})", text))
            else:
                return None, "Marks 单元包含无法确定的多行或非分值内容"
        if len(numeric) > 1:
            return None, "同一评分条目有多个整数分值，无法确定是总分还是分项"
        if numeric:
            return numeric[0], None

        first_partial = (rows[0].get("partial", "") or "") if rows else ""
        total_match = re.match(r"^\s*(\d{1,2})(?=\s+[MAB]\d\b|\s*$)", first_partial)
        if total_match:
            return int(total_match.group(1)), None

        partial_tokens: list[int] = []
        for row in rows:
            text = row.get("partial", "") or ""
            if re.search(r"\b(?:or|alternatively)\b.*\b[MAB]\d\b", text, re.I | re.S):
                return None, "无明确总分且评分说明包含替代评分路径"
            for line in text.splitlines():
                token = re.match(r"^\s*[MAB](\d{1,2})\b", line)
                if token:
                    partial_tokens.append(int(token.group(1)))
        total = sum(marks_tokens) + sum(partial_tokens)
        return (total or None), None

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
        counts: dict[str, int] = {}
        for entry in draft.entries:
            counts[entry.number_path] = counts.get(entry.number_path, 0) + 1
        draft.metadata["entry_count"] = len(draft.entries)
        draft.metadata["distinct_numbers"] = len(counts)
        dupes = sorted(path for path, count in counts.items() if count > 1)
        if dupes:
            draft.findings.append(
                {
                    "rule": "ms_duplicate_numbers",
                    "severity": "warning",
                    "message": f"重复题号: {dupes[:20]}",
                    "evidence": {"counts": {path: counts[path] for path in dupes}},
                }
            )

        overlap = {
            entry.number_path: [
                child.number_path for child in draft.entries
                if child.number_path.startswith(entry.number_path + "(")
                and child.marks is not None
            ]
            for entry in draft.entries if entry.marks is not None
        }
        overlap = {path: children for path, children in overlap.items() if children}
        if overlap:
            draft.findings.append(
                {
                    "rule": "ms_parent_child_marks_ambiguous",
                    "severity": "warning",
                    "message": "父题和子题均有分值，保留原值而不重复求和",
                    "evidence": {"paths": overlap},
                }
            )
        missing = [entry.number_path for entry in draft.entries if entry.marks is None]
        if missing:
            draft.findings.append(
                {
                    "rule": "ms_marks_missing",
                    "severity": "warning",
                    "message": "部分评分条目未能确定分值",
                    "evidence": {"paths": missing},
                }
            )
        draft.metadata["total_marks"] = (
            None if dupes or overlap or missing else sum(entry.marks for entry in draft.entries)
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
