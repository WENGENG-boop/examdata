#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""S02 (tmp tool): generate ielts-api/data/expected-structure.json.

Curated tables transcribed from S02 probe evidence (see evidence dir):
  - listening-sections.json / listening-sections-b1517.json  (part start pages)
  - reading-sections.json                                    (passage start pages)
  - range-scan-all.txt / scan-boundaries.txt                 (question ranges)
  - probe-w / probe-gt / probe-b* / key-pages                (W/S + GT pages)

Assertions enforce per-test continuity of question numbers; totals may be
40/41/42 where the actual book differs from the default (e.g. book 1).
"""
import json
import os
import sys
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "ielts-api", "data", "expected-structure.json")

RUN_ID = "20261003T140007Z-repair"

STD_L = [[1, 10], [11, 20], [21, 30], [31, 40]]
STD_R = [[1, 13], [14, 26], [27, 40]]

# ---------------------------------------------------------------- listening
LISTENING_PAGES = {
    1: {1: [18, 20, 22, 24], 2: [40, 41, 42, 44], 3: [60, 62, 63, 64], 4: [81, 83, 84, 85]},
    2: {1: [2, 3, 4, 5], 2: [14, 15, 16, None], 3: [25, 26, 27, 28], 4: [36, None, 37, 38]},
    3: {1: [12, 13, 15, 16], 2: [34, 36, 38, 40], 3: [58, 59, 61, 62], 4: [80, 82, 83, 85]},
    4: {1: [11, 13, 15, 18], 2: [35, 37, 39, 41], 3: [58, 60, 62, 64], 4: [82, 83, 85, 87]},
    5: {1: [11, 13, 14, 16], 2: [33, 34, 36, 37], 3: [56, 58, 60, 61], 4: [79, 80, 82, 84]},
    6: {1: [11, 13, 15, 17], 2: [34, 36, 38, 39], 3: [56, 58, 60, 62], 4: [79, 80, 82, 84]},
    7: {1: [15, 17, 19, 21], 2: [38, 39, 41, 43], 3: [61, 63, 65, 68], 4: [86, 88, 90, 92]},
    8: {1: [9, 11, 13, 15], 2: [32, 34, 36, 38], 3: [55, 58, 60, 62], 4: [80, 81, 83, 85]},
    10: {1: [3, 5, 7, 9], 2: [26, 28, 30, 32], 3: [50, 51, 53, 55], 4: [73, 75, 77, 79]},
    11: {1: [3, 5, 7, 9], 2: [26, 28, 30, 32], 3: [50, 52, 54, 56], 4: [73, 75, 77, 79]},
    12: {5: [11, 13, 15, 16], 6: [31, 32, 34, 36], 7: [54, 55, 57, 59], 8: [75, 76, 78, 80]},
    13: {1: [11, 12, 14, 16], 2: [None, 34, 36, 38], 3: [55, 56, 58, 60], 4: [77, 78, 80, 82]},
    14: {1: [11, 12, 14, 16], 2: [33, 34, 36, 38], 3: [54, 55, 57, 59], 4: [76, 78, 80, 82]},
    15: {1: [11, 12, 14, 16], 2: [32, 33, 35, 37], 3: [53, 55, 57, 58], 4: [75, 76, 78, 80]},
    17: {1: [10, 11, 13, 15], 2: [31, 32, 34, 36], 3: [53, 54, 56, 58], 4: [75, 76, 78, 80]},
}

LISTENING_RANGES = {
    1: {1: [[1, 10], [11, 21], [22, 31], [32, 41]],
        2: [[1, 10], [11, 20], [21, 32], [33, 41]],
        3: [[1, 12], [13, 23], [24, 32], [33, 42]],
        4: [[1, 12], [13, 21], [22, 31], [32, 42]]},
}

LISTENING_TEST_NOTES = {
    (2, 1): "compressed-layout inference: p2 header area mixed with front-matter text; S06 re-check required",
    (2, 2): "section 4 header not captured in probe; content expected on p16; S06 re-check required",
    (2, 4): "section 2 header not captured in probe; content spans p36-37; S06 re-check required",
    (13, 2): "section 1 page not captured in probe (p34 body text 'Questions 11-16' confirms section 2); S06 re-check required",
}

# ---------------------------------------------------------------- reading
READING_PAGES = {
    1: {1: [26, 30, 34], 2: [46, 50, 54], 3: [66, 70, 74], 4: [86, 90, 93]},
    2: {1: [6, 8, 10], 2: [17, 19, 21], 3: [29, 31, 32], 4: [39, 41, 43]},
    3: {1: [18, 23, 27], 2: [42, 46, 51], 3: [64, 68, 73], 4: [88, 92, 96]},
    4: {1: [19, 24, 28], 2: [43, 47, 51], 3: [66, 71, 75], 4: [89, 93, 97]},
    5: {1: [17, 21, 25], 2: [39, 44, 49], 3: [63, 67, 72], 4: [86, 90, 95]},
    6: {1: [19, 23, 27], 2: [41, 45, 49], 3: [64, 68, 72], 4: [86, 90, 94]},
    7: {1: [23, 27, 31], 2: [45, 49, 53], 3: [70, 74, 79], 4: [94, 97, 101]},
    8: {1: [17, 21, 25], 2: [40, 44, 48], 3: [64, 69, 73], 4: [87, 92, 96]},
    10: {1: [10, 14, 18], 2: [34, 38, 42], 3: [57, 61, 65], 4: [81, 85, 90]},
    11: {1: [11, 14, 18], 2: [34, 38, 42], 3: [58, 62, 66], 4: [80, 84, 89]},
    12: {5: [17, 21, 24], 6: [37, 43, 47], 7: [60, 64, 67], 8: [81, 84, 89]},
    13: {1: [17, 21, 25], 2: [39, 43, 47], 3: [61, 65, 69], 4: [83, 86, 90]},
    14: {1: [17, 21, 26], 2: [39, 43, 47], 3: [60, 64, 68], 4: [83, 87, 91]},
    15: {1: [17, 21, 25], 2: [38, 41, 45], 3: [59, 63, 67], 4: [81, 85, 89]},
    17: {1: [16, 20, 24], 2: [37, 41, 45], 3: [59, 63, 67], 4: [81, 85, 89]},
}

READING_RANGES = {
    1: {1: [[1, 15], [16, 28], [29, 40]], 2: [[1, 12], [13, 27], [28, 41]],
        3: [[1, 12], [13, 26], [27, 38]], 4: [[1, 13], [14, 27], [28, 39]]},
    2: {1: [[1, 13], [14, 27], [28, 40]], 2: STD_R, 3: STD_R, 4: STD_R},
    3: {1: [[1, 14], [15, 28], [29, 40]], 2: [[1, 13], [14, 28], [29, 40]],
        3: [[1, 12], [13, 25], [26, 40]], 4: [[1, 13], [14, 27], [28, 40]]},
    4: {1: [[1, 14], [15, 26], [27, 40]], 2: [[1, 13], [14, 26], [27, 40]],
        3: [[1, 13], [14, 26], [27, 40]], 4: [[1, 13], [14, 27], [28, 40]]},
    5: {1: [[1, 13], [14, 26], [27, 40]], 2: [[1, 13], [14, 27], [28, 40]],
        3: [[1, 13], [14, 26], [27, 40]], 4: [[1, 13], [14, 26], [27, 40]]},
    6: {1: [[1, 13], [14, 26], [27, 40]], 2: [[1, 13], [14, 26], [27, 40]],
        3: [[1, 13], [14, 27], [28, 40]], 4: [[1, 13], [14, 26], [27, 40]]},
}

# ---------------------------------------------------------------- writing / speaking (academic tests)
WS_PAGES = {
    1: {1: {"w": [37, 38], "s": 39}, 2: {"w": [57, 58], "s": 59}, 3: {"w": [78, 79], "s": 80}, 4: {"w": [97, 98], "s": 99}},
    2: {1: {"w": [12, 13], "s": 13}, 2: {"w": [23, 24], "s": 24}, 3: {"w": [34, 35], "s": 35}, 4: {"w": [45, 46], "s": 46}},
    3: {1: {"w": [31, 32], "s": 33}, 2: {"w": [55, 56], "s": 57}, 3: {"w": [77, 78], "s": 79}, 4: {"w": [101, 102], "s": 103}},
    4: {1: {"w": [32, 33], "s": 34}, 2: {"w": [55, 56], "s": 57}, 3: {"w": [79, 80], "s": 81}, 4: {"w": [101, 102], "s": 103}},
    5: {1: {"w": [30, 31], "s": 32}, 2: {"w": [53, 54], "s": 55}, 3: {"w": [76, 77], "s": 78}, 4: {"w": [99, 100], "s": 101}},
    6: {1: {"w": [31, 32], "s": 33}, 2: {"w": [53, 54], "s": 55}, 3: {"w": [76, 77], "s": 78}, 4: {"w": [99, 100], "s": 101}},
    7: {1: {"w": [35, 36], "s": 37}, 2: {"w": [58, 59], "s": 60}, 3: {"w": [83, 84], "s": 85}, 4: {"w": [106, 107], "s": 108}},
    8: {1: {"w": [29, 30], "s": 31}, 2: {"w": [52, 53], "s": 54}, 3: {"w": [77, 78], "s": 79}, 4: {"w": [100, 101], "s": 102}},
    10: {1: {"w": [23, 24], "s": 25}, 2: {"w": [47, 48], "s": 49}, 3: {"w": [70, 71], "s": 72}, 4: {"w": [94, 95], "s": 96}},
    11: {1: {"w": [23, 24], "s": 25}, 2: {"w": [47, 48], "s": 49}, 3: {"w": [70, 71], "s": 72}, 4: {"w": [93, 94], "s": 95}},
    12: {5: {"w": [28, 29], "s": 30}, 6: {"w": [51, 52], "s": 53}, 7: {"w": [72, 73], "s": 74}, 8: {"w": [93, 94], "s": 95}},
    13: {1: {"w": [30, 31], "s": 32}, 2: {"w": [52, 53], "s": 54}, 3: {"w": [74, 75], "s": 76}, 4: {"w": [95, 96], "s": 97}},
    14: {1: {"w": [30, 31], "s": 32}, 2: {"w": [51, 52], "s": 53}, 3: {"w": [73, 74], "s": 75}, 4: {"w": [95, 96], "s": 97}},
    15: {1: {"w": [29, 30], "s": 31}, 2: {"w": [50, 51], "s": 52}, 3: {"w": [72, 73], "s": 74}, 4: {"w": [94, 95], "s": 96}},
    17: {1: {"w": [28, 29], "s": 30}, 2: {"w": [50, 51], "s": 52}, 3: {"w": [72, 73], "s": 74}, 4: {"w": [93, 94], "s": 95}},
}

# ---------------------------------------------------------------- general training
GT_DATA = {
    1: {"status": "in_book", "tests": {
        "gta": {"ranges": [[1, 14], [15, 29], [30, 41]], "rpages": [100, 104, 108], "w": [111, 112],
                "wnote": "WT1 p111, WT2 p112 (probe)"}}},
    2: {"status": "in_book", "tests": {
        "gta": {"ranges": [[1, 13], [14, 26], [27, 40]], "rpages": [47, 49, 51], "w": [53, 53], "wnote": "both tasks on p53 (probe)"},
        "gtb": {"ranges": [[1, 13], [14, 26], [27, 40]], "rpages": [54, 56, 58], "w": [60, 60], "wnote": "both tasks on p60 (probe)"}}},
    3: {"status": "in_book", "tests": {
        "gta": {"ranges": [[1, 13], [14, 26], [27, 40]], "rpages": [104, 107, 111], "w": [116, 117], "wnote": "WT1 p116, WT2 p117 (probe)"},
        "gtb": {"ranges": [[1, 13], [14, 27], [28, 40]], "rpages": [118, 122, 126], "w": [129, 130], "wnote": "WT1 p129, WT2 p130 (probe)"}}},
    4: {"status": "in_book", "tests": {
        "gta": {"ranges": [[1, 14], [15, 27], [28, 40]], "rpages": [104, 108, 112], "w": [116, 116], "wnote": "both tasks on p116; section-1 header OCR 'Questions 1-5' but body reads 1-14 (probe)"},
        "gtb": {"ranges": [[1, 14], [15, 27], [28, 40]], "rpages": [117, 122, 126], "w": [130, 130], "wnote": "both tasks on p130 (probe)"}}},
    5: {"status": "in_book", "tests": {
        "gta": {"ranges": [[1, 14], [15, 27], [28, 40]], "rpages": [102, 106, 110], "w": [114, 114], "wnote": "both tasks on p114 (probe)"},
        "gtb": {"ranges": [[1, 14], [15, 27], [28, 40]], "rpages": [115, 120, 124], "w": [128, 128], "wnote": "both tasks on p128 (probe); section-1 page p115 confirmed earlier ('SECTION l Questions 1-14')"}}},
    6: {"status": "in_book", "tests": {
        "gta": {"ranges": [[1, 14], [15, 27], [28, 40]], "rpages": [102, 106, 110], "w": [114, 114], "wnote": "both tasks on p114 (probe)"},
        "gtb": {"ranges": [[1, 14], [15, 27], [28, 40]], "rpages": [115, 119, 123], "w": [127, 127], "wnote": "both tasks on p127 (probe)"}}},
    7: {"status": "in_book", "tests": {
        "gta": {"ranges": [[1, 14], [15, 27], [28, 40]], "rpages": [109, 113, 117], "w": [121, 121], "wnote": "both tasks on p121 (probe)"},
        "gtb": {"ranges": [[1, 14], [15, 27], [28, 40]], "rpages": [122, 126, 130], "w": [133, 133], "wnote": "both tasks on p133 (probe)"}}},
    8: {"status": "in_book", "tests": {
        "gta": {"ranges": [[1, 14], [15, 27], [28, 40]], "rpages": [103, 107, 111], "w": [115, 115], "wnote": "both tasks on p115 (probe); section-3 header OCR truncated (28-33) but range 28-40 from scan boundaries"},
        "gtb": {"ranges": [[1, 14], [15, 27], [28, 40]], "rpages": [116, 120, 124], "w": [128, 128], "wnote": "both tasks on p128 (probe)"}}},
    10: {"status": "in_book", "tests": {
        "gta": {"ranges": [[1, 14], [15, 27], [28, 40]], "rpages": [97, 101, 105], "w": [109, 109], "wnote": "both tasks on p109 (inferred: OCR 'T A S K 1', spend-anchor at p109; S06 verify)"},
        "gtb": {"ranges": [[1, 14], [15, 27], [28, 40]], "rpages": [110, 114, 118], "w": [122, 122], "wnote": "both tasks on p122 (probe)"}}},
    11: {"status": "not_in_book", "reason": "table of contents (p2) lists no General Training test; no GT markers in book body", "probe": "probe-gt p2-6"},
    12: {"status": "not_in_book", "reason": "copyright page (p3) states Academic; no GT markers in book body", "probe": "gt-probe p2-5"},
    13: {"status": "not_in_book", "reason": "p3 shows a different ISBN/edition imprint (Academic only)", "probe": "gt-probe p3"},
    14: {"status": "not_in_book", "reason": "p3 shows a different ISBN/edition imprint (Academic only)", "probe": "gt-probe p3"},
    15: {"status": "not_in_book", "reason": "p3 Chinese front-matter page identifies Academic; no GT markers", "probe": "gt-probe p3"},
    17: {"status": "not_in_book", "reason": "table of contents (p3) lists no General Training test", "probe": "gt-probe p3"},
}

# ---------------------------------------------------------------- book-level facts
TEXT_LAYER = {b: True for b in [1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 17]}
for b in [9, 16, 18, 19, 20]:
    TEXT_LAYER[b] = False

UNVERIFIED_REASON = {}
for b in [9, 16, 18, 19, 20]:
    UNVERIFIED_REASON[b] = "no_text_layer"
UNVERIFIED_REASON[21] = "no_local_pdf"

BOOKS_ALL = list(range(1, 22))


def expand(ranges):
    out = []
    for a, b in ranges:
        out.extend(range(a, b + 1))
    return out


def check_contiguous(ranges, label):
    nums = expand(ranges)
    if nums[0] != 1:
        raise AssertionError(f"{label}: first number {nums[0]} != 1")
    for i in range(1, len(nums)):
        if nums[i] != nums[i - 1] + 1:
            raise AssertionError(f"{label}: gap at {nums[i - 1]}->{nums[i]}")
    return nums


def test_numbers(book):
    if book == 12:
        return [5, 6, 7, 8]
    return [1, 2, 3, 4]


def build():
    books_out = []
    for book in BOOKS_ALL:
        entry = {
            "book": book,
            "text_layer": TEXT_LAYER.get(book),
            "tests": [],
        }
        verified = book in TEXT_LAYER and TEXT_LAYER[book] and book != 21
        if book == 21:
            verified = False
        base_status = "verified" if verified else "unverified"
        base_reason = None if verified else UNVERIFIED_REASON.get(book, "unknown")

        for t in test_numbers(book):
            tentry = {"test": t, "test_index": test_numbers(book).index(t) + 1}
            # ---- listening
            if verified:
                pages = LISTENING_PAGES[book][t]
                ranges = LISTENING_RANGES.get(book, {}).get(t, STD_L)
                if len(pages) != 4:
                    raise AssertionError(f"b{book} T{t} listening pages != 4")
                nums = check_contiguous(ranges, f"b{book} T{t} L")
                parts = []
                for i in range(4):
                    parts.append({
                        "part": f"P{i+1}",
                        "ranges": [ranges[i]],
                        "pages": [pages[i]] if pages[i] else [],
                        "page_unconfirmed": pages[i] is None,
                        "note": LISTENING_TEST_NOTES.get((book, t)) if pages[i] is None else None,
                    })
                tentry["listening"] = {"status": "verified", "expected_total": len(nums), "parts": parts}
            else:
                tentry["listening"] = {"status": base_status, "reason": base_reason,
                                       "expected_total": 40,
                                       "parts": [{"part": f"P{i+1}", "ranges": [STD_L[i]], "pages": [], "page_unconfirmed": True}
                                                 for i in range(4)]}
            # ---- academic reading
            if verified:
                rp = READING_PAGES[book][t]
                rr = READING_RANGES.get(book, {}).get(t, STD_R)
                nums = check_contiguous(rr, f"b{book} T{t} R")
                parts = [{"part": f"P{i+1}", "ranges": [rr[i]], "pages": [rp[i]]} for i in range(3)]
                tentry["academic_reading"] = {"status": "verified", "expected_total": len(nums), "parts": parts}
            else:
                tentry["academic_reading"] = {"status": base_status, "reason": base_reason,
                                              "expected_total": 40,
                                              "parts": [{"part": f"P{i+1}", "ranges": [STD_R[i]], "pages": []} for i in range(3)]}
            # ---- writing / speaking
            if verified:
                ws = WS_PAGES[book][t]
                tentry["academic_writing"] = {"status": "verified", "tasks": [
                    {"part": "WT1", "pages": [ws["w"][0]]},
                    {"part": "WT2", "pages": [ws["w"][1]]}]}
                tentry["speaking"] = {"status": "verified", "parts": [{"part": "SP", "pages": [ws["s"]]}]}
            else:
                tentry["academic_writing"] = {"status": base_status, "reason": base_reason,
                                              "tasks": [{"part": "WT1", "pages": []}, {"part": "WT2", "pages": []}]}
                tentry["speaking"] = {"status": base_status, "reason": base_reason,
                                      "parts": [{"part": "SP", "pages": []}]}
            entry["tests"].append(tentry)

        # ---- general
        gt = GT_DATA.get(book)
        if gt is None:
            entry["general"] = {"status": "unverified", "reason": UNVERIFIED_REASON.get(book, "unknown"), "tests": []}
        elif gt["status"] == "in_book":
            gtests = []
            for label, g in gt["tests"].items():
                nums = check_contiguous(g["ranges"], f"b{book} {label} GT R")
                if len(g["rpages"]) != 3:
                    raise AssertionError(f"b{book} {label} GT rpages != 3")
                gtests.append({
                    "test": label,
                    "test_index": 1 if label == "gta" else 2,
                    "reading": {"status": "verified", "expected_total": len(nums),
                                "parts": [{"part": f"P{i+1}", "ranges": [g["ranges"][i]], "pages": [g["rpages"][i]]} for i in range(3)]},
                    "writing": {"status": "verified", "tasks": [
                        {"part": "WT1", "pages": [g["w"][0]]},
                        {"part": "WT2", "pages": [g["w"][1]]}],
                        "note": g.get("wnote")},
                })
            entry["general"] = {"status": "in_book", "tests": gtests}
        else:
            entry["general"] = {"status": gt["status"], "reason": gt["reason"], "probe": gt["probe"], "tests": []}
        books_out.append(entry)

    out = {
        "schema": "ielts.expected-structure/1",
        "generated_by": "ielts-api/tools/tmp_gen_structure.py",
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_id": RUN_ID,
        "source_evidence": "ielts-data/runs/20261003T140007Z-repair/evidence/",
        "books": books_out,
    }
    return out


def main():
    data = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    # summary to stdout
    n_units = 0
    for b in data["books"]:
        for t in b["tests"]:
            n_units += len(t["listening"]["parts"]) + len(t["academic_reading"]["parts"])
            n_units += len(t["academic_writing"]["tasks"]) + len(t["speaking"]["parts"])
        for g in b["general"]["tests"]:
            n_units += len(g["reading"]["parts"]) + len(g["writing"]["tasks"])
    print(json.dumps({"out": OUT, "books": len(data["books"]), "units": n_units}, ensure_ascii=False))


if __name__ == "__main__":
    main()
