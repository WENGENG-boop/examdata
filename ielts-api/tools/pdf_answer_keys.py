#!/usr/bin/env python3
"""pdf_answer_keys.py — 从本地剑桥雅思真题 PDF 的答案页提取逐套题号范围（v5）。

目的（S02）：为 expected-manifest 提供"来自原书"的证据：
  - 每册每套 Listening / Academic Reading / General Training Reading 的
    题号集合与 Part/Passage 分段范围；
  - 每项证据带 1-based 文件页。

v5 相对 v4 的修正（均有页面原文佐证，见 evidence/key-pages/ 转储）：
  6. normalize 增加定向 OCR 归一：数字间 em/en dash/波浪号/CJK 一 → "-"
     （剑10/13）；"Ç" → ","（剑10 "Reading Passage 1ÇQuestions"）；
     "Sectio11/Questio11s" → "Section/Questions"（剑6）；"Questions I 1-20"
     → "Questions 11-20"（剑5 T3）；字母间空格标题折叠（剑10 "A C A D E M IC"）；
  7. 裸题号行的保守 OCR 修复（OCR_DIGIT 映射），仅在严格序列续接校验通过时
     采纳，并逐条记入输出 ocr_repairs（剑6 "IS"=15）；
  8. 技能级题号 = declared ∪ observed（修复剑1 T3 声明缺 Q12 而 observed 含
     Q12 的场景），numbers_source 相应为 declared/observed/declared+observed。

v4 相对 v3 的修正（均有 v3 运行结果或页面原文佐证）：
  1. "Section 1, Questions 1-10" 行不再被 PART_RE 吞掉范围（剑3 全空根因）；
  2. 写作页排除：TEST 标记拒绝 WRITING/TASK 行（"TEST 1, WRITING TASK 1"
     误报为测试标记）；终止条件识别 "Sample Writing answers"（大小写不敏感，
     剑15 的 kp=27 根因）与 MODEL ANSWER + WRITING；
  3. 页级归属游标：无标记页按技能续接规则（Listening→Reading 续接当前测试，
     Reading→Listening 开新待定块）归属；待定块按页序分配缺失编号（剑4 T4
     被并入 T3、剑15 写作页抢占 T1-T4 的根因）；
  4. GT 独立块：显式 Test A/B 字母优先；无字母页按"含 Q1 即新套"合并；
     输出键 gt（单套无字母）/ gt_a / gt_b…，不再混入数字测试；
  5. pending 组在 missing 为空时被静默丢弃的问题修复（扩展缺失编号 + anomaly）。

注意：剑2 答案页为多栏交错（listening/reading 答案在同一页交错排版且无 TEST
标记），自动定位不可靠 —— 由 manual-verification.json 覆盖，本工具对其输出
标 anomalies 记录 unreliable_columns。剑1 的 41/42 题属原书结构（question 页
已验证），由 manual 层标注 expected。

输出：JSON 到指定路径；stdout 仅打印摘要。绝不写入 tmp_audit_ielts。
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import pymupdf

AK_RE = re.compile(r"answer\s*key|answer\s*keys|listening and reading answer keys", re.I)
TEST_RE = re.compile(r"^(?:PRACTICE\s+)?TEST\s*[.:·]?\s*([1-9]|[IVX]{1,4})\b", re.I)
GT_TEST_RE = re.compile(r"TEST\s*[-–—.·]?\s*([AB])\b")
GT_HEAD_RE = re.compile(r"GENERAL\s*TRAIN|^GENERAL\s*$|TRAI\S{0,3}ING\s*TEST", re.I)
GT_MARK_RE = re.compile(r"GENERAL|TRAI\S{0,4}G", re.I)
LISTEN_RE = re.compile(r"^(LISTENING|LISTENING KEYS|LISTENI\S{0,2}G)\s*$", re.I)
READ_RE = re.compile(r"^(READING|ACADEMIC READING|READING MODULE|READI\S{0,2}G)\s*$", re.I)
SKIP_LINE_RE = re.compile(r"answer", re.I)
PART_RE = re.compile(r"^(?:Section|SECTION|Part|PART)\s*([1-9]|I{1,3}|IV|V|VI)\b")
PASSAGE_RE = re.compile(r"^(?:Reading Passage|READING PASSAGE|Rea\S{0,3}ing Passage)\s*([1-3]|I{1,3})\b", re.I)
RANGE_RE = re.compile(
    r"Questions?\s*(\d{1,2})\s*(?:[^\w\d]{1,6}|\s+(?:and|to)\s+)\s*(\d{1,2})",
    re.I,
)
BARE_INT_RE = re.compile(r"^(\d{1,2})$")
WRITING_LINE_RE = re.compile(r"WRIT|TASK|SPEAK", re.I)
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}


def norm_num(tok: str) -> int:
    tok = tok.upper()
    return int(tok) if tok.isdigit() else ROMAN.get(tok, 0)


# 答案页“裸题号行”的保守 OCR 修复映射（仅在严格序列续接校验通过时采纳并记录）。
# 覆盖已见实例：剑6 "IS"=15、"ll"=11。刻意不含 B/O/Z 等答案字母常见项。
OCR_DIGIT = {"I": "1", "l": "1", "|": "1", "S": "5", "s": "5"}


def ocr_number_candidate(s: str):
    if not (2 <= len(s) <= 4):
        return None
    out = []
    for ch in s:
        if ch.isdigit():
            out.append(ch)
        elif ch in OCR_DIGIT:
            out.append(OCR_DIGIT[ch])
        else:
            return None
    if not any(ch.isdigit() for ch in out):
        return None
    try:
        n = int("".join(out))
    except ValueError:
        return None
    return n if 1 <= n <= 45 else None


def normalize(text: str) -> str:
    t = text.replace("\u00a0", " ")
    t = re.sub(r"(?<=\d)[·．](?=\d)", "", t)
    # OCR 连字符变体（em/en dash、波浪号、CJK 一）在数字之间统一为 "-"（剑10/13 页面原文）
    t = re.sub(r"(?<=\d)\s*[–—~一]\s*(?=\d)", "-", t)
    # OCR 逗号变体（剑10 "Reading Passage 1ÇQuestions"）
    t = re.sub(r"(?<=[0-9A-Za-z])[Çç](?=[A-Za-z])", ",", t)
    t = re.sub(r"\bQ\s*uestions?", "Questions", t)     # 剑10/13/15 "Q uestions"
    t = re.sub(r"\bQu\s+estions?", "Questions", t)
    t = re.sub(r"\bQuesti[o。0]ns?", "Questions", t)
    t = re.sub(r"Sectio11", "Section", t, flags=re.I)   # 剑6 "Sectio11 3, Questio11s"
    t = re.sub(r"Questio11s", "Questions", t, flags=re.I)
    t = re.sub(r"Questio11\b", "Question", t, flags=re.I)
    t = re.sub(r"(Questions?\s*)[Il|]\s+(\d)", r"\g<1>1\g<2>", t)   # 剑5 "Questions I 1-20"
    t = re.sub(r"(Questions?\s*)[Il|]{2}(?=[\s\d-])", r"\g<1>11", t)
    # 字母间空格的大写标题（剑10 "A C A D E M IC READING" -> "ACADEMIC READING"）
    t = re.sub(r"\b[A-Z]{1,2}\b(?:\s+[A-Z]{1,2}\b){2,}",
               lambda m: m.group(0).replace(" ", ""), t)
    return t


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def new_container(attribution="marker"):
    return {"parts": [], "pages": [], "attribution": attribution}


def new_block(page, gt=None):
    return {"gt": gt, "parts": [], "pages": [page], "last_skill": None}


def container_part(cont, kind, part_no, skill, page):
    for p in cont["parts"]:
        if p["part"] == part_no and p["skill"] == skill:
            if page not in p["pages"]:
                p["pages"].append(page)
            return p
    p = {"part": part_no, "kind": kind, "skill": skill, "ranges": [], "observed": [], "pages": [page]}
    cont["parts"].append(p)
    return p


def merge_container(dst, src):
    for pg in src["pages"]:
        if pg not in dst["pages"]:
            dst["pages"].append(pg)
    for p in src["parts"]:
        d = container_part(dst, p["kind"], p["part"], p["skill"], p["pages"][0])
        for r in p["ranges"]:
            if r not in d["ranges"]:
                d["ranges"].append(r)
        for o in p["observed"]:
            if not d["observed"] or o == d["observed"][-1] + 1:
                d["observed"].append(o)


def container_has_one(cont):
    for p in cont["parts"]:
        for a, _b in p["ranges"]:
            if a == 1:
                return True
        if p["observed"] and p["observed"][0] == 1:
            return True
    return False


class BookParser:
    def __init__(self, pdf_path: Path, book: int):
        self.pdf_path = pdf_path
        self.book = book
        self.out = {
            "book": book,
            "pdf": str(pdf_path).replace("\\", "/"),
            "pdf_sha256": sha256_of(pdf_path),
            "pdf_pages": 0,
            "key_pages": [],
            "tests": {},
            "anomalies": [],
        }
        self.tests = self.out["tests"]
        self.blocks = []      # academic 待定块（无标记页归组）
        self.gt_blocks = []   # GT 块
        self._test = None
        self._variant = "academic"
        self._skill = None
        self._part = None
        self._cursor = None   # {"kind": "test"/"block"/"gt", ...}

    # ---------- helpers ----------
    def _slot(self, test):
        t = self.tests.setdefault(str(test), {})
        key = self._skill if self._skill in ("listening", "reading") else "unknown"
        return t.setdefault(key, new_container("marker"))

    def _add(self, target, kind, part_no, page, a=None, b=None, n=None):
        if target[0] == "test":
            cont = self._slot(target[1])
        else:
            cont = target[1]
        if page not in cont["pages"]:
            cont["pages"].append(page)
        skill = self._skill if self._skill in ("listening", "reading") else "unknown"
        p = container_part(cont, kind, part_no, skill, page)
        recorded = False
        if a is not None and [a, b] not in p["ranges"]:
            p["ranges"].append([a, b])
            recorded = True
        if n is not None and (not p["observed"] or n == p["observed"][-1] + 1):
            p["observed"].append(n)
            recorded = True
        return recorded

    def _continues(self, last_skill, seg_skill):
        if seg_skill is None or last_skill is None:
            return True
        if last_skill == seg_skill:
            return True
        return last_skill == "listening" and seg_skill == "reading"

    def _decide_target(self, page, test, variant, gt, seg_skill):
        if test is not None:
            self._cursor = {"kind": "test", "test": test, "last_skill": None}
            return ("test", test)
        if variant == "general" or gt is not None or (
                self._cursor is not None and self._cursor["kind"] == "gt"):
            blk = new_block(page, gt)
            self.gt_blocks.append(blk)
            self._cursor = {"kind": "gt", "block": blk, "last_skill": seg_skill}
            return ("block", blk)
        if self._cursor is not None and self._cursor["kind"] in ("test", "block") \
                and self._continues(self._cursor["last_skill"], seg_skill):
            if self._cursor["kind"] == "test":
                if seg_skill is not None:
                    self._cursor["last_skill"] = seg_skill
                return ("test", self._cursor["test"])
            blk = self._cursor["block"]
            if page not in blk["pages"]:
                blk["pages"].append(page)
            self._cursor["last_skill"] = seg_skill
            return ("block", blk)
        blk = new_block(page)
        self.blocks.append(blk)
        self._cursor = {"kind": "block", "block": blk, "last_skill": seg_skill}
        return ("block", blk)

    # ---------- main ----------
    def run(self):
        doc = pymupdf.open(self.pdf_path)
        n_pages = doc.page_count
        self.out["pdf_pages"] = n_pages
        start = max(0, int(n_pages * 0.45))
        key_started = False
        for i in range(start, n_pages):
            raw = doc[i].get_text("text")
            if not raw.strip():
                continue
            if not key_started:
                if AK_RE.search(raw):
                    key_started = True
                    self.out["key_pages"].append(i + 1)
                else:
                    continue
            else:
                self.out["key_pages"].append(i + 1)
            if re.search(r"sample\s+writing\s+answers?", raw, re.I) or (
                    re.search(r"(MODEL|SAMPLE)[- ]?ANSWER", raw, re.I) and "WRITING" in raw.upper()):
                break
            self.process_page(i + 1, raw)
        doc.close()
        self.post_process()
        return self.out

    # ---------- page ----------
    def process_page(self, page, raw):
        lines = [normalize(l.strip()) for l in raw.splitlines() if l.strip()]
        tmarks = []
        gt_head_seen = False
        for idx, s in enumerate(lines):
            if SKIP_LINE_RE.search(s):
                continue
            m = TEST_RE.match(s)
            if m and len(s) < 45 and not WRITING_LINE_RE.search(s):
                tmarks.append((idx, norm_num(m.group(1)), "academic", None))
                continue
            g = GT_TEST_RE.search(s)
            if g and len(s) < 70 and re.search(r"TEST", s) and not WRITING_LINE_RE.search(s):
                if gt_head_seen or GT_HEAD_RE.search(s) or GT_MARK_RE.search(s) \
                        or self._variant == "general":
                    tmarks.append((idx, None, "general", g.group(1).upper()))
                continue
            if GT_HEAD_RE.search(s) and len(s) < 70:
                gt_head_seen = True
                tmarks.append((idx, None, "general", None))
            elif GT_MARK_RE.search(s) and len(s) < 70:
                gt_head_seen = True

        # 同页既有 GT 头部（无字母）又有 TEST A/B 字母标记时，丢弃无字母标记：
        # 头部只是标题，整页归该字母测试（剑8 p159 空块 gt_b 的根因）
        if any(g is not None for (_i, _t, v, g) in tmarks if v == "general"):
            tmarks = [m for m in tmarks if not (m[2] == "general" and m[3] is None)]

        distinct = {(t, v, g) for (_i, t, v, g) in tmarks}
        if not tmarks:
            segments = [(0, len(lines), None, None, None)]
        elif len(distinct) == 1:
            _i, t, v, g = tmarks[0]
            segments = [(0, len(lines), t, v, g)]
        else:
            segments = []
            pos = 0
            for k, (idx, t, v, g) in enumerate(tmarks):
                end = tmarks[k + 1][0] if k + 1 < len(tmarks) else len(lines)
                segments.append((pos, end, t, v, g))
                pos = end

        for (a, b, test, variant, gt) in segments:
            seg = lines[a:b]
            if not seg:
                continue
            if test is not None:
                self._test = test
                self._variant = "academic"
            elif variant == "general":
                self._variant = "general"
            smarks = []
            for idx, s in enumerate(seg):
                if SKIP_LINE_RE.search(s):
                    continue
                if LISTEN_RE.match(s):
                    smarks.append((idx, "listening"))
                elif READ_RE.match(s):
                    smarks.append((idx, "reading"))
            if smarks and len({k for (_i, k) in smarks}) == 1:
                ssegs = [(0, len(seg), smarks[0][1])]
            elif smarks:
                ssegs = []
                pos = 0
                for k, (idx, skill) in enumerate(smarks):
                    end = smarks[k + 1][0] if k + 1 < len(smarks) else len(seg)
                    ssegs.append((pos, end, skill))
                    pos = end
            else:
                ssegs = [(0, len(seg), None)]
            for (sa, sb, skill) in ssegs:
                if skill is not None:
                    self._skill = skill
                target = self._decide_target(page, test, variant, gt, skill)
                self.process_lines(seg[sa:sb], page, target)

    def process_lines(self, lines, page, target):
        for s in lines:
            handled = False
            kind = None
            m = PART_RE.match(s)
            if m:
                self._part = norm_num(m.group(1))
                if self._skill is None:
                    self._skill = "listening"
                handled = True
                kind = "section"
            else:
                m2 = PASSAGE_RE.match(s)
                if m2:
                    self._part = norm_num(m2.group(1))
                    if self._skill is None:
                        self._skill = "reading"
                    handled = True
                    kind = "passage"
            part_no = self._part if self._part is not None else 0
            if handled:
                self._add(target, kind, part_no, page)
                # 不 continue：同一行可能含 "Section 1, Questions 1-10" 的范围声明
            for rm in RANGE_RE.finditer(s):
                a, b = int(rm.group(1)), int(rm.group(2))
                if a > 45 or b > 45 or a >= b or (b - a) > 30:
                    self.out["anomalies"].append(
                        {"page": page, "line": s[:80], "reason": "range_out_of_bounds", "a": a, "b": b}
                    )
                    continue
                self._add(target, "range", part_no, page, a=a, b=b)
            m3 = BARE_INT_RE.match(s)
            if m3:
                n = int(m3.group(1))
                if 1 <= n <= 45:
                    self._add(target, "list", part_no, page, n=n)
            else:
                cand = ocr_number_candidate(s)
                if cand is not None and self._add(target, "list", part_no, page, n=cand):
                    self.out.setdefault("ocr_repairs", []).append(
                        {"page": page, "line": s[:40], "as": cand})

    # ---------- attribution ----------
    def post_process(self):
        # 1) GT 块：显式字母优先；无字母按"含 Q1 即新套"合并
        gt_tests = []
        for blk in self.gt_blocks:
            prev = gt_tests[-1] if gt_tests else None
            if blk["gt"]:
                if prev and prev["letter"] == blk["gt"]:
                    merge_container(prev["cont"], blk)
                else:
                    gt_tests.append({"letter": blk["gt"], "had_letter": True, "cont": blk})
                continue
            if prev and not container_has_one(blk) \
                    and blk["pages"][0] - prev["cont"]["pages"][-1] <= 1:
                merge_container(prev["cont"], blk)
                self.out["anomalies"].append(
                    {"reason": "gt_continuation_merge", "pages": blk["pages"]})
            else:
                gt_tests.append({"letter": None, "had_letter": False, "cont": blk})
        used = {t["letter"] for t in gt_tests if t["letter"]}
        avail = [c for c in "ABCDEFGH" if c not in used]
        for t in gt_tests:
            if not t["letter"]:
                t["letter"] = avail.pop(0) if avail else "X"
        for t in gt_tests:
            if len(gt_tests) == 1 and not t["had_letter"]:
                key = "gt"
            else:
                key = "gt_" + t["letter"].lower()
            dst = self.tests.setdefault(key, {}).setdefault("reading", new_container("marker"))
            dst["attribution"] = "marker" if t["had_letter"] else "sequence_completion"
            merge_container(dst, t["cont"])
            self.out["anomalies"].append(
                {"reason": "gt_test", "key": key, "letter": t["letter"], "pages": t["cont"]["pages"]})

        # 2) academic 待定块 → 缺失测试编号（按页序）
        labeled = sorted(int(t) for t in self.tests if self.tests[t] and t.isdigit())
        blocks = self.blocks
        if not labeled:
            missing = list(range(1, len(blocks) + 1))
        else:
            max_t = max(labeled)
            missing = [n for n in range(1, max_t + 1) if n not in labeled]
            k = max_t
            while len(missing) < len(blocks):
                k += 1
                missing.append(k)
        if len(blocks) > len(missing):
            self.out["anomalies"].append(
                {"reason": "unassigned_pending_blocks", "blocks": len(blocks), "missing": missing})
        for blk, tno in zip(blocks, missing):
            t = self.tests.setdefault(str(tno), {})
            for p in blk["parts"]:
                key = p["skill"] if p["skill"] in ("listening", "reading") else "unknown"
                dst = t.setdefault(key, new_container("sequence_completion"))
                dst["attribution"] = "sequence_completion"
                merge_container(dst, {"pages": blk["pages"], "parts": [p]})
            self.out["anomalies"].append(
                {"reason": "sequence_completion", "test": tno, "pages": blk["pages"],
                 "parts": [[p["skill"], p["part"], p["ranges"], p["observed"][:3]] for p in blk["parts"]]})

        if len(blocks) == 1 and len(blocks[0]["pages"]) > 2:
            self.out["anomalies"].append(
                {"reason": "possible_missing_skill_headers", "pages": blocks[0]["pages"]})

        # 3) 汇总
        for _t, tv in self.tests.items():
            for _k, sk in tv.items():
                declared, observed = [], []
                for p in sk["parts"]:
                    for a, b in p["ranges"]:
                        declared.extend(range(a, b + 1))
                    observed.extend(p["observed"])
                sk["declared_numbers"] = sorted(set(declared))
                sk["observed_numbers"] = sorted(set(observed))
                if declared:
                    # declared ∪ observed，但 observed 仅补区间内空缺；区间外仅接受
                    # 从 max(declared)+1 起的连续尾段（≥3 个），否则视为页脚/串页污染
                    # （剑11 T4 L 页脚 "41" 的教训）。
                    lo, hi = min(declared), max(declared)
                    nums = set(declared)
                    for n in observed:
                        if lo <= n <= hi:
                            nums.add(n)
                    tail = []
                    k = hi + 1
                    while k in observed:
                        tail.append(k)
                        k += 1
                    if len(tail) >= 3:
                        nums.update(tail)
                    sk["numbers"] = sorted(nums)
                    sk["numbers_source"] = "declared+observed" if observed else "declared"
                elif observed:
                    sk["numbers"] = sorted(set(observed))
                    sk["numbers_source"] = "observed"
                else:
                    sk["numbers"] = []
                    sk["numbers_source"] = "none"
                sk["parts_summary"] = [
                    {"part": p["part"], "kind": p["kind"], "skill": p["skill"],
                     "ranges": p["ranges"], "observed": p["observed"], "pages": p["pages"]}
                    for p in sk["parts"]
                ]
                del sk["parts"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--books", default="1-20")
    ap.add_argument("--pdf-dir", default="tmp_audit_ielts/downloads")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    books = []
    for part in args.books.split(","):
        if "-" in part:
            a, b = part.split("-")
            books.extend(range(int(a), int(b) + 1))
        else:
            books.append(int(part))

    pdf_dir = Path(args.pdf_dir)
    results = {}
    for b in books:
        p = pdf_dir / f"book_{b}.pdf"
        if not p.exists():
            results[str(b)] = {"book": b, "missing": True}
            continue
        try:
            results[str(b)] = BookParser(p, b).run()
        except Exception as e:  # noqa: BLE001
            results[str(b)] = {"book": b, "error": str(e)}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    summary = {}
    for b, r in results.items():
        if r.get("missing"):
            summary[b] = "missing"
        elif r.get("error"):
            summary[b] = "error: " + r["error"][:60]
        else:
            tests = {
                t: {k: {"n": len(v.get("numbers", [])), "src": v.get("numbers_source"),
                        "pg": v.get("pages", [])[:4]}
                    for k, v in tv.items()}
                for t, tv in r.get("tests", {}).items()
            }
            summary[b] = {"kp": len(r.get("key_pages", [])), "anom": len(r.get("anomalies", [])),
                          "tests": tests}
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
