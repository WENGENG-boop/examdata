"""``python -m examdata.tagging`` 命令行（argparse，纯标准库）。

    python -m examdata.tagging assign --dry-run --json
    python -m examdata.tagging assign --subject ial18-biology --write --replace
    python -m examdata.tagging eval-cambridge --examples 10

``assign`` 默认 dry-run（不写库、不写复核文件）；真实写库必须显式 ``--write``，
这是本阶段的护栏：论文管道还在并行建设，真实标注留到后续阶段。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Optional, Sequence

from ..core.config import get_settings
from ..core.db import enable_immediate_writes, init_db, session_scope
from .assign import DEFAULT_MIN_SCORE, LOW_CONFIDENCE, assign
from .cambridge import evaluate_cambridge
from .review import DEFAULT_BATCH_SIZE, DEFAULT_MAX_CONFIDENCE, apply_review, export_review


def _print_stats(title: str, stats: dict[str, Any]) -> None:
    print(title)
    for key in (
        "board",
        "dry_run",
        "replace",
        "subject_filter",
        "scanned",
        "tagged",
        "assigned",
        "second_tags",
        "unassigned",
        "replaced",
        "skipped_manual",
        "skipped_reviewed",
        "skipped_existing",
        "skipped_no_subject",
        "skipped_empty",
        "low_confidence",
    ):
        print(f"  {key:<20} {stats.get(key)}")
    distribution = stats.get("score_distribution") or {}
    print(
        "  score_distribution   "
        f"n={distribution.get('n')} min={distribution.get('min')} "
        f"p50={distribution.get('p50')} p90={distribution.get('p90')} max={distribution.get('max')}"
    )
    for path in stats.get("review_files") or []:
        print(f"  review_file          {path}")


def _cmd_assign(args: argparse.Namespace) -> int:
    init_db()
    dry_run = not args.write
    with session_scope() as session:
        stats = assign(
            session,
            subject=args.subject,
            limit=args.limit,
            dry_run=dry_run,
            replace=args.replace,
            min_score=args.min_score,
            low_confidence=args.low_confidence,
            review_dir=Path(args.review_dir) if args.review_dir else None,
        )
    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    mode = "dry-run（未写库）" if dry_run else "已写库"
    _print_stats(f"Edexcel 内容点标注 · {mode} · {get_settings().database_url}", stats)
    if dry_run:
        print("  提示：dry-run 不产生任何副作用；真实写库请加 --write（本阶段先不跑）。")
    return 0


def _cmd_eval_cambridge(args: argparse.Namespace) -> int:
    init_db()
    with session_scope() as session:
        report = evaluate_cambridge(session, examples=args.examples, subject=args.subject)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print(f"Cambridge 只读对照（候选 {report['candidates']} 个种子 subtopic，对照 keyword-v1 top-1）")
    print(f"  题目                {report['questions']}")
    print(
        f"  BM25 覆盖           {report['bm25_assigned']}/{report['questions']}"
        f" = {report['bm25_coverage']}"
    )
    print(
        f"  keyword 覆盖        {report['keyword_assigned']}/{report['questions']}"
        f" = {report['keyword_coverage']}"
    )
    print(
        f"  两边都有            {report['both']}；top-1 一致 {report['agree_top1']}"
        f" = {report['agreement_strict']}；宽松一致 {report['agreement_lenient']}"
        f"；keyword top-1 落在 BM25 前三 {report['agreement_top3']}"
    )
    print(
        f"  只有 BM25 / 只有 keyword / 都没有  "
        f"{report['bm25_only']} / {report['keyword_only']} / {report['neither']}"
    )
    for row in report.get("disagreements") or []:
        print(
            f"  分歧 #{row['question_id']} ({row['subject']} {row['number_label']}): "
            f"keyword={row['keyword_top1']['code']} {row['keyword_top1']['name']} | "
            f"bm25={row['bm25_top1']['code']} {row['bm25_top1']['name']} "
            f"score={row['bm25_top1']['score']}"
        )
    return 0


def _cmd_review_export(args: argparse.Namespace) -> int:
    init_db()
    with session_scope() as session:
        stats = export_review(
            session,
            subject=args.subject,
            out_dir=Path(args.out),
            max_confidence=args.max_confidence,
            batch_size=args.batch_size,
        )
    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print(f"复核包导出 · {stats['subject']}")
    print(f"  待复核题目   {stats['items']}")
    print(f"  批次         {stats['batches']}（{stats['units']} 个单元）")
    print(f"  points 清单  {stats['points_file']}")
    print(f"  输出目录     {stats['out_dir']}")
    return 0


def _cmd_review_apply(args: argparse.Namespace) -> int:
    init_db()
    dry_run = not args.write
    with session_scope() as session:
        stats = apply_review(
            session,
            subject=args.subject,
            decisions_path=Path(args.decisions),
            dry_run=dry_run,
        )
    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True))
        return 1 if stats["errors"] else 0
    mode = "dry-run（未写库）" if dry_run else "已写库"
    print(f"复核回写 · {stats['subject']} · {mode}")
    for key in ("decisions", "kept", "changed", "dropped"):
        print(f"  {key:<12} {stats.get(key)}")
    print(f"  errors       {len(stats['errors'])}")
    for message in stats["errors"][:20]:
        print(f"    - {message}")
    if stats.get("applied_log"):
        print(f"  应用日志     {stats['applied_log']}")
    return 1 if stats["errors"] else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m examdata.tagging",
        description="Edexcel IAL 内容点标注（BM25，确定性、可复现）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    assign_parser = sub.add_parser("assign", help="给题目挂内容点（默认 dry-run）")
    assign_parser.add_argument("--subject", help="仅处理指定科目（subject.slug 或 code）")
    assign_parser.add_argument("--limit", type=int, default=None, help="最多处理多少题")
    assign_parser.add_argument(
        "--min-score", type=float, default=DEFAULT_MIN_SCORE,
        help=f"第二标签要求 top-1 达到的分数阈值（默认 {DEFAULT_MIN_SCORE}）",
    )
    assign_parser.add_argument(
        "--low-confidence", type=float, default=LOW_CONFIDENCE,
        help=f"低置信阈值，低于它仍写库但计入复核文件（默认 {LOW_CONFIDENCE}）",
    )
    assign_parser.add_argument("--replace", action="store_true", help="重跑：只删同一 assigned_by 的旧行")
    assign_parser.add_argument("--review-dir", help="低置信复核文件目录（默认 <data_dir>/tagging/review）")
    assign_parser.add_argument("--json", action="store_true", help="输出 JSON 统计")
    mode = assign_parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="不写库（默认）")
    mode.add_argument("--write", action="store_true", help="真实写库（本阶段先不用）")
    assign_parser.set_defaults(handler=_cmd_assign, write=False)

    eval_parser = sub.add_parser("eval-cambridge", help="cambridge 只读对照评估")
    eval_parser.add_argument("--subject", help="仅评估指定科目代码")
    eval_parser.add_argument("--examples", type=int, default=10, help="分歧样例条数（默认 10）")
    eval_parser.add_argument("--json", action="store_true", help="输出 JSON 报告")
    eval_parser.set_defaults(handler=_cmd_eval_cambridge)

    export_parser = sub.add_parser(
        "review-export", help="导出低置信题复核包（points 清单 + 分批 JSONL）"
    )
    export_parser.add_argument("--subject", required=True, help="科目（subject.slug 或 code）")
    export_parser.add_argument("--out", required=True, help="输出目录")
    export_parser.add_argument(
        "--max-confidence", type=float, default=DEFAULT_MAX_CONFIDENCE,
        help=f"仅导出低于该置信度的题（默认 {DEFAULT_MAX_CONFIDENCE}）",
    )
    export_parser.add_argument(
        "--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
        help=f"每批题目数（默认 {DEFAULT_BATCH_SIZE}）",
    )
    export_parser.add_argument("--json", action="store_true", help="输出 JSON 统计")
    export_parser.set_defaults(handler=_cmd_review_export)

    apply_parser = sub.add_parser("review-apply", help="回写复核决策（默认 dry-run）")
    apply_parser.add_argument("--subject", required=True, help="科目（subject.slug 或 code）")
    apply_parser.add_argument("--decisions", required=True, help="决策 JSONL 文件或目录")
    apply_parser.add_argument("--json", action="store_true", help="输出 JSON 统计")
    apply_mode = apply_parser.add_mutually_exclusive_group()
    apply_mode.add_argument("--dry-run", action="store_true", help="只校验、不写库（默认）")
    apply_mode.add_argument("--write", action="store_true", help="真实写库")
    apply_parser.set_defaults(handler=_cmd_review_apply, write=False)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    # 批量标注/复核命令：BEGIN IMMEDIATE + 更长锁等待，便于多进程并行
    # （见 core/db.py 的说明）；只读子命令不受影响。
    enable_immediate_writes()
    return int(args.handler(args))


__all__ = ["build_parser", "main"]
