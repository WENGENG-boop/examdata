"""r12: dump current taxonomy rows for the 49 adjudicated questions + resolve target codes."""
from __future__ import annotations

import sqlite3

QIDS = [
    # WBI13 keeps
    68222, 68225, 68231, 68237, 68240, 68247, 68250, 68253, 68258, 68259, 68264,
    # WAC11 fixes
    68322, 68324, 68343, 68358, 68369, 68371, 68372, 68374, 68380, 68386,
    68395, 68396, 68397, 68415, 68440, 68470, 68471, 68472,
    # WAC12
    68345, 68459, 68460, 68461, 68462, 68463, 68466, 68468,
    # WAC01
    68412, 68414,
    # WGE01
    68494, 68512,
    # YLA1
    68525, 68529, 68531,
    # WPS
    68544, 68549, 68555, 68563, 68570,
]

TARGET_CODES = [
    "WAC11-1.6.1", "WAC11-1.3.13", "WAC11-1.5.1", "WAC11-1.4.8", "WAC11-1.4.10",
    "WAC11-1.4.11", "WAC11-1.1.16", "WAC11-1.2.3", "WAC11-1.5.2", "WAC11-1.2.5",
    "WAC11-1.1.17", "WAC11-1.1.15", "WAC11-1.6.2", "WAC11-1.3.18",
    "WAC12-2.1.13", "WAC12-2.8.6", "WAC12-2.7.2", "WAC12-2.7.1",
    "WAC01-1.3.3.4", "WGE01-1.3.1", "YLA1-01-1.2.22",
    "WPS02-3.1.3", "WPS02-3.2.1", "WPS02-3.2.7", "WPS03-5.3.4",
]

con = sqlite3.connect(".data/examdata.db")
con.row_factory = sqlite3.Row
cur = con.cursor()

print("=== current rows for 49 qids ===")
for qid in QIDS:
    rows = cur.execute(
        """SELECT qt.id, qt.node_id, tn.code, tn.name, qt.source, qt.confidence,
                  qt.assigned_by, qt.reviewed
           FROM question_taxonomy qt JOIN taxonomy_node tn ON tn.id = qt.node_id
           WHERE qt.question_id = ? ORDER BY qt.id""",
        (qid,),
    ).fetchall()
    if not rows:
        print(f"q{qid}: <NO ROWS>")
        continue
    parts = [
        f"[id={r['id']} {r['code']} src={r['source']} conf={r['confidence']} rev={r['reviewed']} by={r['assigned_by']}]"
        for r in rows
    ]
    print(f"q{qid}: " + " | ".join(parts))

print()
print("=== target code -> node ===")
for code in TARGET_CODES:
    rows = cur.execute(
        "SELECT id, code, name FROM taxonomy_node WHERE code = ?", (code,)
    ).fetchall()
    if len(rows) == 1:
        print(f"{code} -> node {rows[0]['id']}  {rows[0]['name'][:70]}")
    else:
        print(f"{code} -> {len(rows)} matches: {[(r['id'], r['name'][:50]) for r in rows]}")

con.close()
