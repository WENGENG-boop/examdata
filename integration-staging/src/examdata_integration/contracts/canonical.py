"""Canonicalisation of native identity and deterministic public IDs (plan 4.2).

Decision record: `docs/integration/execution/A04_IDENTITY_DECISION.md`.

Summary of the algorithm frozen here:

1. Each entity kind has a fixed, ordered tuple of identity keys
   (`IDENTITY_KEYS`). A missing key is an error; a key that is known to be
   unknown must be the explicit `UNKNOWN` sentinel, which encodes differently
   from "not recorded" (`None`).
2. Values are normalised by key class: code-like values are upper-cased and
   whitespace-collapsed, text-like values keep their case, hash-like values are
   lower-cased hex.
3. The canonical identity string is
   ``<kind>\x1f<key>=<value>\x1e<key>=<value>...`` with values encoded by
   :func:`encode_value` (nested mappings/lists use canonical JSON).
4. The public ID is ``<prefix>_<digest>`` where digest is the first 20 bytes
   (160 bits) of ``sha256(canonical_identity.encode("utf-8"))`` encoded as
   lower-case RFC4648 base32 without padding (32 URL-safe characters).

Nothing here depends on mutable content: question text, titles and answer values
are never part of a logical identity (plan 4.2 rules 3 and 6).
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any, Mapping

from .enums import EntityKind, ID_TYPE_PREFIX

DIGEST_BYTES = 20
_KEY_SEP = "\x1f"
_FIELD_SEP = "\x1e"
_ABSENT = "\x00"
_EXPLICIT_UNKNOWN = "\x01"
_WS = re.compile(r"\s+")


class UnknownType:
    """Sentinel for "explicitly unknown", distinct from ``None`` (not recorded)."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return "UNKNOWN"

    def __bool__(self) -> bool:
        return False


UNKNOWN = UnknownType()

CODE_KEYS = frozenset({
    "system", "exam_system", "provider_id", "source_id", "qualification",
    "qualification_level", "native_code", "native_subject_code", "subject",
    "subject_code", "paper", "paper_code", "component", "unit_code", "season",
    "session", "specification_code", "specification_version", "kind", "role",
    "document_role", "storage_mode", "media_type", "scope_kind",
    "denominator_kind", "scheme", "code", "zone", "coordinate_system", "source",
    "variant", "skill", "section_kind", "applicability", "candidate_facing",
    "access_mode", "availability", "capability",
})

HASH_KEYS = frozenset({"sha256", "document_sha256", "input_revision", "content_sha256"})

IDENTITY_KEYS: dict[EntityKind, tuple[str, ...]] = {
    EntityKind.EXAMINATION_SYSTEM: ("system",),
    EntityKind.COURSE: ("system", "qualification", "native_code", "specification_version"),
    EntityKind.SYLLABUS: ("system", "course_native_code", "version"),
    EntityKind.CONTAINER: ("system", "kind", "native_identity"),
    EntityKind.QUESTION: ("system", "container_native_identity", "native_id", "number_path",
                          "parent_native_id"),
    EntityKind.ANSWER: ("system", "question_native_id", "source", "native_answer_key"),
    EntityKind.REGION: ("system", "document_role", "document_sha256", "page", "bbox",
                        "coordinate_system"),
    EntityKind.ASSET: ("system", "media_type", "sha256", "storage_mode"),
    EntityKind.TAG: ("scheme", "version", "code"),
    EntityKind.MATERIAL: ("system", "kind", "native_id", "applicability"),
    EntityKind.TIMETABLE_EVENT: ("system", "qualification", "zone", "course_native_code",
                                 "component", "date", "session"),
    EntityKind.TIMETABLE_WINDOW: ("system", "qualification", "zone", "original_text", "source"),
    EntityKind.COVERAGE: ("scope_kind", "scope_native_identity", "denominator_kind"),
    EntityKind.JOB_STATUS: ("scope", "input_revision"),
}


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def normalize_code(value: str) -> str:
    """Code-like normalisation: NFC, whitespace-collapsed, upper-cased."""
    return _WS.sub(" ", _nfc(str(value)).strip()).upper()


