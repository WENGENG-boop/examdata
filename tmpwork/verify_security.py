"""一次性验证脚本：证明 api/security.py 的两条中间件（跑完即弃，tmpwork/ 已 gitignore）。

用法（工作目录必须是仓库根）：
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tmpwork/verify_security.py

验证三件事：
1. 不设环境变量 -> /health 200，且不挂任何中间件（行为与接入前一致）；
2. 设 EXAMDATA_API_KEY -> 缺头 401、正确头 200、/health 等豁免路径仍 200；
3. 设 EXAMDATA_CORS_ORIGINS -> 响应带 access-control-allow-origin；
   并额外验证两个变量同时设置时 CORS 位于最外层（预检不被鉴权拦住）。
"""

from __future__ import annotations

import importlib
import inspect
import os
import sys

from fastapi.testclient import TestClient

import examdata.api.app  # noqa: F401  仅确保子模块已导入
from examdata.api.security import API_KEY_ENV, CORS_ORIGINS_ENV, install_security

# 注意：examdata/api/__init__.py 里 `from .app import app` 把包属性
# examdata.api.app 指向了 FastAPI 实例（遮蔽同名子模块），
# 所以这里必须从 sys.modules 取模块本体。
APP_MODULE = "examdata.api.app"

RESULTS: list[bool] = []


def check(label: str, ok: bool, evidence: str = "") -> None:
    RESULTS.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  <- {evidence}" if evidence else ""))


def fresh_app():
    """重新加载 app 模块拿全新的 app 对象（中间件挂上后无法卸载，只能换对象）。"""
    module = sys.modules[APP_MODULE]
    importlib.reload(module)
    app = module.app
    if "install_security" not in inspect.getsource(module):
        # 目前 app.py 还没接入安全层（由主代理负责）；若之后已接入，这里自动跳过，
        # 避免重复安装。
        install_security(app)
    return app


def middleware_names(app) -> list[str]:
    """自外向内列出用户中间件。Starlette 的 user_middleware[0] 在最外层。"""
    return [m.cls.__name__ for m in app.user_middleware]


print("== 场景 0：不设任何环境变量 ==")
os.environ.pop(API_KEY_ENV, None)
os.environ.pop(CORS_ORIGINS_ENV, None)
app = fresh_app()
print(f"  user_middleware = {middleware_names(app)}")
with TestClient(app) as client:
    r = client.get("/health")
    check("/health 200", r.status_code == 200, f"status={r.status_code} body={r.text[:60]}")
    r = client.get("/papers", params={"limit": 1})
    check("/papers 200 且无需任何请求头", r.status_code == 200, f"status={r.status_code}")
check(
    "未配置时不挂任何安全中间件",
    not any(n in middleware_names(app) for n in ("_ApiKeyMiddleware", "CORSMiddleware")),
)

print("\n== 场景 0b：变量存在但为空（空 key 不能算有效配置） ==")
os.environ[API_KEY_ENV] = ""
os.environ[CORS_ORIGINS_ENV] = "  ,  "
app = fresh_app()
print(f"  user_middleware = {middleware_names(app)}")
with TestClient(app) as client:
    r = client.get("/papers", params={"limit": 1})
    check("空 EXAMDATA_API_KEY 不启用鉴权", r.status_code == 200, f"status={r.status_code}")
check("空值时同样不挂中间件", middleware_names(app) == [])

print("\n== 场景 1：只设 EXAMDATA_API_KEY=s3cret-key ==")
os.environ[API_KEY_ENV] = "s3cret-key"
os.environ.pop(CORS_ORIGINS_ENV, None)
app = fresh_app()
print(f"  user_middleware = {middleware_names(app)}")
with TestClient(app) as client:
    r = client.get("/papers", params={"limit": 1})
    check("不带 X-API-Key -> 401", r.status_code == 401, f"status={r.status_code} body={r.text}")
    check(
        "401 响应体是 FastAPI 的 detail 形状",
        r.json().get("detail") and set(r.json()) == {"detail"},
        f"json={r.json()}",
    )
    r = client.get("/papers", params={"limit": 1}, headers={"X-API-Key": "s3cret-key"})
    check("带正确 X-API-Key -> 200", r.status_code == 200, f"status={r.status_code}")
    r = client.get("/papers", params={"limit": 1}, headers={"X-API-Key": "wrong"})
    check("带错误 X-API-Key -> 401", r.status_code == 401, f"status={r.status_code}")
    r = client.get("/papers", params={"limit": 1}, headers={"X-API-Key": "s3cret-key-extra"})
    check("前缀相同但长度不同 -> 401（compare_digest 语义）", r.status_code == 401)
    for path in ("/health", "/docs", "/redoc", "/openapi.json"):
        r = client.get(path)
        check(f"豁免路径 {path} 不带 key -> 200", r.status_code == 200, f"status={r.status_code}")
    r = client.get("/health", headers={"X-API-Key": "s3cret-key"})
    check("/health 带 key 也 200", r.status_code == 200)

