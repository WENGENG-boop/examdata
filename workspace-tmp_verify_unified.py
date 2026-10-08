"""临时校验脚本（不属于仓库）。

unified.py 当前有一处语法错误（docstring 里未转义的双引号，line 327），
不能直接 import。这里把源码复制一份、只在临时副本里修掉那处引号，
再以 `examdata.api._tmp_unified` 的模块名加载（相对 import 仍解析到
examdata.api 包），从而在不改动对端文件的前提下实测真实行为。
"""
import importlib.util
import json
import os
import re
import sys

REPO = r"C:\Users\weo\Desktop\api\examdata"
SRC = os.path.join(REPO, "src", "examdata", "api", "unified.py")
TMP = r"C:\Users\weo\Desktop\api\tmp_unified_patched.py"


def patch_source(text: str) -> str:
    """把跨局检索 description 里未转义的 ASCII 双引号换成全角引号。"""
    fixed, n = re.subn(
        r'跨局检索时"某一局没有结果"和"这一局根本没有数据"是两件事',
        "跨局检索时「某一局没有结果」和「这一局根本没有数据」是两件事",
        text,
    )
    print(f"[patch] 替换处数 = {n}")
    return fixed


def load_router():
    text = open(SRC, encoding="utf-8").read()
    open(TMP, "w", encoding="utf-8").write(patch_source(text))
    spec = importlib.util.spec_from_file_location("examdata.api._tmp_unified", TMP)
    module = importlib.util.module_from_spec(spec)
    sys.modules["examdata.api._tmp_unified"] = module
    spec.loader.exec_module(module)
    return module.router


from fastapi import FastAPI
from fastapi.testclient import TestClient
from examdata.api.security import install_security

app = FastAPI()
app.include_router(load_router())
install_security(app)
client = TestClient(app)


def show(label, resp, limit=1500):
    body = resp.text
    if len(body) > limit:
        body = body[:limit] + f"...<截断 {len(resp.text) - limit} 字符>"
    print(f"\n=== {label} ===")
    print("status:", resp.status_code)
    print("headers:", {k: v for k, v in resp.headers.items() if k.lower() in (
        "content-type", "content-disposition", "content-length",
        "access-control-allow-origin", "www-authenticate")})
    print("body:", body)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "offline"
    if which == "offline":
        show("GET /api/v1/boards", client.get("/api/v1/boards"))
        show("GET /api/v1/search?limit=2", client.get("/api/v1/search", params={"limit": 2}))
        show("GET /api/v1/search?board=pearson", client.get("/api/v1/search", params={"board": "pearson", "limit": 2}))
        show("GET /api/v1/search?board=CIE&subject=0580", client.get("/api/v1/search", params={"board": "CIE", "subject": "0580", "limit": 2}))
        show("GET /api/v1/search?board=xxx (非法)", client.get("/api/v1/search", params={"board": "xxx"}))
        show("GET /api/v1/search?keyword=triangle&limit=1", client.get("/api/v1/search", params={"keyword": "triangle", "limit": 1}))
        show("GET /api/v1/question/1", client.get("/api/v1/question/1"), 3000)
        show("GET /api/v1/question/999999", client.get("/api/v1/question/999999"))
        show("GET /api/v1/paper?format=xml (非法)", client.get("/api/v1/paper", params={"subject": "0580", "year": 2024, "season": "Jun", "format": "xml"}))
        show("GET /api/v1/paper?board=xxx (非法)", client.get("/api/v1/paper", params={"subject": "0580", "year": 2024, "season": "Jun", "board": "xxx"}))
        show("GET /api/v1/paper?season=bad", client.get("/api/v1/paper", params={"subject": "0580", "year": 2024, "season": "bad"}))
        show("GET /api/v1/paper CIE question 不支持", client.get("/api/v1/paper", params={"subject": "0580", "year": 2024, "season": "Jun", "question": "2"}))
    elif which == "live":
        show("resolve CIE (download=false)", client.get("/api/v1/paper", params={"subject": "0580", "year": 2024, "season": "Jun", "paper": "11", "download": "false"}))
        show("resolve edexcel inferred (download=false)", client.get("/api/v1/paper", params={"subject": "accounting", "year": 2024, "season": "June", "download": "false"}))
