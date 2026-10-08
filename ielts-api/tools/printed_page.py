#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""S02 tool: batch-resolve printed page numbers for (pdf, physical_page) pairs.

Input : JSON file  {"items": [{"key": "1:26", "pdf": "C:/.../book_1.pdf", "page": 26}, ...]}
Output: JSON file  {"ok": true, "results": {"1:26": {"first": null, "last": 26, "chosen": 26}}, "errors": [...]}

Heuristic: a printed page number appears as a standalone integer line near the
top or bottom of the page text (Cambridge books print it in the header/footer
margin). First and last standalone integer lines are recorded; the bottom one
is preferred, falling back to the top one. No number found -> null.
"""
import json
import sys


def standalone_int(line):
    s = line.strip()
    if not s or len(s) > 3:
        return None
    if not s.isdigit():
        return None
    v = int(s)
    if 1 <= v <= 400:
        return v
    return None


def resolve(doc, page_no):
    page = doc[page_no - 1]
    text = page.get_text("text") or ""
    lines = [ln for ln in text.splitlines()]
    nonempty = [ln for ln in lines if ln.strip()]
    head = nonempty[:2]
    tail = nonempty[-2:]
    first = None
    last = None
    for ln in head:
        v = standalone_int(ln)
        if v is not None:
            first = v
            break
    for ln in reversed(tail):
        v = standalone_int(ln)
        if v is not None:
            last = v
            break
    chosen = last if last is not None else first
    return {"first": first, "last": last, "chosen": chosen}


def main():
    if len(sys.argv) != 3:
        print(json.dumps({"ok": False, "error": "usage: printed_page.py <items.json> <out.json>"}))
        return 2
    items_path, out_path = sys.argv[1], sys.argv[2]
    with open(items_path, encoding="utf-8") as f:
        payload = json.load(f)
    items = payload.get("items", [])
    try:
        import fitz  # pymupdf
    except Exception as e:  # pragma: no cover
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"ok": False, "error": f"pymupdf unavailable: {e}", "results": {}}, f)
        return 3
    results = {}
    errors = []
    docs = {}
    try:
        for it in items:
            key = it["key"]
            pdf = it["pdf"]
            page_no = int(it["page"])
            try:
                if pdf not in docs:
                    docs[pdf] = fitz.open(pdf)
                doc = docs[pdf]
                if page_no < 1 or page_no > doc.page_count:
                    results[key] = {"first": None, "last": None, "chosen": None, "error": "page out of range"}
                    continue
                results[key] = resolve(doc, page_no)
            except Exception as e:
                results[key] = {"first": None, "last": None, "chosen": None, "error": str(e)}
                errors.append(f"{key}: {e}")
    finally:
        for d in docs.values():
            try:
                d.close()
            except Exception:
                pass
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"ok": True, "results": results, "errors": errors}, f, ensure_ascii=False)
    print(json.dumps({"ok": True, "n": len(results), "errors": len(errors)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
