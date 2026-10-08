import sys
import pymupdf as fitz

pdf = r"C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads/book_10.pdf"
doc = fitz.open(pdf)
OUT = r"C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/scratch/s18"

fonts = {}
for xref, tag in [(1378, 'TT3_p153_answers'), (1383, 'TT2_p153'), (1701, 'TT4_p152_answers')]:
    name, ext, ftype, buf = doc.extract_font(xref)
    fonts[tag] = (buf, name)
    print(tag, name, len(buf))

for tag, (buf, name) in fonts.items():
    font = fitz.Font(fontbuffer=buf)
    for c in "!\"#$%&'()*+,-.OC":
        try:
            tl = font.text_length(c, fontsize=100)
        except Exception as e:
            tl = -1
        print(f"{tag} char={c!r} len={tl:.1f}")

# render each char of each font at fontsize=160
for tag, (buf, name) in fonts.items():
    font = fitz.Font(fontbuffer=buf)
    chars = "!\"#$%&'()*+,-." if tag != 'TT2_p153' else "OC"
    for i, c in enumerate(chars):
        page = doc.new_page(width=200, height=200)
        tw = fitz.TextWriter(page.rect)
        tw.append((30, 150), c, font=font, fontsize=160)
        tw.write_text(page)
        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), colorspace=fitz.csGRAY)
        fn = f"{OUT}/glyphs_render/{tag}_{i:02d}_{ord(c):02x}.png"
        pix.save(fn)
        doc.delete_page(doc.page_count - 1)
print("done")
