"""Cumulative work/output budget for one PaperQA request (not a process RSS limit)."""
from dataclasses import dataclass
from .errors import UpstreamError

MAX_REQUEST_BYTES = 256 * 1024 * 1024
MAX_DOCUMENTS = 64
MAX_OUTPUT_FILES = 256


@dataclass
class RequestBudget:
    limit: int | None = None
    used: int = 0

    def charge(self, amount: int, stage: str) -> None:
        limit = MAX_REQUEST_BYTES if self.limit is None else self.limit
        if amount < 0 or amount > limit - self.used:
            raise UpstreamError(f"Request budget exceeded during {stage}")
        self.used += amount

    def check_files(self, count: int) -> None:
        if count > MAX_OUTPUT_FILES:
            raise UpstreamError("Request output file limit exceeded")


class BudgetedFetcher:
    """Count catalogue and file response bytes without owning the wrapped client."""
    def __init__(self, fetcher, budget):
        self.fetcher = fetcher
        self.budget = budget

    def __getattr__(self, name):
        return getattr(self.fetcher, name)

    def _request(self, method, *args, **kwargs):
        response = getattr(self.fetcher, method)(*args, **kwargs)
        content = getattr(response, "content", None)
        text = getattr(response, "text", None)
        size = len(content) if content else len((text or "").encode("utf-8"))
        stage = "PDF downloads" if kwargs.get("expect_binary") else "catalogue responses"
        self.budget.charge(size, stage)
        return response

    def get(self, *args, **kwargs):
        return self._request("get", *args, **kwargs)

    def get_text(self, *args, **kwargs):
        return self._request("get_text", *args, **kwargs)

    def post_form(self, *args, **kwargs):
        return self._request("post_form", *args, **kwargs)
