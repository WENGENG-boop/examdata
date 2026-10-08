"""r13 recheck: verify the 16 resplit WPS docs' DB question paths match the
artifact-derived question tree exactly. Read-only.

Usage: ./.venv/Scripts/python.exe -X utf8 tmp_r13_recheck.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import select  # noqa: E402

from examdata.core.config import get_settings  # noqa: E402
from examdata.core.db import get_session_factory, init_db  # noqa: E402
from examdata.core.models import (  # noqa: E402
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
    init_db()
    session = get_session_factory()()
    settings = get_settings()
    t0 = time.time()
    scan = json.loads((ROOT / "tmp_r13_scan.json").read_text(encoding="utf-8"))
    doc_ids = [int(e["doc"]) for e in scan]
    print(f"docs to recheck: {len(doc_ids)}", flush=True)
    report = []
    for doc_id in doc_ids:
        doc = session.get(Document, doc_id)
        if doc is None:
            report.append({"doc": doc_id, "error": "document missing"})
            continue
        paper = session.scalar(select(Paper).where(Paper.document_id == doc.id))
        if paper is None:
            report.append({"doc": doc.id, "title": doc.title, "error": "paper missing"})
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
        entry = {
            "doc": doc.id,
            "title": doc.title,
            "paper_id": paper.id,
            "db_n": len(db_paths),
            "code_n": len(code_paths),
            "match": db_paths == code_paths,
        }
        if db_paths != code_paths:
            db_set, code_set = set(db_paths), set(code_paths)
            fd = None
            for j in range(max(len(db_paths), len(code_paths))):
                a = db_paths[j] if j < len(db_paths) else None
                b = code_paths[j] if j < len(code_paths) else None
                if a != b:
                    fd = {"i": j, "db": a, "code": b}
                    break
            entry.update({
                "db_only": [p for p in db_paths if p not in code_set][:12],
                "code_only": [p for p in code_paths if p not in db_set][:12],
                "first_div": fd,
            })
        report.append(entry)
    session.close()
    (ROOT / "tmp_r13_recheck.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = [r for r in report if r.get("match")]
    bad = [r for r in report if not r.get("match")]
    errs = [r for r in report if "error" in r]
    lines = [f"docs={len(report)} match={len(ok)} mismatch={len(bad)} errors={len(errs)} time={time.time()-t0:.0f}s"]
    for r in bad:
        lines.append(
            f"doc {r['doc']} p{r.get('paper_id')} db_n={r.get('db_n')} code_n={r.get('code_n')} "
            f"first_div={r.get('first_div')}")
        lines.append(f"   db_only={r.get('db_only')}")
        lines.append(f"   code_only={r.get('code_only')}")
        lines.append(f"   title={r.get('title','')[:80]}")
    for r in errs:
        lines.append(f"ERROR doc {r['doc']} {r.get('title','')[:70]}: {r['error']}")
    txt = "\n".join(lines)
    (ROOT / "tmp_r13_recheck.out").write_text(txt + "\n", encoding="utf-8")
    print(txt[:4000])


if __name__ == "__main__":
    main()
