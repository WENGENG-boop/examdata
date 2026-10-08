"""Append browser-visual verification records for the 0472 volumes (temporary helper).

Bboxes are read from the current indexes so the records match exactly.
"""
import json
import os
import sys

BR = r"C:\Users\weo\Desktop\api\cie-location-batch"
sys.path.insert(0, os.path.join(BR, "tools"))
import batchlib as B  # noqa: E402

BAN = ("未做视觉核验", "未视觉核验", "未做视觉", "PAGE_NOT_READY",
       "没有做视觉核验", "视觉核验未完成")

# (key, question, role, page, extra_checks, observed)
TARGETS = [
    ("0472/2026/Jun/21", "1(b)", "qp", 3, {"label_visible": True},
     "题号 (b) 以粗体印在区域左上角（其下为消息卡图片顶边）；浏览器目视（r4 条带裁剪图）确认"),
    ("0472/2026/Jun/21", "1(c)", "qp", 3, {"label_visible": True},
     "题号 (c) 以粗体印在区域左上角（其下为信件方框顶边）；浏览器目视（r4 条带裁剪图）确认"),
    ("0472/2026/Jun/21", "3(b)", "qp", 6, {"label_visible": True},
     "题号 (b) 以粗体印在区域左上角（其下为选项 A believed / B made / C decided / D said）；浏览器目视（r4 条带裁剪图）确认"),
    ("0472/2026/Jun/21", "3(c)", "qp", 6, {"label_visible": True},
     "题号 (c) 以粗体印在区域左上角（其下为选项行 A amount…）；浏览器目视（r4 条带裁剪图）确认"),
    ("0472/2026/Jun/21", "3(e)", "qp", 7, {"label_visible": True},
     "题号 (e) 以粗体印在区域左上角（其下为选项 A actually / B exactly / C typically / D rarely）；浏览器目视（r4 条带裁剪图）确认"),
    ("0472/2026/Jun/21", "3(f)", "qp", 7, {"label_visible": True},
     "题号 (f) 以粗体印在区域左上角（其下为选项 A topic / B method / C fact / D result）；浏览器目视（r4 条带裁剪图）确认"),
    ("0472/2026/Jun/21", "6(h)", "qp", 13, {"label_visible": True},
     "题号 (h) 以粗体印在区域左上角（题干 How did Martha feel about the cat she made?）；浏览器目视（r3_qp13_hi 裁剪图）确认"),
    ("0472/2026/Jun/21", "6(i)", "qp", 13, {"label_visible": True},
     "题号 (i) 以粗体印在区域左上角（题干 What did Martha and her grandma both enjoy most about their day? 与 [Total: 11] 在区域内）；浏览器目视（r3_qp13_hi 裁剪图）确认"),
    ("0472/2026/Jun/21", "6(i)", "ms", 8, {"label_visible": True},
     "MS 行 6(i) sharing experiences 在区域内可见；浏览器目视（r3_ms8_hi 裁剪图）确认"),
    ("0472/2026/Jun/22", "1", "qp", 3, {},
     "父题 1 的第 3 页区域覆盖 (b)(c) 与 [Total: 3] 所在整幅版心；浏览器目视（r4 条带裁剪图）确认"),
    ("0472/2026/Jun/22", "1(a)", "ms", 6, {"label_visible": True},
     "MS 行 1(a) B 在区域内可见；浏览器目视（r3_ms6_q1 裁剪图）确认"),
    ("0472/2026/Jun/22", "1(b)", "qp", 3, {"label_visible": True},
     "题号 (b) 以粗体印在区域左上角（其下为通知板图片顶边）；浏览器目视（r4 条带裁剪图）确认"),
    ("0472/2026/Jun/22", "1(b)", "ms", 6, {"label_visible": True},
     "MS 行 1(b) D 在区域内可见；浏览器目视（r3_ms6_q1 裁剪图）确认"),
    ("0472/2026/Jun/22", "1(c)", "qp", 3, {"label_visible": True},
     "题号 (c) 以粗体印在区域左上角（其下为信件方框顶边）；浏览器目视（r3_qp3_c 裁剪图）确认"),
    ("0472/2026/Jun/22", "1(c)", "ms", 6, {"label_visible": True},
     "MS 行 1(c) B 在区域内可见；浏览器目视（r3_ms6_q1 裁剪图）确认"),
    ("0472/2026/Jun/22", "3(a)", "qp", 6, {"label_visible": True},
     "题号 (a) 以粗体印在区域左上角（其下为选项 A correct / B useful / C favourite / D usual）；浏览器目视（r3_qp6_q3 裁剪图）确认"),
    ("0472/2026/Jun/22", "3(b)", "qp", 6, {"label_visible": True},
     "题号 (b) 以粗体印在区域左上角（其下为选项 A arranges / B starts / C prepares / D …）；浏览器目视（r4 条带裁剪图）确认"),
    ("0472/2026/Jun/22", "3(b)", "ms", 6, {"label_visible": True},
     "MS 行 3(b) C 在区域内可见；浏览器目视（r3_ms6_q3 裁剪图）确认"),
    ("0472/2026/Jun/22", "3(d)", "qp", 7, {"label_visible": True},
     "题号 (d) 以粗体印在区域左上角（其下为选项 A just / B ever / C already / D rather）；浏览器目视（r4 条带裁剪图）确认"),
    ("0472/2026/Jun/22", "3(d)", "ms", 6, {"label_visible": True},
     "MS 行 3(d) A 在区域内可见；浏览器目视（r3_ms6_q3 裁剪图）确认"),
    ("0472/2026/Jun/22", "3(e)", "qp", 7, {"label_visible": True},
     "题号 (e) 以粗体印在区域左上角（其下为选项 A exact / B accurate / C perfect / D serious）；浏览器目视（r4 条带裁剪图）确认"),
    ("0472/2026/Jun/22", "3(e)", "ms", 6, {"label_visible": True},
     "MS 行 3(e) D 在区域内可见；浏览器目视（r3_ms6_q3 裁剪图）确认"),
    ("0472/2026/Jun/22", "3(f)", "qp", 7, {"label_visible": True},
     "题号 (f) 以粗体印在区域左上角（其下为选项 A enter…）；浏览器目视（r4 条带裁剪图）确认"),
    ("0472/2026/Jun/22", "3(f)", "ms", 6, {"label_visible": True},
     "MS 行 3(f) A 在区域内可见；浏览器目视（r3_ms6_q3 裁剪图）确认"),
    ("0472/2026/Jun/22", "4(h)", "qp", 9, {"label_visible": True},
     "题号 (h) 以粗体印在区域左上角；浏览器目视（r3_qp9_hi 裁剪图）确认"),
    ("0472/2026/Jun/22", "4(i)", "qp", 9, {"label_visible": True},
     "题号 (i) 以粗体印在区域左上角；浏览器目视（r3_qp9_hi 裁剪图）确认"),
    ("0472/2026/Jun/22", "4(i)", "ms", 7, {"label_visible": True},
     "MS 行 4(i) introduce him to people 在区域内可见；浏览器目视（r3_ms7_q4 裁剪图）确认"),
    ("0472/2026/Jun/22", "6(h)", "qp", 13, {"label_visible": True},
     "题号 (h) 以粗体印在区域左上角；浏览器目视（r3_qp13_hi 裁剪图）确认"),
    ("0472/2026/Jun/22", "6(i)", "qp", 13, {"label_visible": True},
     "题号 (i) 与题干 What did Liza do to thank her friends for the surprise? 及 [Total: 11] 在区域内可见；浏览器目视（r3_qp13_hi 裁剪图）确认"),
    ("0472/2026/Jun/22", "6(i)", "ms", 8, {"label_visible": True},
     "MS 行 6(i) (She) printed / gave / made a book of photos 在区域内可见；浏览器目视（r3_ms8_q6 裁剪图）确认"),
]


