"""A04 - identity canonicalization and registry rules (plan 4.2).

Covers: determinism, URL-safe public IDs, native-locator round-trip, alias
resolution (case-insensitive), collision detection (recorded *and* raised),
alias-conflict detection (recorded, raised, and atomic), identity-key coverage
for every ``EntityKind``, and the required-field contract of the models.

No original code, network, or live database is touched: only the staged
``examdata_integration.contracts`` package is exercised.
"""
from __future__ import annotations

import pytest

import examdata_integration.contracts.models as _models
from examdata_integration.contracts.base import ContractError
from examdata_integration.contracts.canonical import (
    IDENTITY_KEYS,
    digest_for,
    is_url_safe_public_id,
    public_id,
    UNKNOWN,
)
from examdata_integration.contracts.enums import ID_TYPE_PREFIX, EntityKind
from examdata_integration.contracts.ids import (
    AliasConflictError,
    IdentityCollisionError,
    IdentityRegistry,
)
from examdata_integration.contracts.models import MODELS, REQUIRED_FIELDS


def _question_identity(native_id: str, *, container: str = "book-1") -> dict:
    return {
        "system": "ielts",
        "container_native_identity": {"native_id": container},
        "native_id": native_id,
        "number_path": [native_id],
        "parent_native_id": None,
    }


# --- determinism ------------------------------------------------------------
def test_public_id_is_deterministic():
    fields = _question_identity("Q41")
    first = public_id(EntityKind.QUESTION, fields)
    second = public_id(EntityKind.QUESTION, dict(fields))
    assert first == second
    assert first == f"q_{digest_for(EntityKind.QUESTION, fields)}"


def test_registry_is_deterministic_across_instances():
    a = IdentityRegistry()
    b = IdentityRegistry()
    ra = a.register(EntityKind.QUESTION, _question_identity("Q1"),
                    native_locator={"native_id": "Q1"})
    rb = b.register(EntityKind.QUESTION, _question_identity("Q1"),
                    native_locator={"native_id": "Q1"})
    assert ra.public_id == rb.public_id


def test_case_and_whitespace_do_not_change_a_code_identity():
    a = public_id(EntityKind.COURSE, {"system": "cie", "qualification": None,
                                      "native_code": "9999", "specification_version": None})
    b = public_id(EntityKind.COURSE, {"system": "CIE", "qualification": None,
                                      "native_code": " 9999 ", "specification_version": None})
    assert a == b


# --- URL safety -------------------------------------------------------------
def test_every_public_id_is_url_safe():
    for kind in EntityKind:
        keys = IDENTITY_KEYS[kind]
        fields = {k: (None if k != "system" else "x") for k in keys}
        # fill a couple of keys with distinct non-null values where required
        fields = {k: f"v-{k}" for k in keys}
        pid = public_id(kind, fields)
        assert is_url_safe_public_id(pid), pid
        assert pid.startswith(f"{ID_TYPE_PREFIX[kind]}_")


def test_url_safe_rejects_malformed_ids():
    assert not is_url_safe_public_id("q_tooshort")
    assert not is_url_safe_public_id("zz_" + "a" * 32)
    assert not is_url_safe_public_id("no-underscore")


# --- native locator round-trip ----------------------------------------------
def test_native_locator_round_trips_exactly():
    reg = IdentityRegistry()
    locator = {"provider": "ielts", "container_native_id": "book-1", "native_id": "Q7"}
    rec = reg.register(EntityKind.QUESTION, _question_identity("Q7"), native_locator=locator)
    assert reg.native_locator(rec.public_id) == locator
    # a copy is returned, mutating it must not corrupt the registry
    got = reg.native_locator(rec.public_id)
    got["native_id"] = "tampered"
    assert reg.native_locator(rec.public_id)["native_id"] == "Q7"


def test_registry_serialises_and_restores():
    reg = IdentityRegistry()
    rec = reg.register(EntityKind.CONTAINER,
                       {"system": "ielts", "kind": "book", "native_identity": {"native_id": "b1"}},
                       native_locator={"native_id": "b1"}, aliases=["SB1"])
    restored = IdentityRegistry.from_dict(reg.to_dict())
    assert restored.public_ids() == reg.public_ids()
    assert restored.resolve_alias("sb1") == rec.public_id


