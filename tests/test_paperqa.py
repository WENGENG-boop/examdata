from io import BytesIO
import importlib
import json
from zipfile import ZipFile

import httpx
import pymupdf
import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from examdata.core.config import Settings
from examdata.core.fetch import Fetcher, FetchResult
from examdata.paperqa import query, resolve
from examdata.paperqa.api import response_payload
from examdata.paperqa.errors import AccessDenied, InvalidRequest, LocationError, NotFound, UpstreamError
from examdata.paperqa.locator import locate
from examdata.paperqa.models import Request
from examdata.paperqa.sources.pearson import public_url
from examdata.adapters.edexcel.servlet import build_fq, fetch_records


def pdf_bytes():
    with pymupdf.open() as pdf:
        pdf.new_page()
        page = pdf.new_page()
        for x, y, text in [(43, 100, '1'), (80, 100, 'First question'), (43, 300, '2'),
                           (80, 300, 'Second question'), (60, 320, '(a)'), (80, 340, '(i)'),
                           (80, 380, '(ii)'), (60, 450, '(b)'), (80, 450, 'Last subquestion')]:
            page.insert_text((x, y), text)
        return pdf.tobytes()


class FakeFetcher:
    def __init__(self, data=None, status=200):
        self.data = pdf_bytes() if data is None else data
        self.status = status
        self.calls = []

    def post_form(self, url, data, **kwargs):
        self.calls.append(('POST', url, data, kwargs))
        rows = [{'file': f'9709_m26_{role}_12.pdf'} for role in ['qp', 'ms']]
        rows += [{'file': '../evil.pdf'}, {'file': '9709_s26_qp_12.pdf'}]
        return FetchResult(url, 200, text=json.dumps({'total': len(rows), 'rows': rows}))

    def get_text(self, url):
        self.calls.append(('CAT', url))
        records = [{'url': f'/content/dam/pdf/Economics/wec11-01-{kind}-20240510.pdf',
                    'category': [f'Pearson-UK:Document-Type/{label}']}
                   for kind, label in [('que', 'Question-paper'), ('rms', 'Mark-scheme')]]
        return FetchResult(url, 200, text=json.dumps({'searchResults': {'algoliaRecords': records}}))

    def get(self, url, **kwargs):
        self.calls.append(('GET', url, kwargs))
        assert kwargs == {'expect_binary': True, 'follow_redirects': False}
        return FetchResult(url, self.status, content=self.data)


