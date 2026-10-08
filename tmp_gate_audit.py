"""审计校准门控（_MS_BARE_MARGIN）删除的裸锚点：合法/垃圾分类。

对每个 matched MS 文档跑两次 _ms_anchors：margin=巨大（pre-gate）与 margin=真实
（post-gate，按页门控），把只出现在 pre-gate 的锚点按「是否在 wanted / 是否为
wanted 前缀 / 两者都不是」分类，并记录相对页校准列的 delta d 与到全文档最近带
括号题号列的距离 cd（列匹配例外候选），供修复方案定量参考。

用法: python tmp_gate_audit.py [out.txt]
"""
import sqlite3
import sys

import pymupdf

sys.path.insert(0, "src")

from examdata.core.config import get_settings
from examdata.core.storage import ContentAddressedStore
import examdata.edexcel_papers.pipeline as P

OUT = sys.argv[1] if len(sys.argv) > 1 else "tmp_gate_audit.txt"
REAL_MARGIN = P._MS_BARE_MARGIN


def calib(pdf):
    """复刻预扫：返回 (page_calib, doc_calib)。"""
    page_calib: dict[int, float] = {}
    doc_calib: float | None = None
    for index, page in enumerate(pdf):
        if index == 0:
            continue
        bounds = page.rect
        rotation = page.rotation_matrix
        for word in page.get_text("words"):
            rect = pymupdf.Rect(word[:4]) * rotation
            if not bounds.height * 0.04 < rect.y0 < bounds.height * 0.9:
                continue
            if rect.x0 >= bounds.width * P._MS_NUMBER_X:
                continue
            token = P._normalize_ms_token(word[4])
            if not any(ch.isalpha() for ch in token):
                continue
            if not (
                P._MS_NUMBER.match(token)
                or P._MS_COMPACT.fullmatch(token)
                or P._MS_PART.fullmatch(token)
            ):
                continue
            if index not in page_calib or rect.x0 > page_calib[index]:
                page_calib[index] = rect.x0
            if doc_calib is None or rect.x0 > doc_calib:
                doc_calib = rect.x0
    return page_calib, doc_calib


def paren_columns(pdf) -> list[float]:
    """全文档带括号题号 token（'1(a)'、'(a)(i)' 型）的 x0 集合，作为列匹配例外的候选列。"""
    cols: list[float] = []
    for index, page in enumerate(pdf):
        if index == 0:
            continue
        bounds = page.rect
        rotation = page.rotation_matrix
        for word in page.get_text("words"):
            rect = pymupdf.Rect(word[:4]) * rotation
            if not bounds.height * 0.04 < rect.y0 < bounds.height * 0.9:
                continue
            if rect.x0 >= bounds.width * P._MS_NUMBER_X:
                continue
            token = P._normalize_ms_token(word[4])
            if "(" not in token or not any(ch.isalpha() for ch in token):
                continue
            if P._MS_NUMBER.match(token) or P._MS_PART.fullmatch(token):
                cols.append(rect.x0)
    return cols


