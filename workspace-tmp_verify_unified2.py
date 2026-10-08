"""临时校验脚本（不属于仓库）：实测统一网关与安全层。

两部分：
1. 用真实应用 `examdata.api.app:app` 走 TestClient，验证 /api/v1/* 行为与下载；
2. 另起一个临时 app 挂 install_security，验证 EXAMDATA_API_KEY / CORS 语义。
"""
import os
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

from examdata.api.app import app as real_app

client = TestClient(real_app)


def show(label, resp, limit=1200, raw=False):
    body = resp.text if not raw else f"<{len(resp.content)} 字节二进制>"
    if len(body) > limit:
        body = body[:limit] + f"...<截断 {len(resp.text) - limit} 字符>"
    print(f"\n=== {label} ===")
    print("status:", resp.status_code)
    print("headers:", {k: v for k, v in resp.headers.items() if k.lower() in (
        "content-type", "content-disposition", "content-length",
        "access-control-allow-origin", "www-authenticate")})
    print("body:", body)


def download_cases():
    show("CIE qp 单文件", client.get("/api/v1/paper", params={
        "subject": "0580", "year": 2024, "season": "Jun", "paper": "11", "mode": "qp"}),
        raw=True)
    r = client.get("/api/v1/paper", params={
        "subject": "0580", "year": 2024, "season": "Jun", "paper": "11", "mode": "both"})
    show("CIE both 多文件 ZIP", r, raw=True)
    r = client.get("/api/v1/paper", params={
        "subject": "0580", "year": 2024, "season": "Jun", "paper": "11",
        "mode": "qp", "format": "json"})
    show("CIE qp format=json（截断 base64）", r, 900)
    r = client.get("/api/v1/paper", params={
        "subject": "ial18-economics", "year": 2024, "season": "June",
        "paper": "wec11-01", "mode": "paper"})
    show("Edexcel paper 整卷", r, raw=True)
    r = client.get("/api/v1/paper", params={
        "subject": "ial18-economics", "year": 2024, "season": "June",
        "paper": "wec11-01", "question": "1", "mode": "question"})
    show("Edexcel question 裁剪 PNG", r, raw=True)
    r = client.get("/api/v1/paper", params={
        "subject": "ial18-economics", "year": 2024, "season": "June",
        "paper": "wec11-01", "question": "12(a)", "mode": "qa"})
    show("Edexcel qa 配对 ZIP", r, raw=True)
    r = client.get("/api/v1/paper", params={
        "subject": "ial18-economics", "year": 2024, "season": "June",
        "paper": "wec11-01", "question": "12(a)", "mode": "qa", "format": "json"})
    show("Edexcel qa format=json（截断）", r, 1500)


def security_cases():
    os.environ["EXAMDATA_API_KEY"] = "secret-key-123"
    os.environ["EXAMDATA_CORS_ORIGINS"] = "https://app.example.com, https://other.example.com"
    from examdata.api.security import install_security
    from examdata.api.unified import router

    app2 = FastAPI()
    app2.include_router(router)
    install_security(app2)
    c2 = TestClient(app2)
    show("带 key 调 /api/v1/boards", c2.get("/api/v1/boards", headers={"X-API-Key": "secret-key-123"}), 200)
    show("不带 key 调 /api/v1/boards", c2.get("/api/v1/boards"))
    show("错误 key 调 /api/v1/boards", c2.get("/api/v1/boards", headers={"X-API-Key": "wrong"}))
    show("不带 key 调 /health（豁免）", c2.get("/health"))
    show("CORS 预检 OPTIONS", c2.options("/api/v1/boards", headers={
        "Origin": "https://app.example.com",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "X-API-Key"}))
    show("CORS 未授权 origin", c2.get("/api/v1/boards", headers={
        "X-API-Key": "secret-key-123", "Origin": "https://evil.example.com"}), 200)
    del os.environ["EXAMDATA_API_KEY"]
    del os.environ["EXAMDATA_CORS_ORIGINS"]


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "downloads"
    if which == "downloads":
        download_cases()
    elif which == "security":
        security_cases()
