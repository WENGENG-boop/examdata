"""把解析后的 spec 节点树装载进数据库（Pearson Edexcel IAL）。

用法：
    python -m examdata.specs.loader                     # 装载 .data/specs/parsed 下全部合并版
    python -m examdata.specs.loader ial18-biology       # 只装载指定科目
    python -m examdata.specs.loader --dry-run           # 只做一致性检查，不写库

写库约定：
- board = edexcel；qualification = edexcel-ial（get-or-create）；
  subject.code = slug，挂在 edexcel-ial 下。
- taxonomy_node.code = spec 标签（`{unit_key}-{code}`；unit 节点即 unit_key），
  同一内容点全库同标由该唯一约束保证。
- node_type：unit / topic（有子节点的上层）/ subtopic / point（叶子内容点）。
- source = "official"；attrs 记录 subject、unit、页码与正文。
- 幂等：按 (board_id, code) upsert，重跑只更新 name/parent/attrs。

自检：label 全局唯一、同 label 同名、父子链完整；冲突与孤儿全部打印。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.db import session_scope
from ..core.models import Board, Qualification, Subject, TaxonomyNode
from .models import ParsedSpec, SpecNode, SpecUnit

ROOT = Path(__file__).resolve().parents[3]
PARSED_DIR = ROOT / ".data" / "specs" / "parsed"

BOARD_KEY = "edexcel"
QUAL_KEY = "edexcel-ial"
QUAL_NAME = "Pearson Edexcel International A Level"

TEXT_CAP = 4000  # attrs.text 截断上限，避免 JSON 膨胀

# 跨 spec 版本（ial-maths 旧版 vs ial18-mathematics 现行版）同编号内容点的标题裁定：
# 以现行 spec 为准；旧版/异写记入 attrs.title_alt，保证「同标签同标题」且差异可审计。
# - WFM01-5: 现行 spec 印刷标题带串行词 "integration"（其总览表为 "matrix algebra"），
#   旧版与总览一致，采用 "Matrix algebra"。
# - WFM03-1: 旧版拼写 "Hyberbolic" 系笔误，采用现行 "Hyperbolic functions"。
# - WST03-5: 现行措辞更完整，采用 "Regression and correlation"。
TITLE_OVERRIDES: dict[str, dict[str, Any]] = {
    "WFM01-5": {"title": "Matrix algebra", "alt": ["Matrix algebra integration"]},
    "WFM03-1": {"title": "Hyperbolic functions", "alt": ["Hyberbolic functions"]},
    "WST03-5": {"title": "Regression and correlation", "alt": ["Correlation"]},
}


def merged_slugs() -> list[str]:
    """parsed 目录下的合并版 slug（无 -0/-1 等分片后缀）。"""
    slugs: list[str] = []
    for path in sorted(PARSED_DIR.glob("*.json")):
        stem = path.stem
        if stem.endswith(("-0", "-1", "-2", "-3")):
            continue
        slugs.append(stem)
    return slugs


def load_spec(session: Session, slug: str, spec: ParsedSpec) -> dict[str, int]:
    """装载一个科目的 spec；返回 created/updated 计数。"""
    stats = {"created": 0, "updated": 0}
    board = session.scalar(select(Board).where(Board.key == BOARD_KEY))
    if board is None:
        raise RuntimeError(f"board {BOARD_KEY!r} 不存在，请先初始化数据库")

    qual = session.scalar(
        select(Qualification).where(
            Qualification.board_id == board.id, Qualification.key == QUAL_KEY
        )
    )
    if qual is None:
        qual = Qualification(board_id=board.id, key=QUAL_KEY, name=QUAL_NAME, attrs={})
        session.add(qual)
        session.flush()

    subject = session.scalar(
        select(Subject).where(
            Subject.qualification_id == qual.id, Subject.code == slug
        )
    )
    counts = spec.counts()
    subject_attrs: dict[str, Any] = {
        "spec_url": spec.spec_url,
        "spec_sha256": spec.spec_sha256,
        "parser": spec.parser,
        "counts": counts,
        "issues": spec.issues,
    }
    if subject is None:
        subject = Subject(
            qualification_id=qual.id,
            code=slug,
            title=spec.title or slug,
            slug=slug,
            attrs=subject_attrs,
        )
        session.add(subject)
        session.flush()
    else:
        subject.title = spec.title or subject.title
        subject.slug = slug
        subject.attrs = subject_attrs

    # code → 节点 id 缓存；先建父再建子
    node_ids: dict[str, int] = {}

    def upsert_node(
        code: str,
        name: str,
        node_type: str,
        parent_id: Optional[int],
        attrs: dict[str, Any],
    ) -> int:
        existing = session.scalar(
            select(TaxonomyNode).where(
                TaxonomyNode.board_id == board.id, TaxonomyNode.code == code
            )
        )
        if existing is None:
            node = TaxonomyNode(
                board_id=board.id,
                parent_id=parent_id,
                code=code,
                name=name,
                node_type=node_type,
                source="official",
                attrs=attrs,
            )
            session.add(node)
            session.flush()
            stats["created"] += 1
            node_ids[code] = node.id
            return node.id
        existing.name = name
        existing.node_type = node_type
        existing.parent_id = parent_id
        existing.source = "official"
        existing.attrs = attrs
        stats["updated"] += 1
        node_ids[code] = existing.id
        return existing.id

    def visit(node: SpecNode, unit: SpecUnit, parent_id: int, depth: int) -> None:
        has_children = bool(node.children)
        if has_children:
            node_type = "topic" if depth == 1 else "subtopic"
        else:
            node_type = "point"
        override = TITLE_OVERRIDES.get(node.label)
        title = override["title"] if override else node.title
        attrs = {
            "subject": slug,
            "code": node.code,
            "unit_key": unit.unit_key,
            "unit_name": unit.name,
            "page": node.page,
            "text": (node.text or "")[:TEXT_CAP],
        }
        if override:
            attrs["title_alt"] = override["alt"]
        node_id = upsert_node(node.label, title, node_type, parent_id, attrs)
        for child in node.children:
            visit(child, unit, node_id, depth + 1)

    for unit in spec.units:
        unit_attrs = {
            "subject": slug,
            "unit_key": unit.unit_key,
            "unit_code": unit.code,
            "unit_name": unit.name,
        }
        unit_id = upsert_node(unit.unit_key, unit.name, "unit", None, unit_attrs)
        for node in unit.nodes:
            visit(node, unit, unit_id, depth=1)

    return stats


def check_specs(slugs: list[str]) -> tuple[list[str], list[str]]:
    """装载前的一致性检查：同 label 同名（含版本标题裁定）、label 字符。

    返回 (problems, notes)；notes 记录已被 TITLE_OVERRIDES 裁定的版本差异。
    """
    problems: list[str] = []
    notes: list[str] = []
    seen: dict[str, tuple[str, str]] = {}  # label → (name, slug)
    for slug in slugs:
        path = PARSED_DIR / f"{slug}.json"
        if not path.exists():
            problems.append(f"{slug}: parsed JSON 缺失 {path}")
            continue
        spec = ParsedSpec.from_dict(json.loads(path.read_text(encoding="utf-8")))
        for problem in spec.validate():
            problems.append(f"{slug}: [validate] {problem}")
        for _unit, node in spec.all_nodes():
            if node.label in seen:
                prev_name, prev_slug = seen[node.label]
                if prev_name != node.title:
                    override = TITLE_OVERRIDES.get(node.label)
                    allowed = {prev_name, node.title}
                    if override and allowed <= ({override["title"]} | set(override["alt"])):
                        notes.append(
                            f"label {node.label!r} 版本标题差异已裁定为 {override['title']!r}: "
                            f"{prev_slug} {prev_name!r} / {slug} {node.title!r}"
                        )
                    else:
                        problems.append(
                            f"label {node.label!r} 冲突: {prev_slug} {prev_name!r} vs "
                            f"{slug} {node.title!r}"
                        )
            else:
                seen[node.label] = (node.title, slug)
    return problems, notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m examdata.specs.loader", description=__doc__
    )
    parser.add_argument("slugs", nargs="*", help="科目 slug（缺省=parsed 下全部合并版）")
    parser.add_argument("--dry-run", action="store_true", help="只检查，不写库")
    args = parser.parse_args(argv)

    slugs = args.slugs or merged_slugs()
    if not slugs:
        print("[loader] 没有可装载的 parsed JSON")
        return 1

    problems, notes = check_specs(slugs)
    for n in notes:
        print(f"[check] {n}")
    for p in problems:
        print(f"[check] {p}")
    if problems:
        print(f"[loader] 一致性检查失败：{len(problems)} 个问题，未写库")
        return 1

    if args.dry_run:
        print(f"[loader] dry-run OK：{len(slugs)} 个科目通过一致性检查")
        return 0

    total = {"created": 0, "updated": 0}
    with session_scope() as session:
        for slug in slugs:
            path = PARSED_DIR / f"{slug}.json"
            spec = ParsedSpec.from_dict(json.loads(path.read_text(encoding="utf-8")))
            stats = load_spec(session, slug, spec)
            total["created"] += stats["created"]
            total["updated"] += stats["updated"]
            print(
                f"{slug}: created={stats['created']} updated={stats['updated']} "
                f"(units={spec.counts()['units']} nodes={spec.counts()['nodes']})"
            )
        session.flush()
        # 写库后自检：edexcel board 下 official 节点无孤儿、同 code 同名（唯一约束已保证）
        board = session.scalar(select(Board).where(Board.key == BOARD_KEY))
        orphans = session.scalar(
            select(TaxonomyNode.id)
            .where(
                TaxonomyNode.board_id == board.id,
                TaxonomyNode.source == "official",
                TaxonomyNode.parent_id.is_not(None),
            )
            .where(~TaxonomyNode.parent_id.in_(select(TaxonomyNode.id)))
            .limit(1)
        )
        if orphans is not None:
            print("[loader] 自检失败：存在孤儿节点")
            return 1
    print(
        f"[loader] {len(slugs)} subject(s) OK; taxonomy_node created={total['created']} "
        f"updated={total['updated']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
