from pathlib import Path
from io import BytesIO
import json
import subprocess
import sys
from zipfile import ZipFile

import pymupdf
from fastapi.testclient import TestClient
from examdata.paperqa import query
from examdata.paperqa.locator import locate
from examdata.api.app import app

root = Path('tmpwork/paperqa-live')
root.mkdir(exist_ok=True)
cases = [
    dict(board='cie', subject='9709', year=2026, season='Mar', paper='12', mode=mode)
    for mode in ['qp', 'ms', 'both']
] + [
    dict(board='edexcel', subject='Economics', year=2024, season='Jun', paper='wec11-01', mode='paper'),
    dict(board='edexcel', subject='Economics', year=2024, season='Jun', paper='wec11-01', question='1', mode='question'),
    dict(board='edexcel', subject='ial18-economics', year=2024, season='Jun', paper='wec11-01', question='12(a)', mode='qa'),
]
for index, case in enumerate(cases):
    result = query(**case, out_dir=root / f'python-{index}')
    print('PYTHON', json.dumps(result.metadata()))
    for f in result.files:
        assert (root / f'python-{index}' / f.name).read_bytes() == f.data
        if f.media_type == 'image/png':
            image = pymupdf.Pixmap(f.data)
            assert image.width > 100 and image.height > 20
        else:
            with pymupdf.open(stream=f.data, filetype='pdf') as pdf:
                assert pdf.page_count > 0
with TestClient(app) as client:
    for index, case in enumerate(cases):
        meta = client.get('/paper-qa/resolve', params=case)
        assert meta.status_code == 200, meta.text
        assert meta.json()['files'] == []
        response = client.get('/paper-qa/query', params=case)
        assert response.status_code == 200, response.text[:1000]
        kind = response.headers['content-type']
        if kind == 'application/zip':
            with ZipFile(BytesIO(response.content)) as zipfile:
                assert zipfile.testzip() is None
                members = zipfile.namelist()
        else:
            members = [response.headers['content-disposition']]
        print('HTTP', index, kind, len(response.content), members)
        (root / f'http-{index}.bin').write_bytes(response.content)
for index in [0, 5]:
    args = [sys.executable, '-m', 'examdata.cli', 'paper-qa']
    for key, value in cases[index].items():
        args.extend(['--' + key, str(value)])
    args.extend(['--out', str(root / f'cli-{index}'), '--json'])
    completed = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', check=True)
    payload = json.loads(completed.stdout)
    assert payload['files']
    print('CLI', json.dumps(payload))
for filename, role in [('wec11.pdf', 'qp'), ('wec11_rms.pdf', 'ms')]:
    with pymupdf.open('tmpwork/probe/' + filename) as pdf:
        clips = locate(pdf, '12(a)', role)
        assert clips[0][0] == 10 and clips[-1][0] == 10
        text = ' '.join(pdf[p].get_text(clip=clip) for p, clip in clips)
        assert 'capital goods' in text.lower()
        assert '12 (b)' not in text
        main = locate(pdf, '12', role)
        assert len(main) > 3
        final = locate(pdf, '14', role)
        final_text = ' '.join(pdf[p].get_text(clip=clip) for p, clip in final)
        assert 'Acknowledgements' not in final_text
        if role == 'qp':
            assert final[-1][0] == 24
        print('LOCATOR', filename, '12(a)', [(p + 1, tuple(r)) for p, r in clips], '14 last page', final[-1][0] + 1)
print('LIVE VERIFICATION PASSED')
