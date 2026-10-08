import fitz, sys
p=sys.argv[1]
pages=[int(x) for x in sys.argv[2].split(',')]
ranges=[tuple(int(v) for v in r.split('-')) for r in sys.argv[3].split(',')]
d=fitz.open(p)
for n in pages:
    pg=d[n-1]; pg.set_rotation(0)
    pm=pg.get_pixmap(matrix=fitz.Matrix(1,1),colorspace=fitz.csGRAY,alpha=False,clip=pg.rect)
    W,H,n_=pm.width,pm.height,pm.n; buf=pm.samples
    prof=[]
    for x in range(W):
        dark=sum(1 for y in range(H) if buf[y*W*n_+x*n_]<200)
        prof.append(dark/H)
    for (a,b) in ranges:
        out=[]
        for x in range(a,b):
            v=prof[x]
            if v>0.02: out.append(f"{x}:{v:.2f}")
        print(f"p{n} x in [{a},{b}): "+(" ".join(out) if out else "BLANK"))
