from io import BytesIO
import importlib
import pytest
import pymupdf
from examdata.paperqa import query
from examdata.paperqa.api import json_payload, response_payload
from examdata.paperqa.models import Request, Result, OutputFile
from examdata.paperqa.errors import UpstreamError
from examdata.paperqa.budget import RequestBudget
from test_paperqa import FakeFetcher, pdf_bytes


def test_downloads_share_a_cumulative_budget(monkeypatch):
    data = pdf_bytes()
    monkeypatch.setattr("examdata.paperqa.budget.MAX_REQUEST_BYTES", len(data) * 2 - 1)
    fetcher = FakeFetcher(data=data)
    with pytest.raises(UpstreamError, match="PDF downloads"):
        query("cie", "9709", 2026, "Mar", "12", mode="both", fetcher=fetcher)
    assert len([call for call in fetcher.calls if call[0] == "GET"]) == 2


def test_base64_rejects_before_allocating_encoded_content(monkeypatch):
    data = pdf_bytes()
    result = query("cie", "9709", 2026, "Mar", "12", mode="qp", fetcher=FakeFetcher(data=data))
    result.budget.limit = len(data)
    with pytest.raises(UpstreamError, match="base64"):
        json_payload(result)


def test_zip_growth_is_bounded():
    request = Request.parse("cie", "9709", 2026, "Mar", "12", mode="both")
    result = Result(request, [], [OutputFile("a.pdf", b"1234", "application/pdf", "qp"),
                                  OutputFile("b.pdf", b"5678", "application/pdf", "ms")],
                    budget=RequestBudget(limit=20))
    with pytest.raises(UpstreamError, match="ZIP"):
        response_payload(result)


def test_raster_budget_checked_before_pixmap_allocation(monkeypatch):
    from examdata.paperqa.locator import crop_question
    data = pdf_bytes()
    called = []
    monkeypatch.setattr(pymupdf.Page, "get_pixmap", lambda *args, **kwargs: called.append(True))
    with pytest.raises(UpstreamError, match="raster"):
        crop_question(data, "1", "qp", budget=RequestBudget(limit=1))
    assert not called


def test_file_count_limit_applies_to_custom_results(monkeypatch):
    monkeypatch.setattr("examdata.paperqa.budget.MAX_OUTPUT_FILES", 1)
    result = Result(Request.parse("cie", "9709", 2026, "Mar", "12", mode="both"), [],
                    [OutputFile("a", b"a", "application/pdf", "qp"), OutputFile("b", b"b", "application/pdf", "ms")])
    with pytest.raises(UpstreamError, match="file limit"):
        json_payload(result)
