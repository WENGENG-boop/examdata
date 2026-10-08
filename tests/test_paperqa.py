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
from examdata.paperqa.models import Document, Request
from examdata.paperqa.sources.base import download_pdf
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


@pytest.mark.parametrize('mode,question,paper', [('question', None, 'wec11'), ('qa', '1', None), ('paper', '1', 'wec11'), ('both', '1', None)])
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


class TrackingStream(httpx.SyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks
        self.read_chunks = 0
        self.closed = False

    def __iter__(self):
        for chunk in self.chunks:
            self.read_chunks += 1
            yield chunk

    def close(self):
        self.closed = True


@pytest.fixture
def mock_fetcher():
    settings = Settings(
        min_host_interval_seconds=0, host_interval_jitter_seconds=0,
        max_retries=2, retry_backoff_seconds=0, respect_robots=False,
    )
    owned = []

    def create(handler):
        fetcher = Fetcher(settings)
        fetcher._client.close()
        fetcher._client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
        owned.append(fetcher)
        return fetcher

    yield create
    for fetcher in owned:
        fetcher.close()


@pytest.mark.parametrize('binary', [True, False])
def test_fetcher_declared_size_rejected_before_read(monkeypatch, mock_fetcher, binary):
    module = importlib.import_module('examdata.core.fetch')
    monkeypatch.setattr(module, 'MAX_RESPONSE_BYTES', 8)
    stream = TrackingStream([b'not consumed'])
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, headers={'Content-Length': '9'}, stream=stream)

    result = mock_fetcher(handler).get('https://test.test/large', expect_binary=binary)
    assert result.status == 200 and not result.ok and result.error
    assert result.content is None and result.text is None
    assert result.content_length == 9
    assert stream.closed and stream.read_chunks == 0
    assert len(calls) == 1


@pytest.mark.parametrize('length', [None, '1', 'invalid', '-1'])
@pytest.mark.parametrize('binary', [True, False])
def test_fetcher_actual_size_stops_stream(monkeypatch, mock_fetcher, length, binary):
    module = importlib.import_module('examdata.core.fetch')
    monkeypatch.setattr(module, 'MAX_RESPONSE_BYTES', 8)
    stream = TrackingStream([b'1234', b'56789', b'must not be read'])
    headers = {} if length is None else {'Content-Length': length}
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, headers=headers, stream=stream)

    result = mock_fetcher(handler).get('https://test.test/large', expect_binary=binary)
    assert result.status == 200 and not result.ok and result.error
    assert not result.robots_blocked
    assert result.content is None and result.text is None
    assert stream.closed and stream.read_chunks == 2
    assert len(calls) == 1


@pytest.mark.parametrize('headers', [{}, {'Content-Length': '8'}])
@pytest.mark.parametrize('binary', [True, False])
def test_fetcher_exact_limit_and_text_decoding(monkeypatch, mock_fetcher, headers, binary):
    module = importlib.import_module('examdata.core.fetch')
    monkeypatch.setattr(module, 'MAX_RESPONSE_BYTES', 8)
    stream = TrackingStream([b'caf\xe9', b'1234'])
    fetcher = mock_fetcher(lambda request: httpx.Response(
        200, headers={**headers, 'Content-Type': 'text/plain; charset=iso-8859-1'}, stream=stream,
    ))
    result = fetcher.get('https://test.test/exact', expect_binary=binary)
    assert result.ok and result.content == b'caf\xe91234'
    assert result.text == (None if binary else 'café1234')
    assert stream.closed and stream.read_chunks == 2


def test_fetcher_limits_decoded_compressed_body(monkeypatch, mock_fetcher):
    import gzip
    module = importlib.import_module('examdata.core.fetch')
    monkeypatch.setattr(module, 'MAX_RESPONSE_BYTES', 64)
    compressed = gzip.compress(b'x' * 1000)
    assert len(compressed) < 64
    stream = TrackingStream([compressed])
    fetcher = mock_fetcher(lambda request: httpx.Response(
        200, headers={'Content-Encoding': 'gzip', 'Content-Length': str(len(compressed))}, stream=stream,
    ))
    result = fetcher.get('https://test.test/compressed')
    assert not result.ok and result.error
    assert result.content is None and result.text is None and stream.closed


