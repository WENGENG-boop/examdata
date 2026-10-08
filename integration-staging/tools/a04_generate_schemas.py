#!/usr/bin/env python3
"""Generate the A04 machine-readable contract artefacts from the dataclasses.

Introspects the staged contract package and writes, under
``integration-staging/contracts/``:

* ``schema/<name>.schema.json`` - one JSON Schema (2020-12 subset) per model,
  derived from the dataclass fields and from ``REQUIRED_FIELDS`` so the schema
  and ``from_dict`` cannot drift;
* ``identity-keys.json``        - per-entity identity keys and ID type prefixes;
* ``quality-transitions.json``  - the evidence-permitted quality transition table
  plus the forbidden bases.

Every output embeds ``x-generated-by`` (sha256 of this file) so a reader can
prove which generator produced it and re-run ``--check`` to detect drift. No
timestamp is embedded: the artefacts must be byte-stable across runs.

Phase A tool (integration-staging/tools/). Stdlib only; the original project is
never imported and nothing outside the staging root is written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import types
import typing
from dataclasses import MISSING, fields, is_dataclass
from enum import Enum
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve()
STAGING = HERE.parents[1]
SRC = STAGING / "src"
sys.path.insert(0, str(SRC))

from examdata_integration.contracts import base, canonical, enums, models, quality  # noqa: E402

SCHEMA_DIR = STAGING / "contracts" / "schema"

# Classes that are contract models but not entities in ``MODELS``.
EXTRA_CLASSES = (
    "Option", "OptionsPayload", "TableCell", "TablePayload", "MatchingPayload",
    "LabelsPayload", "TextPayload", "UnknownPayload",
    "Lineage", "SourceRef", "Conflict", "ManualDecision", "Gap", "Quality",
)

PAYLOAD_CLASSES = (
    "OptionsPayload", "TablePayload", "MatchingPayload", "LabelsPayload",
    "TextPayload", "UnknownPayload",
)

PRIMITIVES: dict[object, dict] = {
    str: {"type": "string"},
    int: {"type": "integer"},
    float: {"type": "number"},
    bool: {"type": "boolean"},
    type(None): {"type": "null"},
}


def generator_sha256() -> str:
    return hashlib.sha256(HERE.read_bytes()).hexdigest()


def collect_classes() -> dict[str, type]:
    """Every ContractModel subclass reachable from the contract package."""
    out: dict[str, type] = {}
    for module in (models, quality, base):
        for _name, obj in vars(module).items():
            if isinstance(obj, type) and issubclass(obj, base.ContractModel) \
                    and obj is not base.ContractModel:
                out.setdefault(obj.__name__, obj)
    for name in EXTRA_CLASSES:
        obj = getattr(models, name, None) or getattr(base, name, None)
        if obj is None:
            raise SystemExit(f"contract class {name!r} not found")
        out.setdefault(obj.__name__, obj)
    return out


CLASSES = collect_classes()
_HINTS: dict[str, dict[str, typing.Any]] = {}


def hints_for(cls: type) -> dict[str, typing.Any]:
    if cls.__name__ not in _HINTS:
        _HINTS[cls.__name__] = typing.get_type_hints(cls)
    return _HINTS[cls.__name__]


def schema_for(hint: typing.Any) -> dict:
    """Map a Python type annotation onto a JSON Schema (supported subset)."""
    if hint is typing.Any or hint is object:
        return {}

    origin = typing.get_origin(hint)

    if origin in (typing.Union, types.UnionType):
        args = list(typing.get_args(hint))
        non_null = [a for a in args if a is not type(None)]
        nullable = len(non_null) != len(args)
        subs = [schema_for(a) for a in non_null]
        schema = dict(subs[0]) if len(subs) == 1 else {"anyOf": subs}
        if nullable:
            types_ = schema.get("type")
            if isinstance(types_, str):
                schema["type"] = [types_, "null"]
            elif isinstance(types_, list):
                schema["type"] = sorted({*types_, "null"})
            else:
                schema = {"anyOf": [{"type": "null"}, *subs]} if len(subs) > 1 \
                    else {"anyOf": [{"type": "null"}, schema]}
        return schema

    if origin in (list, tuple, set, frozenset):
        args = typing.get_args(hint)
        item = args[0] if args else typing.Any
        return {"type": "array", "items": schema_for(item)}

    if origin is dict:
        args = typing.get_args(hint)
        value = args[1] if len(args) == 2 else typing.Any
        schema: dict = {"type": "object"}
        value_schema = schema_for(value)
        if value_schema:
            schema["additionalProperties"] = value_schema
        return schema

    if isinstance(hint, type) and issubclass(hint, Enum):
        return {"enum": [m.value for m in hint]}

    if isinstance(hint, type) and issubclass(hint, base.ContractModel):
        if hint is base.ContractModel:
            # The payload union: any of the typed payload shapes (nullability is
            # added by the surrounding Optional handling).
            return {"anyOf": [{"$ref": f"#/$defs/{n}"} for n in PAYLOAD_CLASSES]}
        return {"$ref": f"#/$defs/{hint.__name__}"}

    if hint in PRIMITIVES:
        return dict(PRIMITIVES[hint])

    # Unknown annotation: emit no constraint rather than a wrong one.
    return {}


def model_def(cls: type, *, envelope: bool) -> dict:
    """JSON Schema for `cls`.

    ``envelope=True`` describes ``to_dict()`` output, which carries the
    ``schema`` discriminator; ``envelope=False`` describes the shape used inside
    ``$defs``, where nested models are plain dicts without the discriminator.
    """
    required = list(models.REQUIRED_FIELDS.get(cls.__name__, ()))
    properties: dict[str, dict] = {}
    if envelope:
        required = ["schema", *required]
        properties["schema"] = {"const": cls.SCHEMA, "type": "string"}

    hints = hints_for(cls)
    for f in fields(cls):
        prop = schema_for(hints.get(f.name, typing.Any))
        if f.default is not MISSING and f.default is not None and f.default_factory is MISSING \
                and not isinstance(f.default, Enum) and not is_dataclass(f.default) \
                and "default" not in prop:
            try:
                json.dumps(f.default)
            except (TypeError, ValueError):
                pass
            else:
                prop = {**prop, "default": f.default}
        properties[f.name] = prop
    return {
        "title": cls.SCHEMA,
        "type": "object",
        "required": required,
        "properties": properties,
        "additionalProperties": False,
    }


def all_defs() -> dict[str, dict]:
    return {name: model_def(cls, envelope=False) for name, cls in sorted(CLASSES.items())}


def write_json(path: Path, payload: dict) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def schema_filename(cls: type) -> str:
    parts = [p for p in cls.SCHEMA.split("/") if not p.isdigit()]
    return "-".join(parts) + ".schema.json"


def build_outputs(gen_sha: str) -> dict[Path, dict]:
    defs = all_defs()
    emitted = {c.__name__ for c in models.MODELS.values()} | set(EXTRA_CLASSES)
    outputs: dict[Path, dict] = {}

    for name, cls in sorted(CLASSES.items()):
        if name not in emitted:
            continue
        doc: dict = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"contracts/schema/{schema_filename(cls)}",
            "x-generated-by": f"a04_generate_schemas.py sha256:{gen_sha}",
            "$defs": defs,
        }
        doc.update(model_def(cls, envelope=True))
        outputs[SCHEMA_DIR / schema_filename(cls)] = doc

    outputs[STAGING / "contracts" / "identity-keys.json"] = {
        "schema": "identity-keys/1",
        "x-generated-by": f"a04_generate_schemas.py sha256:{gen_sha}",
        "kinds": {
            kind.value: {
                "prefix": enums.ID_TYPE_PREFIX[kind],
                "identity_keys": list(canonical.IDENTITY_KEYS[kind]),
            }
            for kind in enums.EntityKind
        },
        "normalisation": {
            "code_keys": sorted(canonical.CODE_KEYS),
            "hash_keys": sorted(canonical.HASH_KEYS),
            "digest_bytes": canonical.DIGEST_BYTES,
            "absent_encoding": "\\x00",
            "explicit_unknown_encoding": "\\x01",
        },
    }

    outputs[STAGING / "contracts" / "quality-transitions.json"] = {
        "schema": "quality-transitions/1",
        "x-generated-by": f"a04_generate_schemas.py sha256:{gen_sha}",
        "dimensions": {n: [m.value for m in c] for n, c in quality.DIMENSIONS.items()},
        "authoritative_evidence": sorted(e.value for e in quality.AUTHORITATIVE_EVIDENCE),
        "forbidden_basis": dict(quality.FORBIDDEN_BASIS),
        "transitions": quality.transition_table(),
    }
    return outputs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify the files on disk match what would be generated")
    args = ap.parse_args()

    gen_sha = generator_sha256()
    outputs = build_outputs(gen_sha)

    mismatches: list[str] = []
    digests: dict[str, str] = {}
    for path, payload in sorted(outputs.items()):
        rel = path.relative_to(STAGING).as_posix()
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if args.check:
            on_disk = path.read_text(encoding="utf-8") if path.is_file() else None
            if on_disk != text:
                mismatches.append(rel)
            else:
                digests[rel] = digest
                print(f"ok    {rel}  sha256={digest}")
        else:
            digests[rel] = write_json(path, payload)
            print(f"wrote {rel}  sha256={digests[rel]}")

    if args.check:
        for rel in mismatches:
            print(f"STALE {rel}")
        print(f"CHECK: {'PASS' if not mismatches else 'FAIL'} "
              f"({len(outputs) - len(mismatches)}/{len(outputs)})")
        return 0 if not mismatches else 1

    print(f"generated {len(outputs)} files; generator sha256={gen_sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
