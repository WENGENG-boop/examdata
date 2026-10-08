# -*- coding: utf-8 -*-
"""诊断 provenance coverage < 1.0 的根因。只读。"""
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
con = sqlite3.connect("file:.data/examdata.db?mode=ro", uri=True)
cur = con.cursor()

print("== boards ==")
for row in cur.execute("SELECT id, key FROM board ORDER BY id"):
    print(" ", row)

print("\n== coverage ==")
for stype, table in [
    ("question", "question"),
    ("mark_scheme_entry", "mark_scheme_entry"),
    ("asset", "asset"),
    ("official_answer", "official_answer"),
    ("paper", "paper"),
]:
    total = cur.execute(f"SELECT COUNT(id) FROM {table}").fetchone()[0]
    linked = cur.execute(
        "SELECT COUNT(DISTINCT subject_id) FROM provenance_edge WHERE subject_type=?",
        (stype,),
    ).fetchone()[0]
    print(f"  {stype}: total={total} linked={linked} missing={total - linked}")

print("\n== question missing: by board ==")
for row in cur.execute(
    """
    SELECT d.board_id, COUNT(*) FROM question q
    LEFT JOIN paper p ON p.id = q.paper_id
    LEFT JOIN document d ON d.id = p.document_id
    WHERE q.id NOT IN (SELECT subject_id FROM provenance_edge WHERE subject_type='question')
    GROUP BY d.board_id ORDER BY 2 DESC
    """
):
    print(" ", row)

print("\n== question missing: parse_run_id null? ==")
for row in cur.execute(
    """
    SELECT (q.parse_run_id IS NULL) AS pr_null, COUNT(*) FROM question q
    WHERE q.id NOT IN (SELECT subject_id FROM provenance_edge WHERE subject_type='question')
    GROUP BY pr_null
    """
):
    print(" ", row)

print("\n== question missing: parse_run has revision? ==")
for row in cur.execute(
    """
    SELECT (pr.document_revision_id IS NULL) AS rev_null, COUNT(*) FROM question q
    LEFT JOIN parse_run pr ON pr.id = q.parse_run_id
    WHERE q.id NOT IN (SELECT subject_id FROM provenance_edge WHERE subject_type='question')
    GROUP BY rev_null
    """
):
    print(" ", row)

print("\n== question missing sample ==")
for row in cur.execute(
    """
    SELECT q.id, q.paper_id, q.parse_run_id, q.number_path FROM question q
    WHERE q.id NOT IN (SELECT subject_id FROM provenance_edge WHERE subject_type='question')
    LIMIT 10
    """
):
    print(" ", row)

print("\n== asset missing: by board (via question_asset->question->paper->document) ==")
for row in cur.execute(
    """
    SELECT d.board_id, COUNT(*) FROM asset a
    LEFT JOIN question_asset qa ON qa.asset_id = a.id
    LEFT JOIN question q ON q.id = qa.question_id
    LEFT JOIN paper p ON p.id = q.paper_id
    LEFT JOIN document d ON d.id = p.document_id
    WHERE a.id NOT IN (SELECT subject_id FROM provenance_edge WHERE subject_type='asset')
    GROUP BY d.board_id ORDER BY 2 DESC
    """
):
    print(" ", row)

print("\n== asset missing: has question_asset link? ==")
for row in cur.execute(
    """
    SELECT (EXISTS(SELECT 1 FROM question_asset qa WHERE qa.asset_id = a.id)) AS has_link, COUNT(*)
    FROM asset a
    WHERE a.id NOT IN (SELECT subject_id FROM provenance_edge WHERE subject_type='asset')
    GROUP BY has_link
    """
):
    print(" ", row)

print("\n== asset missing sample ==")
for row in cur.execute(
    """
    SELECT a.id, a.storage_key, (SELECT COUNT(*) FROM question_asset qa WHERE qa.asset_id=a.id)
    FROM asset a
    WHERE a.id NOT IN (SELECT subject_id FROM provenance_edge WHERE subject_type='asset')
    LIMIT 10
    """
):
    print(" ", row)

print("\n== official_answer missing: by board ==")
for row in cur.execute(
    """
    SELECT d.board_id, COUNT(*) FROM official_answer oa
    LEFT JOIN question q ON q.id = oa.question_id
    LEFT JOIN paper p ON p.id = q.paper_id
    LEFT JOIN document d ON d.id = p.document_id
    WHERE oa.id NOT IN (SELECT subject_id FROM provenance_edge WHERE subject_type='official_answer')
    GROUP BY d.board_id ORDER BY 2 DESC
    """
):
    print(" ", row)

print("\n== ms_entry missing: by board ==")
for row in cur.execute(
    """
    SELECT d.board_id, COUNT(*) FROM mark_scheme_entry m
    LEFT JOIN mark_scheme ms ON ms.id = m.mark_scheme_id
    LEFT JOIN document d ON d.id = ms.document_id
    WHERE m.id NOT IN (SELECT subject_id FROM provenance_edge WHERE subject_type='mark_scheme_entry')
    GROUP BY d.board_id ORDER BY 2 DESC
    """
):
    print(" ", row)

print("\n== paper missing: by board ==")
for row in cur.execute(
    """
    SELECT d.board_id, COUNT(*) FROM paper p
    LEFT JOIN document d ON d.id = p.document_id
    WHERE p.id NOT IN (SELECT subject_id FROM provenance_edge WHERE subject_type='paper')
    GROUP BY d.board_id ORDER BY 2 DESC
    """
):
    print(" ", row)

print("\n== edges by source_kind ==")
for row in cur.execute(
    "SELECT source_kind, COUNT(*) FROM provenance_edge GROUP BY source_kind"
):
    print(" ", row)
con.close()
