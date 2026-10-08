"""统一抓取器。

所有适配器共用，负责：
- robots.txt 强制（命中 Disallow 直接拒绝，不发出请求；结果以
  FetchResult.robots_blocked 标记，调用方不得把它当成采集故障）
- 每主机限速 + 抖动
- ETag / If-Modified-Since 条件请求（无变化时零下载）
- 超时、重试、指数退避
- 原始 HTML 快照落盘（页面结构回归 + 离线重放）

同时支持 GET 与 POST 表单：部分站点的枚举接口只接受 POST（空 body 会 411），
`post_form()` 与 `get()` 共用同一套 robots / 限速 / 重试语义，不允许绕开抓取器。
"""

from __future__ import annotations

import random
import threading
import time
import zlib
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional
from urllib.parse import urlparse

import httpx

from .config import Settings, get_settings
from .robots import RobotsPolicy, origin_of, parse_robots, robots_url_for

MAX_RESPONSE_BYTES = 64 * 1024 * 1024


class RobotsDisallowed(RuntimeError):
    """目标 URL 被 robots.txt 禁止。绝不重试。"""


class _ResponseTooLarge(ValueError):
    pass


@dataclass
class FetchResult:
    url: str
    status: int
    headers: dict[str, str] = field(default_factory=dict)
    content: bytes | None = None
    text: Optional[str] = None
    not_modified: bool = False
    error: Optional[str] = None
    # robots 拒绝：status=0 且 error 有值，但它不是采集故障，调用方必须区分
    robots_blocked: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None and 200 <= self.status < 300

    @property
    def etag(self) -> Optional[str]:
        return self.headers.get("etag")

    @property
    def last_modified(self) -> Optional[str]:
        return self.headers.get("last-modified")

    @property
    def content_type(self) -> Optional[str]:
        return self.headers.get("content-type")

    @property
    def content_length(self) -> int | None:
        value = next((v for k, v in self.headers.items() if k.lower() == "content-length"), None)
        if value is None:
            return None
        try:
            length = int(value)
        except (TypeError, ValueError):
            return None
        return length if length >= 0 else None


class _HostRateLimiter:
    """每主机最小请求间隔，带抖动，线程安全。"""

    def __init__(self, min_interval: float, jitter: float) -> None:
        self._min = min_interval
        self._jitter = jitter
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, host: str) -> None:
        with self._lock:
            now = time.monotonic()
            last = self._last.get(host, 0.0)
            target = last + self._min + random.uniform(0.0, self._jitter)
            delay = target - now
            if delay > 0:
                time.sleep(delay)
            self._last[host] = time.monotonic()


