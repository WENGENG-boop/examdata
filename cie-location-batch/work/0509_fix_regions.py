# -*- coding: utf-8 -*-
"""0509/2026-Jun-11: fix regions flagged by the visual verification round 1.

QP (30 instances = 14 bboxes x 2 variant pages + 3(e)(iii) on p9 and p15):
  the region crop's bottom edge includes a thin sliver of the next line's
  character tops (worker: "底部文字残片被裁切"). Measure the ink runs in a
  window [x0, y1-15, x1, y1+15] at z=4; the edge run is the one intersecting
  [y1-1.0, y1+0.5]; pull y1 up to edge_run_top - 0.5 so the crop bottom
  (y1+0.4) no longer touches the fragment. Safety valve: -1.6 <= delta <= 0
  (sliver-only; guards against pulling y1 through the region's own last line)
  and y1_new > y0+10, else report and skip.
  Failures: p4/p10: 1(a),1(b),1(c),1(d),1(e); p5/p11: 1(g),1(h);
            p8/p14: 3,3(a),3(b),3(c),3(d),3(e),3(e)(i); p9+p15: 3(e)(iii).
  (3(e)(i) p8/p14 and 3(e)(iii) p9 were found by the systematic edge audit
  work/0509_audit_edges.py — the worker round-1 list had missed them.)
  Controls (measured, never modified): 1(f) p4, 1(h)(i) p5,
            1(h)(ii) p5, 1 p4, 3(e)(ii) p8.

MS (3 static fixes; values measured in window 66 forensics):
  2/p8  [60.0,57.08,540.0,780.0]  -> x0 62.0    (reading y' 60->62; drops the
         0.4pt bottom sliver of the "Section 2" heading band y'[52,60])
  2/p12 [100.0,57.08,466.2,665.76] -> y1 780.75 (reading x' 176.24->61.25;
         includes full table width, left border x'=62.75, 1.5pt margin)
  2/p13 [49.5,57.08,192.3,660.0]   -> y1 780.75 (same)
  p14 shared band + p15 3(f) left as-is (worker "rotated" note = false positive).
"""
import hashlib
import json
import os
import sys

import pymupdf

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(BASE, 'indexes', '0509', '2026-Jun-11', 'cie-index.json')
BACKUP = os.path.join(BASE, 'work', 'index-backups',
                      '0509-2026-Jun-11-before-fix2.json')
QP_PDF = os.path.join(BASE, 'tmp', '0509', '2026-Jun-11', '0509_s26_qp_11.pdf')
PROBE = os.path.join(BASE, 'tmp', '0509', '2026-Jun-11', 'probe')

OLD_SHA = 'a0ef4b69d05dd12716ff92d2f9bef4a6ad9c3edae5b42367aa23ccb4086ce9ba'

QP_FAIL = [
    ('1(a)', [72.4, 137.5, 539.0, 223.7], [4, 10]),
    ('1(b)', [72.4, 223.7, 539.0, 331.85], [4, 10]),
    ('1(c)', [72.4, 331.85, 539.0, 413.46], [4, 10]),
    ('1(d)', [72.4, 413.46, 539.0, 544.3], [4, 10]),
    ('1(e)', [72.4, 544.3, 539.0, 650.4], [4, 10]),
    ('1(g)', [72.4, 58.8, 539.0, 191.5], [5, 11]),
    ('1(h)', [72.4, 191.5, 539.0, 216.9], [5, 11]),
    ('3', [72.4, 60.4, 539.0, 112.48], [8, 14]),
    ('3(a)', [72.4, 112.48, 539.0, 198.07], [8, 14]),
    ('3(b)', [72.4, 198.07, 539.0, 308.7], [8, 14]),
    ('3(c)', [72.4, 308.7, 539.0, 418.19], [8, 14]),
    ('3(d)', [72.4, 418.19, 539.0, 574.6], [8, 14]),
    ('3(e)', [72.4, 574.6, 539.0, 598.76], [8, 14]),
    ('3(e)(i)', [72.4, 598.76, 539.0, 672.7], [8, 14]),
    ('3(e)(iii)', [92.4, 58.4, 541.2, 133.17], [9, 15]),
]
QP_CONTROLS = [
    ('1(f)', [72.4, 650.4, 539.0, 735.6], [4]),
    ('1(h)(i)', [72.4, 215.0, 539.0, 313.6], [5]),
    ('1(h)(ii)', [72.4, 313.6, 539.0, 411.6], [5]),
    ('1', [72.4, 87.5, 539.0, 138.0], [4]),
    ('3(e)(ii)', [72.4, 672.7, 539.0, 746.08], [8]),
]
MS_FIX = [
    ('2', 8, [60.0, 57.08, 540.0, 780.0], [62.0, 57.08, 540.0, 780.0]),
    ('2', 12, [100.0, 57.08, 466.2, 665.76], [100.0, 57.08, 466.2, 780.75]),
    ('2', 13, [49.5, 57.08, 192.3, 660.0], [49.5, 57.08, 192.3, 780.75]),
]

