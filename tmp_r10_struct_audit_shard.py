"""r10 structure audit, sharded: each shard scans docs where idx % nshards == shard.
Read-only. Writes tmp_r10_struct_audit_shard<N>.json / .out

Usage: ./.venv/Scripts/python.exe -X utf8 tmp_r10_struct_audit_shard.py --shard 0 --nshards 6
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from examdata.core.config import get_settings  # noqa: E402
from examdata.core.db import get_session_factory, init_db  # noqa: E402
from examdata.core.models import (  # noqa: E402
    Board,
    Document,
    DocumentRevision,
    Paper,
    Question,
)
from examdata.edexcel_papers.pipeline import (  # noqa: E402
    _artifact_path,
    build_question_tree,
)
from examdata.paperqa.locator import index_questions  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", type=int, required=True)
    ap.add_argument("--nshards", type=int, default=6)
    args = ap.parse_args()

    init_db()
    session = get_session_factory()()
    settings = get_settings()
    t0 = time.time()
    docs_all = session.scalars(
        select(Document)
        .join(Board, Board.id == Document.board_id)
        .where(
            Board.key == "edexcel",
            Document.doc_type.in_(("question_paper", "specimen_paper")),
        )
        .order_by(Document.id)
    ).all()
    docs = [d for i, d in enumerate(docs_all) if i % args.nshards == args.shard]
    report = []
    for i, doc in enumerate(docs):
        if (i + 1) % 100 == 0:
            print(f"  [s{args.shard}] ...{i+1}/{len(docs)} ({time.time()-t0:.0f}s)", flush=True)
        paper = session.scalar(select(Paper).where(Paper.document_id == doc.id))
        if paper is None:
            continue
        db_qs = list(
            session.scalars(
                select(Question)
                .where(Question.paper_id == paper.id)
                .order_by(Question.display_order)
            )
        )
        db_paths = [q.number_path for q in db_qs]
        rev = session.get(DocumentRevision, doc.current_revision_id) if doc.current_revision_id else None
        path = _artifact_path(session, settings, rev.artifact_id) if rev else None
        if path is None or not path.exists():
            report.append({"doc": doc.id, "title": doc.title, "error": "artifact missing"})
            continue
        try:
            data = path.read_bytes()
            nodes = build_question_tree(index_questions(data, "qp"))
            code_paths = [n["number_path"] for n in nodes]
        except Exception as exc:  # noqa: BLE001
            report.append({"doc": doc.id, "title": doc.title, "error": f"{type(exc).__name__}: {exc}"})
            continue
        if db_paths != code_paths:
            db_set, code_set = set(db_paths), set(code_paths)
            n_over = sum(1 for q in db_qs if q.has_override)
            fd = None
            for j in range(max(len(db_paths), len(code_paths))):
                a = db_paths[j] if j < len(db_paths) else None
                b = code_paths[j] if j < len(code_paths) else None
                if a != b:
                    fd = {"i": j, "db": a, "code": b}
                    break
            report.append({
                "doc": doc.id, "title": doc.title, "paper_id": paper.id,
                "db_n": len(db_paths), "code_n": len(code_paths),
                "db_only": [p for p in db_paths if p not in code_set][:12],
                "code_only": [p for p in code_paths if p not in db_set][:12],
                "first_div": fd,
                "overrides": n_over,
            })
    session.close()
    (ROOT / f"tmp_r10_struct_audit_shard{args.shard}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    changed = [r for r in report if "db_only" in r]
    errors = [r for r in report if "error" in r]
    lines = [f"shard={args.shard} docs scanned={len(docs)} mismatch={len(changed)} errors={len(errors)} time={time.time()-t0:.0f}s"]
    for r in sorted(changed, key=lambda x: x["doc"]):
        lines.append(
            f"doc {r['doc']} p{r['paper_id']} db_n={r['db_n']} code_n={r['code_n']} "
            f"over={r['overrides']} first_div={r['first_div']}")
        lines.append(f"   db_only={r['db_only']}")
        lines.append(f"   code_only={r['code_only']}")
        lines.append(f"   title={r['title'][:80]}")
    for r in errors:
        lines.append(f"ERROR doc {r['doc']} {r['title'][:70]}: {r['error']}")
    txt = "\n".join(lines)
    (ROOT / f"tmp_r10_struct_audit_shard{args.shard}.out").write_text(txt + "\n", encoding="utf-8")
    print(txt[:3000])


if __name__ == "__main__":
    main()
