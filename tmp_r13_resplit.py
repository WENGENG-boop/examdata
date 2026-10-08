"""r13 apply: id-preserving resplit of the 16 stale-structure WPS QP docs
(found by the r10 full-coverage structure audit). Machinery reused from r8 apply
(tmp_r8_apply.py); only the ParseRun fix label differs.

Phase A (per QP doc, one transaction):
  - recompute the question tree with the patched locator;
  - match old DB questions to new nodes by region position (page, y0 +- TOL);
  - matched: UPDATE fields in place (question ids preserved);
  - unmatched new: INSERT (parent_id fixed in a second pass);
  - unmatched old: DELETE (+ taxonomy / MS entries / provenance / similarity refs);
  - refresh provenance_edge for all kept questions, update paper counts, write ParseRun.

Phase B: force-resplit every MS doc matched to an affected QP doc (id-preserving for QP,
  full rebuild for the MS side, same as the normal pipeline).
Phase C: rebuild_official_answers for the resplit MS docs.
Phase D: BM25 taxonomy for newly inserted questions (low-confidence list dumped for
  follow-up self-review).

Usage:
  ./.venv/Scripts/python.exe -X utf8 tmp_r13_resplit.py --scan tmp_r13_scan.json           # dry run
  ./.venv/Scripts/python.exe -X utf8 tmp_r13_resplit.py --scan tmp_r13_scan.json --doc 3555
  ./.venv/Scripts/python.exe -X utf8 tmp_r13_resplit.py --scan tmp_r13_scan.json --write
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pymupdf
from sqlalchemy import delete, select

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from examdata.core.config import get_settings  # noqa: E402
from examdata.core.db import (  # noqa: E402
    enable_immediate_writes,
    get_session_factory,
    init_db,
    with_lock_retry,
)
from examdata.core.models import (  # noqa: E402
    Artifact,
    Document,
    DocumentRevision,
    MarkScheme,
    MarkSchemeEntry,
    Paper,
    ParseRun,
    ProvenanceEdge,
    Question,
    QuestionTaxonomy,
    Subject,
    ValidationFinding,
    ReviewTask,
)  # noqa: E402
from examdata.edexcel_papers.pipeline import (  # noqa: E402
    DOC_MARK_SCHEME,
    DOC_QUESTION_PAPER,
    PARSER_VERSION,
    SplitSummary,
    _artifact_path,
    _lookup_qp,
    _paper_code_of,
    _question_marks,
    _region_text,
    _split_ms,
    build_question_tree,
)
from examdata.paperqa.locator import index_questions, is_ciphered  # noqa: E402

ROOT = Path(__file__).resolve().parent
TOL = 8.0


def _now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


def build_new_tree(data: bytes):
    nodes = build_question_tree(index_questions(data, "qp"))
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        page_count = len(pdf)
        ciphered = is_ciphered(pdf)
        texts = {
            n["number_path"]: _region_text(pdf, n["regions"], ciphered=ciphered) for n in nodes
        }
        marks = _question_marks(pdf, nodes, texts, ciphered=ciphered)
    return nodes, texts, marks, page_count


def _qp_doc_surgery(session, settings, doc_id: int, write: bool, applied: list) -> None:
    doc = session.get(Document, doc_id)
    if doc is None or doc.current_revision_id is None:
        applied.append({"doc": doc_id, "error": "no revision"})
        return
    revision = session.get(DocumentRevision, doc.current_revision_id)
    paper = session.scalar(select(Paper).where(Paper.document_id == doc_id))
    if paper is None:
        applied.append({"doc": doc_id, "error": "no paper"})
        return
    old_qs = list(
        session.scalars(
            select(Question).where(Question.paper_id == paper.id).order_by(Question.display_order)
        )
    )
    path = _artifact_path(session, settings, revision.artifact_id)
    if path is None:
        applied.append({"doc": doc_id, "error": "artifact missing"})
        return
    data = path.read_bytes()
    nodes, texts, marks, page_count = build_new_tree(data)

    # ---- match old questions to new nodes by (page, y0 +- TOL) ----
    new_items = []
    for n in nodes:
        reg = n["regions"][0]
        new_items.append(
            {"path": n["number_path"], "page": reg["page"], "y": reg["bbox"][1], "used": False}
        )
    matched: list[tuple[Question, int]] = []
    deleted: list[Question] = []
    for q in old_qs:
        bf = q.bbox_from
        page, y = q.page_from, (bf[1] if bf else None)
        best = None
        if page is not None and y is not None:
            for idx, it in enumerate(new_items):
                if it["used"] or it["page"] != page:
                    continue
                d = abs(it["y"] - y)
                if d <= TOL and (best is None or d < best[0]):
                    best = (d, idx)
        if best is not None:
            new_items[best[1]]["used"] = True
            matched.append((q, best[1]))
        else:
            deleted.append(q)
    inserted_idx = [idx for idx, it in enumerate(new_items) if not it["used"]]

    order_of = {n["number_path"]: i for i, n in enumerate(nodes)}
    entry = {
        "doc": doc_id,
        "title": doc.title,
        "paper_id": paper.id,
        "n_old_q": len(old_qs),
        "n_new_nodes": len(nodes),
        "matched": len(matched),
        "relabeled": [
            {"qid": q.id, "old": q.number_path, "new": nodes[idx]["number_path"]}
            for q, idx in matched
            if q.number_path != nodes[idx]["number_path"]
        ],
        "deleted": [
            {
                "qid": q.id,
                "path": q.number_path,
                "page": q.page_from,
                "marks": q.marks,
                "stem": (q.stem_text or "")[:80],
            }
            for q in deleted
        ],
        "inserted": [
            {
                "path": new_items[idx]["path"],
                "page": new_items[idx]["page"],
                "y": round(new_items[idx]["y"], 1),
                "marks": marks.get(new_items[idx]["path"]),
                "stem": (texts.get(new_items[idx]["path"]) or "")[:80],
            }
            for idx in inserted_idx
        ],
    }
    if not write:
        entry["dry"] = True
        applied.append(entry)
        return

    # ---------------- write path ----------------
    subject = session.get(Subject, doc.subject_id)
    subject_code = subject.code if subject is not None else None
    unit_code = (paper.attrs or {}).get("unit_code")
    if not unit_code:
        from examdata.edexcel_papers.pipeline import derive_paper_code

        unit_code = derive_paper_code(revision.source_url or "")[1]
    artifact = session.get(Artifact, revision.artifact_id)
    sha256 = artifact.sha256 if artifact is not None else ""

    run = ParseRun(
        document_revision_id=revision.id,
        parser_version=PARSER_VERSION,
        params={"doc_type": DOC_QUESTION_PAPER, "subject": subject_code, "fix": "r13-wps-stale-structure"},
        status="running",
        started_at=_now(),
        stats={},
    )
    session.add(run)
    session.flush()

    # 1) insert new questions (parent_id filled in the second pass)
    inserted_qids = []
    for idx in inserted_idx:
        node = next(n for n in nodes if n["number_path"] == new_items[idx]["path"])
        regs = node["regions"]
        first = regs[0] if regs else {}
        last = regs[-1] if regs else {}
        q = Question(
            paper_id=paper.id,
            parent_id=None,
            number_label=node["number_label"][:64],
            number_path=node["number_path"][:128],
            display_order=order_of[node["number_path"]],
            depth=node["depth"],
            kind=node["kind"],
            marks=marks.get(node["number_path"]),
            page_from=first.get("page"),
            page_to=last.get("page"),
            bbox_from=list(first["bbox"]) if first.get("bbox") else None,
            bbox_to=list(last["bbox"]) if last.get("bbox") else None,
            stem_text=texts.get(node["number_path"]) or None,
            parse_run_id=run.id,
            parse_confidence=1.0,
            has_override=False,
            attrs={"regions": regs, "unit_code": unit_code},
        )
        session.add(q)
        session.flush()
        inserted_qids.append(q.id)

    # 2) update matched questions in place
    path_to_qid: dict[str, int] = {}
    for q, idx in matched:
        node = nodes[idx]
        path_key = node["number_path"]
        path_to_qid[path_key] = q.id
        regs = node["regions"]
        first = regs[0] if regs else {}
        last = regs[-1] if regs else {}
        attrs = dict(q.attrs or {})
        attrs["regions"] = regs
        if unit_code:
            attrs["unit_code"] = unit_code
        q.number_label = node["number_label"][:64]
        q.number_path = path_key[:128]
        q.display_order = order_of[path_key]
        q.depth = node["depth"]
        q.kind = node["kind"]
        q.marks = marks.get(path_key)
        q.page_from = first.get("page")
        q.page_to = last.get("page")
        q.bbox_from = list(first["bbox"]) if first.get("bbox") else None
        q.bbox_to = list(last["bbox"]) if last.get("bbox") else None
        q.stem_text = texts.get(path_key) or None
        q.parse_run_id = run.id
        q.parse_confidence = 1.0
        q.attrs = attrs
    session.flush()

    # complete path -> qid map with inserted questions
    for qid, node_path in zip(inserted_qids, [new_items[i]["path"] for i in inserted_idx]):
        path_to_qid[node_path] = qid

    # 3) second pass: parent_id for every kept node
    for node in nodes:
        qid = path_to_qid.get(node["number_path"])
        if qid is None:
            continue
        parent_qid = path_to_qid.get(node["parent_path"]) if node["parent_path"] else None
        session.execute(
            Question.__table__.update()
            .where(Question.id == qid)
            .values(parent_id=parent_qid)
        )
    session.flush()

    # 4) delete unmatched old questions (children first)
    del_ids = [q.id for q in deleted]
    if del_ids:
        session.execute(
            delete(QuestionTaxonomy).where(QuestionTaxonomy.question_id.in_(del_ids))
        )
        session.execute(
            delete(MarkSchemeEntry).where(MarkSchemeEntry.question_id.in_(del_ids))
        )
        session.execute(
            delete(ValidationFinding).where(
                ValidationFinding.subject_type == "question",
                ValidationFinding.subject_id.in_(del_ids),
            )
        )
        session.execute(
            delete(ReviewTask).where(
                ReviewTask.target_type == "question",
                ReviewTask.target_id.in_(del_ids),
            )
        )
        from examdata.core.models import QuestionSimilarity

        session.execute(
            delete(QuestionSimilarity).where(
                QuestionSimilarity.question_a_id.in_(del_ids)
                | QuestionSimilarity.question_b_id.in_(del_ids)
            )
        )
        session.execute(
            delete(ProvenanceEdge).where(
                ProvenanceEdge.subject_type == "question",
                ProvenanceEdge.subject_id.in_(del_ids),
            )
        )
        for depth in sorted({q.depth for q in deleted}, reverse=True):
            ids = [q.id for q in deleted if q.depth == depth]
            session.execute(delete(Question).where(Question.id.in_(ids)))

    # 5) refresh provenance for all kept questions
    old_ids = [q.id for q in old_qs]
    if old_ids:
        session.execute(
            delete(ProvenanceEdge).where(
                ProvenanceEdge.subject_type == "question",
                ProvenanceEdge.subject_id.in_(old_ids),
            )
        )
    for node in nodes:
        qid = path_to_qid.get(node["number_path"])
        if qid is None:
            continue
        session.add(
            ProvenanceEdge(
                subject_type="question",
                subject_id=qid,
                source_kind="official_resource",
                source_ref=f"document:{doc_id}#{node['number_path']}",
                source_url=revision.source_url,
                run_id=run.id,
                attrs={
                    "document_id": doc_id,
                    "revision_id": revision.id,
                    "artifact_sha256": sha256,
                    "number_path": node["number_path"],
                    "paper_id": paper.id,
                },
            )
        )

    # 6) paper counts + run/revision/document status
    depth0 = [n for n in nodes if n["depth"] == 0]
    paper.question_count = len(depth0)
    paper.marks_total = sum(
        v for n in depth0 if (v := marks.get(n["number_path"])) is not None
    )
    paper.parse_run_id = run.id
    paper.page_count = page_count
    run.status = "completed"
    run.finished_at = _now()
    run.stats = {
        "questions": len(nodes),
        "inserted": len(inserted_qids),
        "deleted": len(del_ids),
        "relabeled": len(entry["relabeled"]),
        "page_count": page_count,
    }
    revision.parse_status = "parsed"
    revision.parse_error = None
    doc.status = "ok"
    session.commit()

    entry["inserted_qids"] = inserted_qids
    entry["run_id"] = run.id
    applied.append(entry)


def _assign_new_questions(session, qids: list[int]) -> dict:
    """BM25-assign taxonomy rows for the given questions (mirrors tagging.assign.assign)."""
    from examdata.tagging.assign import (
        ASSIGNED_BY,
        DEFAULT_MIN_SCORE,
        LOW_CONFIDENCE,
        SOURCE,
        rank_question,
        select_tags,
    )
    from examdata.tagging.corpus import (
        CorpusSet,
        QuestionRef,
        load_points,
        unit_code_from_paper,
    )

    stats = {"scanned": 0, "tagged": 0, "rows": 0, "unassigned": 0, "skipped_empty": 0, "low_conf": []}
    points = load_points(session, board_key="edexcel")
    if not points:
        return stats
    corpora = CorpusSet(points)
    stmt = (
        select(
            Question.id,
            Question.number_label,
            Question.stem_text,
            Document.paper_code,
            Paper.attrs,
            Subject.code,
            Subject.slug,
        )
        .join(Paper, Paper.id == Question.paper_id)
        .join(Document, Document.id == Paper.document_id)
        .join(Subject, Subject.id == Document.subject_id, isouter=True)
        .where(Question.id.in_(qids))
        .order_by(Question.id)
    )
    for qid, number_label, stem, paper_code, paper_attrs, subject_code, subject_slug in session.execute(stmt):
        stats["scanned"] += 1
        ref = QuestionRef(
            question_id=qid,
            number_label=number_label or "",
            stem_text=stem or "",
            paper_code=paper_code,
            subject_code=subject_code,
            subject_slug=subject_slug,
            unit_code=unit_code_from_paper(paper_attrs, paper_code),
        )
        if not ref.stem_text.strip():
            stats["skipped_empty"] += 1
            continue
        subject_key, candidates = rank_question(corpora, ref)
        if subject_key is None or not candidates:
            stats["unassigned"] += 1
            continue
        chosen = select_tags(candidates, min_score=DEFAULT_MIN_SCORE)
        written: set[int] = set()
        for cand in chosen:
            if cand.node_id in written:
                continue
            written.add(cand.node_id)
            session.add(
                QuestionTaxonomy(
                    question_id=qid,
                    node_id=cand.node_id,
                    source=SOURCE,
                    confidence=cand.confidence,
                    assigned_by=ASSIGNED_BY,
                    reviewed=False,
                )
            )
            stats["rows"] += 1
        stats["tagged"] += 1
        if candidates[0].confidence < LOW_CONFIDENCE:
            stats["low_conf"].append(
                {
                    "question_id": qid,
                    "number_label": ref.number_label,
                    "paper_code": paper_code,
                    "subject": subject_key,
                    "unit_code": ref.unit_code,
                    "top_confidence": candidates[0].confidence,
                    "candidates": [
                        {"code": c.code, "name": c.name, "score": c.score, "confidence": c.confidence}
                        for c in candidates
                    ],
                }
            )
    return stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--doc", type=int, default=0, help="only this doc id")
    ap.add_argument("--limit", type=int, default=0, help="only the first N docs")
    ap.add_argument("--exclude", type=str, default="", help="comma-separated doc ids to skip")
    ap.add_argument("--scan", type=str, default="tmp_r8_scan3.json", help="scan json to read")
    ap.add_argument("--out-prefix", type=str, default="tmp_r8", help="prefix for output files")
    args = ap.parse_args()
    write = args.write
    excluded = {int(x) for x in args.exclude.split(",") if x.strip()}
    out_prefix = args.out_prefix

    changed = json.load(open(ROOT / args.scan, encoding="utf-8"))
    docs = [r for r in changed if "old_only" in r or "db_only" in r]
    if args.doc:
        docs = [r for r in docs if r["doc"] == args.doc]
    if excluded:
        docs = [r for r in docs if r["doc"] not in excluded]
    if args.limit:
        docs = docs[: args.limit]
    print(f"docs to process: {len(docs)} write={write}", flush=True)

    enable_immediate_writes()
    init_db()
    session = get_session_factory()()
    settings = get_settings()

    applied: list = []
    t0 = time.time()
    out_path = ROOT / f"{out_prefix}_applied.jsonl"
    out = open(out_path, "a" if write else "w", encoding="utf-8")
    try:
        # ---------- Phase A: QP surgery ----------
        for i, r in enumerate(docs):
            doc_id = r["doc"]
            try:
                with_lock_retry(
                    session,
                    lambda: _qp_doc_surgery(session, settings, doc_id, write, applied),
                )
            except Exception as exc:
                session.rollback()
                applied.append({"doc": doc_id, "error": f"{type(exc).__name__}: {exc}"})
                print(f"  !! doc {doc_id}: {type(exc).__name__}: {exc}", flush=True)
            else:
                e = applied[-1]
                if "error" not in e:
                    print(
                        f"  doc {e['doc']}: matched={e['matched']} del={len(e['deleted'])} "
                        f"ins={len(e['inserted'])} relabel={len(e['relabeled'])}"
                        + ("" if write else " [dry]"),
                        flush=True,
                    )
            if write:
                out.write(json.dumps(applied[-1], ensure_ascii=False) + "\n")
                out.flush()
            if (i + 1) % 10 == 0:
                print(f"  QP {i+1}/{len(docs)} ({time.time()-t0:.0f}s)", flush=True)
        print(f"Phase A done ({time.time()-t0:.0f}s)", flush=True)

        if not write:
            # dry-run: report what phase B would do, stop here
            affected = [a["doc"] for a in applied if "error" not in a]
            ms_ids = _ms_targets(session, affected)
            (ROOT / f"{out_prefix}_dry.json").write_text(
                json.dumps(applied, ensure_ascii=False, indent=1), encoding="utf-8"
            )
            print(f"Phase B would resplit {len(ms_ids)} MS docs (dry run)", flush=True)
            print(f"DRY RUN done docs={len(applied)} ({time.time()-t0:.0f}s)", flush=True)
            return

        # ---------- Phase B: MS force resplit ----------
        affected = [a["doc"] for a in applied if "error" not in a]
        ms_ids = _ms_targets(session, affected)
        print(f"Phase B: {len(ms_ids)} MS docs to resplit", flush=True)

        subject_ids = set()
        for d in affected:
            doc = session.get(Document, d)
            if doc is not None:
                subject_ids.add(doc.subject_id)
        qp_index: dict = {}
        for subj_id in subject_ids:
            for qp_doc in session.scalars(
                select(Document).where(
                    Document.subject_id == subj_id, Document.doc_type == DOC_QUESTION_PAPER
                )
            ):
                if qp_doc.current_revision_id is None:
                    continue
                rev = session.get(DocumentRevision, qp_doc.current_revision_id)
                code = _paper_code_of(qp_doc, rev)
                if code:
                    qp_index[(qp_doc.subject_id, qp_doc.series_id, code)] = qp_doc

        summary = SplitSummary()
        cache: dict = {}
        ms_ok: list[int] = []
        for i, ms_id in enumerate(ms_ids):
            ms_doc = session.get(Document, ms_id)
            subject = session.get(Subject, ms_doc.subject_id)
            slug = subject.code if subject is not None else None
            if not slug:
                print(f"  !! MS doc {ms_id}: no subject code", flush=True)
                continue
            before_failed = summary.failed
            try:
                with_lock_retry(
                    session,
                    lambda: _split_ms(
                        session, settings, ms_doc, qp_index, summary, cache, force=True, slug=slug
                    ),
                )
            except Exception as exc:
                session.rollback()
                summary.failed += 1
                summary.errors.append(f"document {ms_id}: {exc}")
                print(f"  !! MS doc {ms_id}: {type(exc).__name__}: {exc}", flush=True)
                continue
            if summary.failed == before_failed:
                ms_ok.append(ms_id)
            if (i + 1) % 10 == 0:
                print(f"  MS {i+1}/{len(ms_ids)} ({time.time()-t0:.0f}s)", flush=True)
        print(
            f"Phase B done: ok={len(ms_ok)} failed={summary.failed} entries={summary.ms_entries} "
            f"({time.time()-t0:.0f}s)",
            flush=True,
        )
        for err in summary.errors:
            print(f"  MS error: {err}", flush=True)

        # ---------- Phase C: rebuild official answers ----------
        n_ans = 0
        if ms_ok:
            for chunk in [ms_ok[i : i + 50] for i in range(0, len(ms_ok), 50)]:
                n_ans += _rebuild_answers(session, chunk)
        print(f"Phase C done: official_answers written={n_ans} ({time.time()-t0:.0f}s)", flush=True)

        # ---------- Phase D: tag newly inserted questions ----------
        new_qids = [qid for a in applied if "error" not in a for qid in a.get("inserted_qids", [])]
        print(f"Phase D: new questions to tag = {len(new_qids)}", flush=True)
        d_stats = _assign_new_questions(session, new_qids) if new_qids else {}
        if new_qids:
            session.commit()
        print(
            f"Phase D done: {json.dumps({k: v for k, v in d_stats.items() if k != 'low_conf'}, ensure_ascii=False)}",
            flush=True,
        )
        if d_stats.get("low_conf"):
            (ROOT / f"{out_prefix}_new_lowconf.json").write_text(
                json.dumps(d_stats["low_conf"], ensure_ascii=False, indent=1), encoding="utf-8"
            )
            print(f"  low-confidence new questions: {len(d_stats['low_conf'])}", flush=True)

        summary_out = {
            "write": True,
            "docs": len(applied),
            "errors": [a for a in applied if "error" in a],
            "qp": {
                "matched": sum(a.get("matched", 0) for a in applied),
                "deleted": sum(len(a.get("deleted", [])) for a in applied),
                "inserted": sum(len(a.get("inserted", [])) for a in applied),
                "relabeled": sum(len(a.get("relabeled", [])) for a in applied),
            },
            "ms_docs_ok": len(ms_ok),
            "ms_entries": summary.ms_entries,
            "official_answers": n_ans,
            "new_questions_tagged": d_stats.get("tagged"),
            "new_questions_rows": d_stats.get("rows"),
            "new_questions_low_conf": len(d_stats.get("low_conf", [])),
            "seconds": round(time.time() - t0, 1),
        }
        (ROOT / f"{out_prefix}_apply_summary.json").write_text(
            json.dumps(summary_out, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(f"ALL DONE {json.dumps(summary_out, ensure_ascii=False)}", flush=True)
    finally:
        out.close()
        session.close()


def _rebuild_answers(session, chunk: list[int]) -> int:
    from examdata.markscheme.answers import rebuild_official_answers

    n = rebuild_official_answers(session, document_ids=chunk)
    session.commit()
    return n


def _ms_targets(session, affected: list[int]) -> list[int]:
    """MS docs to resplit: directly matched to affected QP docs, or resolving to them."""
    if not affected:
        return []
    affected_set = set(affected)
    direct = set(
        session.scalars(
            select(MarkScheme.document_id)
            .where(MarkScheme.matched_paper_document_id.in_(affected))
            .distinct()
        )
    )
    subject_ids = set()
    for d in affected:
        doc = session.get(Document, d)
        if doc is not None:
            subject_ids.add(doc.subject_id)
    # qp_index over the affected subjects (all QP docs), same as split_subject
    qp_index: dict = {}
    for subj_id in subject_ids:
        for qp_doc in session.scalars(
            select(Document).where(
                Document.subject_id == subj_id, Document.doc_type == DOC_QUESTION_PAPER
            )
        ):
            if qp_doc.current_revision_id is None:
                continue
            rev = session.get(DocumentRevision, qp_doc.current_revision_id)
            code = _paper_code_of(qp_doc, rev)
            if code:
                qp_index[(qp_doc.subject_id, qp_doc.series_id, code)] = qp_doc
    via_lookup = set()
    for ms_doc in session.scalars(
        select(Document).where(
            Document.doc_type == DOC_MARK_SCHEME, Document.subject_id.in_(subject_ids)
        )
    ):
        if ms_doc.current_revision_id is None:
            continue
        rev = session.get(DocumentRevision, ms_doc.current_revision_id)
        code = _paper_code_of(ms_doc, rev)
        qp_doc, _conf, _method = _lookup_qp(qp_index, ms_doc, code)
        if qp_doc is not None and qp_doc.id in affected_set:
            via_lookup.add(ms_doc.id)
    return sorted(direct | via_lookup)


if __name__ == "__main__":
    main()
