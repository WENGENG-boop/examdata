# -*- coding: utf-8 -*-
"""帧26 点状线裁决: PDF 像素级扫描 + sheet crop PNG 对照。只读本地文件。"""
import pymupdf, collections

BR = "C:/Users/weo/Desktop/api/cie-location-batch"
qp = pymupdf.open(f"{BR}/tmp/0472/2026-Jun-22/0472_s26_qp_22.pdf")
p = qp[9]
print(f"p10 rect={p.rect} rotation={p.rotation}")

an = p.annots()
print("annots:", [(a.type, tuple(round(v, 1) for v in a.rect)) for a in an] if an else "none")
print("widgets:", [(w.field_name, tuple(round(v, 1) for v in w.rect)) for w in p.widgets()])
print("images:", p.get_images(full=True))
print("links:", p.get_links())

print("== bboxlog x1>455 ==")
for t, r in p.get_bboxlog():
    if r[2] > 455:
        print("  ", t, [round(v, 1) for v in r])

print("== drawings overlapping x>486 ==")
for d in p.get_drawings():
    r = d["rect"]
    if r.x1 > 486 and r.y0 < 780:
        print(f"  [{r.x0:.1f},{r.y0:.1f},{r.x1:.1f},{r.y1:.1f}] w={r.width:.1f} h={r.height:.1f} dashes={d.get('dashes')} type={d['type']}")

print("== drawings with dashes (whole page) ==")
n_dash = 0
for d in p.get_drawings():
    da = d.get("dashes")
    if da and str(da) not in ("[] 0", "None"):
        n_dash += 1
        r = d["rect"]
        print(f"  [{r.x0:.1f},{r.y0:.1f},{r.x1:.1f},{r.y1:.1f}] w={r.width:.1f} h={r.height:.1f} dashes={da}")
print("  dashed drawings count:", n_dash)


def scan_pix(pix, label, xlo, xhi, thresh, pt):
    s = pix.samples
    W, H, n = pix.width, pix.height, pix.n
    hits = []
    for yy in range(H):
        b = yy * W * n
        for xx in range(xlo, xhi):
            i = b + xx * n
            r, g, bl = s[i], s[i + 1], s[i + 2]
            if r < thresh or g < thresh or bl < thresh:
                hits.append((xx, yy, r, g, bl))
    print(f"[{label}] {W}x{H} xlo={xlo} xhi={xhi} thresh={thresh} hits={len(hits)}")
    if hits and pt:
        X0, Y0, z = pt
        xs = [h[0] for h in hits]
        ys = [h[1] for h in hits]
        print(f"   px x {min(xs)}..{max(xs)} y {min(ys)}..{max(ys)}")
        print(f"   pt x {X0 + min(xs) / z:.1f}..{X0 + max(xs) / z:.1f} y {Y0 + min(ys) / z:.1f}..{Y0 + max(ys) / z:.1f}")
        ysu = sorted(set(h[1] for h in hits))
        groups = []
        for v in ysu:
            if groups and v - groups[-1][1] <= 4:
                groups[-1][1] = v
            else:
                groups.append([v, v])
        print("   y groups px:", groups[:30])
        cols = collections.Counter((h[2] // 16 * 16, h[3] // 16 * 16, h[4] // 16 * 16) for h in hits)
        print("   colors:", cols.most_common(6))
    return hits


# A) sheet crop PNG itself: right 80 columns
sp = pymupdf.Pixmap(f"{BR}/tmp/0472/2026-Jun-22/crops/stack-0472-2026-Jun-22-qp-regions-036-qp-p10.png")
print("sheet crop png:", sp.width, sp.height, sp.n)
scan_pix(sp, "SHEET-CROP right80cols", max(0, sp.width - 80), sp.width, 252, (70.8, 58.8, sp.width / 423.2))

# B) fresh repro of same clip
z = sp.width / 423.2
fp = p.get_pixmap(matrix=pymupdf.Matrix(z, z), clip=pymupdf.Rect(70.8, 58.8, 494.0, 558.8), alpha=False)
fp.save(f"{BR}/work/_p10_crop_repro.png")
print("fresh repro:", fp.width, fp.height)
scan_pix(fp, "FRESH-REPRO right80cols", max(0, fp.width - 80), fp.width, 252, (70.8, 58.8, z))

# C) full right margin of PDF x486-612 @4x
z2 = 4
mp = p.get_pixmap(matrix=pymupdf.Matrix(z2, z2), clip=pymupdf.Rect(486, 50, 612, 780), alpha=False)
mp.save(f"{BR}/work/_p10_right4x.png")
scan_pix(mp, "PDF right margin x486-612", 0, mp.width, 250, (486, 50, z2))

# D) dots zone x460-520 y180-235 @8x
z3 = 8
dp = p.get_pixmap(matrix=pymupdf.Matrix(z3, z3), clip=pymupdf.Rect(460, 180, 520, 235), alpha=False)
dp.save(f"{BR}/work/_p10_dots8x.png")
scan_pix(dp, "PDF dots zone x460-520 y180-235", 0, dp.width, 253, (460, 180, z3))

print("done")
