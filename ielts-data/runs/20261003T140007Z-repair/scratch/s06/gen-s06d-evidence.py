# gen-s06d-evidence.py — 生成 S06d 缺槽定位综合证据
import hashlib, json, os

ROOT = "C:/Users/weo/Desktop/api"
RUN = os.path.join(ROOT, "ielts-data/runs/20261003T140007Z-repair")
EV = os.path.join(RUN, "evidence")

reg = json.load(open(os.path.join(EV, "S06-offline-regression.json"), encoding="utf-8"))
cam = json.load(open(os.path.join(EV, "S06-cam21-crosscheck.json"), encoding="utf-8"))
b20 = json.load(open(os.path.join(EV, "S06-book20-structure.json"), encoding="utf-8"))

# 缺槽定位表（本阶段人工定位结论，页码均为 1-based 文件页）
q_cases = [
    {"key": "1-1-listening", "slots": [41], "pages": {"book1": [25]}, "answer_pages": {"book1": [136]}, "status": "pages_imported", "note": "Q41 in any order; 键 41 A"},
    {"key": "1-2-listening", "slots": [40, 41], "pages": {"book1": [45]}, "answer_pages": {"book1": [140]}, "status": "pages_imported", "note": "Q40/41 图页；键 41 eat lots//eat most either way round"},
    {"key": "1-2-reading", "slots": [20, 21, 22, 23, 41], "pages": {"book1": [53, 56]}, "answer_pages": {"book1": [143]}, "status": "pages_imported", "note": "Q20-23 蜂箱图 fp53；Q41 fp56；键 41 H"},
    {"key": "1-4-listening", "slots": [26, 27, 28, 29, 30, 31, 41, 42], "pages": {"book1": [84, 85]}, "answer_pages": {"book1": [148]}, "status": "pages_imported", "note": "Q26-31 铝罐图 fp84；Q41/42 fp85；键 41 fitness testing//body measurements, 42 cellular research//cellular change//body cells"},
    {"key": "3-2-reading", "slots": [9, 10, 11, 12, 13], "pages": {"book3": [45]}, "answer_pages": {}, "status": "pages_imported", "note": "已在 book3 extract-b 覆盖"},
    {"key": "8-3-reading", "slots": [7, 8, 9, 10], "pages": {"book8": [67]}, "answer_pages": {}, "status": "pages_imported", "note": "fp67 文本层 Questions 7-1 O（字母O）；summary 选词 A-I"},
    {"key": "11-2-reading", "slots": [20, 21, 22, 23, 24, 25, 26], "pages": {"book11": [38, 41]}, "answer_pages": {}, "status": "pages_imported", "note": "fp38 标题列表尾+Q20；fp41 21-24 summary、25-26 choose TWO"},
    {"key": "11-3-reading", "slots": [9, 10, 11, 12, 13], "pages": {"book11": [60, 61]}, "answer_pages": {}, "status": "pages_imported", "note": "fp60 Q1-9 笔记含 Q9；fp61 10-13 T/F/NG"},
    {"key": "12-3-listening", "slots": [21, 22, 23, 24, 25, 26], "pages": {"book12": [57]}, "answer_pages": {}, "status": "pages_imported", "note": "fp57 tourism case study flow-chart，box A-H；该 PDF 页眉误写 Test 7"},
    {"key": "17-3-listening", "slots": [8, 9, 10], "pages": {"book17": [53]}, "answer_pages": {}, "status": "pages_imported", "note": "fp53 整块 Q1-10 Advice on surfing holidays"},
    {"key": "21-3-listening", "slots": [23, 24], "pages": {}, "answer_pages": {}, "status": "root_cause_found_fix_deferred_s12", "note": "raw-328 中 Questions 23 and 24 头粘连在选项 E span 末尾；cam21 镜像同组结构干净；融合修复在 S12"},
]
a_cases = [
    {"key": "1-1-listening", "slots": [41], "answer_pages": {"book1": [136]}, "status": "pages_imported"},
    {"key": "1-2-listening", "slots": [40, 41], "answer_pages": {"book1": [140]}, "status": "pages_imported"},
    {"key": "1-2-reading", "slots": [41], "answer_pages": {"book1": [143]}, "status": "pages_imported"},
    {"key": "1-4-listening", "slots": [41, 42], "answer_pages": {"book1": [148]}, "status": "pages_imported"},
    {"key": "10-1-reading", "slots": [34], "answer_pages": {"book10": [145]}, "status": "ocr_done_s06b_fusion_s12", "note": "fp145 乱码块 OCR 复核在 S06b"},
]