class Fetcher:
    """统一 HTTP 抓取器。"""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = httpx.Client(
            follow_redirects=True,
            timeout=self.settings.request_timeout_seconds,
            headers={
                "User-Agent": self.settings.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/pdf,*/*;q=0.8",
                "Accept-Language": "en-GB,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
            },
        )
        self._limiter = _HostRateLimiter(
            self.settings.min_host_interval_seconds,
            self.settings.host_interval_jitter_seconds,
        )
        self._robots: dict[str, RobotsPolicy] = {}
        self._robots_lock = threading.Lock()

    # -- robots ----------------------------------------------------------

    def _policy(self, url: str) -> RobotsPolicy:
        origin = origin_of(url)
        with self._robots_lock:
            if origin in self._robots:
                return self._robots[origin]

        robots_url = robots_url_for(url)
        policy: RobotsPolicy
        try:
            with self._stream_response("GET", robots_url, timeout=15.0) as resp:
                if resp.status_code == 200:
                    body = self._read_body(resp)
                    policy = parse_robots(urlparse(url).netloc, robots_url, body.decode("utf-8", errors="replace"))
                else:
                    policy = RobotsPolicy(
                        host=urlparse(url).netloc, robots_url=robots_url, fetched=False
                    )
        except _ResponseTooLarge:
            # An oversized policy cannot establish permission to fetch the resource.
            policy = parse_robots(urlparse(url).netloc, robots_url, "User-agent: *\nDisallow: /\n")
        except Exception:
            policy = RobotsPolicy(host=urlparse(url).netloc, robots_url=robots_url, fetched=False)

        with self._robots_lock:
            self._robots[origin] = policy
        return policy

    def assert_allowed(self, url: str) -> None:
        if not self.settings.respect_robots:
            return
        policy = self._policy(url)
        if not policy.can_fetch(self.settings.user_agent, url):
            raise RobotsDisallowed(
                f"robots.txt 禁止抓取 {url}（robots: {policy.robots_url}）"
            )

    # -- fetch -----------------------------------------------------------

    def get(
        self,
        url: str,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
        expect_binary: bool = False,
        follow_redirects: bool | None = None,
    ) -> FetchResult:
        """抓取单个 URL。条件请求命中时 not_modified=True 且不返回内容。

        `follow_redirects=False` 用于识别"重定向到登录页"这类门禁信号：
        部分站点对受限文件返回 302 而不是 403，跟随跳转只会拿到登录页 HTML，
        门禁就变成了"下载成功一个 HTML"。
        """
        headers: dict[str, str] = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        return self._request(
            "GET",
            url,
            headers=headers,
            expect_binary=expect_binary,
            follow_redirects=follow_redirects,
        )

    def post_form(
        self,
        url: str,
        data: dict[str, Any],
        *,
        expect_binary: bool = False,
        follow_redirects: bool | None = None,
    ) -> FetchResult:
        """POST application/x-www-form-urlencoded。

        有的站点的枚举接口只接受 POST，且对空 body 直接返回 411——
        必须带上表单体。robots / 限速 / 重试语义与 get() 完全一致，
        不允许绕开统一抓取器另开一条通道。
        """
        return self._request(
            "POST",
            url,
            data=data,
            expect_binary=expect_binary,
            follow_redirects=follow_redirects,
        )

    def get_text(self, url: str, **kwargs) -> FetchResult:
        return self.get(url, expect_binary=False, **kwargs)

    @contextmanager
    def _stream_response(
        self, method: str, url: str, *, follow_redirects: bool | None = None, check_redirect_policy: bool = False, **kwargs
    ) -> Iterator[httpx.Response]:
        request = self._client.build_request(method, url, **kwargs)
        follow = self._client.follow_redirects if follow_redirects is None else follow_redirects
        redirects = 0
        while True:
            response = self._client.send(request, stream=True, follow_redirects=False)
            try:
                if not follow or response.next_request is None:
                    yield response
                    return
                if redirects >= self._client.max_redirects:
                    raise httpx.TooManyRedirects("Exceeded maximum allowed redirects.", request=request)
                request = response.next_request
                if check_redirect_policy:
                    self.assert_allowed(str(request.url))
                    self._limiter.wait(urlparse(str(request.url)).netloc)
                redirects += 1
            finally:
                response.close()

    def _read_body(self, response: httpx.Response) -> bytes:
        buffered = response.is_stream_consumed
        encodings = [] if buffered else response.headers.get_list("content-encoding", split_commas=True)
        for encoding in encodings:
            if encoding.strip().lower() not in {"identity", "gzip", "deflate"}:
                raise httpx.DecodingError("Unsupported response content encoding")
        body = bytearray()
        chunks = (response.content,) if buffered else response.iter_raw()
        for chunk in chunks:
            if len(chunk) > MAX_RESPONSE_BYTES - len(body):
                raise _ResponseTooLarge
            body.extend(chunk)
        content = bytes(body)
        for encoding in reversed(encodings):
            encoding = encoding.strip().lower()
            if encoding == "identity":
                continue
            pending = content
            body = bytearray()
            while pending:
                window = zlib.MAX_WBITS | 16 if encoding == "gzip" else zlib.MAX_WBITS
                decoder = zlib.decompressobj(window)
                remaining = MAX_RESPONSE_BYTES - len(body)
                try:
                    decoded = decoder.decompress(pending, remaining + 1)
                except zlib.error as exc:
                    if encoding != "deflate":
                        raise httpx.DecodingError("Invalid compressed response body") from exc
                    decoder = zlib.decompressobj(-zlib.MAX_WBITS)
                    try:
                        decoded = decoder.decompress(pending, remaining + 1)
                    except zlib.error as raw_exc:
                        raise httpx.DecodingError("Invalid compressed response body") from raw_exc
                if len(decoded) > remaining:
                    raise _ResponseTooLarge
                if not decoder.eof:
                    raise httpx.DecodingError("Incomplete compressed response body")
                body.extend(decoded)
                pending = decoder.unused_data
                if pending and encoding != "gzip":
                    raise httpx.DecodingError("Unexpected data after compressed response body")
            content = bytes(body)
        return content

    def _request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        data: dict[str, Any] | None = None,
        expect_binary: bool = False,
        follow_redirects: bool | None = None,
    ) -> FetchResult:
        """get()/post_form() 的共同实现：robots -> 限速 -> 重试 -> 有界正文。"""
        try:
            self.assert_allowed(url)
        except RobotsDisallowed as exc:
            # 不抛异常：调用方拿到的仍是 FetchResult，靠 robots_blocked 区分
            # "遵守站点规则"与"采集失败"（status=0 两者长得一样）。
            return FetchResult(url=url, status=0, error=str(exc), robots_blocked=True)

        send: dict[str, Any] = {"headers": dict(headers or {})}
        if data is not None:
            send["data"] = data

        host = urlparse(url).netloc
        last_error: str | None = None

        for attempt in range(self.settings.max_retries):
            self._limiter.wait(host)
            try:
                with self._stream_response(method, url, follow_redirects=follow_redirects, check_redirect_policy=True, **send) as resp:
                    result = FetchResult(
                        url=str(resp.url), status=resp.status_code,
                        headers={k.lower(): v for k, v in resp.headers.items()},
                    )
                    if resp.status_code == 304:
                        result.not_modified = True
                        return result
                    if resp.status_code >= 500:
                        last_error = f"HTTP {resp.status_code}"
                    else:
                        if result.content_length is not None and result.content_length > MAX_RESPONSE_BYTES:
                            result.error = f"Response exceeds {MAX_RESPONSE_BYTES} byte limit"
                            return result
                        try:
                            result.content = self._read_body(resp)
                        except _ResponseTooLarge:
                            result.error = f"Response exceeds {MAX_RESPONSE_BYTES} byte limit"
                            return result
                        if not expect_binary:
                            decoded = httpx.Response(200, content=result.content)
                            decoded.encoding = resp.encoding
                            result.text = decoded.text
                        return result
            except RobotsDisallowed as exc:
                return FetchResult(url=url, status=0, error=str(exc), robots_blocked=True)
            except httpx.TooManyRedirects as exc:
                return FetchResult(url=url, status=0, error=f"TooManyRedirects: {exc}")
            except Exception as exc:  # 网络层错误 -> 退避重试
                last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(self.settings.retry_backoff_seconds * (2**attempt))

        return FetchResult(url=url, status=0, error=last_error or "unknown error")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "Fetcher":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def save_snapshot(directory: Path, name: str, text: str) -> Path:
    """保存原始 HTML 快照，用于页面结构回归与离线重放。"""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path
