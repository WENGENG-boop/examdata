"""paperqa 对外 API 的格式契约测试。

覆盖三件事：

1. `Result.metadata()` 的规范化字段——`schema_version`、`counts`、每文件
   `sha256`，以及每题裁剪的来源信息（1 起页码 + PDF bbox）。
2. HTTP 两个路由——二进制响应的 `Content-Disposition` / `Content-Length`、
   `format=json` 的 base64 载荷，以及错误体保持 `{"detail": ...}`。
3. CLI `--json` 与 HTTP JSON 共用同一套 schema。

`FakeFetcher` 与 `tests/test_paperqa.py` 的写法一致（假 PDF + 假 servlet
响应），这里刻意自带一份，避免测试模块之间互相 import。
"""

from __future__ import annotations

import base64
import hashlib
import importlib
import json
from io import BytesIO
from zipfile import ZipFile

import pymupdf
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from examdata.core.fetch import FetchResult
from examdata.paperqa import query, resolve
from examdata.paperqa.models import SCHEMA_VERSION

CIE_ARGS = dict(board='cie', subject='9709', year=2026, season='Mar', paper='12')


def pdf_bytes():
    with pymupdf.open() as pdf:
        pdf.new_page()
        page = pdf.new_page()
        for x, y, text in [(43, 100, '1'), (80, 100, 'First question'), (43, 300, '2'),
                           (80, 300, 'Second question'), (60, 320, '(a)'), (80, 340, '(i)'),
                           (80, 380, '(ii)'), (60, 450, '(b)'), (80, 450, 'Last subquestion')]:
            page.insert_text((x, y), text)
        return pdf.tobytes()


# pymupdf 每次 tobytes() 都会写入新的文档 ID，逐次生成的"同一份"PDF
# 字节并不相同。这里缓存一份，让同一份假官方文件在多次取回时字节一致，
# 才能比较 base64 载荷与二进制响应。
PDF = pdf_bytes()


class FakeFetcher:
    def __init__(self, data=None, status=200):
        self.data = PDF if data is None else data
        self.status = status
        self.calls = []

    def post_form(self, url, data, **kwargs):
        self.calls.append(('POST', url, data, kwargs))
        rows = [{'file': f'9709_m26_{role}_12.pdf'} for role in ['qp', 'ms']]
        return FetchResult(url, 200, text=json.dumps({'total': len(rows), 'rows': rows}))

    def get_text(self, url):
        self.calls.append(('CAT', url))
        records = [{'url': f'/content/dam/pdf/Economics/wec11-01-{kind}-20240510.pdf',
                    'category': [f'Pearson-UK:Document-Type/{label}']}
                   for kind, label in [('que', 'Question-paper'), ('rms', 'Mark-scheme')]]
        return FetchResult(url, 200, text=json.dumps({'searchResults': {'algoliaRecords': records}}))

    def get(self, url, **kwargs):
        self.calls.append(('GET', url, kwargs))
        return FetchResult(url, self.status, content=self.data)


def _patched_app(monkeypatch, tmp_path):
    module = importlib.import_module('examdata.api.app')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, 'paperqa_query', lambda *a: query(*a, fetcher=FakeFetcher()))
    monkeypatch.setattr(module, 'paperqa_resolve', lambda *a: resolve(*a, fetcher=FakeFetcher()))
    return module


def test_metadata_schema_has_version_counts_and_no_files_on_resolve():
    data = resolve(**CIE_ARGS, fetcher=FakeFetcher()).metadata()
    assert data['schema_version'] == SCHEMA_VERSION
    assert set(data) == {'schema_version', 'request', 'counts', 'documents', 'files'}
    assert data['files'] == []
    assert data['counts'] == {'documents': 1, 'files': 0, 'bytes': 0}


