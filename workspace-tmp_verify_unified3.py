"""临时校验脚本 3（不属于仓库）：错误码与边界。"""
import sys

from fastapi.testclient import TestClient

from examdata.api.app import app

client = TestClient(app)


def show(label, resp, limit=400):
    body = resp.text
    if len(body) > limit:
        body = body[:limit] + "...<截断>"
    print(f"\n=== {label} ===\nstatus: {resp.status_code}\nbody: {body}")


CASES = [
    ("paper 缺 subject", "/api/v1/paper", {"year": 2024, "season": "Jun"}),
    ("paper 缺 season", "/api/v1/paper", {"subject": "0580", "year": 2024}),
    ("paper year 越界", "/api/v1/paper", {"subject": "0580", "year": 1999, "season": "Jun"}),
    ("paper year 非整数", "/api/v1/paper", {"subject": "0580", "year": "abc", "season": "Jun"}),
    ("paper 显式 board=cambridge", "/api/v1/paper", {"board": "cambridge", "subject": "0580", "year": 2024, "season": "Jun", "paper": "11", "download": "false"}),
    ("paper 显式 board=ial", "/api/v1/paper", {"board": "ial", "subject": "ial18-economics", "year": 2024, "season": "June", "paper": "wec11-01", "download": "false"}),
    ("paper board=cie 但 subject 非四位", "/api/v1/paper", {"board": "cie", "subject": "accounting", "year": 2024, "season": "Jun"}),
    ("paper board=edexcel 但 season=Mar", "/api/v1/paper", {"board": "edexcel", "subject": "ial18-economics", "year": 2024, "season": "Mar"}),
    ("paper CIE paper 非法", "/api/v1/paper", {"subject": "0580", "year": 2024, "season": "Jun", "paper": "abc"}),
    ("paper CIE 上游没有的文件", "/api/v1/paper", {"subject": "0580", "year": 2024, "season": "Nov", "paper": "99", "download": "false"}),
    ("paper Edexcel question 缺 paper", "/api/v1/paper", {"subject": "ial18-economics", "year": 2024, "season": "June", "question": "1", "mode": "question"}),
    ("paper Edexcel paper 模式带 question", "/api/v1/paper", {"subject": "ial18-economics", "year": 2024, "season": "June", "paper": "wec11-01", "question": "1", "mode": "paper"}),
    ("paper Edexcel mode 非法", "/api/v1/paper", {"subject": "ial18-economics", "year": 2024, "season": "June", "mode": "qp"}),
    ("paper download=false 且 format=json", "/api/v1/paper", {"subject": "0580", "year": 2024, "season": "Jun", "paper": "11", "download": "false", "format": "json"}),
    ("search limit=0", "/api/v1/search", {"limit": 0}),
    ("search limit=501", "/api/v1/search", {"limit": 501}),
    ("search offset=-1", "/api/v1/search", {"offset": -1}),
    ("search year 过滤（无结果）", "/api/v1/search", {"year": 1999}),
    ("boards 带参数（应忽略）", "/api/v1/boards", {"foo": "bar"}),
    ("question 非整数 id", "/api/v1/question/abc", {}),
]


def run():
    for label, path, params in CASES:
        if path == "/api/v1/question/abc":
            show(label, client.get(path))
        else:
            show(label, client.get(path, params=params))


if __name__ == "__main__":
    run()
