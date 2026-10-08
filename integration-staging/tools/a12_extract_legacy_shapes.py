"""A12 static extraction of legacy handler shapes (plan 5.5, packet A12).

Read-only companion to `a01_inventory_routes.py`. It never imports the original
application or any application module: every input is parsed with `ast` from
text, so no database session, settings module or Filesystem side effect can run.

For each route found in the four integration-target API files it records:

* the decorator (method, path, `response_class`/`response_model` if literal),
* the handler signature and every parameter default (e.g. ``Query(50)``),
* every top-level return shape (dict keys, call name, name/constant),
* every explicitly raised `HTTPException` (status + detail expression).

`materials/router.py` and `timetable/router.py` are deliberately *not* parsed:
those routes are active-owner (Kimi) and stay `deferred_active_owner` in the
A12 worksheet; only the A01 inventory row is kept.

The output lands under `docs/integration/execution/evidence/A12/`; the source
hashes are part of the JSON so downstream tools can pin the extraction.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

FILES = {
    "examdata/src/examdata/api/app.py": "",
    "examdata/src/examdata/api/unified.py": "/api/v1",
    "examdata/src/examdata/api/ielts.py": "/api/v1/ielts",
    "examdata/src/examdata/api/toefl.py": "/api/v1/toefl",
}

ROUTE_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}

OUT = ROOT / "docs/integration/execution/evidence/A12/legacy_shape_extract.json"


def _expr(node: ast.AST | None, limit: int = 160) -> str:
    if node is None:
        return ""
    try:
        text = ast.unparse(node)
    except Exception:  # pragma: no cover - unparse is best-effort
        text = type(node).__name__
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _return_shape(value: ast.AST | None) -> dict:
    if value is None:
        return {"kind": "none"}
    if isinstance(value, ast.Dict):
        keys = [k.value for k in value.keys if isinstance(k, ast.Constant)]
        return {"kind": "dict", "keys": keys, "expr": _expr(value)}
    if isinstance(value, ast.Call):
        return {"kind": "call", "call": _expr(value.func, 80), "expr": _expr(value)}
    if isinstance(value, (ast.Name, ast.Attribute)):
        return {"kind": "name", "name": _expr(value, 80)}
    return {"kind": type(value).__name__.lower(), "expr": _expr(value)}


def _iter_body(node: ast.FunctionDef | ast.AsyncFunctionDef):
    """Yield nodes of the function's own body, never nested function bodies."""
    stack = list(node.body)
    while stack:
        current = stack.pop()
        yield current
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        for child in ast.iter_child_nodes(current):
            stack.append(child)


def _params(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[dict]:
    args = node.args
    params: list[dict] = []
    positional = list(args.posonlyargs) + list(args.args)
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    for arg, default in zip(positional, defaults):
        row = {"name": arg.arg}
        if default is not None:
            row["default"] = _expr(default, 200)
        if arg.annotation is not None:
            row["annotation"] = _expr(arg.annotation, 80)
        params.append(row)
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        row = {"name": arg.arg, "keyword_only": True}
        if default is not None:
            row["default"] = _expr(default, 200)
        if arg.annotation is not None:
            row["annotation"] = _expr(arg.annotation, 80)
        params.append(row)
    return params


def _decorator_info(decorator: ast.Call) -> dict:
    info: dict = {}
    for kw in decorator.keywords:
        if kw.arg in {"response_class", "response_model", "status_code"}:
            info[kw.arg] = _expr(kw.value, 120)
    return info


def _raises(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[dict]:
    found: list[dict] = []
    for child in _iter_body(node):
        if not isinstance(child, ast.Raise) or child.exc is None:
            continue
        exc = child.exc
        if isinstance(exc, ast.Call) and _expr(exc.func, 60) in {
            "HTTPException", "fastapi.HTTPException",
        }:
            status = None
            detail = None
            for kw in exc.keywords:
                if kw.arg == "status_code" and isinstance(kw.value, ast.Constant):
                    status = kw.value.value
                if kw.arg == "detail":
                    detail = _expr(kw.value, 140)
            found.append({"exception": "HTTPException", "status": status,
                          "detail": detail})
        else:
            found.append({"exception": _expr(exc, 80), "status": None,
                          "detail": None})
    return found


def extract() -> dict:
    routes: list[dict] = []
    hashes: dict[str, str] = {}
    for relative, prefix in FILES.items():
        path = ROOT / relative
        hashes[relative] = _sha256(path)
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                if not isinstance(decorator.func, ast.Attribute):
                    continue
                if decorator.func.attr not in ROUTE_METHODS:
                    continue
                if not decorator.args or not isinstance(decorator.args[0], ast.Constant):
                    continue
                if not isinstance(decorator.args[0].value, str):
                    continue
                route_path = prefix + decorator.args[0].value
                returns = []
                for child in _iter_body(node):
                    if isinstance(child, ast.Return):
                        returns.append(_return_shape(child.value))
                routes.append({
                    "method": decorator.func.attr.upper(),
                    "path": route_path,
                    "file": relative,
                    "line": node.lineno,
                    "handler": node.name,
                    "decorator": _decorator_info(decorator),
                    "params": _params(node),
                    "returns": returns,
                    "raises": _raises(node),
                })
    routes.sort(key=lambda r: (r["file"], r["line"]))
    return {
        "schema": "examdata.integration.legacy_shape_extract/1",
        "method": "static_ast_no_import",
        "files": list(FILES),
        "source_hashes": hashes,
        "route_count": len(routes),
        "routes": routes,
    }


def main() -> None:
    result = extract()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT).as_posix()}")
    print(f"routes={result['route_count']}")
    for row in (r for rel in FILES for r in result["routes"] if r["file"] == rel):
        calls = ",".join(sorted({s["call"] for s in row["returns"] if s["kind"] == "call"}))
        keys = ",".join(sorted({k for s in row["returns"] if s["kind"] == "dict" for k in s["keys"]}))
        statuses = ",".join(str(s["status"]) for s in row["raises"])
        print(f"{row['method']:4} {row['path']:50} {row['handler']:28} "
              f"calls=[{calls}] keys=[{keys}] raises=[{statuses}]")


if __name__ == "__main__":
    main()
