#!/usr/bin/env python
"""Capture the canonical-identity corpus of one candidate tree (W5F repair).

Read-only: imports ``examdata.integration.contracts.canonical`` from the tree
given by ``--src`` and prints/writes one deterministic JSON document holding,
for every corpus case, the value fed to ``encode_value`` (repr) and the exact
string it produced.  Two captures of the same tree are byte-identical; a
capture of the repaired tree must be byte-identical to the pre-change capture
for every case (the F3 repair may only change nested-UNKNOWN behaviour, which
is not in this corpus because it raised before the repair).

Exit 0 on success, 1 on error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

CASES: list[tuple[str, str, Any]] = [
    # (name, "encode" | "identity" | "normalize", payload)
    ("encode:none", "encode", None),
    ("encode:bool-true", "encode", True),
    ("encode:bool-false", "encode", False),
    ("encode:int-zero", "encode", 0),
    ("encode:int-negative", "encode", -3),
    ("encode:int-big", "encode", 1234567890123456789),
    ("encode:float", "encode", 3.5),
    ("encode:float-integral", "encode", 2.0),
    ("encode:text", "encode", "Hello World"),
    ("encode:text-unicode", "encode", "Ünïcode é 中文"),
    ("encode:text-tab", "encode", "a\tb"),
    ("encode:text-with-ff", "encode", "a\x0cb"),
    ("encode:list-empty", "encode", []),
    ("encode:list-scalars", "encode", [None, True, 2, "s"]),
    ("encode:list-nested", "encode", [1, [2, [3, {"a": None}]], {"b": [True, False]}]),
    ("encode:tuple", "encode", (1, "two", None)),
    ("encode:tuple-nested", "encode", (1, (2, (3,)))),
    ("encode:map-empty", "encode", {}),
    ("encode:map-scalars", "encode", {"b": 1, "a": 2, "c": None}),
    ("encode:map-nested", "encode",
     {"z": {"y": {"x": [1, 2, {"w": "v"}]}}, "a": [None, {"b": True}]}),
    ("encode:map-none-nested", "encode", {"a": None, "b": [None], "c": {"d": None}}),
    ("encode:map-unicode-key", "encode", {"é": "x", "ascii": "y"}),
    ("encode:map-int-keys", "encode", {2: "b", 1: "a"}),
    ("encode:map-str-values-space", "encode", {"a": "  keep  this ", "b": "MiXeD case"}),
    ("normalize:code", "normalize", ("paper", "  0580 /  41 ")),
    ("normalize:text", "normalize", ("title", "  Keep   Case  É ")),
    ("normalize:hash", "normalize", ("sha256", " AB CD EF ")),
    ("normalize:map", "normalize", ("native_identity",
                                    {"paper": "  0580/41 ", "variant": " v1 ", "n": 3})),
    ("normalize:list", "normalize", ("bbox", ["  1 ", 2, None])),
    ("identity:container", "identity", "container"),
    ("identity:question", "identity", "question"),
    ("identity:region", "identity", "region"),
    ("identity:timetable_event", "identity", "timetable_event"),
    ("identity:coverage", "identity", "coverage"),
]


def _identity_fields(kind: str) -> dict[str, Any]:
    from examdata.integration.contracts.canonical import IDENTITY_KEYS
    from examdata.integration.contracts.enums import EntityKind

    keys = IDENTITY_KEYS[EntityKind.coerce(kind)]
    fields: dict[str, Any] = {}
    for key in keys:
        if key == "system":
            fields[key] = "cie"
        elif key == "kind":
            fields[key] = "question"
        elif key == "sha256" or key == "document_sha256":
            fields[key] = "A" * 64
        elif key == "bbox":
            fields[key] = [0, 0, 1, 1]
        elif key == "page":
            fields[key] = 1
        elif key == "native_identity" or key == "container_native_identity":
            fields[key] = {"paper": " 0580/41 ", "variant": "v1", "nested": {"b": None}}
        elif key == "scope_native_identity":
            fields[key] = {"scope": "  mvp ", "level": 2}
        elif key == "native_id":
            fields[key] = "id-1"
        elif key == "coordinate_system":
            fields[key] = "pdf points"
        elif key == "number_path":
            fields[key] = "1 (a) (ii)"
        else:
            fields[key] = f"VALUE-{key}"
    return fields


def collect(src: Path) -> dict[str, Any]:
    sys.path.insert(0, str(src))
    import examdata.integration.contracts.canonical as canonical  # noqa: PLC0415

    module_file = Path(canonical.__file__).resolve()
    cases: list[dict[str, Any]] = []
    for name, mode, payload in CASES:
        row: dict[str, Any] = {"name": name, "mode": mode}
        if mode == "encode":
            row["input_repr"] = repr(payload)
            row["output"] = canonical.encode_value(payload)
        elif mode == "normalize":
            key, value = payload
            row["input_repr"] = f"{key!r} {value!r}"
            row["output"] = repr(canonical.normalize_value(key, value))
        else:
            fields = _identity_fields(payload)
            row["input_repr"] = f"kind={payload!r}"
            row["output"] = canonical.canonical_identity_string(payload, fields)
            row["public_id"] = canonical.public_id(payload, fields)
            row["digest"] = canonical.digest_for(payload, fields)
        cases.append(row)
    return {
        "src": str(src),
        "module_file": str(module_file),
        "module_sha256": hashlib.sha256(module_file.read_bytes()).hexdigest(),
        "cases": cases,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", required=True)
    parser.add_argument("--out", default=None)
    parser.add_argument("--label", default="")
    args = parser.parse_args(argv)

    src = Path(args.src).resolve()
    if not (src / "examdata" / "integration" / "contracts" / "canonical.py").is_file():
        print(json.dumps({"status": "error", "reason": f"no canonical.py under {src}"}))
        return 1
    document = collect(src)
    document["label"] = args.label
    text = json.dumps({k: v for k, v in document.items() if k != "label"},
                      ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8", newline="\n")
    summary = {
        "status": "ok",
        "label": args.label,
        "src": document["src"],
        "module_file": document["module_file"],
        "module_sha256": document["module_sha256"],
        "cases": len(document["cases"]),
        "out_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "out": args.out,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
