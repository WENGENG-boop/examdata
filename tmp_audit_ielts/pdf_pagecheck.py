# PDF 页数真实性检查（PyMuPDF）
import os, sys, json
import pymupdf

dl = 'C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads'
out = {}
for b in range(1, 21):
    f = os.path.join(dl, f'book_{b}.pdf')
    try:
        doc = pymupdf.open(f)
        npages = doc.page_count
        # 取第 1 页前 200 字符文本做内容指纹
        first_text = doc[0].get_text()[:200].replace('\n', ' | ')
        out[b] = {'pages': npages, 'bytes': os.path.getsize(f), 'first_page_snippet': first_text}
        doc.close()
    except Exception as e:
        out[b] = {'error': str(e)}
    print(json.dumps({str(b): out[b]}, ensure_ascii=False)[:300])
json.dump(out, open('C:/Users/weo/Desktop/api/tmp_audit_ielts/pdf_pagecheck.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('PAGECHECK_DONE')