def index_region(key, qid, role, page):
    subject, year, season, paper = key.split("/")
    path = B.index_dir(subject, int(year), season, paper) / "cie-index.json"
    data = json.loads(path.read_bytes().decode("utf-8"))
    for q in data["questions"]:
        if q.get("question") == qid:
            regs = q.get(role) or []
            for i, r in enumerate(regs):
                if r.get("page") == page:
                    return i, len(regs), r["bbox"]
    raise SystemExit("region not found: %s %s %s p%s" % (key, qid, role, page))


def main():
    with open(B.VERIFICATION, "rb") as fh:
        fh.seek(-1, 2)
        if fh.read(1) != b"\n":
            raise SystemExit("verification.jsonl does not end with a newline")
    ts = B.now_iso()
    records = []
    for (key, qid, role, page, extra, observed) in TARGETS:
        idx, count, bbox = index_region(key, qid, role, page)
        checks = {"region_index": idx, "region_count": count}
        checks.update(extra)
        checks["observed"] = observed
        rec = {"at": ts, "key": key, "question": qid, "role": role, "page": page,
               "bbox": bbox, "checks": checks, "issues": [],
               "method": "browser_visual_snapshot", "checked_at": ts}
        blob = json.dumps(rec, ensure_ascii=False)
        for m in BAN:
            if m in blob:
                raise SystemExit("banned marker %r in record for %s %s" % (m, key, qid))
        records.append(rec)
    for rec in records:
        B.append_jsonl(B.VERIFICATION, rec)
    print("appended", len(records), "records")
    for rec in records:
        print(rec["key"], rec["question"], rec["role"], "p%s" % rec["page"], rec["bbox"])


main()