def test_fetcher_small_compressed_text(monkeypatch, mock_fetcher):
    import gzip
    module = importlib.import_module('examdata.core.fetch')
    monkeypatch.setattr(module, 'MAX_RESPONSE_BYTES', 64)
    stream = TrackingStream([gzip.compress('café'.encode())])
    fetcher = mock_fetcher(lambda request: httpx.Response(
        200, headers={'Content-Encoding': 'gzip', 'Content-Type': 'text/plain; charset=utf-8'}, stream=stream,
    ))
    result = fetcher.get('https://test.test/compressed')
    assert result.ok and result.content == 'café'.encode() and result.text == 'café'
    assert stream.closed


def test_fetcher_redirect_body_is_not_buffered(monkeypatch, mock_fetcher):
    module = importlib.import_module('examdata.core.fetch')
    monkeypatch.setattr(module, 'MAX_RESPONSE_BYTES', 8)
    redirect = TrackingStream([b'huge redirect body'])
    final = TrackingStream([b'123456789', b'not consumed'])
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if request.url.path == '/redirect':
            return httpx.Response(302, headers={'Location': '/target'}, stream=redirect)
        return httpx.Response(200, stream=final)

    result = mock_fetcher(handler).get('https://test.test/redirect')
    assert result.url == 'https://test.test/target' and not result.ok
    assert paths == ['/redirect', '/target']
    assert redirect.closed and redirect.read_chunks == 0
    assert final.closed and final.read_chunks == 1


def test_fetcher_redirect_preserves_post_conversion_and_cookies(mock_fetcher):
    redirect = TrackingStream([b'not consumed'])
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path == '/form':
            return httpx.Response(302, headers={
                'Location': '/target', 'Set-Cookie': 'session=public; Path=/',
            }, stream=redirect)
        return httpx.Response(200, text='ok')

    result = mock_fetcher(handler).post_form('https://test.test/form', {'subject': '9709'})
    assert result.ok and result.text == 'ok'
    assert [request.method for request in requests] == ['POST', 'GET']
    assert requests[-1].headers['cookie'] == 'session=public'
    assert redirect.closed and redirect.read_chunks == 0


@pytest.mark.parametrize('status,expected_calls', [(304, 1), (503, 2)])
def test_fetcher_does_not_read_not_modified_or_retry_bodies(mock_fetcher, status, expected_calls):
    streams = []
    requests = []

    def handler(request):
        requests.append(request)
        stream = TrackingStream([b'not consumed'])
        streams.append(stream)
        return httpx.Response(status, headers={'ETag': 'revision'}, stream=stream)

    result = mock_fetcher(handler).get('https://test.test/retry', etag='revision')
    assert len(requests) == expected_calls
    assert all(request.headers['If-None-Match'] == 'revision' for request in requests)
    assert all(stream.closed and stream.read_chunks == 0 for stream in streams)
    assert result.content is None and result.text is None
    assert result.not_modified == (status == 304)
    assert result.status == (304 if status == 304 else 0)


@pytest.mark.parametrize('overflow', ['actual', 'declared'])
@pytest.mark.parametrize('board,subject,year,season,paper', [
    ('cie', '9709', 2026, 'Mar', '12'),
    ('edexcel', 'Economics', 2024, 'Jun', 'wec11-01'),
])
def test_custom_fetcher_cannot_bypass_pdf_limit(monkeypatch, overflow, board, subject, year, season, paper):
    base = importlib.import_module('examdata.paperqa.sources.base')
    data = pdf_bytes()
    monkeypatch.setattr(base, 'MAX_RESPONSE_BYTES', len(data))

    class Oversized(FakeFetcher):
        def get(self, url, **kwargs):
            result = super().get(url, **kwargs)
            if overflow == 'actual':
                result.content += b'x'
            else:
                result.headers['Content-Length'] = str(len(data) + 1)
            return result

    with pytest.raises(UpstreamError, match='size limit') as raised:
        query(board, subject, year, season, paper, fetcher=Oversized(data))
    assert raised.value.status_code == 502


