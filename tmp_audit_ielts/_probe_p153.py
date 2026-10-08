# 探针: 复核 book4 p153 为何走 union-gap 回退（不进主脚本）
import sys
import pymupdf
sys.path.insert(0, r'C:/Users/weo/Desktop/api/tmp_audit_ielts')
import official_pdf_cmp_v3 as m

doc = pymupdf.open(m.BASE + '/downloads/book_4.pdf')
page = doc[152]
W = page.rect.width
words = [(w[0], w[1], w[2], w[3], w[4]) for w in page.get_text('words')]

cands = []
for row in m.row_groups(words):
    if any(t == 'TEST' or t.startswith('TEST') for (_, _, _, _, t) in row):
        continue
    for w in row:
        if m.is_num_cand(w[4]):
            cands.append(w)
clusters = []
for w in sorted(cands, key=lambda w: (w[0], w[1])):
    if clusters and w[0] - max(x[2] for x in clusters[-1]) <= 5:
        clusters[-1].append(w)
    else:
        clusters.append([w])
clusters = [c for c in clusters if len(c) >= 6]
surv = []
for c in clusters:
    c = list(c)
    while len(c) >= 2:
        ys = sorted(x[1] for x in c)
        if ys[1] - ys[0] > 25:
            c = [x for x in c if x[1] != ys[0]]
        else:
            break
    while len(c) >= 2:
        ys = sorted(x[1] for x in c)
        if ys[-1] - ys[-2] > 25:
            c = [x for x in c if x[1] != ys[-1]]
        else:
            break
    surv.append(c)
ymin = min(min(x[1] for x in c) for c in surv) - 10
ymax = max(max(x[3] for x in c) for c in surv) + 20
band = [w for w in words if ymin <= w[1] <= ymax]
cs = sorted(surv, key=lambda c: min(x[0] for x in c))
print('clusters:', [(round(min(x[0] for x in c), 2), round(max(x[2] for x in c), 2), len(c)) for c in cs])
p = min(x[0] for x in cs[1]) - 0.1
print('p =', repr(p))
cross = [w for w in band if w[0] < p < w[2]]
print('crossing (strict):', cross[:12])
print('crossing (tol 0.5):', [w for w in band if w[0] < p - 0.5 and w[2] > p + 0.5][:12])
doc.close()
