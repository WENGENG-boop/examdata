"""校验 CIE 定位索引 JSON。

优先使用 jsonschema；环境里没有该包时退回内置校验器，
它直接读取 cie-index-schema.json，覆盖其中用到的全部关键字。

在 schema 之外补三类语义检查：
- documents 必须恰好一个 qp、至多一个 ms；ms 区域只在有 ms 文档时才允许
- 题号唯一；parent 必须等于按 '(' 右切得到的父题号，且父题必须存在
- 区域 bbox 宽高为正、page 不超页数、bbox 落在该页分析范围内（需要 PDF 原件）

作为库使用时调用 validate(path, qp=None, ms=None) -> (errors, warnings)。
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

import batchlib as B
import paperlib as P

SCHEMA_PATH = B.BATCH_ROOT / "cie-index-schema.json"
KEY_DIR_RE = re.compile(r"^(\d{4})-([A-Z][a-z]{2})-(\d{1,2})$")
SUBJECT_DIR_RE = re.compile(r"^\d{4}$")

try:
    import jsonschema
except ImportError:
    jsonschema = None


def _stdout_utf8() -> None:
    enc = (getattr(sys.stdout, "encoding", "") or "").replace("-", "").lower()
    if enc != "utf8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def load_schema(path: Path = SCHEMA_PATH) -> dict:
    return json.loads(Path(path).read_bytes().decode("utf-8"))


def _resolve(root: dict, ref: str) -> dict | None:
    if not ref.startswith("#/"):
        return None
    node = root
    for part in ref[2:].split("/"):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _is_type(value, name: str) -> bool:
    if name == "object":
        return isinstance(value, dict)
    if name == "array":
        return isinstance(value, list)
    if name == "string":
        return isinstance(value, str)
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "boolean":
        return isinstance(value, bool)
    if name == "null":
        return value is None
    return True


def _matches_pattern(value: str, pattern: str) -> bool:
    if pattern.startswith("^") and pattern.endswith("$"):
        return re.fullmatch(pattern, value) is not None
    return re.search(pattern, value) is not None


def _check(instance, schema, path: str, root: dict, errors: list[str], depth: int = 0) -> None:
    if not isinstance(schema, dict):
        return
    if depth > 40:
        errors.append(f"{path}: schema 嵌套过深，停止校验")
        return

    if "$ref" in schema:
        target = _resolve(root, schema["$ref"])
        if target is None:
            errors.append(f"{path}: 无法解析 $ref {schema['$ref']}")
            return
        _check(instance, target, path, root, errors, depth + 1)
        return

    if "anyOf" in schema:
        branches = []
        for branch in schema["anyOf"]:
            branch_errors: list[str] = []
            _check(instance, branch, path, root, branch_errors, depth + 1)
            if not branch_errors:
                branches = []
                break
            branches.append(branch_errors)
        else:
            errors.append(f"{path}: 不匹配 anyOf 的任何分支")
            errors.extend(min(branches, key=len))

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: 必须是 {schema['const']!r}，实际 {instance!r}")

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: 必须是 {schema['enum']} 之一，实际 {instance!r}")

    if "type" in schema and not _is_type(instance, schema["type"]):
        errors.append(f"{path}: 类型必须是 {schema['type']}，实际 {type(instance).__name__}")
        return

    if isinstance(instance, str):
        if "pattern" in schema and not _matches_pattern(instance, schema["pattern"]):
            errors.append(f"{path}: {instance!r} 不匹配 {schema['pattern']}")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{path}: 长度 {len(instance)} 超过 maxLength {schema['maxLength']}")
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: 长度 {len(instance)} 小于 minLength {schema['minLength']}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: {instance} 小于 minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: {instance} 大于 maximum {schema['maximum']}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: 只有 {len(instance)} 项，少于 minItems {schema['minItems']}")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: 有 {len(instance)} 项，超过 maxItems {schema['maxItems']}")
        for i, sub in enumerate(schema.get("prefixItems", [])):
            if i < len(instance):
                _check(instance[i], sub, f"{path}[{i}]", root, errors, depth + 1)
        if "items" in schema:
            for i, item in enumerate(instance):
                _check(item, schema["items"], f"{path}[{i}]", root, errors, depth + 1)

    if isinstance(instance, dict):
        props = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in instance:
                errors.append(f"{path}: 缺少必填字段 {name!r}")
        if schema.get("additionalProperties") is False:
            for name in instance:
                if name not in props:
                    errors.append(f"{path}: 出现 schema 未定义的字段 {name!r}")
        for name, sub in props.items():
            if name in instance:
                _check(instance[name], sub, f"{path}.{name}", root, errors, depth + 1)


def _schema_errors(data, schema: dict) -> tuple[list[str], str]:
    if jsonschema is not None:
        validator = jsonschema.Draft202012Validator(schema)
        out = []
        for err in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
            loc = "/".join(str(p) for p in err.absolute_path) or "$"
            out.append(f"{loc}: {err.message}")
        return out, "jsonschema"
    errors: list[str] = []
    _check(data, schema, "$", schema, errors)
    return errors, "内置校验器"


def derived_parent(question: str) -> str | None:
    if "(" not in question:
        return None
    return question.rsplit("(", 1)[0]


def _semantic(data: dict, errors: list[str], warnings: list[str]) -> None:
    docs = data.get("documents")
    if isinstance(docs, list):
        roles = [d.get("role") for d in docs if isinstance(d, dict)]
        for role in ("qp", "ms"):
            n = roles.count(role)
            if role == "qp" and n != 1:
                errors.append(f"documents: 必须恰好一个 qp 文档，实际 {n} 个")
            if role == "ms" and n > 1:
                errors.append(f"documents: 至多一个 ms 文档，实际 {n} 个")
        if "ms" not in roles:
            for q in data.get("questions") or []:
                if isinstance(q, dict) and q.get("ms"):
                    errors.append(f"questions: {q.get('question')!r} 有 ms 区域但没有 ms 文档")
                    break

    questions = data.get("questions")
    if not isinstance(questions, list):
        return
    seen: dict[str, int] = {}
    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            continue
        name = q.get("question")
        if not isinstance(name, str):
            continue
        if name in seen:
            errors.append(f"questions[{i}].question: 题号 {name!r} 与 questions[{seen[name]}] 重复")
        else:
            seen[name] = i

    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            continue
        name = q.get("question")
        if not isinstance(name, str):
            continue
        want = derived_parent(name)
        got = q.get("parent")
        if got != want:
            errors.append(f"questions[{i}].parent: {name!r} 的 parent 应为 {want!r}，实际 {got!r}")
        if want is not None and want not in seen:
            errors.append(f"questions[{i}].parent: {name!r} 的父题 {want!r} 不在 questions 中")
        if q.get("uncertain") is not False:
            warnings.append(f"{name}: uncertain 未显式为 false")
        if not q.get("notes"):
            warnings.append(f"{name}: notes 为空")

    children: dict[str, list[int]] = {}
    for i, q in enumerate(questions):
        if isinstance(q, dict) and isinstance(q.get("question"), str):
            children.setdefault(q["question"], []).append(i)
    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            continue
        name = q.get("question")
        marks = q.get("marks")
        if not isinstance(name, str) or not isinstance(marks, int) or isinstance(marks, bool):
            continue
        kids = [questions[j] for j in children.get(name, []) if j != i]
        kid_marks = [k.get("marks") for k in kids]
        if kids and all(isinstance(m, int) and not isinstance(m, bool) for m in kid_marks):
            total = sum(kid_marks)
            if total != marks:
                warnings.append(
                    f"{name}: marks={marks} 但直接子题合计 {total}（{len(kids)} 个子题）")


def _key_from_path(index_path: Path) -> str | None:
    parent = index_path.parent.name
    subject = index_path.parent.parent.name
    m = KEY_DIR_RE.match(parent)
    if not m or not SUBJECT_DIR_RE.match(subject):
        return None
    return f"{subject}/{m.group(1)}/{m.group(2)}/{m.group(3)}"


def _locate_pdf(role: str, sha: str | None, explicit, index_path: Path,
                key: str | None, warnings: list[str]) -> Path | None:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    else:
        if key:
            entry = P.load_paper(key) or {}
            doc = entry.get(f"{role}_document")
            filename = doc.get("filename") if isinstance(doc, dict) else None
            if not filename:
                names = entry.get(role) or []
                filename = names[0] if isinstance(names, list) and names else None
            if filename:
                candidates.append(P.paper_tmp(key) / filename)
        for sibling in sorted(index_path.parent.glob("*.pdf")):
            candidates.append(sibling)

    tried: list[str] = []
    for path in candidates:
        if not path.exists():
            tried.append(f"{path.name}(不存在)")
            continue
        if sha and B.sha256_file(path) != sha:
            tried.append(f"{path.name}(sha 不符)")
            continue
        return path
    detail = "、".join(tried) if tried else "没有可用路径"
    warnings.append(f"{role}: 找不到与索引 sha256 相符的 PDF，跳过几何检查（{detail}）")
    return None


def _page_bounds(path: Path) -> tuple[int, dict[int, tuple[float, float, float, float]]]:
    import pymupdf
    bounds: dict[int, tuple[float, float, float, float]] = {}
    with pymupdf.open(path) as pdf:
        count = pdf.page_count
        for i, page in enumerate(pdf):
            bounds[i + 1] = P.analysis_bounds(page)
    return count, bounds


def _geometry(data: dict, errors: list[str], warnings: list[str],
              qp, ms, index_path: Path) -> dict:
    docs = data.get("documents")
    if not isinstance(docs, list):
        return {}
    by_role = {d.get("role"): d for d in docs if isinstance(d, dict)}
    key = _key_from_path(index_path)
    pages: dict[str, dict[int, tuple[float, float, float, float]]] = {}
    counts: dict[str, int] = {}
    for role, explicit in (("qp", qp), ("ms", ms)):
        doc = by_role.get(role)
        if not isinstance(doc, dict):
            continue
        path = _locate_pdf(role, doc.get("sha256"), explicit, index_path, key, warnings)
        if path is None:
            continue
        try:
            counts[role], pages[role] = _page_bounds(path)
        except Exception as exc:
            warnings.append(f"{role}: 无法打开 {path.name}（{exc}），跳过几何检查")

    for i, q in enumerate(data.get("questions") or []):
        if not isinstance(q, dict):
            continue
        for role in ("qp", "ms"):
            regions = q.get(role)
            if not isinstance(regions, list):
                continue
            for j, region in enumerate(regions):
                if not isinstance(region, dict):
                    continue
                where = f"questions[{i}]({q.get('question')}).{role}[{j}]"
                bbox = region.get("bbox")
                if isinstance(bbox, list) and len(bbox) == 4 and all(
                        isinstance(v, (int, float)) and not isinstance(v, bool) for v in bbox):
                    if not bbox[2] > bbox[0]:
                        errors.append(f"{where}.bbox: 宽度必须为正，实际 x0={bbox[0]} x1={bbox[2]}")
                    if not bbox[3] > bbox[1]:
                        errors.append(f"{where}.bbox: 高度必须为正，实际 y0={bbox[1]} y1={bbox[3]}")
                if role not in counts:
                    continue
                page = region.get("page")
                if not isinstance(page, int) or isinstance(page, bool):
                    continue
                if page > counts[role]:
                    errors.append(f"{where}.page: 第 {page} 页超出 {role} 文档页数 {counts[role]}")
                    continue
                if not (isinstance(bbox, list) and len(bbox) == 4):
                    continue
                bounds = pages[role][page]
                x0, y0, x1, y1 = bbox
                if not (bounds[0] <= x0 and x1 <= bounds[2]
                        and bounds[1] <= y0 and y1 <= bounds[3]):
                    errors.append(
                        f"{where}.bbox: {bbox} 超出第 {page} 页分析范围 "
                        f"[{bounds[0]:.1f}, {bounds[1]:.1f}, {bounds[2]:.1f}, {bounds[3]:.1f}]")
    return counts


def validate(index_path, qp=None, ms=None, schema_path: Path = SCHEMA_PATH) -> dict:
    """返回报告 dict：errors 为空即视为通过。"""
    index_path = Path(index_path)
    report = {"path": str(index_path), "engine": "n/a", "errors": [], "warnings": [],
              "geometry": {}, "questions": 0, "identity": None, "parse_error": False}
    try:
        raw = index_path.read_bytes()
    except OSError as exc:
        report["errors"].append(f"无法读取 {index_path}: {exc}")
        report["parse_error"] = True
        return report
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        report["errors"].append(f"{index_path} 不是合法 JSON: {exc}")
        report["parse_error"] = True
        return report

    schema = load_schema(schema_path)
    errors, engine = _schema_errors(data, schema)
    report["engine"] = engine
    report["errors"] = errors
    if isinstance(data, dict):
        report["identity"] = data.get("identity")
        questions = data.get("questions")
        report["questions"] = len(questions) if isinstance(questions, list) else 0
    if isinstance(data, dict) and not errors:
        _semantic(data, errors, report["warnings"])
    if isinstance(data, dict):
        report["geometry"] = _geometry(data, errors, report["warnings"], qp, ms, index_path)
    return report


def _describe(data) -> str:
    if not isinstance(data, dict):
        return ""
    ident = data.get("identity") or {}
    docs = {d.get("role") for d in data.get("documents") or [] if isinstance(d, dict)}
    return (f"{ident.get('subject')}/{ident.get('year')}/{ident.get('season')}/"
            f"{ident.get('paper')}  题数={len(data.get('questions') or [])}  "
            f"文档={'+'.join(sorted(d for d in docs if d))}")


def main() -> int:
    _stdout_utf8()
    parser = argparse.ArgumentParser(description="校验 cie-index.json")
    parser.add_argument("index", help="cie-index.json 路径")
    parser.add_argument("--qp", help="QP PDF 路径（覆盖自动定位）")
    parser.add_argument("--ms", help="MS PDF 路径（覆盖自动定位）")
    parser.add_argument("--quiet", action="store_true", help="只打印结论行")
    args = parser.parse_args()

    path = Path(args.index)
    report = validate(path, args.qp, args.ms)
    try:
        data = json.loads(path.read_bytes().decode("utf-8"))
    except Exception:
        data = None

    status = "通过" if not report["errors"] else "失败"
    print(f"[{status}] {path}")
    print(f"  校验器: {report['engine']}")
    if data is not None:
        print(f"  索引: {_describe(data)}")
    geo = report["geometry"]
    if geo:
        print("  几何: " + "  ".join(f"{role} {n} 页" for role, n in sorted(geo.items())))
    else:
        print("  几何: 跳过（没有可用的 PDF 原件）")
    print(f"  错误: {len(report['errors'])}  警告: {len(report['warnings'])}")
    if not args.quiet:
        for item in report["errors"]:
            print(f"    ! {item}")
        for item in report["warnings"]:
            print(f"    ~ {item}")
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