print("\n== 场景 2：只设 EXAMDATA_CORS_ORIGINS=https://a.example, https://b.example ==")
os.environ.pop(API_KEY_ENV, None)
os.environ[CORS_ORIGINS_ENV] = "https://a.example, https://b.example"
app = fresh_app()
print(f"  user_middleware = {middleware_names(app)}")
with TestClient(app) as client:
    r = client.get("/health", headers={"Origin": "https://a.example"})
    check(
        "白名单内 origin 带 access-control-allow-origin",
        r.headers.get("access-control-allow-origin") == "https://a.example",
        f"acao={r.headers.get('access-control-allow-origin')!r}",
    )
    r = client.get("/health", headers={"Origin": "https://b.example"})
    check(
        "第二个白名单 origin 也放行",
        r.headers.get("access-control-allow-origin") == "https://b.example",
        f"acao={r.headers.get('access-control-allow-origin')!r}",
    )
    r = client.get("/health", headers={"Origin": "https://evil.example"})
    check(
        "白名单外 origin 不带该头",
        "access-control-allow-origin" not in r.headers,
        f"acao={r.headers.get('access-control-allow-origin')!r}",
    )
    r = client.options(
        "/papers",
        headers={
            "Origin": "https://a.example",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-api-key",
        },
    )
    check(
        "预检 OPTIONS 200，允许全部方法/头",
        r.status_code == 200
        and r.headers.get("access-control-allow-origin") == "https://a.example"
        and r.headers.get("access-control-allow-headers") == "x-api-key",
        f"status={r.status_code} allow-methods={r.headers.get('access-control-allow-methods')!r} "
        f"allow-headers={r.headers.get('access-control-allow-headers')!r}",
    )

print("\n== 场景 2b：EXAMDATA_CORS_ORIGINS=* ==")
os.environ[CORS_ORIGINS_ENV] = "*"
app = fresh_app()
with TestClient(app) as client:
    r = client.get("/health", headers={"Origin": "https://anything.example"})
    check(
        "`*` 模式放行任意 origin",
        r.headers.get("access-control-allow-origin") == "*",
        f"acao={r.headers.get('access-control-allow-origin')!r}",
    )

print("\n== 场景 3：同时设 API Key 与 CORS（验证中间件顺序） ==")
os.environ[API_KEY_ENV] = "s3cret-key"
os.environ[CORS_ORIGINS_ENV] = "https://a.example"
app = fresh_app()
print(f"  user_middleware（自外向内） = {middleware_names(app)}")
check("CORS 位于最外层", middleware_names(app)[:1] == ["CORSMiddleware"])
with TestClient(app) as client:
    r = client.options(
        "/papers",
        headers={
            "Origin": "https://a.example",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-api-key",
        },
    )
    check(
        "预检 OPTIONS 不因缺 key 被拦（200）",
        r.status_code == 200,
        f"status={r.status_code} body={r.text[:60]}",
    )
    r = client.get("/papers", params={"limit": 1}, headers={"Origin": "https://a.example"})
    check(
        "缺 key 的跨域请求 401，且仍带 CORS 头（前端能读到错误）",
        r.status_code == 401 and r.headers.get("access-control-allow-origin") == "https://a.example",
        f"status={r.status_code} acao={r.headers.get('access-control-allow-origin')!r}",
    )
    r = client.get(
        "/papers", params={"limit": 1}, headers={"Origin": "https://a.example", "X-API-Key": "s3cret-key"}
    )
    check("带 key 的跨域请求 200", r.status_code == 200, f"status={r.status_code}")
    r = client.get("/health", headers={"Origin": "https://a.example"})
    check("豁免路径跨域 200", r.status_code == 200, f"status={r.status_code}")

print(f"\n合计 {len(RESULTS)} 项，通过 {sum(RESULTS)} 项，失败 {len(RESULTS) - sum(RESULTS)} 项")
sys.exit(0 if all(RESULTS) else 1)
