"""命令行入口。

用法（在 examdata/ 目录下，先 pip install -e .）：

    examdata initdb
    examdata cambridge-syllabuses
    examdata cambridge-discover --limit 5
    examdata cambridge-probe --slug cambridge-igcse-mathematics-0580
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .core.config import get_settings
from .core.db import init_db, session_scope
from .core.fetch import Fetcher
from .adapters.registry import get_adapter_class, available_adapters
from .sync.service import SyncService

app = typer.Typer(add_completion=False, help="国际考试真题统一数据服务")
console = Console()


@app.command("initdb")
def cmd_initdb() -> None:
    """建表。"""
    init_db()
    console.print(f"[green]数据库已初始化[/green] -> {get_settings().database_url}")


@app.command("adapters")
def cmd_adapters() -> None:
    """列出已注册适配器。"""
    for key in available_adapters():
        cls = get_adapter_class(key)
        console.print(f"  {key:<12} {cls.board_name:<28} accessibility={cls.accessibility}")


@app.command("cambridge-syllabuses")
def cmd_cambridge_syllabuses(
    json_out: Optional[str] = typer.Option(None, "--json", help="输出 JSON 到文件"),
) -> None:
    """枚举 Cambridge 全部公开 syllabus（第一层发现）。"""
    with Fetcher() as fetcher:
        adapter = get_adapter_class("cambridge")(fetcher)
        refs = list(adapter.discover_syllabuses())

    by_qual = Counter(r.qualification_name for r in refs)
    console.print(f"[bold]共 {len(refs)} 个 syllabus[/bold]")
    for name, n in sorted(by_qual.items()):
        console.print(f"  {name}: {n}")

    table = Table("code", "slug", "title", "qualification")
    for r in refs[:25]:
        table.add_row(r.code, r.slug, r.title[:52], r.qualification_key)
    console.print(table)
    if len(refs) > 25:
        console.print(f"... 其余 {len(refs) - 25} 条见 --json 输出")

    if json_out:
        payload = [
            {
                "slug": r.slug,
                "code": r.code,
                "title": r.title,
                "qualification_key": r.qualification_key,
                "source_url": r.source_url,
                "past_papers_url": r.attrs.get("past_papers_url"),
            }
            for r in refs
        ]
        with open(json_out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        console.print(f"[green]已写入 {json_out}[/green]")


@app.command("cambridge-probe")
def cmd_cambridge_probe(
    slug: str = typer.Option(..., "--slug", help="syllabus slug，如 cambridge-igcse-mathematics-0580"),
) -> None:
    """探查单个 syllabus 的 past-papers 页（第二、三层发现）。"""
    from .adapters.base import SyllabusRef

    with Fetcher() as fetcher:
        adapter = get_adapter_class("cambridge")(fetcher)
        ref = SyllabusRef(
            slug=slug,
            code=slug.rsplit("-", 1)[-1],
            title=slug,
            qualification_key="unknown",
            qualification_name="unknown",
            source_url="",
            attrs={},
        )
        resources = list(adapter.discover_resources(ref))

    console.print(f"[bold]{slug}[/bold] -> {len(resources)} 个资源")
    table = Table("doc_type", "year", "series", "paper", "conf", "label")
    for r in resources:
        table.add_row(
            r.doc_type,
            str(r.meta.get("year") or "-"),
            str(r.meta.get("series") or "-"),
            str(r.meta.get("paper_code") or "-"),
            f"{r.confidence:.2f}",
            (r.label or "")[:44],
        )
    console.print(table)
    console.print("文件类型分布: " + str(dict(Counter(r.doc_type for r in resources))))


@app.command("cambridge-discover")
def cmd_cambridge_discover(
    limit: Optional[int] = typer.Option(None, "--limit", help="仅处理前 N 个 syllabus（验证用）"),
    json_out: Optional[str] = typer.Option(None, "--json", help="输出 JSON 到文件"),
) -> None:
    """全量发现：家族 -> syllabus -> 资源。不下载，仅枚举与分类。"""
    with Fetcher() as fetcher:
        adapter = get_adapter_class("cambridge")(fetcher)
        refs = list(adapter.discover_syllabuses())
        if limit:
            refs = refs[:limit]

        total = 0
        doc_types: Counter[str] = Counter()
        years: Counter[int] = Counter()
        low_conf: list[dict] = []
        failures: list[str] = []
        all_resources: list[dict] = []

        for i, ref in enumerate(refs, 1):
            try:
                resources = list(adapter.discover_resources(ref))
            except Exception as exc:
                failures.append(f"{ref.slug}: {type(exc).__name__}: {exc}")
                continue
            if not resources:
                failures.append(f"{ref.slug}: 未发现资源")
                continue
            total += len(resources)
            for r in resources:
                doc_types[r.doc_type] += 1
                if r.meta.get("year"):
                    years[int(r.meta["year"])] += 1
                if r.confidence < 0.6:
                    low_conf.append(
                        {
                            "slug": ref.slug,
                            "url": r.url,
                            "label": r.label,
                            "doc_type": r.doc_type,
                            "confidence": r.confidence,
                            "cross_check": r.evidence.get("cross_check"),
                        }
                    )
                all_resources.append(
                    {
                        "syllabus_slug": ref.slug,
                        "subject_code": r.meta.get("subject_code"),
                        "qualification_key": ref.qualification_key,
                        "url": r.url,
                        "label": r.label,
                        "doc_type": r.doc_type,
                        "confidence": r.confidence,
                        "year": r.meta.get("year"),
                        "series": r.meta.get("series"),
                        "paper_code": r.meta.get("paper_code"),
                        "component": r.meta.get("component"),
                        "variant": r.meta.get("variant"),
                    }
                )
            console.print(f"[{i}/{len(refs)}] {ref.slug}: {len(resources)}", highlight=False)

    console.print()
    console.print(f"[bold green]syllabus: {len(refs)}  资源总数: {total}[/bold green]")
    console.print("文件类型分布: " + str(dict(doc_types.most_common())))
    console.print("年份分布: " + str(dict(sorted(years.items()))))
    console.print(f"低置信度(<0.6): {len(low_conf)}   失败 syllabus: {len(failures)}")
    if failures:
        for f in failures[:10]:
            console.print(f"  [red]{f}[/red]")

    if json_out:
        with open(json_out, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "resources": all_resources,
                    "low_confidence": low_conf,
                    "failures": failures,
                },
                fh,
                ensure_ascii=False,
                indent=2,
            )
        console.print(f"[green]已写入 {json_out}[/green]")


@app.command("fetch")
def cmd_fetch(
    url: str = typer.Option(..., "--url"),
    out: str = typer.Option(..., "--out", help="保存路径"),
) -> None:
    """抓取单个文件（走统一抓取器：robots 强制 + 限速 + 重试）。"""
    from pathlib import Path

    with Fetcher() as fetcher:
        res = fetcher.get(url, expect_binary=True)
    if not res.ok or res.content is None:
        console.print(f"[red]抓取失败[/red] status={res.status} error={res.error}")
        raise typer.Exit(code=1)
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(res.content)
    console.print(f"[green]已保存[/green] {path} ({len(res.content)} bytes)")


@app.command("parse-pdf")
def cmd_parse_pdf(
    path: str = typer.Option(..., "--path"),
    json_out: Optional[str] = typer.Option(None, "--json"),
    show: int = typer.Option(12, "--show", help="展示前 N 道题"),
) -> None:
    """解析试卷 PDF，输出题目树与校验发现。"""
    from pathlib import Path

    from .parsing.pdfdoc import load_pdf
    from .parsing.segment import attach_assets, build_question_tree

    doc = load_pdf(Path(path))
    console.print(
        f"页数={doc.page_count} 文本型={doc.is_text_native} 文字覆盖={doc.text_coverage:.4f}"
    )
    tree = build_question_tree(doc)
    asset_stats = attach_assets(tree, doc)

    console.print(f"[bold]顶层题目数={len(tree.roots)} 节点总数={len(tree.flat())}[/bold]")
    console.print(f"分值合计={tree.total_marks}")
    console.print(f"资产统计={asset_stats}")

    for root in tree.roots[:show]:
        _print_node(root, 0)

    if tree.findings:
        console.print("\n[bold]校验发现:[/bold]")
        for f in tree.findings:
            console.print(f"  [{f['severity']}] {f['rule']}: {f['message']}")

    if json_out:
        import json as _json

        with open(json_out, "w", encoding="utf-8") as fh:
            _json.dump(tree.to_dict(), fh, ensure_ascii=False, indent=2)
        console.print(f"[green]已写入 {json_out}[/green]")


@app.command("sync")
def cmd_sync(
    adapter_key: str = typer.Option("cambridge", "--adapter", help="考试局适配器"),
    syllabus: Optional[str] = typer.Option(None, "--syllabus", help="仅同步指定 slug 或科目代码"),
    syllabuses: Optional[int] = typer.Option(None, "--syllabuses", help="仅前 N 个 syllabus"),
    resources: Optional[int] = typer.Option(None, "--resources", help="每个 syllabus 仅前 N 个资源"),
    download: bool = typer.Option(True, "--download/--no-download", help="是否实际下载文件"),
) -> None:
    """完整数据闭环：发现 -> 去重 -> 下载 -> 版本化 -> 落库。

    重复运行不会重复下载（ETag / If-Modified-Since），
    内容变更会生成新的 DocumentRevision 而不是覆盖历史。
    """
    init_db()
    with Fetcher() as fetcher:
        adapter = get_adapter_class(adapter_key)(fetcher)
        with session_scope() as session:
            svc = SyncService(session, adapter)
            stats = svc.run(
                syllabus_limit=syllabuses,
                resource_limit=resources,
                download=download,
                syllabus_filter=syllabus,
            )

    table = Table(title=f"同步完成 · {adapter_key}")
    table.add_column("指标")
    table.add_column("值", justify="right")
    for key, value in stats.to_dict().items():
        if key == "errors":
            continue
        table.add_row(key, str(value))
    console.print(table)
    if stats.errors:
        console.print(f"[yellow]错误 {len(stats.errors)} 条，前 5 条:[/yellow]")
        for err in stats.errors[:5]:
            console.print(f"  - {err[:160]}")


@app.command("parse-docs")
def cmd_parse_docs(
    limit: Optional[int] = typer.Option(None, "--limit", help="仅解析前 N 个待解析版本"),
    document_id: Optional[int] = typer.Option(None, "--document-id", help="仅解析指定文档"),
    show_tree: bool = typer.Option(False, "--show-tree", help="打印解析出的题目树"),
) -> None:
    """解析已下载的 PDF：题目结构化 + 评分标准关联 + 校验落库。

    只处理 parse_status=pending 的 DocumentRevision；
    解析产物写入新的 ParseRun，历史结果保留，便于新旧算法对比。
    """
    from sqlalchemy import select

    from .core.models import DocumentRevision
    from .parsing.pipeline import ParsePipeline

    init_db()
    with session_scope() as session:
        pipe = ParsePipeline(session)
        stats = pipe.run(limit=limit, document_id=document_id)

        if show_tree:
            rows = session.scalars(
                select(DocumentRevision)
                .where(DocumentRevision.parse_status == "parsed")
                .order_by(DocumentRevision.id)
            ).all()
            for rev in rows:
                console.print(f"[bold]revision {rev.id}[/bold] document {rev.document_id}")

    table = Table(title="解析完成")
    table.add_column("指标")
    table.add_column("值", justify="right")
    for key, value in stats.to_dict().items():
        if key == "errors":
            continue
        table.add_row(key, str(value))
    console.print(table)
    if stats.errors:
        console.print(f"[yellow]失败 {len(stats.errors)} 条，前 5 条:[/yellow]")
        for err in stats.errors[:5]:
            console.print(f"  - {err[:160]}")


@app.command("search-papers")
def cmd_search_papers(
    board: Optional[str] = typer.Option(None, "--board", help="考试局 key，如 cambridge"),
    qualification: Optional[str] = typer.Option(None, "--qualification", help="考试体系 key"),
    subject_code: Optional[str] = typer.Option(None, "--subject", help="科目代码，如 0580"),
    year: Optional[int] = typer.Option(None, "--year", help="年份"),
    session: Optional[str] = typer.Option(None, "--session", help="考试季，如 june"),
    paper_code: Optional[str] = typer.Option(None, "--paper", help="Paper 代码，如 11"),
    component: Optional[str] = typer.Option(None, "--component"),
    variant: Optional[str] = typer.Option(None, "--variant"),
    level: Optional[str] = typer.Option(None, "--level"),
    limit: int = typer.Option(50, "--limit"),
    as_json: bool = typer.Option(False, "--json", help="输出 JSON"),
) -> None:
    """按考试信息检索试卷（需求：试卷检索能力）。"""
    from .query import PaperFilter, count_papers, search_papers

    f = PaperFilter(
        board=board,
        qualification=qualification,
        subject_code=subject_code,
        year=year,
        session=session,
        paper_code=paper_code,
        component=component,
        variant=variant,
        level=level,
        limit=limit,
    )
    init_db()
    with session_scope() as session:
        rows = search_papers(session, f)
        total = count_papers(session, f)
    if as_json:
        console.print_json(json.dumps({"total": total, "items": rows}, ensure_ascii=False))
        return
    table = Table(title=f"试卷检索（共 {total} 条，显示 {len(rows)}）")
    for col in ("board", "subject", "year", "session", "paper", "type", "marks", "题数", "status"):
        table.add_column(col)
    for r in rows:
        table.add_row(
            r["board"] or "",
            r["subject_code"] or "",
            str(r["year"] or ""),
            r["session"] or "",
            r["paper_code"] or "",
            r["doc_type"] or "",
            str(r["marks_total"] if r["marks_total"] is not None else ""),
            str(r["question_count"] if r["question_count"] is not None else ""),
            r["status"] or "",
        )
    console.print(table)


@app.command("search-questions")
def cmd_search_questions(
    board: Optional[str] = typer.Option(None, "--board"),
    subject_code: Optional[str] = typer.Option(None, "--subject"),
    year: Optional[int] = typer.Option(None, "--year"),
    session: Optional[str] = typer.Option(None, "--session"),
    paper_code: Optional[str] = typer.Option(None, "--paper"),
    number_path: Optional[str] = typer.Option(None, "--number", help="题号路径，如 1(a)"),
    keyword: Optional[str] = typer.Option(None, "--keyword", help="题干关键词"),
    marks_min: Optional[int] = typer.Option(None, "--marks-min"),
    marks_max: Optional[int] = typer.Option(None, "--marks-max"),
    leaves_only: bool = typer.Option(False, "--leaves", help="只取可独立作答的叶子题"),
    roots_only: bool = typer.Option(False, "--roots", help="只取大题"),
    has_asset: bool = typer.Option(False, "--has-asset", help="只取带图形/图表的题"),
    has_answer: bool = typer.Option(False, "--has-answer", help="只取有官方答案的题"),
    taxonomy_code: Optional[str] = typer.Option(None, "--taxonomy", help="知识点代码"),
    limit: int = typer.Option(20, "--limit"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """题目级检索（需求：题目检索能力）。"""
    from .query import QuestionFilter, count_questions, search_questions

    f = QuestionFilter(
        board=board,
        subject_code=subject_code,
        year=year,
        session=session,
        paper_code=paper_code,
        number_path=number_path,
        keyword=keyword,
        marks_min=marks_min,
        marks_max=marks_max,
        leaves_only=leaves_only,
        roots_only=roots_only,
        has_asset=True if has_asset else None,
        has_official_answer=True if has_answer else None,
        taxonomy_code=taxonomy_code,
        limit=limit,
    )
    init_db()
    with session_scope() as session:
        rows = search_questions(session, f)
        total = count_questions(session, f)
    if as_json:
        console.print_json(json.dumps({"total": total, "items": rows}, ensure_ascii=False))
        return
    table = Table(title=f"题目检索（共 {total} 条，显示 {len(rows)}）")
    for col in ("id", "题号", "分值", "科目", "年份", "Paper", "题干"):
        table.add_column(col, overflow="fold")
    for r in rows:
        table.add_row(
            str(r["question_id"]),
            r["number_path"],
            str(r["marks"] if r["marks"] is not None else ""),
            r["subject_code"] or "",
            str(r["year"] or ""),
            r["paper_code"] or "",
            (r["stem_text"] or "").replace("\n", " ")[:60],
        )
    console.print(table)


@app.command("show-question")
def cmd_show_question(
    question_id: int = typer.Argument(..., help="题目 id"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """取出一道题的完整数据：题干、图形资产、官方答案、评分条目。"""
    from .query import get_question_bundle

    init_db()
    with session_scope() as session:
        bundle = get_question_bundle(session, question_id)
    if bundle is None:
        console.print(f"[red]题目 {question_id} 不存在[/red]")
        raise typer.Exit(code=1)
    if as_json:
        console.print_json(json.dumps(bundle, ensure_ascii=False))
        return
    q = bundle["question"]
    console.print(f"[bold]{q['number_path']}[/bold]  marks={q['marks']}  depth={q['depth']}")
    console.print(f"  试卷: {bundle['paper']['paper_code']} ({bundle['paper']['year']})")
    console.print(f"  题干: {(q['stem_text'] or '')[:200]}")
    if bundle["assets"]:
        table = Table(title="图形资产")
        for col in ("asset_id", "mime", "尺寸", "页", "storage_key"):
            table.add_column(col)
        for a in bundle["assets"]:
            table.add_row(
                str(a["asset_id"]),
                a["mime"] or "",
                f"{a['width']}x{a['height']}",
                str(a["page"] or ""),
                a["storage_key"],
            )
        console.print(table)
    if bundle["mark_scheme_entries"]:
        table = Table(title="评分标准条目")
        for col in ("题号", "分值", "答案", "M/A/B", "ECF"):
            table.add_column(col, overflow="fold")
        for e in bundle["mark_scheme_entries"]:
            table.add_row(
                e["number_path"] or "",
                str(e["marks"] if e["marks"] is not None else ""),
                (e["answer_text"] or "")[:40],
                f"{e['method_marks']}/{e['accuracy_marks']}/{e['independent_marks']}",
                str(e["ecf"]),
            )
        console.print(table)


@app.command("sample-questions")
def cmd_sample_questions(
    subject_code: Optional[str] = typer.Option(None, "--subject"),
    year: Optional[int] = typer.Option(None, "--year"),
    marks_min: Optional[int] = typer.Option(None, "--marks-min"),
    count: Optional[int] = typer.Option(None, "--count", help="抽题数量"),
    marks_target: Optional[int] = typer.Option(None, "--marks", help="目标总分"),
    seed: Optional[int] = typer.Option(None, "--seed"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """随机抽题 / 自动组题基础能力（数据层，不含学生端逻辑）。"""
    from .query import QuestionFilter, sample_questions

    f = QuestionFilter(
        subject_code=subject_code,
        year=year,
        marks_min=marks_min,
        leaves_only=True,
        limit=5000,
    )
    init_db()
    with session_scope() as session:
        comp = sample_questions(session, f, count=count, marks_target=marks_target, seed=seed)
    if as_json:
        console.print_json(
            json.dumps(
                {
                    "marks_total": comp.marks_total,
                    "requested_marks": comp.requested_marks,
                    "questions": comp.questions,
                },
                ensure_ascii=False,
            )
        )
        return
    table = Table(title=f"抽题结果：{len(comp.questions)} 题，合计 {comp.marks_total} 分")
    for col in ("id", "题号", "分值", "Paper", "题干"):
        table.add_column(col, overflow="fold")
    for r in comp.questions:
        table.add_row(
            str(r["question_id"]),
            r["number_path"],
            str(r["marks"] or ""),
            r["paper_code"] or "",
            (r["stem_text"] or "").replace("\n", " ")[:60],
        )
    console.print(table)


@app.command("monitor")
def cmd_monitor(as_json: bool = typer.Option(False, "--json")) -> None:
    """后台监控：各考试局同步/解析状态与待检查队列（需求：后台监控）。"""
    from .query import board_health, review_queue, sync_status

    init_db()
    with session_scope() as session:
        status = sync_status(session)
        health = board_health(session)
        reviews = review_queue(session, limit=50)
    if as_json:
        console.print_json(
            json.dumps(
                {"sync": status, "health": health, "review_queue": reviews},
                ensure_ascii=False,
            )
        )
        return
    table = Table(title="同步与解析状态")
    for col in ("board", "文档", "试卷", "题目", "已解析", "待解析", "失败", "错误", "待检查", "最后同步"):
        table.add_column(col)
    for s in status:
        table.add_row(
            s["board"],
            str(s["documents"]),
            str(s["papers"]),
            str(s["questions"]),
            str(s["parsed"]),
            str(s["pending"]),
            str(s["failed"]),
            str(s["open_errors"]),
            str(s["open_review_tasks"]),
            (s["last_sync_at"] or "")[:19],
        )
    console.print(table)
    console.print(f"[bold]资源候选状态[/bold]: {health}")
    if reviews:
        console.print(f"[yellow]待人工检查 {len(reviews)} 条[/yellow]")
        for r in reviews[:5]:
            console.print(f"  - #{r['id']} {r['target_type']}:{r['target_id']} {r['reason']}")


@app.command("taxonomy-sync")
def cmd_taxonomy_sync() -> None:
    """把官方 syllabus 的知识点种子写库（幂等）。"""
    from .intelligence import sync_taxonomy

    init_db()
    with session_scope() as session:
        stats = sync_taxonomy(session)
    console.print(
        f"[green]知识点同步完成[/green] 科目 {stats['subjects']} 个，新增节点 {stats['nodes']} 个"
    )


@app.command("taxonomy-assign")
def cmd_taxonomy_assign(
    subject: Optional[str] = typer.Option(None, "--subject", help="仅处理指定科目代码"),
    replace: bool = typer.Option(False, "--replace", help="覆盖已有的 auto 标注（不动 manual）"),
    limit: Optional[int] = typer.Option(None, "--limit"),
) -> None:
    """给题目自动标注知识点（关键词打分，确定性可复现）。"""
    from .intelligence import assign_taxonomy, sync_taxonomy

    init_db()
    with session_scope() as session:
        sync_taxonomy(session)
        stats = assign_taxonomy(session, subject_code=subject, limit=limit, replace=replace)
    table = Table(title="知识点标注")
    table.add_column("指标")
    table.add_column("值", justify="right")
    for key, value in stats.items():
        table.add_row(key, str(value))
    console.print(table)


@app.command("difficulty-estimate")
def cmd_difficulty_estimate(
    subject: Optional[str] = typer.Option(None, "--subject"),
    replace: bool = typer.Option(False, "--replace", help="重算已有估计值"),
) -> None:
    """估计题目难度（source=estimated，与官方难度分离存储）。"""
    from .intelligence import estimate_all

    init_db()
    with session_scope() as session:
        stats = estimate_all(session, subject_code=subject, replace=replace)
    console.print(
        f"[green]难度估计完成[/green] 扫描 {stats['questions']} 题，写入 {stats['written']} 条"
    )


@app.command("similarity-find")
def cmd_similarity_find(
    subject: Optional[str] = typer.Option(None, "--subject"),
    min_score: float = typer.Option(0.62, "--min-score", help="余弦相似度阈值"),
    top_k: int = typer.Option(5, "--top-k", help="每题保留的相似题上限"),
    replace: bool = typer.Option(False, "--replace"),
) -> None:
    """发现相似题（TF-IDF n-gram 余弦，确定性）。"""
    from .intelligence import find_similar

    init_db()
    with session_scope() as session:
        stats = find_similar(
            session, subject_code=subject, replace=replace, min_score=min_score, top_k=top_k
        )
    console.print(
        f"[green]相似题计算完成[/green] 参与 {stats['questions']} 题，"
        f"写入 {stats['pairs']} 对，文本过短跳过 {stats['skipped_short']} 题"
    )


@app.command("enrich")
def cmd_enrich(
    subject: Optional[str] = typer.Option(None, "--subject"),
    min_score: float = typer.Option(0.62, "--min-score"),
) -> None:
    """一次跑完智能层：知识点 -> 难度 -> 相似题 -> 生成解析。"""
    from .intelligence import (
        assign_taxonomy,
        estimate_all,
        find_similar,
        generate_explanations,
        sync_taxonomy,
    )

    init_db()
    with session_scope() as session:
        tax_nodes = sync_taxonomy(session)
        tax = assign_taxonomy(session, subject_code=subject, replace=True)
        diff = estimate_all(session, subject_code=subject, replace=True)
        sim = find_similar(session, subject_code=subject, replace=True, min_score=min_score)
        expl = generate_explanations(session, subject_code=subject, replace=True)

    table = Table(title="智能层构建完成")
    table.add_column("阶段")
    table.add_column("结果")
    table.add_row("知识点节点", f"科目 {tax_nodes['subjects']} 个 / 新增 {tax_nodes['nodes']} 个")
    table.add_row(
        "知识点标注",
        f"扫描 {tax['scanned']} 题 / 写入 {tax['assigned']} 条 / 未标注 {tax['unassigned']} 题",
    )
    table.add_row("难度估计", f"{diff['written']} / {diff['questions']} 题")
    table.add_row(
        "相似题", f"{sim['pairs']} 对 / 参与 {sim['questions']} 题 / 过短跳过 {sim['skipped_short']}"
    )
    table.add_row(
        "生成解析",
        f"生成 {expl['generated']} 条 / 无官方依据跳过 {expl['skipped_no_official']} 题",
    )
    console.print(table)
    if expl["generated"]:
        console.print(
            "[yellow]生成解析均为 provider=rule-based、review_status=pending，"
            "需人工审核后才可视为可信材料[/yellow]"
        )


@app.command("classify-content")
def cmd_classify_content(
    apply: bool = typer.Option(
        False, "--apply", help="把内容判定写入 doc_classification（默认只报告）"
    ),
    subject: Optional[str] = typer.Option(None, "--subject"),
) -> None:
    """基于 PDF 内容识别文件类型，与锚文本判定交叉验证。

    规格要求文件类型判断"不能只依赖文件名，还需要结合文件本身信息与文档内容"。
    """
    from sqlalchemy import select as _select

    from .core.models import Artifact, Document, DocumentRevision
    from .parsing.content_classify import classify_content, reconcile

    init_db()
    rows: list[tuple[int, str, str, str, str]] = []
    with session_scope() as session:
        stmt = (
            _select(Document.id, Document.doc_type, Document.title, Artifact.storage_key)
            .join(DocumentRevision, DocumentRevision.document_id == Document.id)
            .join(Artifact, Artifact.id == DocumentRevision.artifact_id)
            .order_by(Document.id)
        )
        if subject:
            from .core.models import Subject

            stmt = stmt.join(Subject, Subject.id == Document.subject_id).where(
                Subject.code == subject
            )
        rows = [tuple(r) for r in session.execute(stmt).all()]

        if apply:
            from .core.models import DocClassification

            # 幂等：先删掉这些文档已有的内容级判定再重写。
            # 否则每跑一次就多一批行，监控视图里会看到几十条互相矛盾的判定。
            content_methods = ("label+content", "content", "conflict", "label")
            for old in session.scalars(
                _select(DocClassification).where(
                    DocClassification.method.in_(content_methods)
                )
            ).all():
                session.delete(old)
            session.flush()

            for did, label_type, title, storage_key in rows:
                ev = classify_content(get_settings().artifacts_dir / storage_key)
                final, conf, method = reconcile(label_type, ev)
                session.add(
                    DocClassification(
                        document_id=did,
                        doc_type=final,
                        confidence=conf,
                        evidence={
                            "label_type": label_type,
                            "content": ev.to_dict(),
                            "final_type": final,
                        },
                        method=method,
                    )
                )

    table = Table(title=f"内容级文件类型识别（{len(rows)} 份）")
    for col in ("doc", "标签判定", "内容判定", "最终", "置信度", "方式"):
        table.add_column(col)
    conflicts = 0
    for did, label_type, _title, storage_key in rows:
        ev = classify_content(get_settings().artifacts_dir / storage_key)
        final, conf, method = reconcile(label_type, ev)
        if method == "conflict":
            conflicts += 1
        table.add_row(
            str(did),
            label_type or "-",
            ev.doc_type or "-",
            final,
            f"{conf:.2f}",
            method,
        )
    console.print(table)
    if conflicts:
        console.print(f"[yellow]{conflicts} 份文件的标签判定与内容判定冲突，已进入待检查[/yellow]")
    else:
        console.print("[green]标签判定与内容判定全部一致[/green]")


@app.command("override-set")
def cmd_override_set(
    target_type: str = typer.Argument(..., help="question / mark_scheme_entry / document / paper"),
    target_id: int = typer.Argument(...),
    field: str = typer.Option(..., "--field", help="字段名，如 marks"),
    value: str = typer.Option(..., "--value", help="新值（JSON 或纯文本）"),
    author: str = typer.Option(..., "--author", help="操作人（必填，用于追责）"),
    note: Optional[str] = typer.Option(None, "--note"),
) -> None:
    """登记一条人工修正。人工确认的内容不会被下一次自动同步覆盖。"""
    from .governance import OverrideError, set_override

    parsed: object
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parsed = value

    init_db()
    try:
        with session_scope() as session:
            result = set_override(
                session,
                target_type=target_type,
                target_id=target_id,
                field_path=field,
                value=parsed,
                author=author,
                note=note,
            )
    except OverrideError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)
    console.print(
        f"[green]已登记修正[/green] #{result['id']} {target_type}:{target_id}.{field} "
        f"{result['source_value']!r} -> {result['value']!r}"
    )


@app.command("override-list")
def cmd_override_list(
    target_type: Optional[str] = typer.Option(None, "--target-type"),
    target_id: Optional[int] = typer.Option(None, "--target-id"),
    conflicts: bool = typer.Option(False, "--conflicts", help="只看冲突未生效的"),
) -> None:
    """列出人工修正记录。"""
    from .governance import list_overrides

    init_db()
    with session_scope() as session:
        rows = list_overrides(
            session, target_type=target_type, target_id=target_id, only_conflicts=conflicts
        )
    if not rows:
        console.print("没有人工修正记录")
        return
    table = Table(title=f"人工修正（{len(rows)} 条）")
    for col in ("id", "目标", "字段", "人工值", "原值", "作者", "生效", "冲突"):
        table.add_column(col, overflow="fold")
    for r in rows:
        table.add_row(
            str(r["id"]),
            f"{r['target_type']}:{r['target_id']}",
            r["field_path"],
            str(r["value"])[:24],
            str(r["source_value"])[:24],
            r["author"] or "",
            "是" if r["active"] else "否",
            "是" if r["conflict_detected"] else "否",
        )
    console.print(table)


@app.command("review-list")
def cmd_review_list(
    status: str = typer.Option("open", "--status", help="open / in_progress / done / dismissed"),
    limit: int = typer.Option(50, "--limit"),
) -> None:
    """待人工检查队列。"""
    from .governance import list_reviews

    init_db()
    with session_scope() as session:
        rows = list_reviews(session, status=status, limit=limit)
    if not rows:
        console.print(f"没有状态为 {status} 的待检查项")
        return
    table = Table(title=f"待检查（{len(rows)} 条，status={status}）")
    for col in ("id", "优先级", "目标", "原因", "指派", "结论"):
        table.add_column(col, overflow="fold")
    for r in rows:
        table.add_row(
            str(r["id"]),
            str(r["priority"]),
            f"{r['target_type']}:{r['target_id']}",
            r["reason"],
            r["assignee"] or "",
            (r["resolution"] or "")[:40],
        )
    console.print(table)


@app.command("review-resolve")
def cmd_review_resolve(
    review_id: int = typer.Argument(...),
    resolution: str = typer.Option(..., "--resolution", help="处置结论"),
    author: str = typer.Option(..., "--author"),
    dismiss: bool = typer.Option(False, "--dismiss", help="确认无需处理（而非已处理）"),
) -> None:
    """处置一条待检查项。"""
    from .governance import OverrideError, resolve_review

    init_db()
    try:
        with session_scope() as session:
            result = resolve_review(
                session,
                review_id=review_id,
                resolution=resolution,
                author=author,
                status="dismissed" if dismiss else "done",
            )
    except OverrideError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)
    console.print(f"[green]已处置[/green] #{result['id']} -> {result['status']}")


@app.command("provenance-rebuild")
def cmd_provenance_rebuild(
    board: Optional[str] = typer.Option(None, "--board"),
) -> None:
    """重建溯源边（纯投影，幂等）。"""
    from .governance import coverage, rebuild

    init_db()
    with session_scope() as session:
        stats = rebuild(session, board=board)
        cov = coverage(session)
    table = Table(title="溯源重建完成")
    table.add_column("主体")
    table.add_column("写入边数", justify="right")
    for key, value in stats.items():
        table.add_row(key, str(value))
    console.print(table)
    table2 = Table(title="溯源覆盖率")
    for col in ("主体", "总数", "有来源", "边数", "覆盖率"):
        table2.add_column(col)
    for key, c in cov.items():
        table2.add_row(
            key, str(c["total"]), str(c["linked"]), str(c["edges"]), f"{c['ratio']:.1%}"
        )
    console.print(table2)


@app.command("provenance-trace")
def cmd_provenance_trace(
    subject_type: str = typer.Argument(..., help="question / asset / mark_scheme_entry ..."),
    subject_id: int = typer.Argument(...),
) -> None:
    """追踪某个主体的来源。"""
    from .governance import trace

    init_db()
    with session_scope() as session:
        rows = trace(session, subject_type, subject_id)
    if not rows:
        console.print(f"{subject_type}:{subject_id} 没有溯源记录")
        return
    for r in rows:
        console.print(f"[bold]{r['source_kind']}[/bold] {r['source_ref']}")
        console.print(f"  来源: {r['source_url']}")
        console.print(f"  观测时间: {r['observed_at']}")
        console.print(f"  证据: {json.dumps(r['attrs'], ensure_ascii=False)[:200]}")


@app.command("reparse")
def cmd_reparse(
    document_id: Optional[int] = typer.Option(None, "--document-id"),
    limit: Optional[int] = typer.Option(None, "--limit"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """用当前算法重新解析历史资源，并对比新旧结果。

    不重新下载：只读本地内容寻址存储里的原始文件。
    """
    from .governance import reparse_documents

    init_db()
    with session_scope() as session:
        result = reparse_documents(
            session,
            document_ids=[document_id] if document_id else None,
            limit=limit,
        )
    if as_json:
        console.print_json(json.dumps(result, ensure_ascii=False))
        return
    console.print(
        f"[bold]重新解析 {result['documents']} 份文档[/bold]，"
        f"其中 {result['regressed']} 份出现回归"
    )
    table = Table(title="新旧结果对比（只列出有变化的文档）")
    for col in ("文档", "题数", "大题", "分值", "资产", "评分条目", "已关联", "重复题号", "结论"):
        table.add_column(col)
    for d in result["diffs"]:
        if not d["changes"]:
            continue
        b, a = d["before"], d["after"]
        table.add_row(
            str(d["document_id"]),
            f"{b['questions']}->{a['questions']}",
            f"{b['roots']}->{a['roots']}",
            f"{b['marks_sum']}->{a['marks_sum']}",
            f"{b['assets']}->{a['assets']}",
            f"{b['mark_scheme_entries']}->{a['mark_scheme_entries']}",
            f"{b['entries_linked']}->{a['entries_linked']}",
            f"{b['duplicate_paths']}->{a['duplicate_paths']}",
            "[red]回归[/red]" if d["is_regression"] else "正常",
        )
    console.print(table)
    for d in result["diffs"]:
        for r in d["regressions"]:
            console.print(f"  [red]文档 {d['document_id']}: {r}[/red]")


@app.command("explain")
def cmd_explain(
    subject: Optional[str] = typer.Option(None, "--subject"),
    limit: Optional[int] = typer.Option(None, "--limit"),
    replace: bool = typer.Option(False, "--replace", help="重算已有解析"),
) -> None:
    """生成学生向解题解析（规则式，从官方 Mark Scheme 派生）。

    生成内容与官方内容严格分离：provider=rule-based、is_official=False、
    review_status=pending（默认不可信，需人工审核）。
    """
    from .intelligence import generate_explanations

    init_db()
    with session_scope() as session:
        stats = generate_explanations(session, subject_code=subject, limit=limit, replace=replace)
    table = Table(title="解析生成完成")
    table.add_column("项")
    table.add_column("值", justify="right")
    for key, value in stats.items():
        table.add_row(key, str(value))
    console.print(table)
    console.print(
        "[yellow]生成内容均为 review_status=pending，需人工审核后才可视为可信学习材料[/yellow]"
    )


@app.command("explain-review")
def cmd_explain_review(
    explanation_id: int = typer.Argument(...),
    approve: bool = typer.Option(False, "--approve"),
    reject: bool = typer.Option(False, "--reject"),
    author: str = typer.Option(..., "--author"),
) -> None:
    """人工审核生成的解析。"""
    from .intelligence import review_explanation

    if approve == reject:
        console.print("[red]必须且只能指定 --approve 或 --reject[/red]")
        raise typer.Exit(code=1)

    init_db()
    try:
        with session_scope() as session:
            result = review_explanation(
                session,
                explanation_id,
                status="approved" if approve else "rejected",
                author=author,
            )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)
    console.print(f"[green]已审核[/green] #{result['id']} -> {result['review_status']}")


@app.command("serve")
def cmd_serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port"),
    reload: bool = typer.Option(False, "--reload"),
) -> None:
    """启动只读检索 API（FastAPI + OpenAPI 文档）。"""
    import uvicorn

    init_db()
    console.print(f"[green]API 文档[/green] http://{host}:{port}/docs")
    uvicorn.run("examdata.api.app:app", host=host, port=port, reload=reload)


@app.command("db-stats")
def cmd_db_stats() -> None:
    """查看已落库的数据规模。"""
    from sqlalchemy import func, select

    from .core.models import (
        Artifact,
        Document,
        DocumentRevision,
        MarkSchemeEntry,
        Question,
        ResourceCandidate,
        Subject,
    )

    init_db()
    with session_scope() as session:
        rows = [
            ("资源候选", ResourceCandidate),
            ("科目", Subject),
            ("文档", Document),
            ("文档版本", DocumentRevision),
            ("内容对象", Artifact),
            ("题目", Question),
            ("评分条目", MarkSchemeEntry),
        ]
        table = Table(title="数据库规模")
        table.add_column("实体")
        table.add_column("数量", justify="right")
        for name, model in rows:
            count = session.scalar(select(func.count()).select_from(model)) or 0
            table.add_row(name, str(count))
        console.print(table)


def _print_node(node, indent: int) -> None:
    pad = "  " * indent
    marks = f" [{node.marks}]" if node.marks is not None else ""
    pages = f" p{node.page_from}-{node.page_to}" if node.page_from else ""
    assets = f" img={len(node.assets)}" if node.assets else ""
    snippet = node.text.replace("\n", " ")[:64]
    console.print(f"{pad}{node.number_path}{marks}{pages}{assets}  {snippet}")
    for child in node.children:
        _print_node(child, indent + 1)


@app.command("paper-qa")
def cmd_paper_qa(
    board: str = typer.Option(..., "--board"),
    subject: str = typer.Option(..., "--subject"),
    year: int = typer.Option(..., "--year"),
    season: str = typer.Option(..., "--season"),
    paper: Optional[str] = typer.Option(None, "--paper"),
    question: Optional[str] = typer.Option(None, "--question"),
    mode: Optional[str] = typer.Option(None, "--mode"),
    out: Optional[str] = typer.Option(None, "--out"),
    as_json: bool = typer.Option(
        False, "--json", help="输出与 HTTP JSON 同一套 schema 的清单"
    ),
) -> None:
    """CIE 整份 PDF / Edexcel IAL 整卷 PDF 与题目·答案 PNG；未给 --out 不落盘。

    `--json` 与 HTTP 的 `/paper-qa/resolve`、`/paper-qa/query?format=json`
    共用同一套 schema（schema_version / request / counts / documents / files），
    字段名与层级完全一致。CLI 只在内存里持有字节，所以 `--json` 里每个文件的
    `data_base64` 恒为 null——要落地用 `--out`，要 base64 载荷走 HTTP。
    """
    from .paperqa import PaperQAError, query

    try:
        result = query(board, subject, year, season, paper, question, mode, out)
    except (PaperQAError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    if as_json:
        typer.echo(json.dumps(result.metadata(), ensure_ascii=False))
        return

    request = result.request
    selector = f"[bold]{request.board}[/bold] {request.subject} {request.season} {request.year} mode={request.mode}"
    if request.paper:
        selector += f" paper={request.paper}"
    if request.question:
        selector += f" question={request.question}"
    console.print(selector)
    console.print(
        f"清单 {len(result.documents)} 份 -> 取回 {len(result.files)} 个文件，"
        f"共 {sum(len(f.data) for f in result.files)} bytes"
    )
    if result.files:
        # file / bbox 用 fold 而不是省略号：80 列下省略会把文件名截成
        # 无用的前缀，而文件名正是用户接着 --out 时要用的东西。
        from rich.table import Column

        table = Table(
            Column("file", overflow="fold"),
            Column("role"),
            Column("type"),
            Column("bytes", justify="right"),
            Column("page", justify="right"),
            Column("bbox", overflow="fold"),
            Column("sha256"),
        )
        for file in result.files:
            bbox = "-" if file.bbox is None else ",".join(f"{v:.0f}" for v in file.bbox)
            table.add_row(
                file.name,
                file.role,
                file.media_type,
                str(len(file.data)),
                str(file.page) if file.page is not None else "-",
                bbox,
                file.sha256[:12],
            )
        console.print(table)
    if out is None:
        typer.echo("Files returned in memory; use --out to save them.")


if __name__ == "__main__":
    app()
