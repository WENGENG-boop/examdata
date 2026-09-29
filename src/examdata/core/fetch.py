"""统一抓取器。

所有适配器共用，负责：
- robots.txt 强制（命中 Disallow 直接拒绝，不发出请求）
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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from .config import Settings, get_settings
from .robots import RobotsPolicy, origin_of, parse_robots, robots_url_for


class RobotsDisallowed(RuntimeError):
    """目标 URL 被 robots.txt 禁止。绝不重试。"""


@dataclass
class FetchResult:
    url: str
    status: int
    headers: dict[str, str] = field(default_factory=dict)
    content: bytes | None = None
    text: Optional[str] = None
    not_modified: bool = False
    error: Optional[str] = None

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
            resp = self._client.get(robots_url, timeout=15.0)
            if resp.status_code == 200:
                policy = parse_robots(urlparse(url).netloc, robots_url, resp.text)
            else:
                policy = RobotsPolicy(
                    host=urlparse(url).netloc, robots_url=robots_url, fetched=False
                )
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
        """get()/post_form() 的共同实现：robots -> 限速 -> 重试 -> 结果归一化。"""
        try:
            self.assert_allowed(url)
        except RobotsDisallowed as exc:
            return FetchResult(url=url, status=0, error=str(exc))

        send: dict[str, Any] = {"headers": dict(headers or {})}
        if data is not None:
            send["data"] = data
        if follow_redirects is not None:
            send["follow_redirects"] = follow_redirects

        host = urlparse(url).netloc
        last_error: str | None = None

        for attempt in range(self.settings.max_retries):
            self._limiter.wait(host)
            try:
                resp = self._client.request(method, url, **send)
            except Exception as exc:  # 网络层错误 -> 退避重试
                last_error = f"{type(exc).__name__}: {exc}"
                time.sleep(self.settings.retry_backoff_seconds * (2**attempt))
                continue

            if resp.status_code == 304:
                return FetchResult(
                    url=str(resp.url),
                    status=304,
                    headers={k.lower(): v for k, v in resp.headers.items()},
                    not_modified=True,
                )

            if resp.status_code >= 500:
                last_error = f"HTTP {resp.status_code}"
                time.sleep(self.settings.retry_backoff_seconds * (2**attempt))
                continue

            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            if expect_binary:
                return FetchResult(
                    url=str(resp.url), status=resp.status_code, headers=hdrs, content=resp.content
                )
            return FetchResult(
                url=str(resp.url),
                status=resp.status_code,
                headers=hdrs,
                content=resp.content,
                text=resp.text,
            )

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