Z = 4
DARK = 200
MIN_DARK_PX = 3
MERGE_GAP_PT = 2.0
EDGE_LO = 1.0   # window: [y1-EDGE_LO, y1+EDGE_HI]
EDGE_HI = 0.5
DELTA_LO = -1.6   # sliver-only range for (edge_run_top - 0.5) - y1
DELTA_HI = 0.0
MIN_ROOM = 10.0


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def measure(page, bbox):
    """Return (runs, edge_run). runs = merged ink runs in [x0,y1-15,x1,y1+15]."""
    x0, y0, x1, y1 = bbox
    clip = pymupdf.Rect(x0, y1 - 15, x1, y1 + 15)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(Z, Z), clip=clip,
                          colorspace=pymupdf.csGRAY, alpha=False)
    w, h, stride = pix.width, pix.height, pix.stride
    s = pix.samples
    runs = []
    cur = None
    for row in range(h):
        off = row * stride
        dark = 0
        for v in s[off:off + w]:
            if v < DARK:
                dark += 1
                if dark >= MIN_DARK_PX:
                    break
        if dark >= MIN_DARK_PX:
            if cur is None:
                cur = [row, row]
            else:
                cur[1] = row
        elif cur is not None:
            runs.append(cur)
            cur = None
    if cur is not None:
        runs.append(cur)
    gap_px = int(MERGE_GAP_PT * Z)
    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] - 1 <= gap_px:
            merged[-1][1] = r[1]
        else:
            merged.append(list(r))
    pt = [(clip.y0 + a / Z, clip.y0 + (b + 1) / Z) for a, b in merged]
    edge = None
    for r in pt:
        if r[0] <= y1 + EDGE_HI and r[1] >= y1 - EDGE_LO:
            edge = r
            break
    return pt, edge


def fmt_runs(runs, y1):
    out = []
    for a, b in runs:
        tag = '>cut' if b > y1 + 0.45 else ''
        out.append(f'[{a:.2f},{b:.2f}{tag}]')
    return ' '.join(out) or '(none)'


def qslug(q):
    return q.replace('(', '_').replace(')', '').replace(' ', '')


