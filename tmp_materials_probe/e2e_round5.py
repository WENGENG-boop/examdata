"""第 5 轮 E2E 抽查：/api/v1/materials 对真实上游（进程内 TestClient，不 override get_fetcher）。

与 tests/test_api_materials.py 的差别：不替换 get_fetcher，每请求走真实
Fetcher（robots、限速、重试），检查修①后的 URL 经 API 面暴露正确，以及
静态/动态取回对真实上游的端到端行为。预期值来自调研快照
（tmp_materials_probe/evidence/*.json）。

覆盖：
1. GET /api/v1/materials —— count=8、6 个 CIE id、dynamic_endpoints
2. GET /materials/cie-additional-materials-list —— 修① URL 已进入 API 面
3. GET /materials/cie-mf19-.../content —— 311234B、sha 快照一致
4. GET /materials/cie-mc-answer-sheet/content —— 129066B、form-2a.pdf
5. GET /materials/cie-periodic-table/content —— 422 指引（无版本）
   + /materials/cie-inserts/content —— 422 且 dynamic_endpoint 指向 in-paper
6. GET /materials/cie/in-paper?subject=0500&year=2024&season=Jun&role=in —— 6 份
7. 同 6 + paper=11&download=1 —— 114871B、sha、role/paper 响应头（5xx 重试一次）
"""

from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from examdata.materials import router as materials_router

LOG_PATH = Path(__file__).resolve().parent / "e2e_out" / "e2e_round5_2026-10-05.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
_log = LOG_PATH.open("w", encoding="utf-8")

RESULTS: list[tuple[str, bool, str]] = []


def emit(line: str) -> None:
    print(line, flush=True)
    _log.write(line + "\n")
    _log.flush()


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    emit(f"[{'PASS' if ok else 'FAIL'}] {name} :: {detail}")


