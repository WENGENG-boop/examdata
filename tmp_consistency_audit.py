"""只读：spec 内容点一致性审计（board=edexcel）。

检查项：
1. 重复 code（同一 code 出现在多个节点）→ 冲突；
2. 同一 (subject, code) 的 name 不一致 → 冲突；
3. 孤立节点（parent 缺失）；
4. 非 unit 节点的 unit 前缀一致性；
5. point 节点总数/按科目统计。

用法: python tmp_consistency_audit.py [out.json]
"""
import collections
import json
import sqlite3
import sys

sys.path.insert(0, "src")


def main() -> None:
    out_path = sys.argv[1] if len(sys.argv) > 1 else "tmp_consistency_audit.json"
    con = sqlite3.connect("file:.data/examdata.db?mode=ro", uri=True)
    cur = con.cursor()

    rows = cur.execute(
        "select id, parent_id, code, name, node_type, source, attrs "
        "from taxonomy_node where board_id=2 order by id"
    ).fetchall()

    def attrs_of(a):
        if not a:
            return {}
        try:
            return json.loads(a)
        except Exception:
            return {}

    nodes = {r[0]: r for r in rows}
    report = {"total_nodes": len(rows), "conflicts": [], "warnings": []}

    # 1+2: duplicate codes / name mismatch
    by_code = collections.defaultdict(list)
    for nid, parent, code, name, ntype, source, attrs in rows:
        a = attrs_of(attrs)
        by_code[(a.get("subject") or "", code)].append((nid, name, ntype))

    dup_codes = {k: v for k, v in by_code.items() if len(v) > 1}
    for (subject, code), items in sorted(dup_codes.items()):
        names = {name for _, name, _ in items}
        kind = "same-name-duplicate" if len(names) == 1 else "different-name"
        report["conflicts"].append(
            {
                "type": kind,
                "subject": subject,
                "code": code,
                "nodes": [{"id": i, "name": nm, "type": t} for i, nm, t in items],
            }
        )

    # 3: missing parents
    for nid, parent, code, name, ntype, source, attrs in rows:
        if ntype == "unit":
            continue
        if parent is None or parent not in nodes:
            report["warnings"].append({"type": "missing-parent", "node": nid, "code": code})

    # 4: unit prefix consistency
    def unit_ancestor(nid):
        seen = set()
        cur_id = nid
        while cur_id is not None and cur_id not in seen:
            seen.add(cur_id)
            node = nodes.get(cur_id)
            if node is None:
                return None
            if node[4] == "unit":
                return node
            cur_id = node[1]
        return None

    prefix_bad = []
    no_unit = []
    for nid, parent, code, name, ntype, source, attrs in rows:
        if ntype == "unit":
            continue
        u = unit_ancestor(nid)
        if u is None:
            no_unit.append(code)
            continue
        if not code.startswith(u[2]):
            prefix_bad.append({"code": code, "unit": u[2], "type": ntype})
    if prefix_bad:
        report["warnings"].append({"type": "prefix-mismatch", "items": prefix_bad[:50]})
    if no_unit:
        report["warnings"].append({"type": "no-unit-ancestor", "codes": no_unit[:50]})

    # 5: stats by subject
    points = collections.Counter()
    kinds = collections.defaultdict(collections.Counter)
    for nid, parent, code, name, ntype, source, attrs in rows:
        a = attrs_of(attrs)
        subj = a.get("subject") or "?"
        kinds[subj][ntype] += 1
        if ntype == "point":
            points[subj] += 1

    report["points_by_subject"] = dict(sorted(points.items()))
    report["nodes_by_subject"] = {s: dict(c) for s, c in sorted(kinds.items())}

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)

    print(f"total nodes: {report['total_nodes']}")
    print(f"conflicts: {len(report['conflicts'])}")
    for c in report["conflicts"][:20]:
        print("  ", c["type"], c["subject"], c["code"], [n["id"] for n in c["nodes"]])
    print(f"warnings: {len(report['warnings'])}")
    for w in report["warnings"]:
        if w["type"] in ("prefix-mismatch", "no-unit-ancestor"):
            print("  ", w["type"], len(w.get("items") or w.get("codes")))
        else:
            print("  ", w)
    print("points by subject:")
    for s, n in sorted(points.items()):
        print(f"  {s:28s} {n:5d}")
    print(f"written {out_path}")


if __name__ == "__main__":
    main()