# --- aliases ----------------------------------------------------------------
def test_alias_resolution_is_case_insensitive():
    reg = IdentityRegistry()
    rec = reg.register(EntityKind.CONTAINER,
                       {"system": "ielts", "kind": "book", "native_identity": {"native_id": "b1"}},
                       native_locator={"native_id": "b1"},
                       aliases=["SB1", "synthetic/cambridge-1"])
    assert reg.resolve_alias("SB1") == rec.public_id
    assert reg.resolve_alias("sb1") == rec.public_id
    assert reg.resolve_alias("SYNTHETIC/Cambridge-1") == rec.public_id
    assert reg.resolve(rec.public_id) == rec.public_id


def test_alias_conflict_raises_records_and_is_atomic():
    reg = IdentityRegistry()
    reg.register(EntityKind.CONTAINER,
                 {"system": "ielts", "kind": "book", "native_identity": {"native_id": "b1"}},
                 native_locator={"native_id": "b1"}, aliases=["shared"])
    with pytest.raises(AliasConflictError):
        reg.register(EntityKind.CONTAINER,
                     {"system": "ielts", "kind": "book", "native_identity": {"native_id": "b2"}},
                     native_locator={"native_id": "b2"}, aliases=["SHARED"])
    assert len(reg.alias_events) == 1
    assert reg.alias_events[0]["kept"] != reg.alias_events[0]["rejected"]
    # the rejected identity must NOT be half-registered
    assert len(reg.records()) == 1
    rejected_pid = public_id(EntityKind.CONTAINER,
                             {"system": "ielts", "kind": "book", "native_identity": {"native_id": "b2"}})
    assert rejected_pid not in reg.public_ids()


# --- collisions -------------------------------------------------------------
def test_collision_raises_and_is_recorded(monkeypatch):
    import examdata_integration.contracts.ids as ids_mod

    forced = "q_" + "a" * 32
    monkeypatch.setattr(ids_mod, "derive_public_id", lambda kind, fields: forced)

    reg = IdentityRegistry()
    reg.register(EntityKind.QUESTION, _question_identity("Q1"), native_locator={"native_id": "Q1"})
    with pytest.raises(IdentityCollisionError):
        reg.register(EntityKind.QUESTION, _question_identity("Q2"), native_locator={"native_id": "Q2"})
    assert len(reg.collision_events) == 1
    event = reg.collision_events[0]
    assert event["public_id"] == forced
    assert event["kept_canonical_identity"] != event["rejected_canonical_identity"]
    # the original record is untouched
    assert len(reg.records()) == 1


def test_same_native_identity_registers_once():
    reg = IdentityRegistry()
    r1 = reg.register(EntityKind.QUESTION, _question_identity("Q1"), native_locator={"native_id": "Q1"})
    r2 = reg.register(EntityKind.QUESTION, _question_identity("Q1"), native_locator={"native_id": "Q1"})
    assert r1.public_id == r2.public_id
    assert len(reg.records()) == 1
    assert not reg.collision_events


# --- identity-key coverage --------------------------------------------------
def test_every_entity_kind_has_identity_keys_and_prefix():
    for kind in EntityKind:
        assert kind in IDENTITY_KEYS, kind
        assert IDENTITY_KEYS[kind], kind
        assert kind in ID_TYPE_PREFIX, kind


def test_missing_or_extra_identity_key_is_refused():
    from examdata_integration.contracts.canonical import canonical_identity_string

    with pytest.raises(KeyError):
        canonical_identity_string(EntityKind.QUESTION, {"system": "ielts"})
    extra = _question_identity("Q1")
    extra["unexpected"] = 1
    with pytest.raises(TypeError):
        canonical_identity_string(EntityKind.QUESTION, extra)


# --- required fields --------------------------------------------------------
def test_required_fields_agree_with_from_dict():
    valid = {
        "Option": {"key": "A"},
        "TableCell": {"row": 1, "column": 2},
        "Course": {"system": "cie"},
        "ExaminationSystemModel": {"system": "cie"},
        "TimetableEvent": {"system": "cie"},
    }
    for model_name, required in REQUIRED_FIELDS.items():
        model = getattr(_models, model_name)
        with pytest.raises(ContractError):
            model.from_dict({})
        for key in required:
            payload = {k: v for k, v in valid[model_name].items() if k != key}
            with pytest.raises(ContractError):
                model.from_dict(payload)


def test_absent_and_unknown_encode_differently():
    base = {"system": "cie", "qualification": None, "native_code": "9999",
            "specification_version": None}
    absent = public_id(EntityKind.COURSE, dict(base))
    unknown = public_id(EntityKind.COURSE, {**base, "qualification": UNKNOWN})
    assert absent != unknown