def normalize_text(value: str) -> str:
    """Text-like normalisation: NFC, whitespace-collapsed, case preserved."""
    return _WS.sub(" ", _nfc(str(value)).strip())


def normalize_alias(value: str) -> str:
    """Alias normalisation used for lookup (plan 4.2 rule 4): casefolded text."""
    return normalize_text(value).casefold()


def normalize_hash(value: str) -> str:
    """Hash-like normalisation: lower-case hex, no separators."""
    return str(value).strip().lower()


def normalize_value(key: str, value: Any) -> Any:
    """Apply the normalisation policy for `key`."""
    if value is None or value is UNKNOWN:
        return value
    if key in HASH_KEYS:
        return normalize_hash(value)
    if isinstance(value, str):
        if key in CODE_KEYS:
            return normalize_code(value)
        return normalize_text(value)
    if isinstance(value, Mapping):
        return {k: normalize_value(k, v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize_value(key, v) for v in value]
    return value


def encode_value(value: Any) -> str:
    """Encode one normalised value into its canonical string form."""
    if value is None:
        return _ABSENT
    if value is UNKNOWN:
        return _EXPLICIT_UNKNOWN
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return json.dumps({k: value[k] for k in sorted(value)},
                          ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if isinstance(value, (list, tuple)):
        return json.dumps(list(value), ensure_ascii=False, separators=(",", ":"))
    raise TypeError(f"cannot encode {type(value).__name__} in a canonical identity")


def identity_keys(kind: EntityKind) -> tuple[str, ...]:
    try:
        return IDENTITY_KEYS[EntityKind.coerce(kind)]
    except KeyError as exc:  # pragma: no cover - guarded by coerce
        raise KeyError(f"no identity keys defined for {kind!r}") from exc


def canonical_identity_string(kind: EntityKind, fields: Mapping[str, Any]) -> str:
    """Return the canonical identity string for `kind` and its identity fields.

    Raises KeyError if an identity key is absent (never silently dropped) and
    TypeError if an unexpected extra key is supplied.
    """
    kind = EntityKind.coerce(kind)
    keys = identity_keys(kind)
    missing = [k for k in keys if k not in fields]
    extra = sorted(set(fields) - set(keys))
    if missing:
        raise KeyError(f"{kind.value}: missing identity key(s) {missing}")
    if extra:
        raise TypeError(f"{kind.value}: unexpected identity key(s) {extra}")
    parts = [kind.value]
    for key in keys:
        parts.append(f"{key}={encode_value(normalize_value(key, fields[key]))}")
    return _KEY_SEP + _FIELD_SEP.join(parts)


def digest_for(kind: EntityKind, fields: Mapping[str, Any]) -> str:
    """Return the base32 digest of the canonical identity of `kind`."""
    raw = hashlib.sha256(canonical_identity_string(kind, fields).encode("utf-8")).digest()
    import base64

    return base64.b32encode(raw[:DIGEST_BYTES]).decode("ascii").rstrip("=").lower()


def public_id(kind: EntityKind, fields: Mapping[str, Any]) -> str:
    """Return the deterministic, URL-safe public ID for a native identity."""
    kind = EntityKind.coerce(kind)
    return f"{ID_TYPE_PREFIX[kind]}_{digest_for(kind, fields)}"


def content_revision(payload: Any) -> str:
    """Content revision: sha256 of the canonical JSON of a content payload.

    Kept separate from the logical identity on purpose (plan 4.2 rule 6).
    """
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def is_url_safe_public_id(value: str) -> bool:
    """True when `value` is `<prefix>_<32 base32 chars>` with a known prefix."""
    if not isinstance(value, str) or "_" not in value:
        return False
    prefix, _, digest = value.partition("_")
    if prefix not in set(ID_TYPE_PREFIX.values()):
        return False
    return len(digest) == 32 and all(c in "abcdefghijklmnopqrstuvwxyz234567" for c in digest)
