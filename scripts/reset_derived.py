"""清空可重建的派生数据并重置解析状态，用于干净地重跑解析流水线。

派生数据（题目/评分/资产/校验/智能层/生成解析）都是可重建的，
人工修正存在 field_override，不在此处删除。

删除顺序必须是"子表在前、父表在后"，否则 PRAGMA foreign_keys=ON 会拒绝删除：
  mark_scheme_entry.question_id -> question.id
  official_answer.question_id   -> question.id
  question_asset                -> question.id / asset.id
  question.parent_id            -> question.id（自引用，靠级联顺序解决）
"""

import sqlite3

TABLES = [
    # 最底层：引用 question / asset / mark_scheme 的关联与内容表。
    # formula / question_taxonomy / difficulty / question_similarity 同样引用
    # question.id，虽然目前多为空表，但必须一并清理，否则有数据时
    # delete from question 会触发外键约束失败。
    "question_asset",
    "official_answer",
    "generated_explanation",
    "mark_scheme_entry",
    "formula",
    "question_taxonomy",
    "difficulty",
    "question_similarity",
    # 中间层
    "asset",
    "question",
    "mark_scheme",
    "paper",
    # 校验与运行记录
    "validation_finding",
    "review_task",
    "parse_run",
]

c = sqlite3.connect(".data/examdata.db")
c.execute("PRAGMA foreign_keys=ON")
for t in TABLES:
    n = c.execute("delete from " + t).rowcount
    print("  cleared %-20s %s" % (t, n))
c.execute("update document_revision set parse_status='pending', parse_error=NULL")
c.execute("update document set status='stored'")
c.commit()
print("pending revisions:", c.execute(
    "select count(*) from document_revision where parse_status='pending'").fetchone()[0])
