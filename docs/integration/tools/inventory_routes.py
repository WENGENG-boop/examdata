"""Read route decorators with AST; never import app or initialize its database."""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FILES = {
    "examdata/src/examdata/api/app.py": "",
    "examdata/src/examdata/api/unified.py": "/api/v1",
    "examdata/src/examdata/api/ielts.py": "/api/v1/ielts",
    "examdata/src/examdata/api/toefl.py": "/api/v1/toefl",
    "examdata/src/examdata/materials/router.py": "/api/v1",
    "examdata/src/examdata/timetable/router.py": "/api/v1",
}
routes = []
for relative, prefix in FILES.items():
    tree = ast.parse((ROOT / relative).read_text(encoding="utf-8-sig"))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            method = decorator.func.attr
            if method not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            if not decorator.args or not isinstance(decorator.args[0], ast.Constant):
                continue
            route = prefix + decorator.args[0].value
            routes.append({"method": method.upper(), "path": route, "file": relative,
                           "line": node.lineno, "handler": node.name,
                           "parameters": [a.arg for a in node.args.args]})
routes.sort(key=lambda r: (r["path"], r["method"]))
keys = [(r["method"], r["path"]) for r in routes]
groups = {relative: sum(r["file"] == relative for r in routes) for relative in FILES}
result = {"as_of": "2026-10-05", "method": "static_ast_explicit_decorators",
          "limitations": ["Not live OpenAPI; excludes framework docs routes and dynamically generated routes.",
                          "Prefixes reflect inspected router registration; regenerate after registration changes."],
          "explicit_route_count": len(routes), "unique_path_count": len({r["path"] for r in routes}),
          "duplicate_method_paths": sorted({f"{m} {p}" for m, p in keys if keys.count((m, p)) > 1}),
          "groups": groups, "routes": routes}
output = ROOT / "docs/integration/ROUTE_INVENTORY_CURRENT.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in result.items() if k != "routes"}, ensure_ascii=False, indent=2))
