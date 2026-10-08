import json, sqlite3, collections

db = sqlite3.connect(r".data/examdata.db")
db.row_factory = sqlite3.Row

rows = db.execute("SELECT id, board_id, parent_id, code, node_type, name, attrs FROM taxonomy_node WHERE board_id=2").fetchall()
print("total nodes board 2:", len(rows))

by_kind = collections.Counter(r["node_type"] for r in rows)
print("by kind:", dict(sorted(by_kind.items())))

nodes = {r["id"]: r for r in rows}
code_counts = collections.Counter(r["code"] for r in rows)
dups = {c: n for c, n in code_counts.items() if n > 1}
print("duplicate codes:", dups)

def attrs(r):
    try:
        return json.loads(r["attrs"]) if r["attrs"] else {}
    except Exception:
        return {}

subjects = collections.defaultdict(lambda: collections.Counter())
for r in rows:
    a = attrs(r)
    subj = a.get("subject") or "?"
    subjects[subj][r["node_type"]] += 1

print()
print(f"{'subject':26s} {'unit':>5s} {'topic':>6s} {'subtopic':>9s} {'point':>6s} {'total':>6s}")
for subj in sorted(subjects):
    c = subjects[subj]
    total = sum(c.values())
    print(f"{subj:26s} {c['unit']:5d} {c['topic']:6d} {c['subtopic']:9d} {c['point']:6d} {total:6d}")

parent_kind = collections.Counter()
missing_parent = []
for r in rows:
    if r["node_type"] == "unit":
        continue
    p = nodes.get(r["parent_id"]) if r["parent_id"] else None
    if p is None:
        missing_parent.append(r["code"])
        continue
    parent_kind[(r["node_type"], p["node_type"])] += 1

print()
print("child->parent kind pairs:", dict(sorted(parent_kind.items(), key=lambda kv: str(kv[0]))))
print("missing parent count:", len(missing_parent), missing_parent[:10])

def unit_ancestor(r):
    seen = set()
    cur = r
    while cur is not None and cur["node_type"] != "unit":
        if cur["id"] in seen:
            return None
        seen.add(cur["id"])
        cur = nodes.get(cur["parent_id"])
    return cur

prefix_mismatch = []
no_unit = []
for r in rows:
    if r["node_type"] == "unit":
        continue
    u = unit_ancestor(r)
    if u is None:
        no_unit.append(r["code"])
        continue
    if not r["code"].startswith(u["code"]):
        prefix_mismatch.append((r["code"], u["code"], r["node_type"]))

print("no unit ancestor:", len(no_unit), no_unit[:10])
print("prefix mismatch:", len(prefix_mismatch))
for m in prefix_mismatch[:20]:
    print("  ", m)

subs = db.execute("SELECT id, slug, name FROM subject WHERE board_id=2").fetchall()
print()
print("board2 subjects:", len(subs))
for s in subs:
    print("  ", s["id"], s["slug"], s["name"])
