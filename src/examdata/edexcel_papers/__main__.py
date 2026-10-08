"""Edexcel IAL 试卷管道命令行。

    python -m examdata.edexcel_papers enumerate --subject ial18-biology
    python -m examdata.edexcel_papers run --subject ial18-biology --series "june 2024"
    python -m examdata.edexcel_papers split --subject ial18-biology --force
    python -m examdata.edexcel_papers report --subject ial18-biology --json

``--series`` 接受 "June 2024" / "June-2024" / "june 2024" 三种写法，
内部统一归一到 "june 2024"。``run`` 缺 catalog 时会先自动枚举一次。
退出码：任一科目报错或有资源/切分失败时为 1。
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Any, Optional

from sqlalchemy import func, select

from ..adapters.edexcel.classify import (
    DOC_MARK_SCHEME,
    DOC_QUESTION_PAPER,
    normalize_exam_series,
)
from ..core.config import get_settings
from ..core.db import (
    enable_immediate_writes,
    get_session_factory,
    init_db,
    with_lock_retry,
)
from ..core.fetch import Fetcher
from ..core.models import (
    Board,
    Document,
    DocumentRevision,
    MarkScheme,
    Paper,
    ParseRun,
    Question,
    QuestionTaxonomy,
    Subject,
    TaxonomyNode,
)
from .enumerate import (
    IAL_SUBJECTS,
    catalog_path,
    catalog_resources,
    enumerate_subject,
    load_catalog,
    save_catalog,
    syllabus_ref,
)
from .pipeline import (
    PARSER_VERSION,
    PdfGuardFetcher,
    split_subject,
    sync_resources,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m examdata.edexcel_papers",
        description="Edexcel IAL 试卷管道（枚举 / 下载 / 切分 / 报告）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_enum = sub.add_parser("enumerate", help="查询 Pearson servlet 并落 catalog")
    _add_subjects(p_enum)
    p_enum.add_argument("--limit", type=int, default=None, help="只保留前 N 个资源")
    p_enum.add_argument("--json", action="store_true")

    p_run = sub.add_parser("run", help="下载 + 切分")
    _add_subjects(p_run)
    p_run.add_argument("--series", default=None, help='考季，如 "june 2024"')
    p_run.add_argument("--limit", type=int, default=None, help="试跑：限制资源/文档数")
    p_run.add_argument("--refresh", action="store_true", help="强制重新下载（不重切分）")
    p_run.add_argument("--no-download", action="store_true", help="只登记不下载")
    p_run.add_argument("--json", action="store_true")

    p_split = sub.add_parser("split", help="只切分已下载的卷（不联网）")
    _add_subjects(p_split)
    p_split.add_argument("--series", default=None)
    p_split.add_argument("--limit", type=int, default=None)
    p_split.add_argument("--force", action="store_true", help="删掉本模块的派生数据重切")
    p_split.add_argument("--json", action="store_true")

    p_report = sub.add_parser("report", help="按科目汇总统计")
    _add_subjects(p_report)
    p_report.add_argument("--json", action="store_true")
    return parser


def _add_subjects(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--subject",
        action="append",
        default=None,
        metavar="SLUG",
        help="可重复；默认全部 21 个 IAL 科目",
    )


def _subjects(args: argparse.Namespace) -> list[str]:
    chosen = args.subject or list(IAL_SUBJECTS)
    unknown = [slug for slug in chosen if slug not in IAL_SUBJECTS]
    if unknown:
        raise SystemExit(
            "unknown subject slug(s): "
            + ", ".join(unknown)
            + "\nvalid slugs: "
            + ", ".join(sorted(IAL_SUBJECTS))
        )
    return chosen


def _sync_line(sync: Any) -> str:
    return (
        f"sync: created={sync.created} revision={sync.revision} unchanged={sync.unchanged} "
        f"skipped={sync.skipped} gated={sync.gated} robots={sync.robots} failed={sync.failed}"
    )


def _split_line(split: Any) -> str:
    return (
        f"split: papers={split.papers} questions={split.questions} ms={split.mark_schemes} "
        f"entries={split.ms_entries} ms_matched={split.ms_matched} "
        f"ms_unmatched={split.ms_unmatched} skipped={split.skipped} "
        f"conflicts={split.conflicts} failed={split.failed}"
    )


def _retry_locked(session: Any, action: Any) -> Any:
    """顶层锁重试：兜住 split_subject/sync_resources 内部未包裹查询的锁竞争。

    单条文档的切分已有 with_lock_retry；长事务下 busy_timeout 仍可能耗尽，
    此时按科目整体重试（跳过逻辑保证重试幂等、代价低）。
    """
    return with_lock_retry(
        session, action, attempts=10, base_delay=0.5, max_delay=10.0
    )


def _run_enumerate(args: argparse.Namespace, session: Any, fetcher: Fetcher) -> tuple[list[dict], list[str]]:
    settings = get_settings()
    payload: list[dict[str, Any]] = []
    failed: list[str] = []
    for slug in _subjects(args):
        try:
            catalog = enumerate_subject(fetcher, slug, limit=args.limit)
        except Exception as exc:
            failed.append(slug)
            payload.append({"slug": slug, "error": str(exc)})
            print(f"[enumerate] {slug}: ERROR {exc}", file=sys.stderr)
            continue
        path = save_catalog(catalog, settings)
        counts = catalog["counts"]
        payload.append(
            {
                "slug": slug,
                "query_mode": catalog["query_mode"],
                "tags_source": catalog["tags_source"],
                "spec_variants": catalog["spec_variants"],
                "counts": counts,
                "notes": catalog["notes"],
                "catalog": str(path),
            }
        )
        print(
            f"[enumerate] {slug}: mode={catalog['query_mode']} tags={catalog['tags_source']} "
            f"records={counts['records']} QP={counts['question_papers']} "
            f"MS={counts['mark_schemes']} gated={counts['gated']} -> {path}"
        )
        if args.limit and counts["resources"] >= args.limit:
            print(f"[enumerate] {slug}: limited to {args.limit} resources", file=sys.stderr)
    return payload, failed


def _run_pipeline(args: argparse.Namespace, session: Any, fetcher: Fetcher) -> tuple[list[dict], list[str]]:
    settings = get_settings()
    series = normalize_exam_series(args.series) if args.series else None
    guard = PdfGuardFetcher(settings)
    payload: list[dict[str, Any]] = []
    failed: list[str] = []
    try:
        for slug in _subjects(args):
            entry: dict[str, Any] = {"slug": slug, "series": series}
            try:
                catalog = load_catalog(settings, slug)
                if catalog is None:
                    print(f"[run] {slug}: no catalog; enumerating first")
                    catalog = enumerate_subject(fetcher, slug)
                    save_catalog(catalog, settings)
                resources = catalog_resources(catalog)
                if series:
                    resources = [
                        res
                        for res in resources
                        if (res.meta.get("series") or "").lower() == series
                    ]
                if args.limit:
                    resources = resources[: args.limit]
                sync = _retry_locked(
                    session,
                    lambda: sync_resources(
                        session,
                        settings,
                        syllabus_ref(slug),
                        resources,
                        fetcher=guard,
                        download=not args.no_download,
                        refresh=args.refresh,
                    ),
                )
                split = _retry_locked(
                    session,
                    lambda: split_subject(
                        session,
                        settings,
                        slug,
                        series=series,
                        limit=args.limit,
                        force=False,
                    ),
                )
            except Exception as exc:
                session.rollback()
                failed.append(slug)
                entry["error"] = str(exc)
                payload.append(entry)
                print(f"[run] {slug}: ERROR {exc}", file=sys.stderr)
                continue
            entry["sync"] = asdict(sync)
            entry["split"] = asdict(split)
            payload.append(entry)
            if sync.failed or split.failed:
                failed.append(slug)
            label = f"{slug} {series}" if series else slug
            print(f"[run] {label}: {_sync_line(sync)} | {_split_line(split)}")
            for message in (sync.errors + split.errors)[:5]:
                print(f"[run] {slug}: {message}", file=sys.stderr)
    finally:
        guard.close()
    return payload, failed


def _run_split(args: argparse.Namespace, session: Any) -> tuple[list[dict], list[str]]:
    settings = get_settings()
    series = normalize_exam_series(args.series) if args.series else None
    payload: list[dict[str, Any]] = []
    failed: list[str] = []
    for slug in _subjects(args):
        try:
            split = _retry_locked(
                session,
                lambda: split_subject(
                    session,
                    settings,
                    slug,
                    series=series,
                    limit=args.limit,
                    force=args.force,
                ),
            )
        except Exception as exc:
            session.rollback()
            failed.append(slug)
            payload.append({"slug": slug, "series": series, "error": str(exc)})
            print(f"[split] {slug}: ERROR {exc}", file=sys.stderr)
            continue
        payload.append({"slug": slug, "series": series, "split": asdict(split)})
        if split.failed:
            failed.append(slug)
        label = f"{slug} {series}" if series else slug
        print(f"[split] {label}: {_split_line(split)}")
        for message in split.errors[:5]:
            print(f"[split] {slug}: {message}", file=sys.stderr)
    return payload, failed


def _points_by_subject(session: Any) -> dict[str, int]:
    board = session.scalar(select(Board).where(Board.key == "edexcel"))
    if board is None:
        return {}
    rows = session.execute(
        select(TaxonomyNode.attrs).where(
            TaxonomyNode.board_id == board.id, TaxonomyNode.node_type == "point"
        )
    ).all()
    out: dict[str, int] = {}
    for (attrs,) in rows:
        if isinstance(attrs, dict):
            subject = attrs.get("subject")
            if subject:
                out[subject] = out.get(subject, 0) + 1
    return out


def _report_subject(session: Any, slug: str, points: dict[str, int]) -> dict[str, Any]:
    settings = get_settings()
    catalog = load_catalog(settings, slug)
    out: dict[str, Any] = {
        "slug": slug,
        "points": points.get(slug, 0),
        "catalog": bool(catalog),
        "gated": sum(
            1
            for res in (catalog or {}).get("resources", [])
            if (res.get("meta") or {}).get("is_gated")
        ),
        "query_mode": (catalog or {}).get("query_mode"),
        "question_papers": 0,
        "mark_schemes": 0,
        "question_papers_downloaded": 0,
        "mark_schemes_downloaded": 0,
        "papers": 0,
        "questions": 0,
        "questions_with_marks": 0,
        "questions_with_ms_regions": 0,
        "questions_tagged": 0,
        "taxonomy_assignments": 0,
        "mark_schemes_matched": 0,
        "split_failures": 0,
        "split_failure_reasons": [],
        "note": None,
    }
    subject = session.scalar(select(Subject).where(Subject.code == slug))
    if subject is None:
        out["note"] = "subject not in database; run sync first"
        return out

    counts = dict(
        session.execute(
            select(Document.doc_type, func.count())
            .where(Document.subject_id == subject.id)
            .group_by(Document.doc_type)
        ).all()
    )
    out["question_papers"] = counts.get(DOC_QUESTION_PAPER, 0)
    out["mark_schemes"] = counts.get(DOC_MARK_SCHEME, 0)

    downloaded = dict(
        session.execute(
            select(Document.doc_type, func.count())
            .where(
                Document.subject_id == subject.id,
                Document.current_revision_id.isnot(None),
            )
            .group_by(Document.doc_type)
        ).all()
    )
    out["question_papers_downloaded"] = downloaded.get(DOC_QUESTION_PAPER, 0)
    out["mark_schemes_downloaded"] = downloaded.get(DOC_MARK_SCHEME, 0)

    out["papers"] = (
        session.scalar(
            select(func.count())
            .select_from(Paper)
            .join(Document, Paper.document_id == Document.id)
            .where(Document.subject_id == subject.id)
        )
        or 0
    )
    out["questions"] = (
        session.scalar(
            select(func.count())
            .select_from(Question)
            .join(Paper, Question.paper_id == Paper.id)
            .join(Document, Paper.document_id == Document.id)
            .where(Document.subject_id == subject.id)
        )
        or 0
    )
    out["questions_with_marks"] = (
        session.scalar(
            select(func.count())
            .select_from(Question)
            .join(Paper, Question.paper_id == Paper.id)
            .join(Document, Paper.document_id == Document.id)
            .where(Document.subject_id == subject.id, Question.marks.isnot(None))
        )
        or 0
    )
    out["questions_with_ms_regions"] = sum(
        1
        for (attrs,) in session.execute(
            select(Question.attrs)
            .join(Paper, Question.paper_id == Paper.id)
            .join(Document, Paper.document_id == Document.id)
            .where(Document.subject_id == subject.id)
        ).all()
        if isinstance(attrs, dict) and attrs.get("ms_regions")
    )
    out["questions_tagged"] = (
        session.scalar(
            select(func.count(func.distinct(QuestionTaxonomy.question_id)))
            .select_from(QuestionTaxonomy)
            .join(Question, QuestionTaxonomy.question_id == Question.id)
            .join(Paper, Question.paper_id == Paper.id)
            .join(Document, Paper.document_id == Document.id)
            .where(Document.subject_id == subject.id)
        )
        or 0
    )
    out["taxonomy_assignments"] = (
        session.scalar(
            select(func.count())
            .select_from(QuestionTaxonomy)
            .join(Question, QuestionTaxonomy.question_id == Question.id)
            .join(Paper, Question.paper_id == Paper.id)
            .join(Document, Paper.document_id == Document.id)
            .where(Document.subject_id == subject.id)
        )
        or 0
    )
    out["mark_schemes_matched"] = (
        session.scalar(
            select(func.count())
            .select_from(MarkScheme)
            .join(Document, MarkScheme.document_id == Document.id)
            .where(
                Document.subject_id == subject.id,
                MarkScheme.matched_paper_document_id.isnot(None),
            )
        )
        or 0
    )
    failures = session.execute(
        select(ParseRun.error)
        .join(DocumentRevision, ParseRun.document_revision_id == DocumentRevision.id)
        .join(Document, DocumentRevision.document_id == Document.id)
        .where(
            Document.subject_id == subject.id,
            ParseRun.parser_version == PARSER_VERSION,
            ParseRun.status == "failed",
        )
    ).all()
    out["split_failures"] = len(failures)
    out["split_failure_reasons"] = [reason for (reason,) in failures if reason][:10]
    return out


def _run_report(args: argparse.Namespace, session: Any) -> tuple[list[dict], list[str]]:
    points = _points_by_subject(session)
    payload = [_report_subject(session, slug, points) for slug in _subjects(args)]
    for row in payload:
        print(
            f"[report] {row['slug']}: points={row['points']} "
            f"QP={row['question_papers']}({row['question_papers_downloaded']} downloaded) "
            f"MS={row['mark_schemes']}({row['mark_schemes_downloaded']} downloaded) "
            f"gated={row['gated']} papers={row['papers']} questions={row['questions']} "
            f"with_marks={row['questions_with_marks']} "
            f"with_ms_regions={row['questions_with_ms_regions']} "
            f"ms_matched={row['mark_schemes_matched']} split_failed={row['split_failures']}"
        )
        for reason in row["split_failure_reasons"]:
            print(f"[report] {row['slug']}: {reason}", file=sys.stderr)
    return payload, []


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    settings = get_settings()
    # 批量命令：BEGIN IMMEDIATE + 更长锁等待，避免多进程并行时被事务升级
    # 的即时失败饿死（见 core/db.py 的说明）。
    enable_immediate_writes()
    init_db()
    session = get_session_factory()()
    fetcher = Fetcher(settings)
    failed: list[str] = []
    payload: list[dict[str, Any]] = []
    try:
        if args.command == "enumerate":
            payload, failed = _run_enumerate(args, session, fetcher)
        elif args.command == "run":
            payload, failed = _run_pipeline(args, session, fetcher)
        elif args.command == "split":
            payload, failed = _run_split(args, session)
        elif args.command == "report":
            payload, failed = _run_report(args, session)
        else:  # pragma: no cover - argparse 已限制取值
            raise SystemExit(f"unknown command: {args.command}")
    finally:
        fetcher.close()
        session.close()

    if args.json:
        print(json.dumps({"subjects": payload, "failed": failed}, ensure_ascii=False, indent=2))
    if args.command == "enumerate":
        # enumerate 没有 sync/split 的失败面；列出 catalog 路径便于脚本消费
        for row in payload:
            if "catalog" in row:
                print(f"[enumerate] catalog: {catalog_path(settings, row['slug'])}")
    return 1 if failed else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
