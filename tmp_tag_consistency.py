"""Check spec label consistency across the library (goal criterion 2).

Checks:
1. code -> name: every taxonomy code maps to exactly one name (board edexcel);
   same code with different names = conflict.
2. same-code nodes: duplicate node rows for one code (board edexcel).
3. same point, different labels: identical normalized (unit, name) pairs under
   two different point codes within the same subject = potential duplicate point.

Output: tmp_tag_consistency.txt
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m

ROOT = Path(__file__).resolve().parent
DB = ROOT / ".data" / "examdata.db"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"[\s\.\u2026]+", " ", s).strip().lower()
    return s


def main() -> None:
    engine = create_engine(f"sqlite:///{DB}")
    lines: list[str] = []
    with Session(engine) as s:
        board = s.execute(select(m.Board).where(m.Board.key == "edexcel")).scalar()
        nodes = list(
            s.scalars(select(m.TaxonomyNode).where(m.TaxonomyNode.board_id == board.id)).all()
        )
        by_id = {n.id: n for n in nodes}
        print(f"edexcel taxonomy nodes: {len(nodes)}")

        # subject mapping via ancestor chain
        def subject_of(node: m.TaxonomyNode) -> str:
            cur = node
            seen = 0
            while cur.parent_id and seen < 12:
                cur = by_id.get(cur.parent_id, cur)
                seen += 1
            return cur.code or "?"

        # 1) code -> names
        code_names: dict[str, set[str]] = defaultdict(set)
        code_nodes: dict[str, list[int]] = defaultdict(list)
        for n in nodes:
            code_names[n.code].add(n.name)
            code_nodes[n.code].append(n.id)
        conflicts = {c: names for c, names in code_names.items() if len(names) > 1}
        dup_nodes = {c: ids for c, ids in code_nodes.items() if len(ids) > 1}
        print(f"codes: {len(code_names)}; code->name conflicts: {len(conflicts)}; duplicate node rows: {len(dup_nodes)}")
        lines.append(f"codes={len(code_names)} name_conflicts={len(conflicts)} dup_node_rows={len(dup_nodes)}")
        for c, names in sorted(conflicts.items()):
            lines.append(f"CONFLICT {c}: {sorted(names)}")
        for c, ids in sorted(dup_nodes.items()):
            lines.append(f"DUP_ROWS {c}: node ids {ids}")

        # 2) same normalized (unit, name) under two codes -> potential same point
        groups: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
        for n in nodes:
            if n.node_type != "point":
                continue
            unit = None
            cur = n
            seen = 0
            while cur is not None and seen < 12:
                if re.match(r"^[A-Za-z]{1,4}\d{2,3}$", cur.code or ""):
                    unit = cur.code
                    break
                cur = by_id.get(cur.parent_id) if cur.parent_id else None
                seen += 1
            groups[(unit or "?", norm(n.name))].append((n.code, n.name))
        dup_points = {k: v for k, v in groups.items() if len({c for c, _ in v}) > 1}
        print(f"potential same-point-different-code groups: {len(dup_points)}")
        lines.append(f"potential_dup_points={len(dup_points)}")
        for (unit, nm), v in sorted(dup_points.items()):
            lines.append(f"DUP_POINT unit={unit} name={nm!r} codes={[c for c, _ in v]}")

        out = ROOT / "tmp_tag_consistency.txt"
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"report -> {out}")

        # 3) point coverage sanity: points per unit
        unit_counts: dict[str, int] = defaultdict(int)
        for n in nodes:
            if n.node_type == "point":
                unit_counts[subject_of(n)] += 1
        print("points per subject root:", dict(sorted(unit_counts.items())))


if __name__ == "__main__":
    main()