@pytest.mark.parametrize('mode,count', [('qp', 1), ('ms', 1), ('both', 2), ('qp+ms', 2)])
def test_cie_modes_memory(mode, count, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = query('cie', '9709', 2026, 'Mar', '12', mode=mode, fetcher=FakeFetcher())
    assert len(r.files) == count
    assert all(f.data.startswith(b'%PDF-') for f in r.files)
    assert list(tmp_path.iterdir()) == []
    assert len(r.metadata()['documents']) == count


@pytest.mark.parametrize('mode', ['paper', 'question', 'qa'])
def test_edexcel_modes(mode):
    r = query('edexcel', 'Economics', 2024, 'Jun', 'wec11-01',
              None if mode == 'paper' else '2(a)', mode, fetcher=FakeFetcher())
    assert {f.role for f in r.files} == ({'qp', 'ms'} if mode == 'qa' else {'qp'})
    assert all(f.data.startswith(b'%PDF-' if mode == 'paper' else b'\x89PNG') for f in r.files)
    if mode == 'qa':
        output = response_payload(r)
        with ZipFile(BytesIO(output.data)) as archive:
            assert len(archive.namelist()) == len(r.files)


@pytest.mark.parametrize('changes', [
    {'board': 'bad'}, {'subject': '../bad'}, {'year': 1999}, {'year': '2024.5'},
    {'season': 'Jan'}, {'mode': 'qa'}, {'question': '1'}, {'paper': '../12'},
    {'paper': '123'}, {'subject': 'math'}, {'question': '1;url'},
])
def test_invalid_cie(changes):
    args = dict(board='cie', subject='9709', year=2026, season='Mar', paper='12')
    args.update(changes)
    with pytest.raises(InvalidRequest):
        query(**args, fetcher=FakeFetcher())


@pytest.mark.parametrize('mode,question,paper', [('question', None, 'wec11'), ('qa', '1', None), ('paper', '1', 'wec11'), ('both', None, None)])
def test_invalid_edexcel(mode, question, paper):
    with pytest.raises(InvalidRequest):
        query('edexcel', 'Economics', 2024, 'Jun', paper, question, mode, fetcher=FakeFetcher())


def test_winter_means_january():
    assert Request.parse('edexcel', 'Economics', 2024, 'Winter').season == 'January'


@pytest.mark.parametrize('given,canonical', [
    ('2(a)', '2(a)'), ('2(a)(ii)', '2(a)(ii)'), ('12', '12'),
    ('2a', '2(a)'), ('2ai', '2(a)(i)'), ('2aii', '2(a)(ii)'), ('2aiv', '2(a)(iv)'),
])
def test_question_shorthand_is_canonicalised(given, canonical):
    assert Request.parse('edexcel', 'Economics', 2024, 'Jun', 'wec11', given,
                         'question').question == canonical


@pytest.mark.parametrize('bad', ['2ab', '2(a)(y)', '0', '2a1', '2aiiiiv'])
def test_question_shorthand_rejects_garbage(bad):
    with pytest.raises(InvalidRequest):
        Request.parse('edexcel', 'Economics', 2024, 'Jun', 'wec11', bad, 'question')


@pytest.mark.parametrize('url', [
    'https://evil.test/content/dam/pdf/a.pdf', '//evil.test/a.pdf',
    'https://qualifications.pearson.com.evil.test/content/dam/pdf/a.pdf',
    '/content/dam/secure/a.pdf', '/content/dam/gold/a.pdf', '/content/dam/silver/a.pdf',
    '/content/dam/pdf/../secure/a.pdf', '/content/dam/pdf/%2e%2e/a.pdf',
    '/content/dam/pdf/a.pdf?redirect=http://evil.test', '/content/dam/pdf/a.pdf#x',
    'http://qualifications.pearson.com/content/dam/pdf/a.pdf', '/content/dam/pdf/a\\b.pdf',
])
def test_public_path_security(url):
    with pytest.raises(AccessDenied):
        public_url(url)


@pytest.mark.parametrize('status,data,error', [(302, b'x', AccessDenied), (403, b'x', AccessDenied),
    (404, b'x', UpstreamError), (200, b'<html>login</html>', UpstreamError), (200, b'%PDF-broken', UpstreamError)])
def test_download_failures(status, data, error):
    with pytest.raises(error):
        query('cie', '9709', 2026, 'Mar', '12', fetcher=FakeFetcher(data, status))


def test_resolve_never_downloads():
    fetcher = FakeFetcher()
    r = resolve('cie', '9709', 2026, 'Mar', '12', fetcher=fetcher)
    assert not r.files
    assert all(call[0] != 'GET' for call in fetcher.calls)


def test_output_explicit_and_no_overwrite(tmp_path):
    args = ('cie', '9709', 2026, 'Mar', '12')
    r = query(*args, out_dir=tmp_path, fetcher=FakeFetcher())
    assert (tmp_path / r.files[0].name).read_bytes() == r.files[0].data
    with pytest.raises(FileExistsError):
        query(*args, out_dir=tmp_path, fetcher=FakeFetcher())


def test_locator_boundaries_and_roman():
    with pymupdf.open(stream=pdf_bytes(), filetype='pdf') as pdf:
        main = locate(pdf, '1', 'qp')
        assert main[0][1].y1 < 300
        roman = locate(pdf, '2(a)(i)', 'qp')
        assert roman[0][1].y0 > 320
        assert roman[0][1].y1 < 380
        with pytest.raises(LocationError):
            locate(pdf, '99', 'qp')


def test_locator_summary_repeats_and_end():
    with pymupdf.open() as pdf:
        pdf.new_page()
        page = pdf.new_page()
        for x, y, text in [(43, 100, '1'), (60, 110, '(a)'), (60, 140, '(b)'), (60, 170, '(c)')]:
            page.insert_text((x, y), text)
        page = pdf.new_page()
        for x, y, text in [(43, 100, '1'), (60, 100, '(a)'), (80, 120, 'Actual question'), (60, 300, '(b)')]:
            page.insert_text((x, y), text)
        page = pdf.new_page()
        page.insert_text((43, 100), '2')
        page.insert_text((43, 500), 'TOTAL FOR PAPER = 20 MARKS')
        page = pdf.new_page()
        page.insert_text((43, 100), 'Acknowledgements')
        assert locate(pdf, '1(a)', 'qp')[0][0] == 2
        assert locate(pdf, '1', 'qp')[-1][0] == 2
        assert locate(pdf, '2', 'qp')[-1][0] == 3


def test_scanned_pdf_fails():
    with pymupdf.open() as pdf:
        pdf.new_page()
        pdf.new_page()
        with pytest.raises(LocationError):
            locate(pdf, '1', 'qp')


def test_servlet_or_and_failure():
    assert build_fq(['a', ['b', 'c']]) == 'category:"a" AND (category:"b" OR category:"c")'
    from examdata.adapters.edexcel.servlet import ServletError
    class Broken:
        def get_text(self, url):
            return FetchResult(url, 500)
    with pytest.raises(ServletError):
        fetch_records(Broken(), ['a'])


def test_http_metadata_binary_zip_and_errors(monkeypatch, tmp_path):
    module = importlib.import_module('examdata.api.app')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, 'paperqa_query', lambda *a: query(*a, fetcher=FakeFetcher()))
    monkeypatch.setattr(module, 'paperqa_resolve', lambda *a: resolve(*a, fetcher=FakeFetcher()))
    with TestClient(module.app) as client:
        args = dict(board='cie', subject='9709', year=2026, season='Mar', paper='12')
        assert client.get('/paper-qa/resolve', params=args).json()['files'] == []
        assert client.get('/paper-qa/query', params=args).content.startswith(b'%PDF-')
        r = client.get('/paper-qa/query', params={**args, 'mode': 'both'})
        assert r.headers['content-type'] == 'application/zip'
        assert len(ZipFile(BytesIO(r.content)).namelist()) == 2
        assert client.get('/paper-qa/query', params={**args, 'question': '1'}).status_code == 422
        assert client.get('/paper-qa/query', params={**args, 'paper': '99'}).status_code == 404
    assert not list(tmp_path.iterdir())


