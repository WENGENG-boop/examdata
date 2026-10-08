"""Dump parent-question context for pending low-confidence items (read-only)."""
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

PENDING = [68324, 68343, 68380, 68412, 68414, 68471, 68472, 68494, 68555, 68563, 68570]
EXTRA_SIBLINGS = True


def qdesc(session, q):
    paper = session.get(Paper, q.paper_id)
    doc = session.get(Document, paper.document_id) if paper else None
    return {
        "id": q.id,
        "path": q.number_path,
        "label": q.number_label,
        "marks": q.marks,
        "page": q.page_from,
        "parent_id": q.parent_id,
        "paper": doc.paper_code if doc else None,
        "stem": (q.stem_text or "")[:2000],
    }


def main() -> None:
    init_db()
    session: Session = get_session_factory()()
    out = []
    for qid in PENDING:
        q = session.get(Question, qid)
        if q is None:
            out.append({"question_id": qid, "missing": True})
            continue
        entry = {"question_id": qid, "self": qdesc(session, q)}
        # walk up the parent chain
        chain = []
        cur = q
        seen = set()
        while cur.parent_id and cur.parent_id not in seen:
            seen.add(cur.parent_id)
            p = session.get(Question, cur.parent_id)
            if p is None:
                break
            chain.append(qdesc(session, p))
            cur = p
        entry["ancestors"] = chain
        # siblings of the top ancestor (same parent)
        if chain:
            top = cur
            sibs = list(
                session.scalars(
                    select(Question).where(
                        Question.paper_id == top.paper_id,
                        Question.parent_id == top.parent_id,
                        Question.id != top.id,
                    ).order_by(Question.id)
                )
            )
            entry["top_siblings"] = [qdesc(session, s) for s in sibs]
        # tags of self
        tags = list(
            session.scalars(
                select(QuestionTaxonomy).where(QuestionTaxonomy.question_id == q.id)
            )
        )
        entry["self_tags"] = []
        for t in tags:
            node = session.get(TaxonomyNode, t.node_id)
            entry["self_tags"].append(
                {"code": node.code if node else None, "source": t.source, "conf": t.confidence}
            )
        out.append(entry)
    session.close()
    (ROOT / "tmp_r11_parent_ctx.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    # human readable
    lines = []
    for e in out:
        lines.append("=" * 100)
        if e.get("missing"):
            lines.append(f"q{e['question_id']} MISSING")
            continue
        s = e["self"]
        lines.append(f"q{s['id']} {s['paper']} path={s['path']} label={s['label']} marks={s['marks']} page={s['page']}")
        lines.append(f"-- tags: {[t['code'] for t in e['self_tags']]}")
        lines.append(f"-- SELF stem --\n{s['stem']}")
        for a in e["ancestors"]:
            lines.append(f"-- ANCESTOR q{a['id']} path={a['path']} label={a['label']} marks={a['marks']} page={a['page']} --\n{a['stem']}")
        if e.get("top_siblings"):
            lines.append(f"-- siblings of top ancestor ({len(e['top_siblings'])}) --")
            for sb in e["top_siblings"][:8]:
                lines.append(f"   q{sb['id']} {sb['label']} p{sb['page']}: {sb['stem'][:150].replace(chr(10),' | ')}")
        lines.append("")
    (ROOT / "tmp_r11_parent_ctx.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {len(out)} entries")


if __name__ == "__main__":
    main()
