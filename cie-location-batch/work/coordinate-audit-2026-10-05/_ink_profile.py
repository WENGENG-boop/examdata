import fitz, sys
p = sys.argv[1]
pages = []
for part in sys.argv[2].split(','):
    if '-' in part:
        a,b=part.split('-'); pages+=list(range(int(a),int(b)+1))
    else: pages.append(int(part))
d = fitz.open(p)
for n in pages:
    pg = d[n-1]
    pg.set_rotation(0)
    rect = pg.rect
    pm = pg.get_pixmap(matrix=fitz.Matrix(1,1), colorspace=fitz.csGRAY, alpha=False, clip=rect)
    W,H = pm.width, pm.height
    buf = pm.samples
    n_ = pm.n
    # per-column (x) darkness: fraction of dark px in that column
    prof=[]
    for x in range(W):
        dark=0
        for y in range(H):
            if buf[y*W*n_ + x*n_] < 200: dark+=1
        prof.append(dark/H)
    # report content extent: columns with >0.5% dark
    thr=0.005
    cols=[i for i,v in enumerate(prof) if v>thr]
    print(f"--- p{n} rot={pg.rotation} pix {W}x{H} (x = display-Y axis)")
    if not cols:
        print("    NO INK"); continue
    print(f"    ink x-range: {min(cols)} .. {max(cols)}  (unrot_x pt)")
    # print binned profile every 20 px
    line=[]
    for i in range(0,W,20):
        v=max(prof[i:i+20]) if i<W else 0
        line.append(f"{i}:{v:.3f}")
    print("    profile:", " ".join(line))
