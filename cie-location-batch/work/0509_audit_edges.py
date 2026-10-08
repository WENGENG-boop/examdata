# -*- coding: utf-8 -*-
"""0509: systematic bottom/top edge audit of EVERY QP region in the index.

For each region [x0,y0,x1,y1]:
  bottom: window [x0,y1-15,x1,y1+15]; find first merged ink run with
    bottom > y1+0.45 (ink extending below the pad line y1+0.4).
      r[0] - y1 = t.  sliver = 0.4 - t (if > 0 the crop includes it).
      t <= -2.0 -> own last line cut by the boundary (flag separately).
  top: window [x0,y0-15,x1,y0+15]; find first run with bottom > y0-0.5.
      t0 = r[0] - y0.  cut = -0.4 - t0 (if > 0 the crop cuts own first line).

Writes work/0509_edges_report.json and prints a table.
"""
import json
import os

import pymupdf

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(BASE, 'indexes', '0509', '2026-Jun-11', 'cie-index.json')
QP_PDF = os.path.join(BASE, 'tmp', '0509', '2026-Jun-11', '0509_s26_qp_11.pdf')
REPORT = os.path.join(BASE, 'work', '0509_edges_report.json')

Z = 4
DARK = 200
MIN_DARK_PX = 3
MERGE_GAP_PT = 2.0


def measure(page, clip):
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
    return [(round(clip.y0 + a / Z, 2), round(clip.y0 + (b + 1) / Z, 2))
            for a, b in merged]


def main():
    doc = json.load(open(INDEX, encoding='utf-8'))
    pdf = pymupdf.open(QP_PDF)
    report = []
    print('%-9s %-3s %-28s %-34s %s' % ('q', 'pg', 'bbox', 'bottom', 'top'))
    for q in doc['questions']:
        for r in q.get('qp', []):
            pg = r['page']
            x0, y0, x1, y1 = r['bbox']
            page = pdf[pg - 1]
            runs_b = measure(page, pymupdf.Rect(x0, y1 - 15, x1, y1 + 15))
            r_star = None
            for rr in runs_b:
                if rr[1] > y1 + 0.45:
                    r_star = rr
                    break
            bottom = {'class': 'clean'}
            if r_star is not None:
                t = round(r_star[0] - y1, 2)
                if t <= -2.0:
                    bottom = {'class': 'own_line_cut?', 't': t,
                              'run': list(r_star)}
                else:
                    sliver = round(0.4 - t, 2)
                    bottom = {'class': 'sliver' if sliver > 0 else 'clean_far',
                              't': t, 'sliver': sliver, 'run': list(r_star)}
            # own-ending run (informational)
            own = None
            for rr in runs_b:
                if rr[1] <= y1 + 0.45:
                    own = rr
            if own is not None:
                bottom['own_last_run'] = list(own)
                bottom['own_gap'] = round(y1 - own[1], 2)

            runs_t = measure(page, pymupdf.Rect(x0, y0 - 15, x1, y0 + 15))
            r0 = None
            for rr in runs_t:
                if rr[1] > y0 - 0.5:
                    r0 = rr
                    break
            top = {'class': 'clean'}
            if r0 is not None:
                t0 = round(r0[0] - y0, 2)
                cut = round(-0.4 - t0, 2)
                top = {'class': 'top_cut' if cut > 0 else 'clean_near',
                       't0': t0, 'cut': cut, 'run': list(r0)}
            rec = {'question': q['question'], 'page': pg, 'bbox': r['bbox'],
                   'bottom': bottom, 'top': top}
            report.append(rec)
            bnote = bottom['class']
            if bottom['class'] == 'sliver':
                bnote += ' t=%s sliver=%s' % (bottom['t'], bottom['sliver'])
            elif bottom['class'] == 'own_line_cut?':
                bnote += ' t=%s' % bottom['t']
            tnote = top['class']
            if top['class'] == 'top_cut':
                tnote += ' cut=%s' % top['cut']
            print('%-9s p%-2d %-28s %-34s %s' % (
                q['question'], pg, str(r['bbox']), bnote, tnote))

    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
        f.write('\n')
    n_sliver = sum(1 for r in report if r['bottom']['class'] == 'sliver')
    n_cut = sum(1 for r in report if r['bottom']['class'] == 'own_line_cut?')
    n_tc = sum(1 for r in report if r['top']['class'] == 'top_cut')
    print('\nregions: %d  bottom slivers: %d  own-cut?: %d  top-cuts: %d'
          % (len(report), n_sliver, n_cut, n_tc))
    print('report:', REPORT)


if __name__ == '__main__':
    main()