@pytest.mark.parametrize('status', [302, 401, 403])
def test_oversized_access_denial_keeps_mapping(monkeypatch, status):
    base = importlib.import_module('examdata.paperqa.sources.base')
    monkeypatch.setattr(base, 'MAX_RESPONSE_BYTES', 1)
    with pytest.raises(AccessDenied) as raised:
        query('cie', '9709', 2026, 'Mar', '12', fetcher=FakeFetcher(b'%PDF-large', status))
    assert raised.value.status_code == 403


def test_pdf_download_stream_limit_maps_to_upstream(monkeypatch, mock_fetcher):
    module = importlib.import_module('examdata.core.fetch')
    monkeypatch.setattr(module, 'MAX_RESPONSE_BYTES', 8)
    stream = TrackingStream([b'%PDF-', b'large body', b'not consumed'])
    fetcher = mock_fetcher(lambda request: httpx.Response(200, stream=stream))
    document = Document('paper.pdf', 'https://test.test/paper.pdf', 'qp', '12')
    with pytest.raises(UpstreamError) as raised:
        download_pdf(fetcher, document)
    assert raised.value.status_code == 502
    assert stream.closed and stream.read_chunks == 2


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



def test_cross_host_redirect_strips_authorization_and_skips_body(mock_fetcher):
    seen=[]
    redirect=TrackingStream([b"never read"])
    def handler(request):
        seen.append((request.url.host,request.headers.get("authorization")))
        if request.url.host == "first.test":
            return httpx.Response(302,headers={"Location":"https://second.test/final"},stream=redirect)
        return httpx.Response(200,content=b"ok")
    fetcher=mock_fetcher(handler)
    fetcher._client.headers["Authorization"]="Bearer synthetic"
    result=fetcher.get("https://first.test/start")
    assert result.ok and result.content==b"ok"
    assert seen==[("first.test","Bearer synthetic"),("second.test",None)]
    assert redirect.closed and redirect.read_chunks==0


def test_redirect_exhaustion_is_terminal_and_closes_every_response(mock_fetcher):
    streams=[]
    def handler(request):
        stream=TrackingStream([b"never read"]);streams.append(stream)
        return httpx.Response(302,headers={"Location":"/again"},stream=stream)
    fetcher=mock_fetcher(handler);fetcher._client.max_redirects=2
    result=fetcher.get("https://test.test/again")
    assert result.status==0 and "TooManyRedirects" in result.error
    assert len(streams)==3
    assert all(stream.closed and stream.read_chunks==0 for stream in streams)


def test_redirect_rechecks_destination_robots_before_resource_request():
    calls=[]
    def handler(request):
        calls.append((request.url.host,request.url.path))
        if request.url.path=="/robots.txt":
            policy="User-agent: *\nDisallow: /" if request.url.host=="second.test" else "User-agent: *\nAllow: /"
            return httpx.Response(200,text=policy)
        if request.url.host=="first.test":
            return httpx.Response(302,headers={"Location":"https://second.test/private"})
        raise AssertionError("Disallowed redirect resource requested")
    with Fetcher(Settings(respect_robots=True,min_host_interval_seconds=0,host_interval_jitter_seconds=0,max_retries=2)) as fetcher:
        fetcher._client.close();fetcher._client=httpx.Client(transport=httpx.MockTransport(handler),follow_redirects=True)
        result=fetcher.get("https://first.test/start")
    assert result.robots_blocked
    assert calls==[("first.test","/robots.txt"),("first.test","/start"),("second.test","/robots.txt")]