def test_cli_json_and_validation(monkeypatch):
    import examdata.paperqa
    from examdata.cli import app
    monkeypatch.setattr(examdata.paperqa, 'query', lambda *a: query(*a, fetcher=FakeFetcher()))
    args = ['paper-qa', '--board', 'cie', '--subject', '9709', '--year', '2026', '--season', 'Mar', '--paper', '12', '--json']
    r = CliRunner().invoke(app, args)
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)['files'][0]['size'] > 0
    r = CliRunner().invoke(app, args + ['--mode', 'qa'])
    assert r.exit_code == 1


def test_fetcher_post_form_redirect_and_robots():
    requests = []
    def handler(request):
        requests.append(request)
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nDisallow: /blocked\n')
        if request.url.path == '/redirect':
            return httpx.Response(302, headers={'location': '/target'})
        return httpx.Response(200, text='ok')
    settings = Settings(min_host_interval_seconds=0, host_interval_jitter_seconds=0, max_retries=1)
    with Fetcher(settings) as fetcher:
        fetcher._client.close()
        fetcher._client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
        assert fetcher.post_form('https://test.test/form', {'subject': '9709'}).ok
        assert requests[-1].method == 'POST'
        assert requests[-1].content == b'subject=9709'
        assert fetcher.get('https://test.test/redirect', follow_redirects=False).status == 302
        assert fetcher.get('https://test.test/redirect').ok
        before = len(requests)
        assert not fetcher.post_form('https://test.test/blocked', {}).ok
        assert len(requests) == before


def test_context_booklet_does_not_include_other_questions():
    from examdata.paperqa.locator import crop_question
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((43, 100), 'You must have a Source Booklet')
        page = pdf.new_page()
        page.insert_text((43, 100), '1')
        page.insert_text((80, 100), 'Define capital goods (Extract C)')
        page.insert_text((43, 300), '2')
        page.insert_text((80, 300), 'Other question')
        page = pdf.new_page()
        page.insert_text((43, 100), 'Source Booklet')
        page.insert_text((43, 130), 'Do not return this Booklet')
        page = pdf.new_page()
        page.insert_text((43, 100), 'Extract C: Capital goods')
        page.insert_text((43, 400), 'Acknowledgements')
        images = crop_question(pdf.tobytes(), '1', 'qp')
        assert [p for p, data in images] == [2, 4]


def test_ambiguous_pearson_document():
    from examdata.paperqa.errors import AmbiguousDocument
    class Duplicate(FakeFetcher):
        def get_text(self, url):
            response = super().get_text(url)
            data = json.loads(response.text)
            records = data['searchResults']['algoliaRecords']
            records.append({**records[0], 'url': records[0]['url'].replace('20240510', '20240511')})
            response.text = json.dumps(data)
            return response
    with pytest.raises(AmbiguousDocument):
        query('edexcel', 'Economics', 2024, 'Jun', 'wec11-01', fetcher=Duplicate())


def test_cie_partial_catalogue_is_error():
    class Partial(FakeFetcher):
        def post_form(self, url, data, **kwargs):
            return FetchResult(url, 200, text=json.dumps({'total': 100, 'rows': []}))
    with pytest.raises(UpstreamError):
        resolve('cie', '9709', 2026, 'Mar', fetcher=Partial())


def test_owned_fetcher_does_not_initialize_storage(monkeypatch, tmp_path):
    api = importlib.import_module('examdata.paperqa.api')
    class Owned(FakeFetcher):
        def __init__(self, settings):
            super().__init__()
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(api, 'Fetcher', Owned)
    def forbidden(*args):
        raise AssertionError('Unexpected filesystem initialization')
    monkeypatch.setattr(Settings, 'ensure_dirs', forbidden)
    query('cie', '9709', 2026, 'Mar')
    assert not list(tmp_path.iterdir())