def test_metadata_records_size_sha256_and_absent_crop_source():
    result = query(**CIE_ARGS, fetcher=FakeFetcher())
    record = result.metadata()['files'][0]
    assert record['size'] == len(result.files[0].data) > 0
    assert record['sha256'] == hashlib.sha256(result.files[0].data).hexdigest()
    # 整份 PDF 没有裁剪来源；未内联时 data_base64 键存在但为 null
    assert record['page'] is None and record['bbox'] is None
    assert record['data_base64'] is None
    assert result.metadata()['counts'] == {
        'documents': 1, 'files': 1, 'bytes': len(result.files[0].data),
    }


def test_metadata_inline_data_round_trips_to_original_bytes():
    result = query(**CIE_ARGS, fetcher=FakeFetcher())
    record = result.metadata(inline_data=True)['files'][0]
    raw = base64.b64decode(record['data_base64'])
    assert raw == result.files[0].data
    assert hashlib.sha256(raw).hexdigest() == record['sha256']


def test_question_crops_carry_page_and_bbox():
    result = query('edexcel', 'Economics', 2024, 'Jun', 'wec11-01', '2(a)', 'question',
                   fetcher=FakeFetcher())
    assert len(result.files) == 1
    record = result.metadata()['files'][0]
    assert record['media_type'] == 'image/png'
    assert record['page'] == 2
    x0, y0, x1, y1 = record['bbox']
    assert 0 <= x0 < x1 <= 595 and 0 <= y0 < y1 <= 842
    assert record['sha256'] == hashlib.sha256(result.files[0].data).hexdigest()


def test_http_binary_headers_for_single_and_zip(monkeypatch, tmp_path):
    module = _patched_app(monkeypatch, tmp_path)
    with TestClient(module.app) as client:
        single = client.get('/paper-qa/query', params=CIE_ARGS)
        assert single.status_code == 200
        assert single.headers['content-type'] == 'application/pdf'
        assert single.content.startswith(b'%PDF-')
        assert single.headers['content-disposition'] == (
            'attachment; filename="9709_m26_qp_12.pdf"'
        )
        assert int(single.headers['content-length']) == len(single.content)

        bundle = client.get('/paper-qa/query', params={**CIE_ARGS, 'mode': 'both'})
        assert bundle.headers['content-type'] == 'application/zip'
        assert bundle.headers['content-disposition'] == 'attachment; filename="paper-qa.zip"'
        assert int(bundle.headers['content-length']) == len(bundle.content)
        with ZipFile(BytesIO(bundle.content)) as archive:
            assert len(archive.namelist()) == 2
    assert not list(tmp_path.iterdir())


def test_http_json_format_is_base64_plus_full_metadata(monkeypatch, tmp_path):
    module = _patched_app(monkeypatch, tmp_path)
    with TestClient(module.app) as client:
        binary = client.get('/paper-qa/query', params=CIE_ARGS)
        payload = client.get('/paper-qa/query', params={**CIE_ARGS, 'format': 'json'})
        assert payload.headers['content-type'].startswith('application/json')
        body = payload.json()
        assert body['schema_version'] == SCHEMA_VERSION
        assert body['counts'] == {
            'documents': 1, 'files': 1, 'bytes': len(binary.content),
        }
        record = body['files'][0]
        assert base64.b64decode(record['data_base64']) == binary.content
        assert record['sha256'] == hashlib.sha256(binary.content).hexdigest()
        assert record['size'] == len(binary.content)

        # 多文件走 JSON 时不打 ZIP：每个文件独立一条记录
        both = client.get(
            '/paper-qa/query', params={**CIE_ARGS, 'mode': 'both', 'format': 'json'}
        ).json()
        assert len(both['files']) == 2
        assert all(f['media_type'] == 'application/pdf' for f in both['files'])
        assert all(
            base64.b64decode(f['data_base64']).startswith(b'%PDF-') for f in both['files']
        )

        # 显式 format=binary 与默认等价
        explicit = client.get('/paper-qa/query', params={**CIE_ARGS, 'format': 'binary'})
        assert explicit.content == binary.content


