"""内容点标注包：把题目挂到 spec 内容点（taxonomy_node.node_type == "point"）。

组成：
- ``text``      分词与词形归一（确定性、纯标准库）
- ``bm25``      BM25 打分（参数与公式见模块 docstring）
- ``corpus``    从库里取内容点/题目，拼文档与候选范围（单元约束、科目归属）
- ``assign``    赋标与落库（replace 只删自己的 auto 行；低置信复核文件）
- ``cambridge`` cambridge 只读对照评估（同一打分器，绝不写 cambridge 行）

命令行：``python -m examdata.tagging assign …`` / ``… eval-cambridge``。
本阶段 ``assign`` 默认 dry-run，真实写库要显式 ``--write``。
"""

from .assign import (
    ASSIGNED_BY,
    CALIBRATION,
    DEFAULT_MIN_SCORE,
    LOW_CONFIDENCE,
    SECOND_TAG_RATIO,
    TagCandidate,
    assign,
    confidence_scores,
    rank_question,
    select_tags,
)
from .bm25 import Bm25Index, Doc, build_index
from .cambridge import evaluate_cambridge
from .corpus import (
    BOARD_KEY,
    CorpusSet,
    PointCandidate,
    QuestionRef,
    SubjectCorpus,
    doc_for,
    iter_questions,
    load_points,
    unit_code_from_paper,
)
from .text import tokenize

__all__ = [
    "ASSIGNED_BY",
    "BOARD_KEY",
    "Bm25Index",
    "CALIBRATION",
    "CorpusSet",
    "DEFAULT_MIN_SCORE",
    "Doc",
    "LOW_CONFIDENCE",
    "PointCandidate",
    "QuestionRef",
    "SECOND_TAG_RATIO",
    "SubjectCorpus",
    "TagCandidate",
    "assign",
    "build_index",
    "confidence_scores",
    "doc_for",
    "evaluate_cambridge",
    "iter_questions",
    "load_points",
    "rank_question",
    "select_tags",
    "tokenize",
    "unit_code_from_paper",
]