def main() -> None:
    settings = get_settings()
    store = ContentAddressedStore(settings.artifacts_dir)
    con = sqlite3.connect("file:.data/examdata.db?mode=ro", uri=True)
    rows = con.execute(
        """
        select ms.id, ms.document_id, ms.matched_paper_document_id
        from mark_scheme ms
        join document d on d.id = ms.document_id
        where d.subject_id between 19 and 26
          and ms.matched_paper_document_id is not null
        order by ms.id
        """
    ).fetchall()
    print(f"{len(rows)} matched MS", flush=True)

    lines: list[str] = []
    cls_counts = {"W": 0, "P": 0, "X": 0}
    deltas: dict[str, list[float]] = {"W": [], "P": [], "X": []}
    add_counts = {"W": 0, "P": 0, "X": 0}
    add_x_lines: list[str] = []
    n_docs = 0
    n_err = 0
    n_docs_removed = 0
    n_docs_added = 0

    for ms_id, ms_doc, qp_doc in rows:
        key_row = con.execute(
            """
            select a.storage_key from document d
            join document_revision r on r.id = d.current_revision_id
            join artifact a on a.id = r.artifact_id where d.id = ?
            """,
            (ms_doc,),
        ).fetchone()
        if not key_row or not key_row[0]:
            continue
        path = store.path_for_key(key_row[0])
        if not path.exists():
            continue
        wanted = {
            r[0]
            for r in con.execute(
                """
                select q.number_path from question q
                join paper p on p.id = q.paper_id
                where p.document_id = ?
                """,
                (qp_doc,),
            )
            if r[0]
        }
        if not wanted:
            continue
        data = path.read_bytes()

        def classify(tok: str) -> str:
            if tok in wanted:
                return "W"
            if any(w.startswith(tok + "(") for w in wanted):
                return "P"
            return "X"

        try:
            with pymupdf.open(stream=data, filetype="pdf") as pdf:
                page_calib, doc_calib = calib(pdf)
                P._MS_BARE_MARGIN = 1e9
                pre = P._ms_anchors(pdf, wanted)
                P._MS_BARE_MARGIN = REAL_MARGIN
                post = P._ms_anchors(pdf, wanted)
                # 每页词表（含变换），用于取行内右侧上下文。
                page_words: dict[int, list[tuple]] = {}
                for i in range(len(pdf)):
                    bounds = pdf[i].rect
                    rot = pdf[i].rotation_matrix
                    ws = []
                    for word in pdf[i].get_text("words"):
                        rect = pymupdf.Rect(word[:4]) * rot
                        ws.append((rect, word[4]))
                    page_words[i] = ws
                paren_cols = paren_columns(pdf)
        except Exception as exc:  # noqa: BLE001
            n_err += 1
            print(f"!! ms={ms_id} doc={ms_doc}: {exc}", flush=True)
            continue
        finally:
            P._MS_BARE_MARGIN = REAL_MARGIN

        pre_keys = {(i, t, round(r[0], 1)) for i, t, r in pre}
        post_keys = {(i, t, round(r[0], 1)) for i, t, r in post}
        removed = [x for x in pre if (x[0], x[1], round(x[2][0], 1)) not in post_keys]
        added = [x for x in post if (x[0], x[1], round(x[2][0], 1)) not in pre_keys]
        if removed:
            n_docs_removed += 1
        if added:
            n_docs_added += 1
        if not removed and not added:
            n_docs += 1
            continue

        lines.append(
            f"ms={ms_id} doc={ms_doc} wanted={len(wanted)} "
            f"removed={len(removed)} added={len(added)}"
        )
        for i, t, r in removed:
            cls = classify(t)
            cls_counts[cls] += 1
            base = page_calib.get(i)
            delta = r[0] - base if base is not None else None
            if delta is not None:
                deltas[cls].append(round(delta, 1))
            ctx = [
                text
                for rect, text in sorted(page_words[i], key=lambda item: item[0].x0)
                if abs(rect.y0 - r[1]) < 3.0 and rect.x0 >= r[2] - 1.0
            ][:3]
            cd = min((abs(r[0] - c) for c in paren_cols), default=None)
            lines.append(
                f"  R p{i+1} {t!r} x={r[0]:.1f} y={r[1]:.1f} "
                f"cal={None if base is None else round(base, 1)}/{doc_calib} "
                f"d={None if delta is None else round(delta, 1)} cls={cls} "
                f"cd={None if cd is None else round(cd, 1)} "
                f"ctx={'|'.join(ctx)}"
            )
        for i, t, r in added:
            cls = classify(t)
            add_counts[cls] += 1
            if cls == "X":
                add_x_lines.append(
                    f"  A ms={ms_id} doc={ms_doc} p{i+1} {t!r} x={r[0]:.1f} "
                    f"y={r[1]:.1f} ctx="
                    + "|".join(
                        text
                        for rect, text in sorted(
                            page_words[i], key=lambda item: item[0].x0
                        )
                        if abs(rect.y0 - r[1]) < 3.0 and rect.x0 >= r[2] - 1.0
                    )[:3]
                )
        n_docs += 1
        if n_docs % 50 == 0:
            print(f"  ... {n_docs} docs done", flush=True)

    summary = [
        f"docs scanned: {n_docs}, errors: {n_err}",
        f"docs with removed: {n_docs_removed}, docs with added: {n_docs_added}",
        f"removed cls counts W/P/X: {cls_counts}",
        f"added cls counts W/P/X: {add_counts}",
    ]
    for cls in ("W", "P", "X"):
        ds = sorted(deltas[cls])
        summary.append(
            f"removed delta[{cls}] n={len(ds)} "
            + (
                f"min/p10/p50/p90/max="
                f"{ds[0]:.1f}/{ds[len(ds)//10]:.1f}/{ds[len(ds)//2]:.1f}/"
                f"{ds[len(ds)*9//10]:.1f}/{ds[-1]:.1f}"
                if ds
                else "empty"
            )
        )
        summary.append(f"  delta[{cls}] values: {ds}")
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(summary) + "\n\n" + "\n".join(lines) + "\n")
    if add_x_lines:
        with open(OUT, "a", encoding="utf-8") as fh:
            fh.write("\nADDED-X:\n" + "\n".join(add_x_lines) + "\n")
    print("\n".join(summary), flush=True)
    print(f"written {OUT}", flush=True)


if __name__ == "__main__":
    main()
