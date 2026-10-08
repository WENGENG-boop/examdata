from pathlib import Path
import fitz
p=fitz.open('cie-location-batch/tmp/9715/2023-Nov-21/9715_w23_ms_21.pdf')[5]
raw=fitz.Rect(196.4,57.2,220.8,735.6)
rot=raw*p.rotation_matrix
derot=raw*p.derotation_matrix
print('rect',p.rect,'rotation',p.rotation,'rotation_matrix',p.rotation_matrix,'derotation_matrix',p.derotation_matrix)
print('raw',raw,'rot',rot,'derot',derot)
for name,clip in [('raw',raw),('rot',rot),('derot',derot)]:
 try:
  pix=p.get_pixmap(matrix=fitz.Matrix(1.5,1.5),clip=clip,alpha=False)
  out=Path('cie-location-batch/work')/f'9715-clip-test-{name}.png'
  pix.save(out)
  print(name,'pix',pix.width,pix.height,'file',out.resolve())
 except Exception as e: print(name,'ERROR',repr(e))