def test_http_resolve_schema_parity_and_detail_error_bodies(monkeypatch, tmp_path):
    module = _patched_app(monkeypatch, tmp_path)
    with TestClient(module.app) as client:
        manifest = client.get('/paper-qa/resolve', params=CIE_ARGS).json()
        assert manifest['files'] == []
        assert manifest['schema_version'] == SCHEMA_VERSION

        query_json = client.get(
            '/paper-qa/query', params={**CIE_ARGS, 'format': 'json'}
        ).json()
        assert set(manifest) == set(query_json)
        assert set(manifest['files']) == set()

        # 错误体保持 FastAPI 的 {"detail": ...}，状态码语义不变
        missing = client.get('/paper-qa/query', params={**CIE_ARGS, 'paper': '99'})
        assert missing.status_code == 404
        assert set(missing.json()) == {'detail'}
        invalid = client.get('/paper-qa/query', params={**CIE_ARGS, 'question': '1'})
        assert invalid.status_code == 422
        assert set(invalid.json()) == {'detail'}
        bad_format = client.get('/paper-qa/query', params={**CIE_ARGS, 'format': 'xml'})
        assert bad_format.status_code == 422
        assert set(bad_format.json()) == {'detail'}


def test_http_openapi_documents_routes_without_write_or_url_params(monkeypatch, tmp_path):
    module = _patched_app(monkeypatch, tmp_path)
    with TestClient(module.app) as client:
        spec = client.get('/openapi.json').json()
    for path in ('/paper-qa/resolve', '/paper-qa/query'):
        operation = spec['paths'][path]['get']
        assert operation['description'].strip()
        names = {p['name'] for p in operation.get('parameters', [])}
        assert names.isdisjoint({'out', 'out_dir', 'url'})
    query_names = {
        p['name'] for p in spec['paths']['/paper-qa/query']['get'].get('parameters', [])
    }
    assert 'format' in query_names


def test_cli_json_shares_the_http_schema(monkeypatch, tmp_path):
    import examdata.paperqa
    from examdata.cli import app as cli_app

    module = _patched_app(monkeypatch, tmp_path)
    monkeypatch.setattr(examdata.paperqa, 'query', lambda *a: query(*a, fetcher=FakeFetcher()))
    args = ['paper-qa', '--board', 'cie', '--subject', '9709', '--year', '2026',
            '--season', 'Mar', '--paper', '12']

    result = CliRunner().invoke(cli_app, args + ['--json'])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload['schema_version'] == SCHEMA_VERSION
    assert payload['files'][0]['size'] > 0
    assert payload['files'][0]['sha256']
    # CLI 只在内存里持有字节，因此不内联 base64
    assert payload['files'][0]['data_base64'] is None

    with TestClient(module.app) as client:
        http_body = client.get(
            '/paper-qa/query', params={**CIE_ARGS, 'format': 'json'}
        ).json()
    assert set(payload) == set(http_body)
    assert set(payload['files'][0]) == set(http_body['files'][0])


def test_cli_human_output_shows_selector_and_memory_note(monkeypatch, tmp_path):
    import examdata.paperqa
    from examdata.cli import app as cli_app

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        examdata.paperqa, 'query',
        lambda *a: query('edexcel', 'Economics', 2024, 'Jun', 'wec11-01', '2(a)',
                         'question', fetcher=FakeFetcher()),
    )
    result = CliRunner().invoke(cli_app, [
        'paper-qa', '--board', 'edexcel', '--subject', 'Economics', '--year', '2024',
        '--season', 'Jun', '--paper', 'wec11-01', '--question', '2(a)', '--mode', 'question',
    ])
    assert result.exit_code == 0, result.output
    assert 'wec11-01' in result.output
    assert 'mode=question' in result.output
    assert 'Files returned in memory; use --out to save them.' in result.output
    assert not list(tmp_path.iterdir())
