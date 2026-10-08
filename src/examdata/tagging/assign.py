"""给 Edexcel IAL 题目挂内容点（spec point）。

赋标规则
--------
- 候选范围：题目所属单元的后代 point（拿不到单元 → 该科目全部 point）。
- top-1：只要分数 > 0 就写。
- 第二标签：仅当 ``score2 ≥ 0.85 × score1`` **且** ``score1 ≥ min_score`` 才写。
  两条同时成立意味着"两个内容点几乎同样贴题"，此时给出第二个候选比硬选一个更诚实。
- 落库：``QuestionTaxonomy(source="auto", assigned_by="edexcel-bm25-v1",
  confidence=…, reviewed=False)``。重跑 ``replace`` 只删同一 ``assigned_by`` 的行，
  绝不碰 ``manual``；``manual`` 占用的节点也不会被自动结果二次写入
  （``(question_id, node_id)`` 唯一约束不含 source）。

置信度公式
----------
对第 i 个候选（分数 s_i，下一名分数 s_{i+1}，无下一名时取 0）：

    abs_i    = min(1, s_i / CALIBRATION)              # 绝对分归一
    margin_i = 1 − s_{i+1} / s_i                      # 与下一名的相对差距
    raw_i    = abs_i · (0.65 + 0.35 · margin_i)       # 绝对强度 × 相对把握
    conf_1   = raw_1
    conf_i   = min(raw_i, conf_{i−1})                 # 名次靠后的置信度不得超过前一名

用乘积而非加权和，是为了让"弱匹配但恰好没有竞争者"也拿到低置信度
（加权和会给它一个 0.35 的地板，等于凭空送分）；强匹配且无竞争者 = 1.0，
强匹配但两名接近 = 0.65，弱匹配 = 只有 abs 那一份。

``CALIBRATION`` 是固定常数（见下），不是运行时统计量，因此同一输入永远给同一输出。
跨科目的分数量纲并不一致（大纲原文长短差异很大），因此置信度只在**同一科目内**
可比；低置信阈值应理解为"该题 top-1 只达到本科目标定强度的一个零头"。
低置信（默认 conf < 0.35）仍然写库，只是额外计数并输出人工复核文件，
避免"分数低就丢掉"造成静默漏标。

dry-run 语义
------------
``dry_run=True`` 不写库、不写复核文件，统计值按"假如写入"计算。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.models import QuestionTaxonomy
from .corpus import BOARD_KEY, CorpusSet, QuestionRef, SubjectCorpus, iter_questions, load_points

SOURCE = "auto"
ASSIGNED_BY = "edexcel-bm25-v1"
# 复核回写：AI/人工复核确认的标签单独来源，与算法行区分（见 review.py）。
REVIEW_SOURCE = "ai-review"
REVIEW_ASSIGNED_BY = "ai-review-v1"
SECOND_TAG_RATIO = 0.85
# 写库时每 N 题提交一次。整个标注过程一个大事务会长时间占住写锁，
# 多进程批量（BEGIN IMMEDIATE）时其他进程只能干等；周期提交把锁窗口压小。
COMMIT_EVERY = 200
# 绝对分归一的标定点：对 21 个科目做"半覆盖查询"（取内容点自身句子每隔一个词）
# 得到的 top-1 分数中位数约 15，取整为 15 —— 即"题目覆盖内容点约一半"≈ 1.0。
# 固定常数 → 同一输入永远给同一输出；将来有真实题目后可据分布重新标定，
# 但重新标定只改置信度、不改 BM25 排序。
CALIBRATION = 15.0
LOW_CONFIDENCE = 0.35
DEFAULT_MIN_SCORE = 0.5
TOP_K = 3

_ABS_WEIGHT = 0.65
_MARGIN_WEIGHT = 0.35
_REVIEW_SAMPLE_CAP = 20


@dataclass(frozen=True)
class TagCandidate:
    code: str
    node_id: int
    name: str
    score: float
    confidence: float


def confidence_scores(
    scores: Sequence[float], *, calibration: float = CALIBRATION
) -> list[float]:
    """按上面的公式把降序分数列转成置信度列（纯函数，便于单独验证）。"""
    out: list[float] = []
    previous: Optional[float] = None
    for index, score in enumerate(scores):
        next_score = scores[index + 1] if index + 1 < len(scores) else 0.0
        margin = 1.0 - (next_score / score) if score > 0 else 0.0
        absolute = min(1.0, max(0.0, score / calibration)) if calibration > 0 else 0.0
        raw = absolute * (_ABS_WEIGHT + _MARGIN_WEIGHT * margin)
        if previous is not None:
            raw = min(raw, previous)
        value = round(min(1.0, max(0.0, raw)), 4)
        out.append(value)
        previous = value
    return out


def rank_question(
    corpora: CorpusSet,
    question: QuestionRef,
    *,
    calibration: float = CALIBRATION,
    top_k: int = TOP_K,
) -> tuple[Optional[str], list[TagCandidate]]:
    """返回 (科目, 候选列表)。候选按分数降序，最多 top_k 个。"""
    subject = corpora.resolve_subject(
        unit_code=question.unit_code,
        subject_candidates=[question.subject_slug, question.subject_code],
    )
    if subject is None:
        return None, []
    corpus: Optional[SubjectCorpus] = corpora.corpus_for(subject)
    if corpus is None:
        return subject, []
    allowed = corpus.candidate_positions(question.unit_code)
    # 多取一名：最后一名需要"下一名分数"才能算 margin，截断后再算会让末位虚高。
    ranked = corpus.rank(question.stem_text, allowed)[: top_k + 1]
    if not ranked:
        return subject, []
    confidences = confidence_scores([score for _, score in ranked], calibration=calibration)
    candidates = [
        TagCandidate(
            code=corpus.points[position].code,
            node_id=corpus.points[position].node_id,
            name=corpus.points[position].name,
            score=round(score, 4),
            confidence=confidences[index],
        )
        for index, (position, score) in enumerate(ranked[:top_k])
    ]
    return subject, candidates


def select_tags(
    candidates: Sequence[TagCandidate], *, min_score: float = DEFAULT_MIN_SCORE
) -> list[TagCandidate]:
    """top-1 必写；第二标签要求分数接近且 top-1 达阈值。"""
    if not candidates:
        return []
    chosen = [candidates[0]]
    if len(candidates) > 1:
        best, second = candidates[0], candidates[1]
        if best.score >= min_score and second.score >= SECOND_TAG_RATIO * best.score:
            chosen.append(second)
    return chosen


def _percentile(values: Sequence[float], quantile: float) -> float:
    """最近秩分位数：小样本下比插值更稳，且完全确定。"""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round(quantile * (len(ordered) - 1)))
    index = min(len(ordered) - 1, max(0, index))
    return round(ordered[index], 4)


def _score_distribution(scores: Sequence[float]) -> dict[str, Any]:
    if not scores:
        return {"n": 0, "min": 0.0, "p25": 0.0, "p50": 0.0, "p75": 0.0, "p90": 0.0, "max": 0.0}
    return {
        "n": len(scores),
        "min": round(min(scores), 4),
        "p25": _percentile(scores, 0.25),
        "p50": _percentile(scores, 0.50),
        "p75": _percentile(scores, 0.75),
        "p90": _percentile(scores, 0.90),
        "max": round(max(scores), 4),
    }


def _safe_name(value: str) -> str:
    return "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in value) or "unknown"


def _review_dir(explicit: Optional[Path]) -> Path:
    if explicit is not None:
        return Path(explicit)
    return Path(get_settings().data_dir) / "tagging" / "review"


def write_review_files(entries: Sequence[dict[str, Any]], *, review_dir: Optional[Path] = None) -> list[str]:
    """把低置信题目按科目写成 jsonl，供人工复核。"""
    directory = _review_dir(review_dir)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        grouped.setdefault(str(entry.get("subject") or "unknown"), []).append(entry)
    written: list[str] = []
    for subject, rows in sorted(grouped.items()):
        path = directory / f"{_safe_name(subject)}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for row in sorted(rows, key=lambda item: int(item["question_id"])):
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        written.append(str(path))
    return written


def assign(
    session: Session,
    *,
    subject: Optional[str] = None,
    limit: Optional[int] = None,
    dry_run: bool = True,
    replace: bool = False,
    min_score: float = DEFAULT_MIN_SCORE,
    low_confidence: float = LOW_CONFIDENCE,
    calibration: float = CALIBRATION,
    review_dir: Optional[Path] = None,
    board_key: str = BOARD_KEY,
) -> dict[str, Any]:
    """批量标注。``dry_run=True`` 时不产生任何副作用（不写库、不写文件）。"""
    stats: dict[str, Any] = {
        "board": board_key,
        "dry_run": dry_run,
        "replace": replace,
        "subject_filter": subject,
        "scanned": 0,
        "assigned": 0,
        "tagged": 0,
        "unassigned": 0,
        "second_tags": 0,
        "replaced": 0,
        "skipped_manual": 0,
        "skipped_reviewed": 0,
        "skipped_existing": 0,
        "skipped_no_subject": 0,
        "skipped_empty": 0,
        "low_confidence": 0,
        "review_files": [],
        "review_samples": [],
    }

    points = load_points(session, board_key=board_key)
    if not points:
        return stats
    corpora = CorpusSet(points)
    questions = iter_questions(session, board_key=board_key, subject=subject, limit=limit)

    top_scores: list[float] = []
    review_entries: list[dict[str, Any]] = []
    for question in questions:
        stats["scanned"] += 1
        if not dry_run and stats["scanned"] % COMMIT_EVERY == 0:
            session.commit()
        if not question.stem_text.strip():
            stats["skipped_empty"] += 1
            continue

        own_rows, manual_nodes, reviewed_nodes = _existing_rows(session, question.question_id)
        if reviewed_nodes:
            # 复核确认过的题整题冻结：不删、不补、不重标（keep/change 决策都保留）
            stats["skipped_reviewed"] += 1
            continue
        if replace:
            for row in own_rows:
                stats["replaced"] += 1
                if not dry_run:
                    session.delete(row)
            if own_rows and not dry_run:
                # 删除只在会话里排队；不 flush 的话紧接着的 INSERT 会在同一事务里
                # 与尚未落地的旧行撞 (question_id, node_id) 唯一约束。
                session.flush()
        else:
            if manual_nodes:
                stats["skipped_manual"] += 1
                continue
            if own_rows:
                stats["skipped_existing"] += 1
                continue

        subject_key, candidates = rank_question(corpora, question, calibration=calibration)
        if subject_key is None:
            stats["skipped_no_subject"] += 1
            continue
        if not candidates:
            stats["unassigned"] += 1
            continue

        chosen = select_tags(candidates, min_score=min_score)
        top_scores.append(candidates[0].score)
        stats["tagged"] += 1
        if len(chosen) > 1:
            stats["second_tags"] += 1

        written_nodes: set[int] = set()
        for candidate in chosen:
            if (
                candidate.node_id in manual_nodes
                or candidate.node_id in reviewed_nodes
                or candidate.node_id in written_nodes
            ):
                continue
            written_nodes.add(candidate.node_id)
            stats["assigned"] += 1
            if not dry_run:
                session.add(
                    QuestionTaxonomy(
                        question_id=question.question_id,
                        node_id=candidate.node_id,
                        source=SOURCE,
                        confidence=candidate.confidence,
                        assigned_by=ASSIGNED_BY,
                        reviewed=False,
                    )
                )

        if candidates[0].confidence < low_confidence:
            stats["low_confidence"] += 1
            entry = {
                "question_id": question.question_id,
                "number_label": question.number_label,
                "paper_code": question.paper_code,
                "subject": subject_key,
                "unit_code": question.unit_code,
                "top_confidence": candidates[0].confidence,
                "candidates": [
                    {
                        "code": candidate.code,
                        "name": candidate.name,
                        "score": candidate.score,
                        "confidence": candidate.confidence,
                    }
                    for candidate in candidates
                ],
            }
            review_entries.append(entry)

    if not dry_run:
        session.flush()
        if review_entries:
            stats["review_files"] = write_review_files(review_entries, review_dir=review_dir)

    stats["score_distribution"] = _score_distribution(top_scores)
    stats["review_samples"] = review_entries[:_REVIEW_SAMPLE_CAP]
    stats["review_sample_cap"] = _REVIEW_SAMPLE_CAP
    return stats


def _existing_rows(
    session: Session, question_id: int
) -> tuple[list[QuestionTaxonomy], set[int], set[int]]:
    """返回 (本方法可替换的行, manual 占用的 node_id, 复核占用的 node_id)。

    - own：``assigned_by == ASSIGNED_BY`` 且未复核的行，``--replace`` 时删除重建；
    - manual：``source == "manual"`` 的行占用的内容点；
    - reviewed：复核流程确认过的行（``assigned_by`` 为算法或复核来源且
      ``reviewed=True``）占用的内容点；这类题整题冻结，重跑算法不删、不补、不重标。
    """
    rows = list(
        session.scalars(
            select(QuestionTaxonomy).where(QuestionTaxonomy.question_id == question_id)
        )
    )
    own = [row for row in rows if row.assigned_by == ASSIGNED_BY and not row.reviewed]
    manual = {row.node_id for row in rows if row.source == "manual"}
    reviewed = {
        row.node_id
        for row in rows
        if row.reviewed and row.assigned_by in (ASSIGNED_BY, REVIEW_ASSIGNED_BY)
    }
    return own, manual, reviewed


__all__ = [
    "ASSIGNED_BY",
    "CALIBRATION",
    "DEFAULT_MIN_SCORE",
    "LOW_CONFIDENCE",
    "REVIEW_ASSIGNED_BY",
    "REVIEW_SOURCE",
    "SECOND_TAG_RATIO",
    "SOURCE",
    "TOP_K",
    "TagCandidate",
    "assign",
    "confidence_scores",
    "rank_question",
    "select_tags",
    "write_review_files",
]
