"""Spec 解析批处理入口。

用法：
    python -m examdata.specs.runner                    # 解析注册表内全部科目
    python -m examdata.specs.runner ial18-biology      # 只解析指定科目
    python -m examdata.specs.runner --list             # 列出已注册科目

输入：.data/specs/text/{key}.txt + .data/specs/manifest.json
输出：.data/specs/parsed/{key}.json（每个文件一份）与 {slug}.json（合并）
报告：逐科打印 单元/节点/叶子/问题 计数与校验结果；校验不过退出码非 0。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .models import ParsedSpec
from .subjects import IMPORT_ERRORS, PARSERS, all_slugs

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / ".data" / "specs"
MANIFEST = DATA / "manifest.json"
TEXT_DIR = DATA / "text"
OUT_DIR = DATA / "parsed"


def _load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _merge(slug: str, specs: list[ParsedSpec]) -> ParsedSpec:
    first = specs[0]
    merged = ParsedSpec(
        subject=slug,
        title=first.title,
        parser="merge",
        spec_url=first.spec_url,
        spec_sha256=";".join(s.spec_sha256 for s in specs if s.spec_sha256),
    )
    for s in specs:
        merged.units.extend(s.units)
        merged.issues.extend(s.issues)
    return merged


def parse_slug(slug: str, manifest: dict, *, write: bool = True) -> tuple[bool, list[str]]:
    """解析一个科目；返回 (是否通过校验, 报告行)。"""
    if slug not in PARSERS:
        return False, [f"{slug}: no parser registered"]
    keys = sorted(k for k in manifest if k == slug or k.startswith(f"{slug}-"))
    if not keys:
        return False, [f"{slug}: no spec files in manifest"]

    lines: list[str] = []
    specs: list[ParsedSpec] = []
    ok = True
    for key in keys:
        meta = manifest[key]
        text = (TEXT_DIR / f"{key}.txt").read_text(encoding="utf-8")
        try:
            spec = PARSERS[slug](text, meta)
        except Exception as exc:  # noqa: BLE001 - 逐科隔离，批量时不让单科拖垮全批
            lines.append(f"{key}: PARSE FAIL {type(exc).__name__}: {exc}")
            ok = False
            continue
        problems = spec.validate()
        counts = spec.counts()
        lines.append(
            f"{key}: units={counts['units']} nodes={counts['nodes']} leaves={counts['leaves']} "
            f"issues={counts['issues']} validation={'OK' if not problems else 'FAIL'}"
        )
        for p in problems:
            lines.append(f"    [validate] {p}")
        for issue in spec.issues:
            lines.append(f"    [issue] {issue}")
        if problems:
            ok = False
        if write:
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            (OUT_DIR / f"{key}.json").write_text(
                json.dumps(spec.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8"
            )
        specs.append(spec)

    if specs:
        merged = _merge(slug, specs)
        problems = merged.validate()
        counts = merged.counts()
        lines.append(
            f"{slug}: TOTAL units={counts['units']} nodes={counts['nodes']} "
            f"leaves={counts['leaves']} issues={counts['issues']} "
            f"validation={'OK' if not problems else 'FAIL'}"
        )
        for p in problems:
            lines.append(f"    [validate] {p}")
        if problems:
            ok = False
        if write:
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            (OUT_DIR / f"{slug}.json").write_text(
                json.dumps(merged.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8"
            )
    return ok, lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m examdata.specs.runner", description=__doc__)
    parser.add_argument("slugs", nargs="*", help="科目 slug（缺省=注册表全部）")
    parser.add_argument("--list", action="store_true", help="列出已注册科目")
    parser.add_argument("--no-write", action="store_true", help="只解析校验，不写 JSON")
    args = parser.parse_args(argv)

    if args.list:
        for slug in all_slugs():
            print(slug)
        return 0

    slugs = args.slugs or all_slugs()
    manifest = _load_manifest()
    if IMPORT_ERRORS:
        for name, err in sorted(IMPORT_ERRORS.items()):
            print(f"[warn] parser module {name} failed to import: {err}")
    failures = 0
    for slug in slugs:
        ok, lines = parse_slug(slug, manifest, write=not args.no_write)
        for line in lines:
            print(line)
        if not ok:
            failures += 1
    if failures:
        print(f"[runner] {failures}/{len(slugs)} subject(s) failed")
        return 1
    print(f"[runner] {len(slugs)} subject(s) OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