partial_entries = [r for r in reg["results"] if r.get("parse_status") == "partial"]
no_raw = [r for r in reg["results"] if "parse_status" not in r]

imports = []
for root_, dirs, files in os.walk(os.path.join(ROOT, "ielts-data/derived/pdf")):
    for f in files:
        if f.startswith("provenance-"):
            p = os.path.join(root_, f)
            m = json.load(open(p, encoding="utf-8"))
            imports.append({
                "file": os.path.relpath(p, ROOT).replace("\\", "/"),
                "book": m.get("book"), "pages": m.get("returned_pages"),
                "imported_at": m.get("imported_at"), "assets": len(m.get("assets", [])),
                "missing_pages": m.get("missing_pages"), "missing_assets": m.get("missing_assets"),
            })
imports.sort(key=lambda x: x["imported_at"] or "")

raw328 = {
    "raw_index": 328, "book": 21, "test": 3, "skill": "listening",
    "slug": "ielts-listening-test-207", "title": "IELTS Listening Test 207 (practicepteonline)",
    "finding": "raw HTML 中 'Questions 23 and 24' 头粘连在前一选项 span 末尾：'...clothing labels. Questions 23 and 24</span>'；该组指令与内容（Choose TWO letters A-E）在后续段落完整存在",
    "effect": "html-questions.mjs RE_Q_HEADING（^锚定）无法识别粘连头 → store 解析丢组 [23,24]（38/40 槽）",
    "cam21_mirror": "cam21 镜像 t3-listening.html 结构干净（<p class='q-label'>），同组 Q23/24 与 accept [D,E] 均在",
    "candidate_fixes": [
        "a) 解析器支持组头粘连拆分（需防误把承载前组选项的块判为新组头）",
        "b) HTML 预处理在 '。Questions N and M' 处插 </p><p> 断段",
        "c) book21 融合优先用 cam21 镜像作源",
    ],
    "decision_deferred_to": "S12 融合",
}

out = {
    "generated_at": "2026-10-04",
    "stage": "S06d",
    "summary": {
        "regression": {"entries": reg["total_entries"], "parsed": reg["parsed"], "ok": reg["ok"], "partial": reg["partial"],
                        "q_missing": reg["totals"]["q_missing"], "a_missing": reg["totals"]["a_missing"], "empty_slots": reg["totals"]["empty_slots"]},
        "q_missing_cases": len(q_cases), "q_missing_slots": sum(len(c["slots"]) for c in q_cases),
        "a_missing_cases": len(a_cases), "a_missing_slots": sum(len(c["slots"]) for c in a_cases),
        "pages_imported_cases": sum(1 for c in q_cases + a_cases if c["status"].startswith("pages_imported")),
        "imports_total": len(imports), "imported_books": sorted(set(i["book"] for i in imports)),
    },
    "q_missing_cases": q_cases,
    "a_missing_cases": a_cases,
    "raw328_stuck_header": raw328,
    "import_inventory": imports,
    "partial_entries_snapshot": [{"key": r["key"], "q": f"{r['questions']}/{r['expected_total']}", "a": r["answers"],
                                   "warnings": r["warnings"], "missing_q": r["questions_missing"], "missing_a": r["answer_missing"]} for r in partial_entries],
    "no_raw_entries": [{"key": f"{r['book']}-{r['test']}-{r['skill']}", "reason": r.get("reason"), "source": "S04 index; book3 T2-T4 listening -> PDF 提取已覆盖; book21 -> cam21 镜像（S06 交叉核对 all_ok）"} for r in no_raw],
    "cam21_crosscheck": {"all_ok": cam.get("all_ok"), "evidence": "evidence/S06-cam21-crosscheck.json"},
    "book20": {"probe": "evidence/S06-book20-probe.json", "download": "evidence/S06-book20-download.json",
                "verify": "evidence/S06-book20-verify.json", "structure": "evidence/S06-book20-structure.json",
                "all_ok": b20.get("all_ok"), "part4_all_found": all(bool(t.get("part4_evidence")) for t in b20["tests"].values())},
}
OUT = os.path.join(EV, "S06d-missing-resolution.json")
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(json.dumps(out["summary"], ensure_ascii=False, indent=1))
print("->", OUT)
