import pymupdf

d = pymupdf.open('tmp/9715/2023-Nov-21/9715_w23_ms_21.pdf')
for pno in (11, 12):
    p = d[pno]
    print('===== page', pno + 1, '=====')
    rm = p.rotation_matrix
    lines = []
    for dr in p.get_drawings():
        for item in dr['items']:
            if item[0] == 'l':
                a, b = item[1], item[2]
            elif item[0] == 're':
                r = item[1]
                # rectangle: check if degenerate (thin) or real
                lines.append(('re', tuple(round(v, 2) for v in r)))
                continue
            else:
                continue
            A = pymupdf.Point(a) * rm
            B = pymupdf.Point(b) * rm
            lines.append(('l', (round(A.x, 2), round(A.y, 2), round(B.x, 2), round(B.y, 2))))
    # horizontal in display = same y
    horiz = [x for x in lines if x[0] == 'l' and abs(x[1][1] - x[1][3]) < 0.6]
    vert = [x for x in lines if x[0] == 'l' and abs(x[1][0] - x[1][2]) < 0.6]
    print('-- horizontal display lines (y, x0, x1):')
    seen = set()
    for _, (x0, y0, x1, y1) in sorted(horiz, key=lambda t: t[1][1]):
        key = (round(y0, 1), round(min(x0, x1), 1), round(max(x0, x1), 1))
        if key in seen:
            continue
        seen.add(key)
        print('  y=%.2f  x %.2f .. %.2f' % (y0, min(x0, x1), max(x0, x1)))
    print('-- vertical display lines (x, y0, y1):')
    seen = set()
    for _, (x0, y0, x1, y1) in sorted(vert, key=lambda t: t[1][0]):
        key = (round(x0, 1), round(min(y0, y1), 1), round(max(y0, y1), 1))
        if key in seen:
            continue
        seen.add(key)
        print('  x=%.2f  y %.2f .. %.2f' % (x0, min(y0, y1), max(y0, y1)))
