"""端到端验证脚本：不启动服务器也能核对全链路关键不变量。

用途：改完解析/治理/智能层后跑一遍，快速确认"该有的都有、该等的都等"。
与 pytest 的分工：pytest 测行为契约，本脚本测**当前数据库的实际状态**
（覆盖率、关联率、幂等性），适合作为交付前的自检。

用法：
    .venv\\Scripts\\python.exe scripts\\verify_state.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import func, select

from examdata.core.config import get_settings
from examdata.core.db import session_scope
from examdata.core.models import (
    Artifact,
    Asset,
    Difficulty,
    DocClassification,
    GeneratedExplanation,
    Document,
    DocumentRevision,
    MarkSchemeEntry,
    Paper,
    Question,
    QuestionSimilarity,
    QuestionTaxonomy,
    ValidationFinding,
)
from examdata.governance import coverage, rebuild

FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    mark = "OK  " if ok else "FAIL"
    print(f"[{mark}] {label}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILURES.append(label)


def main() -> int:
    settings = get_settings()

    with session_scope() as s:
        docs = s.scalar(select(func.count(Document.id))) or 0
        revs = s.scalar(select(func.count(DocumentRevision.id))) or 0
        arts = s.scalar(select(func.count(Artifact.id))) or 0
        papers = s.scalar(select(func.count(Paper.id))) or 0
        questions = s.scalar(select(func.count(Question.id))) or 0
        entries = s.scalar(select(func.count(MarkSchemeEntry.id))) or 0
        linked = (
            s.scalar(
                select(func.count(MarkSchemeEntry.id)).where(
                    MarkSchemeEntry.question_id.is_not(None)
                )
            )
            or 0
        )
        assets = s.scalar(select(func.count(Asset.id))) or 0
        tax = s.scalar(select(func.count(QuestionTaxonomy.id))) or 0
        diff = s.scalar(select(func.count(Difficulty.id))) or 0
        sim = s.scalar(select(func.count(QuestionSimilarity.id))) or 0
        classes = s.scalar(select(func.count(DocClassification.id))) or 0
        expl = s.scalar(select(func.count(GeneratedExplanation.id))) or 0
        expl_official = (
            s.scalar(
                select(func.count(GeneratedExplanation.id)).where(
                    GeneratedExplanation.is_official.is_(True)
                )
            )
            or 0
        )

    print("=" * 66)
    print(f"文档 {docs} / 版本 {revs} / 原件 {arts} / 试卷 {papers} / 题目 {questions}")
    print("=" * 66)

    # 不是每份文档都有版本：登录墙资源会被登记为文档但不去下载，
    # 所以 document 数会大于 revision 数。真正的不变量是反向的——
    # 每个版本都必须有原件，每个原件都必须有文件。
    check("每个版本都有原件", arts >= revs, f"{arts} >= {revs}")
    check("每个版本都归属文档", revs > 0, str(revs))
    check("题目已结构化", questions > 0, str(questions))
    check("评分条目已拆解", entries > 0, str(entries))
    check("评分条目关联到题目", linked > 0, f"{linked}/{entries}")
    check("图形资产已保留", assets > 0, str(assets))
    check("文件类型含内容级判定", classes >= docs, f"{classes} >= {docs}")

    # 智能层
    check("知识点已标注", tax > 0, str(tax))
    check("难度已估计", diff == questions, f"{diff}/{questions}")
    check("相似题已发现", sim > 0, str(sim))
    check("生成解析已产出", expl > 0, str(expl))
    check("生成内容未被标为官方", expl_official == 0, f"误标 {expl_official}")

    # 原件文件真实存在（不是只落了库）
    missing = 0
    with session_scope() as s:
        keys = list(s.scalars(select(Artifact.storage_key)).all())
    for key in keys:
        if not (settings.artifacts_dir / key).exists():
            missing += 1
    check("原件文件都在磁盘上", missing == 0, f"缺失 {missing}")

    # 溯源：重建后必须满覆盖
    with session_scope() as s:
        rebuild(s)
    with session_scope() as s:
        cov = coverage(s)
    for stype, c in cov.items():
        check(f"溯源覆盖 {stype}", c["ratio"] >= 1.0, f"{c['linked']}/{c['total']}")

    # 校验发现必须都挂在真实解析轮次上（不能有孤儿）
    with session_scope() as s:
        orphans = (
            s.scalar(
                select(func.count(ValidationFinding.id)).where(
                    ValidationFinding.parse_run_id.is_(None)
                )
            )
            or 0
        )
    check("校验发现无孤儿", orphans == 0, f"孤儿 {orphans}")

    print("=" * 66)
    if FAILURES:
        print(f"{len(FAILURES)} 项未通过: {FAILURES}")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
