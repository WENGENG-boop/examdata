from pathlib import Path
import fitz

root = Path(__file__).resolve().parents[1]
pdf_dir = root / 'tmp' / '9715' / '2023-Nov-21'
out_dir = root / 'work' / '9715-rendered'
out_dir.mkdir(parents=True, exist_ok=True)
for role, pattern in [('qp', '9715_w23_qp_21.pdf'), ('ms', '9715_w23_ms_21.pdf')]:
    pdf = pdf_dir / pattern
    doc = fitz.open(pdf)
    for i, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=fitz.Matrix(1.65, 1.65), alpha=False)
        out = out_dir / f'{role}-p{i:02}.png'
        pix.save(out)
        print(f'{role}\t{i}\t{page.rect.width:.1f}x{page.rect.height:.1f}\t{out.resolve()}')
