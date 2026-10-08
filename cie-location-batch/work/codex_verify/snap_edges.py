"""Snap region y-edges to word boundaries for the 6 pending volumes.

Dry-run by default; `--apply` writes the index, report, errors.jsonl and
updates papers.json index_sha256.

Rules (locked by measured cases A002/A003 and the 2026-10-02 work notes):
- A crossing word at edge E: w.y0 < E < w.y1 (strict), and the word's x-range
  overlaps the crop x-range (bbox +/- PAD mapped through page rotation, clamped
  to page.rect) by more than MIN_OVL points -- i.e. only text that can actually
  appear in the crop counts. Header/footer slivers overlapping by <=0.22pt are
  ignored; raising MAX_ADJ to chase them was measured to be the wrong fix.
- Classify each crossing word against the edge:
    top edge:    inside = w.y1 - E,  outside = E - w.y0
    bottom edge: inside = E - w.y0,  outside = w.y1 - E
- majority vote decides: in > out -> extend outward (top min(w.y0)-EPS;
  bottom max(w.y1)+EPS); out > in -> shrink inward (top max(w.y1)+EPS;
  bottom min(w.y0)-EPS). Exact in==out split -> manual, no change.
  (Unanimity was too strict: superscripts/symbols fragment one visual line into
  many text-layer blocks, and shared edges must converge to the same line.)
- |adjust| > MAX_ADJ -> manual, no change (listed in the report).
- Ping-pong (vote target ~= previous move's start): use the midpoint of the gap
  between the two text lines if it crosses no word; else manual ("oscillation").
- Iterate at most MAX_ITER moves; still crossing -> revert + manual.
- Only y changes; clamp to analysis bounds; final height >= MIN_H else revert.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import batchlib as B
import paperlib as P

OUT_DIR = B.WORK / "codex_verify"
PAD = 0.4          # must match render_crops.py PAD
EPS = 0.6
MAX_ADJ = 10.0
MAX_ITER = 3
MIN_H = 2.0
MIN_OVL = 1.0      # min x-overlap (points) for a word to count as crossing

KEYS = [
    "0413/2026/Jun/11",
    "0509/2026/Jun/11",
    "8386/2026/Jun/11",
    "9396/2023/Nov/11",
    "9709/2024/Jun/11",
    "9715/2023/Nov/21",
]


def pdf_path(key: str, role: str) -> Path | None:
    entry = P.load_paper(key) or {}
    docs = entry.get(role) or []
    if not docs:
        return None
    name = docs[0] if isinstance(docs[0], str) else docs[0].get("filename")
    return P.paper_tmp(key) / name


def crop_x_range(page, bbox) -> tuple[float, float]:
    """Crop x-extent in the unrotated frame (bbox + PAD, clamped to page.rect)."""
    import pymupdf
    visible = pymupdf.Rect(bbox) * page.rotation_matrix
    clip = pymupdf.Rect(visible.x0 - PAD, visible.y0 - PAD,
                        visible.x1 + PAD, visible.y1 + PAD) & page.rect
    un = clip * page.derotation_matrix
    return (un.x0, un.x1)


def _sample(crossing: list[dict]) -> dict:
    items = sorted(crossing, key=lambda w: (w["y0"], w["x0"]))[:14]
    return {"count": len(crossing), "items": [
        {"text": w["text"], "x0": round(w["x0"], 1), "y0": round(w["y0"], 1),
         "x1": round(w["x1"], 1), "y1": round(w["y1"], 1)} for w in items]}


def snap_edge(words: list[dict], edge: float, side: str) -> dict:
    """Return {"new": float|None, "reason": str|None, "moves": [...], "words": {...}}."""
    cur = edge
    moves: list[dict] = []
    first: dict | None = None
    last_votes: dict | None = None
    for step in range(MAX_ITER + 1):
        crossing = [w for w in words if w["y0"] < cur < w["y1"]]
        if not crossing:
            if not moves:
                return {"new": None, "reason": None, "moves": [], "words": {}}
            return {"new": cur, "reason": None, "moves": moves, "words": first,
                    "votes": last_votes}
        if first is None:
            first = _sample(crossing)
        if step == MAX_ITER:
            return {"new": None, "reason": "not_converged", "moves": moves, "words": first}
        votes = {"in": 0, "out": 0, "tie": 0}
        for w in crossing:
            if side == "top":
                ins, outs = w["y1"] - cur, cur - w["y0"]
            else:
                ins, outs = cur - w["y0"], w["y1"] - cur
            votes["in" if ins > outs else "out" if outs > ins else "tie"] += 1
        last_votes = dict(votes)
        if votes["in"] == votes["out"]:
            return {"new": None, "reason": f"split:{votes['in']}/{votes['out']}",
                    "moves": moves, "words": first, "votes": votes}
        majority = "in" if votes["in"] > votes["out"] else "out"
        if majority == "in":
            new = (min(w["y0"] for w in crossing) - EPS) if side == "top" \
                else (max(w["y1"] for w in crossing) + EPS)
        else:
            new = (max(w["y1"] for w in crossing) + EPS) if side == "top" \
                else (min(w["y0"] for w in crossing) - EPS)
        new = round(new, 2)
        if moves and abs(new - moves[-1]["from"]) < 0.005:
            lo, hi = sorted((new, cur))
            cross_lo = [w for w in words if w["y0"] < lo < w["y1"]]
            cross_hi = [w for w in words if w["y0"] < hi < w["y1"]]
            gap_lo = max((w["y1"] for w in cross_lo), default=None)
            gap_hi = min((w["y0"] for w in cross_hi), default=None)
            if gap_lo is not None and gap_hi is not None and gap_lo < gap_hi:
                q = round((gap_lo + gap_hi) / 2, 2)
                if not any(w["y0"] < q < w["y1"] for w in words):
                    moves.append({"from": round(cur, 2), "to": q, "via": "gap"})
                    return {"new": q, "reason": None, "moves": moves,
                            "words": first, "votes": last_votes}
            return {"new": None, "reason": "oscillation", "moves": moves,
                    "words": first, "votes": last_votes}
        if abs(new - cur) > MAX_ADJ + 1e-9:
            return {"new": None, "reason": f"adj={abs(new - cur):.2f}>{MAX_ADJ}",
                    "moves": moves, "words": first, "votes": last_votes}
        moves.append({"from": round(cur, 2), "to": new})
        cur = new
    return {"new": None, "reason": "not_converged", "moves": moves, "words": first}


def process_region(qtext, role, page_no, bbox, wsel, bounds):
    """Return (changes, manual, (new_y0, new_y1))."""
    x0, y0, x1, y1 = [float(v) for v in bbox]
    tag = {"question": str(qtext), "role": role, "page": page_no}
    changes: list[dict] = []
    manual: list[dict] = []

    def add_manual(edge, res):
        manual.append({**tag, "edge": edge, "reason": res["reason"],
                       "votes": res.get("votes"), "words": res.get("words") or {}})

    top = snap_edge(wsel, y0, "top")
    bot = snap_edge(wsel, y1, "bottom")
    if top["reason"]:
        add_manual("top", top)
        top_new = None
    else:
        top_new = top["new"]
    if bot["reason"]:
        add_manual("bottom", bot)
        bot_new = None
    else:
        bot_new = bot["new"]

    ny0 = top_new if top_new is not None else y0
    ny1 = bot_new if bot_new is not None else y1
    cy0 = max(bounds[1], ny0)
    cy1 = min(bounds[3], ny1)
    if cy1 - cy0 < MIN_H:
        if top_new is not None:
            add_manual("top", {"reason": "height_revert", "words": top["words"]})
        if bot_new is not None:
            add_manual("bottom", {"reason": "height_revert", "words": bot["words"]})
        return [], manual, (y0, y1)

    if top_new is not None and abs(cy0 - ny0) > 1e-9 and any(w["y0"] < cy0 < w["y1"] for w in wsel):
        add_manual("top", {"reason": "post_clamp", "words": top["words"]})
        cy0 = y0
    if bot_new is not None and abs(cy1 - ny1) > 1e-9 and any(w["y0"] < cy1 < w["y1"] for w in wsel):
        add_manual("bottom", {"reason": "post_clamp", "words": bot["words"]})
        cy1 = y1

    if top_new is not None and cy0 != y0:
        changes.append({**tag, "edge": "top", "old": round(y0, 2), "new": round(cy0, 2),
                        "votes": top.get("votes"), "moves": top["moves"], "words": top["words"]})
    if bot_new is not None and cy1 != y1:
        changes.append({**tag, "edge": "bottom", "old": round(y1, 2), "new": round(cy1, 2),
                        "votes": bot.get("votes"), "moves": bot["moves"], "words": bot["words"]})
    return changes, manual, (cy0, cy1)


def process_volume(key: str, apply: bool) -> dict:
    import pymupdf
    subject, year, season, paper = key.split("/")
    idx_path = B.index_dir(subject, int(year), season, paper) / "cie-index.json"
    data = json.loads(idx_path.read_text(encoding="utf-8"))
    sha_before = B.sha256_file(idx_path)

    paths = {role: pdf_path(key, role) for role in ("qp", "ms")}
    docs = {role: pymupdf.open(p) for role, p in paths.items() if p}
    words_cache: dict[tuple, list[dict]] = {}
    bounds_cache: dict[tuple, tuple] = {}

    all_changes: list[dict] = []
    all_manual: list[dict] = []
    stats = Counter()
    for q in data["questions"]:
        for role in ("qp", "ms"):
            for r in q.get(role) or []:
                page_no = int(r["page"])
                if role not in docs:
                    all_manual.append({"question": str(q["question"]), "role": role,
                                       "page": page_no, "edge": "?", "reason": "no_pdf", "words": {}})
                    continue
                stats["regions"] += 1
                cache_key = (role, page_no)
                if cache_key not in words_cache:
                    words_cache[cache_key] = P.page_words(paths[role], page_no)
                page = docs[role][page_no - 1]
                if cache_key not in bounds_cache:
                    bounds_cache[cache_key] = P.analysis_bounds(page)
                bbox = list(r["bbox"])
                xr = crop_x_range(page, bbox)
                wsel = [w for w in words_cache[cache_key]
                        if min(w["x1"], xr[1]) - max(w["x0"], xr[0]) > MIN_OVL]
                changes, manual, (ny0, ny1) = process_region(
                    q["question"], role, page_no, bbox, wsel, bounds_cache[cache_key])
                if changes:
                    r["bbox"] = [bbox[0], ny0, bbox[2], ny1]
                    all_changes.extend(changes)
                all_manual.extend(manual)

    # post-snap scan: remaining strict crossings (with x filter)
    remaining = 0
    for q in data["questions"]:
        for role in ("qp", "ms"):
            for r in q.get(role) or []:
                if role not in docs:
                    continue
                page_no = int(r["page"])
                cache_key = (role, page_no)
                page = docs[role][page_no - 1]
                bbox = r["bbox"]
                xr = crop_x_range(page, bbox)
                wsel = [w for w in words_cache[cache_key]
                        if min(w["x1"], xr[1]) - max(w["x0"], xr[0]) > MIN_OVL]
                x0, y0, x1, y1 = bbox
                remaining += sum(1 for w in wsel if w["y0"] < y0 < w["y1"])
                remaining += sum(1 for w in wsel if w["y0"] < y1 < w["y1"])
    for d in docs.values():
        d.close()

    new_bytes = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    sha_pred = B.sha256_bytes(new_bytes)

    report = {
        "key": key, "generated_at": B.now_iso(), "applied": bool(apply and all_changes),
        "index_path": str(idx_path), "index_sha_before": sha_before,
        "index_sha_after_pred": sha_pred, "pad": PAD, "eps": EPS,
        "stats": {"regions": stats["regions"], "changes": len(all_changes),
                  "manual": len(all_manual), "remaining_crossings": remaining},
        "changes": all_changes, "manual": all_manual,
    }

    if apply and all_changes:
        B.atomic_write_json(idx_path, data)
        actual = B.sha256_file(idx_path)
        report["index_sha_after"] = actual
        if actual != sha_pred:
            report["sha_mismatch"] = {"pred": sha_pred, "actual": actual}
        B.append_jsonl(B.ERRORS, {
            "kind": "bbox_snap", "at": B.now_iso(), "key": key,
            "index_sha_before": sha_before, "index_sha_after": actual,
            "changes": all_changes, "manual": all_manual,
            "remaining_crossings": remaining,
        })
        P.patch_paper(key, index_sha256=actual, bbox_snapped_at=B.now_iso())
        import validate_index as V
        import cleanup_paper as C
        qp_p = paths.get("qp")
        ms_p = paths.get("ms")
        rep = V.validate(idx_path, qp_p, ms_p)
        probs, nstats = C.numbering_problems(key)
        report["validate"] = {"errors": rep.get("errors"), "warnings": rep.get("warnings"),
                              "questions": rep.get("questions")}
        report["numbering"] = {"problems": probs, "stats": nstats}
    elif apply:
        B.append_jsonl(B.ERRORS, {
            "kind": "bbox_snap", "at": B.now_iso(), "key": key,
            "index_sha_before": sha_before, "index_sha_after": sha_before,
            "changes": [], "manual": all_manual, "remaining_crossings": remaining,
        })

    out = OUT_DIR / (key.replace("/", "-") + "-snap-report.json")
    B.atomic_write_json(out, report)
    report["report_path"] = str(out)
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="snap region y-edges to word boundaries")
    ap.add_argument("keys", nargs="*", help="默认 6 卷")
    ap.add_argument("--apply", action="store_true", help="写盘；默认只 dry-run")
    args = ap.parse_args()
    keys = args.keys or KEYS
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    totals = Counter()
    for key in keys:
        rep = process_volume(key, args.apply)
        st = rep["stats"]
        totals["regions"] += st["regions"]
        totals["changes"] += st["changes"]
        totals["manual"] += st["manual"]
        totals["remaining"] += st["remaining_crossings"]
        print(f"{key}: regions={st['regions']} changes={st['changes']} "
              f"manual={st['manual']} remaining_crossings={st['remaining_crossings']} "
              f"applied={rep['applied']}", flush=True)
        for ch in rep["changes"]:
            ws = " ".join(f"'{w['text']}'({w['y0']},{w['y1']})" for w in ch["words"]["items"][:6])
            print(f"  [chg] {ch['question']} {ch['role']} p{ch['page']} {ch['edge']} "
                  f"{ch['old']} -> {ch['new']} n={ch['words']['count']} | {ws}", flush=True)
        for m in rep["manual"]:
            ws = " ".join(f"'{w['text']}'({w['y0']},{w['y1']})" for w in (m["words"].get("items") or [])[:6])
            print(f"  [manual] {m['question']} {m['role']} p{m['page']} {m['edge']} "
                  f"reason={m['reason']} | {ws}", flush=True)
        if "validate" in rep:
            print(f"  validate errors={rep['validate']['errors']} "
                  f"numbering problems={rep['numbering']['problems']}", flush=True)
    print(f"TOTAL regions={totals['regions']} changes={totals['changes']} "
          f"manual={totals['manual']} remaining={totals['remaining']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