def main() -> int:
    started = time.monotonic()
    emit(f"=== e2e_round5 start {time.strftime('%Y-%m-%d %H:%M:%S')} ===")

    app = FastAPI()
    app.include_router(materials_router)
    with TestClient(app) as client:
        # 1. 清单
        try:
            r = client.get("/api/v1/materials")
            payload = r.json()
            ids = sorted(item.get("id") for item in payload.get("items", []))
            cie_ids = sorted(i for i in ids if str(i).startswith("cie-"))
            expected_cie = sorted(
                [
                    "cie-mf19-formulae-and-statistical-tables",
                    "cie-periodic-table",
                    "cie-inserts",
                    "cie-confidential-instructions",
                    "cie-additional-materials-list",
                    "cie-mc-answer-sheet",
                ]
            )
            check(
                "1.1 GET /materials 200 且 count=8",
                r.status_code == 200 and payload.get("count") == 8,
                f"status={r.status_code} count={payload.get('count')}",
            )
            check("1.2 六个 CIE id 齐全", cie_ids == expected_cie, f"cie_ids={cie_ids}")
            dep = payload.get("dynamic_endpoints", {}).get("cie_in_paper")
            check(
                "1.3 dynamic_endpoints.cie_in_paper",
                dep == "/api/v1/materials/cie/in-paper",
                f"value={dep!r}",
            )
        except Exception as exc:  # noqa: BLE001
            check("1.x GET /materials", False, f"exception: {exc!r}")

        # 2. 修① URL 经 API 面暴露
        try:
            r = client.get("/api/v1/materials/cie-additional-materials-list")
            item = r.json()
            url = (item.get("versions") or [{}])[0].get("url")
            expected_url = (
                "https://www.cambridgeinternational.org/Images/"
                "651593-additional-exams-material-list-international-.pdf"
            )
            check("2.1 versions[0].url 为修正后地址", url == expected_url, f"url={url}")
            check(
                "2.2 响应体无旧错误形式",
                "651593-november-2026" not in r.text,
                f"status={r.status_code}",
            )
        except Exception as exc:  # noqa: BLE001
            check("2.x additional-materials-list", False, f"exception: {exc!r}")

        # 3. MF19 静态取回（真实下载）
        try:
            r = client.get(
                "/api/v1/materials/cie-mf19-formulae-and-statistical-tables/content"
            )
            body = r.content
            check(
                "3.1 mf19 200 且 311234B",
                r.status_code == 200 and len(body) == 311234,
                f"status={r.status_code} bytes={len(body)}",
            )
            sha = r.headers.get("x-material-sha256")
            match = r.headers.get("x-material-sha256-match")
            check(
                "3.2 mf19 sha 快照一致（match=true）",
                sha == "c075388ec7227fea086358f4332592a395a3c8d9c82b75890346f84cfc749d90"
                and match == "true",
                f"sha={sha} match={match}",
            )
            check(
                "3.3 mf19 content-disposition 文件名",
                "417318-list-of-formulae-and-statistical-tables.pdf"
                in (r.headers.get("content-disposition") or ""),
                f"cd={r.headers.get('content-disposition')!r}",
            )
        except Exception as exc:  # noqa: BLE001
            check("3.x mf19 content", False, f"exception: {exc!r}")

        # 4. MC 答题卡静态取回
        try:
            r = client.get("/api/v1/materials/cie-mc-answer-sheet/content")
            body = r.content
            check(
                "4.1 mc-answer-sheet 200 且 129066B",
                r.status_code == 200 and len(body) == 129066,
                f"status={r.status_code} bytes={len(body)}",
            )
            sha = r.headers.get("x-material-sha256")
            match = r.headers.get("x-material-sha256-match")
            check(
                "4.2 mc sha 快照一致（match=true）",
                sha == "0e0156de5eca0d144805628d3bd0f3e8e54d7643d52bb6a3d58bda59596bacdc"
                and match == "true",
                f"sha={sha} match={match}",
            )
            check(
                "4.3 mc content-disposition 含 form-2a.pdf",
                "form-2a.pdf" in (r.headers.get("content-disposition") or ""),
                f"cd={r.headers.get('content-disposition')!r}",
            )
        except Exception as exc:  # noqa: BLE001
            check("4.x mc-answer-sheet content", False, f"exception: {exc!r}")

        # 5. 无版本条目 422 指引（无网络）
        try:
            r = client.get("/api/v1/materials/cie-periodic-table/content")
            detail = r.json().get("detail", {}) if r.headers.get(
                "content-type", ""
            ).startswith("application/json") else {}
            check(
                "5.1 periodic-table 422 指引",
                r.status_code == 422
                and detail.get("access") == "in-paper"
                and detail.get("dynamic_endpoint") is None,
                f"status={r.status_code} detail={detail}",
            )
            r2 = client.get("/api/v1/materials/cie-inserts/content")
            detail2 = r2.json().get("detail", {})
            check(
                "5.2 inserts 422 且 dynamic_endpoint 指向 in-paper",
                r2.status_code == 422
                and detail2.get("dynamic_endpoint")
                == "/api/v1/materials/cie/in-paper",
                f"status={r2.status_code} detail={detail2}",
            )
        except Exception as exc:  # noqa: BLE001
            check("5.x 422 指引", False, f"exception: {exc!r}")

        # 6. CIE 镜像动态清单（真实 POST）
        try:
            params = {
                "subject": "0500",
                "year": 2024,
                "season": "Jun",
                "role": "in",
            }
            r = client.get("/api/v1/materials/cie/in-paper", params=params)
            payload = r.json()
            names = sorted(d.get("name") for d in payload.get("documents", []))
            expected_names = sorted(
                f"0500_s24_in_{p}.pdf" for p in ("11", "12", "13", "21", "22", "23")
            )
            check(
                "6.1 in-paper 列表 200 且 6 份",
                r.status_code == 200 and names == expected_names,
                f"status={r.status_code} names={names}",
            )
            check(
                "6.2 files 恒空 / counts.documents=6",
                payload.get("files") == []
                and (payload.get("counts") or {}).get("documents") == 6,
                f"counts={payload.get('counts')}",
            )
        except Exception as exc:  # noqa: BLE001
            check("6.x in-paper list", False, f"exception: {exc!r}")

        # 7. 动态下载（唯一命中，5xx 重试一次）
        try:
            params = {
                "subject": "0500",
                "year": 2024,
                "season": "Jun",
                "paper": "11",
                "role": "in",
                "download": "1",
            }
            r = client.get("/api/v1/materials/cie/in-paper", params=params)
            attempts = 1
            if r.status_code >= 500:
                emit(f"[INFO] download=1 首次 {r.status_code}，3s 后重试一次")
                time.sleep(3)
                r = client.get("/api/v1/materials/cie/in-paper", params=params)
                attempts = 2
            body = r.content
            sha = hashlib.sha256(body).hexdigest() if r.status_code == 200 else None
            check(
                "7.1 download=1 200 且 114871B",
                r.status_code == 200 and len(body) == 114871,
                f"status={r.status_code} bytes={len(body)} attempts={attempts}",
            )
            check(
                "7.2 sha 与镜像快照一致",
                sha
                == "7d49097cb30c27e4f6f640aef77d845ca192206e41b51d728b8aae739cb805c4",
                f"sha={sha}",
            )
            check(
                "7.3 role/paper 响应头与文件名",
                r.headers.get("x-material-role") == "in"
                and r.headers.get("x-material-paper") == "11"
                and "0500_s24_in_11.pdf"
                in (r.headers.get("content-disposition") or ""),
                f"role={r.headers.get('x-material-role')} "
                f"paper={r.headers.get('x-material-paper')} "
                f"cd={r.headers.get('content-disposition')!r}",
            )
        except Exception as exc:  # noqa: BLE001
            check("7.x download=1", False, f"exception: {exc!r}")

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = len(RESULTS) - passed
    elapsed = time.monotonic() - started
    emit(f"=== e2e_round5 done: {passed} PASS / {failed} FAIL, {elapsed:.1f}s ===")
    _log.close()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
