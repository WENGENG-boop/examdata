import pymupdf, sys
pdf=sys.argv[1]
doc=pymupdf.open(pdf)
for f in sys.argv[2:]:
    i=int(f)
    print(f'########## file {i} ##########')
    print(doc[i-1].get_text('text'))
