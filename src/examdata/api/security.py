"""安全与跨域层：可选 CORS 与可选 API Key。

两条中间件遵循同一条原则——**不配置就不生效**：
没有设置对应环境变量时，`install_security` 不给应用挂任何中间件，
行为与引入本模块之前完全一致。这样本地开发、pytest、CLI 都不需要额外配置，
也不会出现"忘了配某个变量，线上语义被悄悄改掉"的情况。

配置直接读 `os.environ`，不并入 `core/config.py`：这两项是**部署期开关**
（由运维在进程环境里决定），不是业务配置；而且必须在 `install_security`
被调用的那一刻读取——若在模块导入时求值，测试里临时设置环境变量就失效了。

环境变量：

- `EXAMDATA_CORS_ORIGINS`：逗号分隔的 origin 白名单，或单个 `*`。
  设置后挂 `CORSMiddleware`（允许全部方法与请求头），供浏览器端
  （前端页面 / Notebook / 在线调试台）跨域调用。不设置则不挂：
  浏览器跨域请求维持被同源策略拦截的现状，本地单机部署无需放宽。
  变量存在但只有空白/逗号时同样按未配置处理。
- `EXAMDATA_API_KEY`：设置后，除豁免路径外的所有请求都必须带
  `X-API-Key` 头且值一致，否则返回 401 `{"detail": ...}`。
  豁免 `/health`、`/docs`、`/redoc`、`/openapi.json`：
  探活与接口文档必须能匿名访问，否则监控和排障会先被自己的鉴权挡住。
  不设置则完全放行，适合只监听 127.0.0.1 的本地部署；
  变量存在但为空字符串时同样按未配置处理（空 key 挡不住任何请求，
  不能算有效配置）。

中间件顺序：Starlette 把新中间件插到栈顶，**后挂的在外层**。
因此这里先挂 API Key、后挂 CORS，让 CORS 始终位于最外层：
浏览器预检 `OPTIONS` 不带自定义头，必须在进鉴权之前就被 CORS 层应答；
401 响应也要经过 CORS 层补上 `access-control-allow-origin`，
否则前端拿到的只是一个读不出原因的失败。
"""

from __future__ import annotations

import os
import secrets

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

CORS_ORIGINS_ENV = "EXAMDATA_CORS_ORIGINS"
API_KEY_ENV = "EXAMDATA_API_KEY"
API_KEY_HEADER = "X-API-Key"
# 豁免鉴权的路径：探活探针与接口文档。写成集合便于 O(1) 判断。
EXEMPT_PATHS = frozenset({"/health", "/docs", "/redoc", "/openapi.json"})


class _ApiKeyMiddleware(BaseHTTPMiddleware):
    """固定 API Key 校验。

    key 在安装时以参数传入（而不是在 `dispatch` 里读环境变量），
    保证校验用的是 `install_security` 被调用那一刻的值。
    """

    def __init__(self, app: ASGIApp, api_key: str) -> None:
        super().__init__(app)
        # 统一编成 bytes 比较：header 值可能是任意 latin-1 字符，
        # 用 str 直接比较会在非 ASCII 输入上抛 TypeError。
        self._expected = api_key.encode("utf-8")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)
        provided = request.headers.get(API_KEY_HEADER, "").encode("utf-8")
        # 用 compare_digest 而不是 ==：逐字节等时比较，避免通过响应时间
        # 推断 key 前缀（时序侧信道）。
        if not secrets.compare_digest(provided, self._expected):
            return JSONResponse(
                status_code=401,
                content={"detail": f"缺少或无效的 {API_KEY_HEADER} 请求头"},
                headers={"WWW-Authenticate": API_KEY_HEADER},
            )
        return await call_next(request)


def _cors_origins() -> list[str]:
    """解析 `EXAMDATA_CORS_ORIGINS`：逗号分隔、去首尾空白、丢弃空项。

    单个 `*` 原样保留，交给 `CORSMiddleware` 走"允许任意 origin"的分支；
    全为空白时返回空列表，调用方据此判定"未配置"。
    """
    raw = os.environ.get(CORS_ORIGINS_ENV, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def install_security(app: FastAPI) -> None:
    """按当前环境变量挂上可选的安全 / 跨域中间件。

    两个变量都没设置时不改动 `app`，因此本函数可以无条件调用。
    必须在应用启动前调用（`add_middleware` 在启动后会抛 RuntimeError）。
    """
    # 顺序有讲究：先鉴权、后 CORS，让 CORS 落在最外层，详见模块 docstring。
    api_key = os.environ.get(API_KEY_ENV)
    if api_key:
        app.add_middleware(_ApiKeyMiddleware, api_key=api_key)

    origins = _cors_origins()
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )
