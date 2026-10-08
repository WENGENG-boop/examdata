#!/usr/bin/env python3
"""answers-from-index.py — S18 我方答案候选导出器（questions.json → compare-official --answers 输入）

将 ielts-data 规范化索引（questions.json）中某一 (book, test, skill, variant) 单元的逐题答案
导出为 answer-matcher.mjs / compare-official.mjs 的 'numbered' 候选契约形状：

    {"source": "ielts-data-index", "identity": {...}, "kind": "numbered",
     "entries": [{"number": 1, "value": "...", "raw": "...", "status": "...", ...}]}

语义约束（S18 计划）：
- value/raw 原样取自 answers[].raw；raw==""（numbered_empty）与 status=="missing"（absent）
  均导出为空候选（matcher 判 empty:true），不移动、不补位、不猜测；
- status 字段保留 attached/missing/empty 原始状态供报告区分；
- 题号取 question.number；同时校验 id 尾部 Q<N> 与 number 一致（不一致记 warnings）。

用法：
  单元模式：--index <questions.json> --book N --test T --skill listening|reading [--variant V] --out F
  批量模式：--index <questions.json> --outdir DIR   （输出 DIR/book_<N>/test_<T>_<skill>_<variant>.json
                                                    及 DIR/_manifest.json）
"""
import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SOURCE = "ielts-data-index"
QNUM_RE = re.compile(r":Q(\d+)$")


def load_index(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def variant_for(doc, book, test, skill, variant):
    if variant:
        return variant
    seen = sorted({q.get("variant") for q in doc["questions"]
                   if q.get("book") == book and str(q.get("test")) == str(test) and q.get("skill") == skill})
    if len(seen) == 1:
        return seen[0]
    default = {"listening": "shared", "reading": "academic"}.get(skill)
    if default in seen:
        return default
    raise SystemExit(f"cannot resolve variant for book={book} test={test} skill={skill}: candidates={seen}")


def cell_entries(doc, book, test, skill, variant):
    answers = doc["answers"]
    entries, warnings = [], []
    for q in doc["questions"]:
        if not (q.get("book") == book and str(q.get("test")) == str(test)
                and q.get("skill") == skill and q.get("variant") == variant):
            continue
        qid = q["id"]
        m = QNUM_RE.search(qid)
        number = q.get("number")
        if m and int(m.group(1)) != number:
            warnings.append({"question_id": qid, "reason": "id_number_mismatch", "number": number, "id_suffix": int(m.group(1))})
        a = answers.get(qid)
        if a is None:
            raw, status, form, asrc = "", "absent_entry", None, None
        else:
            raw = a.get("raw")
            status = a.get("status") or "unknown"
            form = a.get("form")
            asrc = a.get("source")
            if raw is None:
                raw = ""  # missing（absent）→ 空候选，不移动
        entries.append({
            "number": number,
            "value": raw,
            "raw": raw,
            "status": status,
            "form": form,
            "answer_source": asrc,
            "answer_status": q.get("answer_status"),
            "question_type": q.get("type"),
            "source_ref": qid,
        })
    entries.sort(key=lambda e: e["number"])
    nums = [e["number"] for e in entries]
    if len(set(nums)) != len(nums):
        dup = [n for n, c in Counter(nums).items() if c > 1]
        warnings.append({"reason": "duplicate_numbers", "numbers": sorted(dup)})
    return entries, warnings


def cell_doc(doc, book, test, skill, variant, index_path):
    entries, warnings = cell_entries(doc, book, test, skill, variant)
    stats = {
        "total": len(entries),
        "attached": sum(1 for e in entries if e["status"] == "attached"),
        "missing": sum(1 for e in entries if e["status"] == "missing"),
        "empty": sum(1 for e in entries if e["status"] == "empty"),
    }
    return {
        "source": SOURCE,
        "identity": {"book": book, "test": str(test), "skill": skill, "variant": variant},
        "kind": "numbered",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "index": {"path": str(index_path), "dataset_revision": doc.get("dataset_revision")},
        "stats": stats,
        "warnings": warnings,
        "entries": entries,
    }


def cells_in_index(doc):
    keys = sorted({(q["book"], str(q["test"]), q["skill"], q["variant"]) for q in doc["questions"]},
                  key=lambda k: (k[0], int(k[1]), k[2], k[3]))
    return keys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--book", type=int)
    ap.add_argument("--test")
    ap.add_argument("--skill", choices=["listening", "reading"])
    ap.add_argument("--variant")
    ap.add_argument("--out")
    ap.add_argument("--outdir")
    args = ap.parse_args()

    doc = load_index(args.index)

    if args.outdir:
        outdir = Path(args.outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        manifest = {"source": SOURCE, "index": args.index,
                    "dataset_revision": doc.get("dataset_revision"),
                    "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "cells": []}
        for book, test, skill, variant in cells_in_index(doc):
            cd = cell_doc(doc, book, test, skill, variant, args.index)
            rel = f"book_{book}/test_{test}_{skill}_{variant}.json"
            p = outdir / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(cd, f, ensure_ascii=False, indent=1)
            manifest["cells"].append({"book": book, "test": test, "skill": skill, "variant": variant,
                                      "file": rel, "stats": cd["stats"], "warnings": len(cd["warnings"])})
            print(f"wrote {rel}: total={cd['stats']['total']} attached={cd['stats']['attached']} "
                  f"missing={cd['stats']['missing']} empty={cd['stats']['empty']} warnings={len(cd['warnings'])}")
        with open(outdir / "_manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)
        print(f"manifest -> {outdir / '_manifest.json'} ({len(manifest['cells'])} cells)")
        return

    if args.book is None or args.test is None or args.skill is None or not args.out:
        sys.exit("single-cell mode requires --book --test --skill --out (or use --outdir)")
    variant = variant_for(doc, args.book, str(args.test), args.skill, args.variant)
    cd = cell_doc(doc, args.book, str(args.test), args.skill, variant, args.index)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(cd, f, ensure_ascii=False, indent=1)
    s = cd["stats"]
    print(f"wrote {args.out}: total={s['total']} attached={s['attached']} missing={s['missing']} "
          f"empty={s['empty']} warnings={len(cd['warnings'])}")
    for w in cd["warnings"]:
        print("  warning:", json.dumps(w, ensure_ascii=False))


if __name__ == "__main__":
    main()
