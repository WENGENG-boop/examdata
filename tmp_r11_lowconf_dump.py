"""Dump full details for the r8 low-confidence new questions (read-only).

Reads tmp_r8_new_lowconf.json, joins DB for stem/tags, writes:
  tmp_r11_lowconf_review.txt  (human-readable, for manual review)
  tmp_r11_lowconf_review.json (full detail)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from examdata.core.db import get_session_factory, init_db  # noqa: E402
from examdata.core.models import (  # noqa: E402
    Document,
    Paper,
    Question,
    QuestionTaxonomy,
    Subject,
    TaxonomyNode,
)


def main() -> None:
    init_db()
    session: Session = get_session_factory()()
    low = json.load(open(ROOT / "tmp_r8_new_lowconf.json", encoding="utf-8"))
    qids = [e["question_id"] for e in low]
    rows = []
    for e in low:
        q = session.get(Question, e["question_id"])
        if q is None:
            rows.append({**e, "missing_in_db": True})
            continue
        paper = session.get(Paper, q.paper_id)
        doc = session.get(Document, paper.document_id) if paper else None
        subject = session.get(Subject, doc.subject_id) if doc else None
        tags = list(
            session.scalars(
                select(QuestionTaxonomy).where(QuestionTaxonomy.question_id == q.id)
            )
        )
        tag_detail = []
        for t in tags:
            node = session.get(TaxonomyNode, t.node_id)
            tag_detail.append(
                {
                    "node_id": t.node_id,
                    "code": node.code if node else None,
                    "name": node.name if node else None,
                    "source": t.source,
                    "confidence": t.confidence,
                    "assigned_by": t.assigned_by,
                    "reviewed": t.reviewed,
                }
            )
        rows.append(
            {
                "question_id": q.id,
                "number_label": q.number_label,
                "number_path": q.number_path,
                "marks": q.marks,
                "page_from": q.page_from,
                "paper_code": doc.paper_code if doc else None,
                "unit_code": (paper.attrs or {}).get("unit_code") if paper else None,
                "subject": subject.code if subject else None,
                "subject_slug": subject.slug if subject else None,
                "stem_text": q.stem_text,
                "current_tags": tag_detail,
                "candidates": e.get("candidates"),
                "top_confidence": e.get("top_confidence"),
            }
        )
    session.close()
    (ROOT / "tmp_r11_lowconf_review.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    lines = [f"total={len(rows)}"]
    for r in rows:
        if r.get("missing_in_db"):
            lines.append(f"q{r['question_id']} MISSING IN DB (from {r.get('paper_code')})")
            continue
        lines.append("=" * 100)
        lines.append(
            f"q{r['question_id']} {r['subject']}/{r['paper_code']} unit={r['unit_code']} "
            f"label={r['number_label']} marks={r['marks']} page={r['page_from']} "
            f"top_conf={r['top_confidence']}"
        )
        lines.append("-- current tags --")
        for t in r["current_tags"]:
            lines.append(
                f"   [{t['source']}] {t['code']} {t['name']} conf={t['confidence']} "
                f"by={t['assigned_by']} reviewed={t['reviewed']}"
            )
        lines.append("-- candidates --")
        for c in r["candidates"] or []:
            lines.append(f"   {c['code']} {c['name']} score={c['score']} conf={c['confidence']}")
        lines.append("-- stem --")
        stem = (r["stem_text"] or "").replace("\r", "")
        lines.append(stem[:1500])
        lines.append("")
    (ROOT / "tmp_r11_lowconf_review.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {len(rows)} entries to tmp_r11_lowconf_review.txt/.json")


if __name__ == "__main__":
    main()
