from pathlib import Path
import fitz
root=Path(__file__).resolve().parents[1]
for role, pages in [('qp',[2,3,4,5]),('ms',[6,7,8,9,10,11,12,13,14,15,16,17,18])]:
 doc=fitz.open(root/'tmp/9715/2023-Nov-21'/f'9715_w23_{role}_21.pdf')
 print('\nROLE',role)
 for n in pages:
  p=doc[n-1]
  print('PAGE',n,'rotation',p.rotation,'raw size',tuple(p.mediabox),'visual',tuple(p.rect))
  for b in p.get_text('blocks'):
   t=' '.join(str(b[4]).split())
   if t:
    if role=='qp' or any(s in t for s in ('1(a)','1(b)','1(c)','1(d)','1(e)','2(a)','2(b)','2(c)','3(a)','3(b)','3(c)','3(d)','3(e)','4(a)','4(b)','4(c)','4(d)','4(e)','5(a)','5(b)','Question 1','Question 2','Question 3','Question 4','Question 5','Quality of Language')):
     rect=fitz.Rect(b[:4]); vis=rect*p.rotation_matrix
     print(' ',tuple(round(x,1) for x in rect),'vis',tuple(round(x,1) for x in vis),repr(t[:180]))