def main():
    apply = '--apply' in sys.argv
    save_strips = '--strips' in sys.argv

    old_sha = sha256_file(INDEX)
    if old_sha != OLD_SHA:
        print(f'ERROR: index sha {old_sha} != expected {OLD_SHA}')
        sys.exit(2)
    with open(INDEX, encoding='utf-8') as f:
        doc = json.load(f)

    by_q = {q['question']: q for q in doc['questions']}
    qp_doc = pymupdf.open(QP_PDF)
    print(f'QP pdf: {QP_PDF} sha={sha256_file(QP_PDF)} pages={qp_doc.page_count}')
    if save_strips:
        os.makedirs(PROBE, exist_ok=True)

    results = []   # (q, page, old_bbox, new_y1 or None, note)
    print('\n== QP fixes (measure) ==')
    for qno, bbox, pages in QP_FAIL:
        x0, y0, x1, y1 = bbox
        for pg in pages:
            page = qp_doc[pg - 1]
            runs, edge = measure(page, bbox)
            note = 'no_edge_ink'
            new_y1 = None
            if edge is not None:
                cand = round(edge[0] - 0.5, 2)
                d = round(cand - y1, 2)
                if not (DELTA_LO <= d <= DELTA_HI):
                    note = f'suspicious delta {d}'
                elif cand <= y0 + MIN_ROOM:
                    note = f'suspicious y0 room {cand}'
                else:
                    new_y1 = cand
                    note = f'OK delta {d}'
            print(f'{qno:9s} p{pg:02d} {bbox} runs: {fmt_runs(runs, y1)} '
                  f'edge: {("[" + format(edge[0], ".2f") + "," + format(edge[1], ".2f") + "]") if edge else None} '
                  f'-> y1 {y1} -> {new_y1}  {note}')
            results.append((qno, pg, bbox, new_y1, note))
            if save_strips:
                pix = page.get_pixmap(matrix=pymupdf.Matrix(Z, Z),
                                      clip=pymupdf.Rect(x0, y1 - 15, x1, y1 + 15),
                                      alpha=False)
                pix.save(os.path.join(PROBE, f'edge-{qslug(qno)}-p{pg:02d}.png'))

    print('\n== QP controls (never modified) ==')
    for qno, bbox, pages in QP_CONTROLS:
        x0, y0, x1, y1 = bbox
        for pg in pages:
            page = qp_doc[pg - 1]
            runs, edge = measure(page, bbox)
            tag = 'edge_ink_present' if edge else 'no_edge_ink'
            print(f'{qno:9s} p{pg:02d} {bbox} runs: {fmt_runs(runs, y1)} -> {tag}')

    n_fix = sum(1 for r in results if r[3] is not None)
    n_skip = len(results) - n_fix
    print(f'\nQP instances: {len(results)}  fixable: {n_fix}  skipped: {n_skip}')

    print('\n== MS static fixes ==')
    for qno, pg, old, new in MS_FIX:
        print(f'{qno} p{pg:02d} {old} -> {new}')

    if not apply:
        print('\nDRY RUN (no --apply): nothing written.')
        return

    if n_fix == 0:
        print('ERROR: nothing to fix; refusing to write.')
        sys.exit(3)
    if os.path.exists(BACKUP):
        print('BACKUP ALREADY EXISTS, refusing to overwrite:', BACKUP)
        sys.exit(2)
    os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
    with open(BACKUP, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write('\n')

    qp_done = 0
    for qno, pg, bbox, new_y1, note in results:
        if new_y1 is None:
            continue
        q = by_q[qno]
        hits = 0
        for r in q.get('qp', []):
            if r['page'] == pg and r['bbox'] == bbox:
                r['bbox'] = [bbox[0], bbox[1], bbox[2], new_y1]
                qp_done += 1
                hits += 1
        if hits != 1:
            print(f'ERROR: QP fix expected 1 hit for {qno} p{pg}, got {hits}')
            sys.exit(3)

    ms_done = 0
    for qno, pg, old, new in MS_FIX:
        q = by_q[qno]
        hits = 0
        for r in q.get('ms', []):
            if r['page'] == pg and r['bbox'] == old:
                r['bbox'] = list(new)
                ms_done += 1
                hits += 1
        if hits != 1:
            print(f'ERROR: MS fix expected 1 hit for {qno} p{pg}, got {hits}')
            sys.exit(3)

    tmp = INDEX + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write('\n')
    os.replace(tmp, INDEX)

    new_sha = sha256_file(INDEX)
    total = sum(len(q.get('qp', [])) + len(q.get('ms', [])) for q in doc['questions'])
    print(f'\nAPPLIED: qp regions fixed: {qp_done}  ms regions fixed: {ms_done}')
    print(f'old sha: {old_sha}')
    print(f'new sha: {new_sha}')
    print(f'question count: {len(doc["questions"])} total regions: {total}')
    for qno, pg, bbox, new_y1, note in results:
        if new_y1 is not None:
            print(f'  {qno:9s} p{pg:02d} y1 {bbox[3]} -> {new_y1}')


if __name__ == '__main__':
    main()
