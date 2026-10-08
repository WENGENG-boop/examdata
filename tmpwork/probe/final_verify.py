"""交付前最终验证：真实网络 + 真实 HTTP 路由 + 真实 CLI。"""
import json
import sys
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fastapi.testclient import TestClient  # noqa: E402
from typer.testing import CliRunner  # noqa: E402

from examdata.api.app import app  # noqa: E402
from examdata.cli import app as cli_app  # noqa: E402

OUT = Path(__file__).resolve().parent / "final"
OUT.mkdir(exist_ok=True)
_n = 0


def fresh():
    global _n
    _n += 1
    d = OUT / f"r{_n:02d}"
    d.mkdir(exist_ok=True)
    return d


def _members(blob):
    """ZIP 里每个成员的内容。逐条比较，避免被归档时间戳干扰。"""
    with ZipFile(BytesIO(blob)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


print("=========== HTTP /paper-qa/resolve (真实网络) ===========")
with TestClient(app) as client:
    r = client.get(
        "/paper-qa/resolve",
        params={"board": "cie", "subject": "9709", "year": 2026, "season": "Mar", "paper": "12"},
    )
    print(r.status_code, json.dumps(r.json(), ensure_ascii=False)[:300])

    r = client.get(
        "/paper-qa/query",
        params={"board": "cie", "subject": "9709", "year": 2026, "season": "Mar",
                "paper": "12", "mode": "both"},
    )
    print("CIE both:", r.status_code, r.headers.get("content-type"), len(r.content))
    (fresh() / "cie_both.zip").write_bytes(r.content)

    r = client.get(
        "/paper-qa/query",
        params={"board": "edexcel", "subject": "Economics", "year": 2024, "season": "Jun",
                "paper": "wec11-01", "mode": "paper"},
    )
    print("EDX paper:", r.status_code, r.headers.get("content-type"), len(r.content))

    r = client.get(
        "/paper-qa/query",
        params={"board": "edexcel", "subject": "Economics", "year": 2024, "season": "Jun",
                "paper": "wec11-01", "question": "12(a)", "mode": "qa"},
    )
    print("EDX qa 12(a):", r.status_code, r.headers.get("content-type"), len(r.content))
    (fresh() / "edx_qa_12a.zip").write_bytes(r.content)

    # 短写题号 `12a` 必须与 `12(a)` 完全等价（原 paper_qa 承诺的输入形式）
    r_short = client.get(
        "/paper-qa/query",
        params={"board": "edexcel", "subject": "Economics", "year": 2024, "season": "Jun",
                "paper": "wec11-01", "question": "12a", "mode": "qa"},
    )
    print("EDX qa 12a (shorthand):", r_short.status_code, len(r_short.content),
          "same members:", _members(r_short.content) == _members(r.content))

    # 二进制出口的响应头：客户端要能直接落盘
    r_bin = client.get(
        "/paper-qa/query",
        params={"board": "cie", "subject": "9709", "year": 2026, "season": "Mar",
                "paper": "12", "mode": "both"},
    )
    print("CIE both headers:", r_bin.headers.get("content-disposition"),
          "len", r_bin.headers.get("content-length"), "actual", len(r_bin.content))

    # format=json：与 /resolve、CLI --json 同一套 schema，载荷 base64 内联
    r_json = client.get(
        "/paper-qa/query",
        params={"board": "edexcel", "subject": "Economics", "year": 2024, "season": "Jun",
                "paper": "wec11-01", "question": "12(a)", "mode": "qa", "format": "json"},
    )
    payload = r_json.json()
    print("EDX qa format=json:", r_json.status_code, r_json.headers.get("content-type"))
    print("  schema_version:", payload["schema_version"], "counts:", payload["counts"])
    for f in payload["files"]:
        print(f"  file {f['name']} role={f['role']} page={f['page']} bbox={f['bbox']} "
              f"b64={'yes' if f['data_base64'] else 'no'} sha256={f['sha256'][:12]}")

    # /resolve 与 format=json 的 schema 字段集必须一致（只是载荷内联与否）
    rb = None
    for attempt in range(4):
        r_res = client.get(
            "/paper-qa/resolve",
            params={"board": "edexcel", "subject": "Economics", "year": 2024, "season": "Jun",
                    "paper": "wec11-01", "question": "12(a)", "mode": "qa"},
        )
        if r_res.status_code == 200:
            rb = r_res.json()
            break
        print(f"  resolve attempt {attempt}: {r_res.status_code} "
              f"{str(r_res.json().get('detail'))[:70]} (retry)")
    if rb is None:
        print("resolve: FAILED after retries")
    else:
        print("resolve schema keys == query json keys:", set(rb) == set(payload))
        print("resolve files empty (no download):", rb["files"] == [], "counts:", rb["counts"])

    # 非法 format 值必须 422
    r_bad = client.get(
        "/paper-qa/query",
        params={"board": "cie", "subject": "9709", "year": 2026, "season": "Mar",
                "paper": "12", "mode": "both", "format": "xml"},
    )
    print("bad format:", r_bad.status_code, str(r_bad.json().get("detail"))[:60])

    # 错误路径
    for label, params in [
        ("CIE+question(422)", {"board": "cie", "subject": "9709", "year": 2026, "season": "Mar",
                               "paper": "12", "question": "1"}),
        ("bad season(422)", {"board": "cie", "subject": "9709", "year": 2026, "season": "Jan"}),
        ("missing paper(404)", {"board": "edexcel", "subject": "Economics", "year": 2024,
                                "season": "Jun", "paper": "wec99-01", "mode": "paper"}),
    ]:
        r = client.get("/paper-qa/query", params=params)
        print(f"{label}: {r.status_code} {str(r.json().get('detail'))[:90]}")

print("=========== CLI (真实网络) ===========")
runner = CliRunner()
res = runner.invoke(cli_app, [
    "paper-qa", "--board", "cie", "--subject", "9709", "--year", "2026",
    "--season", "Mar", "--paper", "12", "--mode", "both",
    "--out", str(fresh()), "--json",
])
print("exit:", res.exit_code)
print(res.output[:400] if res.exit_code == 0 else res.output[-600:])

res = runner.invoke(cli_app, [
    "paper-qa", "--board", "edexcel", "--subject", "ial18-economics", "--year", "2024",
    "--season", "Jun", "--paper", "wec11-01", "--question", "12(a)", "--mode", "qa",
    "--out", str(fresh()), "--json",
])
print("exit (spec-code subject):", res.exit_code)
print(res.output[:500] if res.exit_code == 0 else res.output[-600:])

print("=========== saved ===========")
for p in sorted(OUT.rglob("*")):
    if p.is_file():
        print(f"  {p.relative_to(OUT)}  {p.stat().st_size}")
