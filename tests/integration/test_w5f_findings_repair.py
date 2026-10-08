"""W5F — the three W5 findings (F1, F2, F3), repaired and verified.

* F1 (medium, ``catalog/revision.py``) — ``RevisionPublisher.publish`` was
  check-then-act: the compare-and-swap *check* and the pointer ''os.replace''
  were two unsynchronised steps, so two builders that read the same current
  could both succeed and the slower one silently overwrote the faster one's
  revision.  The repair serialises the check and the swap with a
  cross-process ``O_CREAT|O_EXCL`` lock file and re-checks the compare-and-swap
  under that lock, so the loser is refused as stale.
* F2 (medium, same file) — ''_atomic_write'' let the transient Windows sharing
  failure (``PermissionError [WinError 5]``) escape from ''os.replace'', and a
  failed replacement left its ``.tmp-<uuid>`` file behind.  The repair retries a
  bounded number of times, reports a persistent failure as the typed
  :class:`AtomicWriteError`, deletes its own temporary file on any failure, and
  retries the pointer *read* (the same concurrent replace can break a reader's
  open) with :class:`PointerUnreadableError` as the typed verdict.
* F3 (low, ``contracts/canonical.py``) — a nested UNKNOWN sentinel reached
  ''json.dumps'' and surfaced as a raw ``TypeError: Object of type UnknownType is
  not JSON serializable``.  The repair encodes the sentinel as the documented
  nested marker ``"\\u0001"`` wherever it is nested and refuses genuinely
  unrepresentable values with the module's typed error; the canonical output for
  every already-supported value is byte-identical to the frozen parent.

Every test here fails on the frozen parent tree (RED: the defects reproduce, or
a candidate-only API is reached through a guard that fails loudly instead of
erroring at collection) and passes on the repaired closure candidate (GREEN).

The byte-stability table below is the corpus captured *before* the repair
(``evidence/w5f/corpus_before_parent_20261007T135327Z.json`` and
``corpus_before_candidate_20261007T135327Z.json``, both module sha256
``6ee49d8f...``): every entry must reproduce byte-for-byte after the repair.
"""
from __future__ import annotations

import inspect
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

import pytest

import b07r2_common as c  # import first: pins EXAMDATA_INTEGRATION_ROOT + asserts candidate origin

import examdata.integration.catalog.revision as revision_mod
import examdata.integration.contracts.canonical as canonical_mod
from examdata.integration.catalog.model import (
    CatalogEntry,
    CatalogSnapshot,
    compute_revision,
)
from examdata.integration.contracts.base import UNKNOWN
from examdata.integration.contracts.enums import EntityKind

c.assert_origin(revision_mod, "catalog.revision")
c.assert_origin(canonical_mod, "contracts.canonical")


# --------------------------------------------------------------------------- #
# Candidate-only API, reached through guards that fail the test loudly (never
# a collection error) so the frozen parent yields per-test failures.
# --------------------------------------------------------------------------- #
def _require_attr(module: Any, name: str, label: str) -> Any:
    value = getattr(module, name, None)
    if value is None:
        pytest.fail(f"{label} is not implemented")
    return value


def _require_param(func: Any, name: str, label: str) -> None:
    try:
        parameters = inspect.signature(func).parameters
    except (TypeError, ValueError):  # pragma: no cover - defensive only
        pytest.fail(f"{label} has no introspectable signature")
    if name not in parameters:
        pytest.fail(f"{label} does not accept a {name!r} keyword")


def _atomic_write_error() -> type:
    return _require_attr(revision_mod, "AtomicWriteError",
                         "catalog.revision.AtomicWriteError")


def _busy_error() -> type:
    return _require_attr(revision_mod, "PublisherBusyError",
                         "catalog.revision.PublisherBusyError")


def _unreadable_error() -> type:
    return _require_attr(revision_mod, "PointerUnreadableError",
                         "catalog.revision.PointerUnreadableError")


def _publisher(root: Path, **kwargs: Any) -> Any:
    cls = revision_mod.RevisionPublisher
    if "lock_timeout_seconds" in kwargs:
        _require_param(cls, "lock_timeout_seconds", "RevisionPublisher")
    return cls(root=root, **kwargs)


# --------------------------------------------------------------------------- #
# Synthetic catalog data (in-memory only) and small fault-injection helpers.
# --------------------------------------------------------------------------- #
def _entry(marker: str) -> CatalogEntry:
    kind = EntityKind.COURSE
    fields = {
        "system": "cie",
        "qualification": "synth-w5f",
        "native_code": marker,
        "specification_version": "2026",
    }
    return CatalogEntry(
        public_id=canonical_mod.public_id(kind, fields),
        kind=kind.value,
        system="cie",
        identity_fields=dict(fields),
        native_locator={"kind": "synthetic-w5f", "ref": marker},
        searchable={"stem": f"synthetic w5f fixture for {marker}"},
        source_revision="rev-w5f-synthetic",
        content_class="synthetic",
        evidence_labels=["synthetic_fixture"],
    )


def _snapshot(*markers: str) -> CatalogSnapshot:
    entries = [_entry(marker) for marker in markers]
    return CatalogSnapshot(
        dataset_revision=compute_revision(entries),
        created_at="2026-10-07T00:00:00+00:00",
        input_revisions={"w5f_test": "synthetic-injected"},
        counts={"course": len(entries)},
        entries=entries,
    )


def _seed_store(publisher: Any) -> str:
    pointer = publisher.publish(_snapshot("seed"))
    return pointer["dataset_revision"]


def _temp_files(directory: Path) -> list[str]:
    return sorted(p.name for p in Path(directory).glob("*.tmp-*"))


def _leftovers(root: Path) -> list[str]:
    """Temporary files and lock files left behind under ``root``."""
    return sorted(p.name for p in Path(root).rglob("*")
                  if p.is_file() and (".tmp-" in p.name or p.name.endswith(".lock")))


class _WriteGate:
    """Block the next ''_atomic_write'' of one exact path (runtime wrapper only)."""

    def __init__(self, blocked_path: Path) -> None:
        self.blocked_path = Path(blocked_path)
        self.entered = threading.Event()
        self.release = threading.Event()

    def install(self, monkeypatch: Any) -> None:
        real = revision_mod._atomic_write

        def wrapper(path: Path, text: str) -> None:
            if Path(path) == self.blocked_path:
                self.entered.set()
                if not self.release.wait(timeout=30):
                    raise AssertionError("w5f write gate was never released")
            real(path, text)

        monkeypatch.setattr(revision_mod, "_atomic_write", wrapper)


class _OsShim:
    """A module-like proxy around ``os`` whose ``replace`` is replaced."""

    def __init__(self, replace: Any) -> None:
        self._replace = replace

    def __getattr__(self, name: str) -> Any:
        if name == "replace":
            return self._replace
        return getattr(os, name)


# --------------------------------------------------------------------------- #
# F1 — the compare-and-swap check and the pointer swap are one transaction.
# --------------------------------------------------------------------------- #
def test_f1_a_stale_builder_cannot_overwrite_a_faster_publisher(tmp_path, monkeypatch):
    root = tmp_path / "catalog"
    publisher = _publisher(root)
    seed_revision = _seed_store(publisher)
    snapshot_fast, snapshot_slow = _snapshot("alpha"), _snapshot("beta")
    revision_fast = snapshot_fast.dataset_revision
    revision_slow = snapshot_slow.dataset_revision
    assert revision_fast != revision_slow != seed_revision

    # The slower builder is held at its revision-file write (outside the lock),
    # i.e. after it passed every check it can pass without the lock.
    gate = _WriteGate(publisher.revision_path(revision_slow))
    gate.install(monkeypatch)
    result: dict[str, Any] = {}

    def slow_builder() -> None:
        try:
            result["pointer"] = publisher.publish(snapshot_slow,
                                                  expected_current=seed_revision)
        except BaseException as exc:  # noqa: BLE001 - recorded, never raised here
            result["error"] = exc

    thread = threading.Thread(target=slow_builder, name="w5f-slow-builder")
    thread.start()
    try:
        assert gate.entered.wait(timeout=30), "the slow builder never reached its write"
        faster = publisher.publish(snapshot_fast, expected_current=seed_revision)
        assert faster["dataset_revision"] == revision_fast
    finally:
        gate.release.set()
        thread.join(timeout=60)
    assert not thread.is_alive(), "the slow builder did not finish"

    error = result.get("error")
    assert isinstance(error, revision_mod.StalePublisherError), (
        f"the stale builder must be refused as stale, got {result!r}")
    assert "refresh and rebuild" in str(error)
    final = publisher.current()
    assert final is not None and final["dataset_revision"] == revision_fast
    assert publisher.current_revision() == revision_fast
    assert _leftovers(root) == []


def test_f1_a_second_publisher_is_bounded_by_the_lock_timeout(tmp_path, monkeypatch):
    root = tmp_path / "catalog"
    holder = _publisher(root)
    seed_revision = _seed_store(holder)
    snapshot_holder, snapshot_waiter = _snapshot("holder"), _snapshot("waiter")
    revision_holder = snapshot_holder.dataset_revision

    busy_cls = _busy_error()
    waiter = _publisher(root, lock_timeout_seconds=0.3)

    # The holder is held inside its pointer write, i.e. while it owns the lock.
    gate = _WriteGate(holder.pointer_path)
    gate.install(monkeypatch)
    result: dict[str, Any] = {}

    def holding_builder() -> None:
        try:
            result["pointer"] = holder.publish(snapshot_holder,
                                               expected_current=seed_revision)
        except BaseException as exc:  # noqa: BLE001 - recorded, never raised here
            result["error"] = exc

    thread = threading.Thread(target=holding_builder, name="w5f-lock-holder")
    thread.start()
    try:
        assert gate.entered.wait(timeout=30), "the holder never reached its pointer write"
        started = time.monotonic()
        with pytest.raises(busy_cls) as excinfo:
            waiter.publish(snapshot_waiter, expected_current=seed_revision)
        elapsed = time.monotonic() - started
    finally:
        gate.release.set()
        thread.join(timeout=60)
    assert not thread.is_alive(), "the holder did not finish"

    assert "retry the publication" in str(excinfo.value)
    assert 0.2 <= elapsed < 5.0, f"the waiting publisher gave up after {elapsed:.3f}s"
    assert "error" not in result, result
    assert result["pointer"]["dataset_revision"] == revision_holder
    assert holder.current_revision() == revision_holder
    assert _leftovers(root) == []


def test_f1_a_stale_lock_file_is_reclaimed_and_never_left_behind(tmp_path):
    root = tmp_path / "catalog"
    publisher = _publisher(root)
    seed_revision = _seed_store(publisher)

    # A crashed holder's leftover: old enough to be treated as stale.
    lock_path = root / "current.json.lock"
    lock_path.write_text("0 0.000\n", encoding="ascii")
    old = time.time() - 600.0
    os.utime(lock_path, (old, old))

    pointer = publisher.publish(_snapshot("after-stale-lock"),
                                expected_current=seed_revision)
    assert pointer["dataset_revision"] != seed_revision
    assert publisher.current_revision() == pointer["dataset_revision"]
    assert not lock_path.exists(), "the reclaimed lock file was left behind"
    assert _leftovers(root) == []


# --------------------------------------------------------------------------- #
# F2 — bounded retries, typed verdicts, no orphaned temporary files.
# --------------------------------------------------------------------------- #
def test_f2_transient_replace_failures_are_retried(tmp_path, monkeypatch):
    target = tmp_path / "catalog" / "revisions" / "rev-transient.json"
    target.parent.mkdir(parents=True)
    calls = {"count": 0}
    real_replace = os.replace

    def flaky(src: Any, dst: Any) -> None:
        calls["count"] += 1
        if calls["count"] <= 2:
            raise PermissionError(13, "Access is denied")
        real_replace(src, dst)

    monkeypatch.setattr(revision_mod, "os", _OsShim(flaky))
    revision_mod._atomic_write(target, "payload\n")

    assert target.read_text(encoding="utf-8") == "payload\n"
    assert calls["count"] == 3
    assert _temp_files(target.parent) == []


def test_f2_a_persistent_replace_failure_is_typed_and_leaves_no_orphans(
        tmp_path, monkeypatch):
    atomic_cls = _atomic_write_error()
    target = tmp_path / "catalog" / "revisions" / "rev-stuck.json"
    target.parent.mkdir(parents=True)
    target.write_text("original\n", encoding="utf-8")
    calls = {"count": 0}

    def always_denied(src: Any, dst: Any) -> None:
        calls["count"] += 1
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(revision_mod, "os", _OsShim(always_denied))
    with pytest.raises(atomic_cls) as excinfo:
        revision_mod._atomic_write(target, "replacement\n")

    assert "could not replace" in str(excinfo.value)
    assert calls["count"] == revision_mod.REPLACE_RETRY_ATTEMPTS
    assert target.read_text(encoding="utf-8") == "original\n"
    assert _temp_files(target.parent) == []


def test_f2_a_contended_pointer_write_keeps_the_current_pointer(tmp_path, monkeypatch):
    _atomic_write_error()
    root = tmp_path / "catalog"
    publisher = _publisher(root)
    seed_revision = _seed_store(publisher)
    snapshot = _snapshot("contended")
    calls = {"count": 0}
    real_replace = os.replace

    def deny_the_pointer(src: Any, dst: Any) -> None:
        calls["count"] += 1
        if Path(dst) == publisher.pointer_path:
            raise PermissionError(13, "Access is denied")
        real_replace(src, dst)

    monkeypatch.setattr(revision_mod, "os", _OsShim(deny_the_pointer))
    with pytest.raises(revision_mod.PublicationRejected) as excinfo:
        publisher.publish(snapshot, expected_current=seed_revision)

    assert "contended" in str(excinfo.value)
    assert calls["count"] == 1 + revision_mod.REPLACE_RETRY_ATTEMPTS
    assert publisher.current_revision() == seed_revision
    assert publisher.retain(snapshot.dataset_revision)
    assert _leftovers(root) == []


def test_f2_a_pointer_lost_to_an_outside_writer_is_reported_stale(tmp_path, monkeypatch):
    _atomic_write_error()
    root = tmp_path / "catalog"
    publisher = _publisher(root)
    seed_revision = _seed_store(publisher)
    snapshot = _snapshot("lost")
    winner = {"revision": "rev-w5f-external-winner", "written": False}
    real_replace = os.replace

    def lose_to_winner(src: Any, dst: Any) -> None:
        if Path(dst) == publisher.pointer_path:
            if not winner["written"]:
                winner["written"] = True
                pointer = {
                    "schema": revision_mod.POINTER_SCHEMA,
                    "dataset_revision": winner["revision"],
                    "published_at": "2026-10-07T00:00:00+00:00",
                    "previous": seed_revision,
                }
                publisher.pointer_path.write_text(
                    json.dumps(pointer, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")
            raise PermissionError(13, "Access is denied")
        real_replace(src, dst)

    monkeypatch.setattr(revision_mod, "os", _OsShim(lose_to_winner))
    with pytest.raises(revision_mod.StalePublisherError) as excinfo:
        publisher.publish(snapshot, expected_current=seed_revision)

    assert winner["revision"] in str(excinfo.value)
    assert winner["written"]
    assert publisher.current_revision() == winner["revision"]
    assert _leftovers(root) == []


def test_f2_transient_pointer_read_failures_are_retried(tmp_path, monkeypatch):
    root = tmp_path / "catalog"
    publisher = _publisher(root)
    seed_revision = _seed_store(publisher)
    real_read_text = Path.read_text
    calls = {"count": 0}

    def flaky_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
        if Path(self) == publisher.pointer_path:
            calls["count"] += 1
            if calls["count"] <= 2:
                raise PermissionError(13, "The process cannot access the file")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", flaky_read_text)
    current = publisher.current()

    assert current is not None and current["dataset_revision"] == seed_revision
    assert calls["count"] == 3


def test_f2_a_persistent_pointer_read_failure_is_typed(tmp_path, monkeypatch):
    unreadable_cls = _unreadable_error()
    root = tmp_path / "catalog"
    publisher = _publisher(root)
    _seed_store(publisher)

    def denied_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
        if Path(self) == publisher.pointer_path:
            raise PermissionError(13, "Access is denied")
        raise AssertionError(f"unexpected read of {self!r}")

    monkeypatch.setattr(Path, "read_text", denied_read_text)
    with pytest.raises(unreadable_cls) as excinfo:
        publisher.current()

    assert "could not be read" in str(excinfo.value)
    assert "8 attempt" in str(excinfo.value)


# --------------------------------------------------------------------------- #
# F3 — the nested UNKNOWN sentinel and the byte-stability corpus.
# --------------------------------------------------------------------------- #
def test_f3_nested_unknown_is_encoded_wherever_it_is_nested():
    assert canonical_mod.encode_value(UNKNOWN) == "\x01"
    assert canonical_mod.encode_value(
        {"paper": "0580/41", "variant": UNKNOWN}) == r'{"paper":"0580/41","variant":"\u0001"}'
    assert canonical_mod.encode_value([0, UNKNOWN, 1, 1]) == r'[0,"\u0001",1,1]'
    assert canonical_mod.encode_value(
        {"a": {"b": [UNKNOWN, {"c": UNKNOWN}]}}) == r'{"a":{"b":["\u0001",{"c":"\u0001"}]}}'
    assert canonical_mod.encode_value((1, UNKNOWN)) == r'[1,"\u0001"]'


CONTAINER_UNKNOWN_FIELDS: dict[str, Any] = {
    "system": "cie",
    "kind": "question",
    "native_identity": {"paper": "0580/41", "variant": UNKNOWN, "nested": {"b": None}},
}
REGION_UNKNOWN_FIELDS: dict[str, Any] = {
    "system": "cie",
    "document_role": "value-document_role",
    "document_sha256": "a" * 64,
    "page": 1,
    "bbox": [0, UNKNOWN, 1, 1],
    "coordinate_system": "pdf points",
}


def test_f3_identities_with_nested_unknown_stay_deterministic():
    container_identity = canonical_mod.canonical_identity_string(
        "container", dict(CONTAINER_UNKNOWN_FIELDS))
    assert container_identity == (
        "\x1fcontainer\x1esystem=CIE\x1ekind=QUESTION\x1enative_identity="
        + r'{"nested":{"b":null},"paper":"0580/41","variant":"\u0001"}')
    assert canonical_mod.public_id("container", dict(CONTAINER_UNKNOWN_FIELDS)) == (
        "container_xnsecenyozyjpeq2khlwwy5rhlw4mjsz")

    region_identity = canonical_mod.canonical_identity_string(
        "region", dict(REGION_UNKNOWN_FIELDS))
    assert region_identity == (
        "\x1fregion\x1esystem=CIE\x1edocument_role=VALUE-DOCUMENT_ROLE"
        "\x1edocument_sha256=" + "a" * 64 + "\x1epage=1\x1ebbox="
        + r'[0,"\u0001",1,1]' + "\x1ecoordinate_system=PDF POINTS")
    assert canonical_mod.public_id("region", dict(REGION_UNKNOWN_FIELDS)) == (
        "region_hlnkeeyfmzor6guislbtchwxrfqeq3gr")
    assert canonical_mod.digest_for("region", dict(REGION_UNKNOWN_FIELDS)) == (
        "hlnkeeyfmzor6guislbtchwxrfqeq3gr")

    # Deterministic: repeated derivations agree, and the marker is not a hash
    # collision with the "not recorded" (None) encoding of the same fields.
    repeated = canonical_mod.public_id("container", dict(CONTAINER_UNKNOWN_FIELDS))
    assert repeated == canonical_mod.public_id("container", dict(CONTAINER_UNKNOWN_FIELDS))
    absent = dict(CONTAINER_UNKNOWN_FIELDS)
    absent["native_identity"] = {"paper": "0580/41", "variant": None, "nested": {"b": None}}
    assert canonical_mod.public_id("container", absent) != repeated


def test_f3_unrepresentable_values_raise_the_modules_typed_error():
    for label, value in (("object", object()), ("bytes", b"xy"), ("set", {1, 2})):
        with pytest.raises(TypeError) as excinfo:
            canonical_mod.encode_value(value)
        assert str(excinfo.value) == f"cannot encode {label} in a canonical identity"

    for nested in ({"a": object()}, [object()], {"a": [{"b": {1, 2}}]}):
        with pytest.raises(TypeError) as excinfo:
            canonical_mod.encode_value(nested)
        assert "cannot encode" in str(excinfo.value)

    with pytest.raises(TypeError) as excinfo:
        canonical_mod.canonical_identity_string(
            "container",
            {"system": "cie", "kind": "question", "native_identity": {"x": object()}})
    assert str(excinfo.value) == "cannot encode object in a canonical identity"


# The payloads of the pre-repair capture (same table as the capture script in
# ``tmp/w5f-repair-*/capture_canonical_corpus.py``): (name, mode, payload).
_CORPUS_CASES: list[tuple[str, str, Any]] = [
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

_CORPUS_BEFORE: dict[str, dict[str, str]] = {
    'encode:none': {'mode': 'encode', 'input_repr': 'None', 'output': '\x00'},
    'encode:bool-true': {'mode': 'encode', 'input_repr': 'True', 'output': 'true'},
    'encode:bool-false': {'mode': 'encode', 'input_repr': 'False', 'output': 'false'},
    'encode:int-zero': {'mode': 'encode', 'input_repr': '0', 'output': '0'},
    'encode:int-negative': {'mode': 'encode', 'input_repr': '-3', 'output': '-3'},
    'encode:int-big': {'mode': 'encode', 'input_repr': '1234567890123456789', 'output': '1234567890123456789'},
    'encode:float': {'mode': 'encode', 'input_repr': '3.5', 'output': '3.5'},
    'encode:float-integral': {'mode': 'encode', 'input_repr': '2.0', 'output': '2.0'},
    'encode:text': {'mode': 'encode', 'input_repr': "'Hello World'", 'output': 'Hello World'},
    'encode:text-unicode': {'mode': 'encode', 'input_repr': "'Ünïcode é 中文'", 'output': 'Ünïcode é 中文'},
    'encode:text-tab': {'mode': 'encode', 'input_repr': "'a\\tb'", 'output': 'a\tb'},
    'encode:text-with-ff': {'mode': 'encode', 'input_repr': "'a\\x0cb'", 'output': 'a\x0cb'},
    'encode:list-empty': {'mode': 'encode', 'input_repr': '[]', 'output': '[]'},
    'encode:list-scalars': {'mode': 'encode', 'input_repr': "[None, True, 2, 's']", 'output': '[null,true,2,"s"]'},
    'encode:list-nested': {'mode': 'encode', 'input_repr': "[1, [2, [3, {'a': None}]], {'b': [True, False]}]", 'output': '[1,[2,[3,{"a":null}]],{"b":[true,false]}]'},
    'encode:tuple': {'mode': 'encode', 'input_repr': "(1, 'two', None)", 'output': '[1,"two",null]'},
    'encode:tuple-nested': {'mode': 'encode', 'input_repr': '(1, (2, (3,)))', 'output': '[1,[2,[3]]]'},
    'encode:map-empty': {'mode': 'encode', 'input_repr': '{}', 'output': '{}'},
    'encode:map-scalars': {'mode': 'encode', 'input_repr': "{'b': 1, 'a': 2, 'c': None}", 'output': '{"a":2,"b":1,"c":null}'},
    'encode:map-nested': {'mode': 'encode', 'input_repr': "{'z': {'y': {'x': [1, 2, {'w': 'v'}]}}, 'a': [None, {'b': True}]}", 'output': '{"a":[null,{"b":true}],"z":{"y":{"x":[1,2,{"w":"v"}]}}}'},
    'encode:map-none-nested': {'mode': 'encode', 'input_repr': "{'a': None, 'b': [None], 'c': {'d': None}}", 'output': '{"a":null,"b":[null],"c":{"d":null}}'},
    'encode:map-unicode-key': {'mode': 'encode', 'input_repr': "{'é': 'x', 'ascii': 'y'}", 'output': '{"ascii":"y","é":"x"}'},
    'encode:map-int-keys': {'mode': 'encode', 'input_repr': "{2: 'b', 1: 'a'}", 'output': '{"1":"a","2":"b"}'},
    'encode:map-str-values-space': {'mode': 'encode', 'input_repr': "{'a': '  keep  this ', 'b': 'MiXeD case'}", 'output': '{"a":"  keep  this ","b":"MiXeD case"}'},
    'normalize:code': {'mode': 'normalize', 'input_repr': "'paper' '  0580 /  41 '", 'output': "'0580 / 41'"},
    'normalize:text': {'mode': 'normalize', 'input_repr': "'title' '  Keep   Case  É '", 'output': "'Keep Case É'"},
    'normalize:hash': {'mode': 'normalize', 'input_repr': "'sha256' ' AB CD EF '", 'output': "'ab cd ef'"},
    'normalize:map': {'mode': 'normalize', 'input_repr': "'native_identity' {'paper': '  0580/41 ', 'variant': ' v1 ', 'n': 3}", 'output': "{'paper': '0580/41', 'variant': 'V1', 'n': 3}"},
    'normalize:list': {'mode': 'normalize', 'input_repr': "'bbox' ['  1 ', 2, None]", 'output': "['1', 2, None]"},
    'identity:container': {'mode': 'identity', 'input_repr': "kind='container'", 'output': '\x1fcontainer\x1esystem=CIE\x1ekind=QUESTION\x1enative_identity={"nested":{"b":null},"paper":"0580/41","variant":"V1"}', 'public_id': 'container_pdp4bnsevsgyysvpigdwpmtlaqegbhlq', 'digest': 'pdp4bnsevsgyysvpigdwpmtlaqegbhlq'},
    'identity:question': {'mode': 'identity', 'input_repr': "kind='question'", 'output': '\x1fquestion\x1esystem=CIE\x1econtainer_native_identity={"nested":{"b":null},"paper":"0580/41","variant":"V1"}\x1enative_id=id-1\x1enumber_path=1 (a) (ii)\x1eparent_native_id=VALUE-parent_native_id', 'public_id': 'q_evpljkoktuqmtcytwe77ihvlbn5f2nn3', 'digest': 'evpljkoktuqmtcytwe77ihvlbn5f2nn3'},
    'identity:region': {'mode': 'identity', 'input_repr': "kind='region'", 'output': '\x1fregion\x1esystem=CIE\x1edocument_role=VALUE-DOCUMENT_ROLE\x1edocument_sha256=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\x1epage=1\x1ebbox=[0,0,1,1]\x1ecoordinate_system=PDF POINTS', 'public_id': 'region_iqmtx24pfbdcdmelrfmvx7m27zycvsoc', 'digest': 'iqmtx24pfbdcdmelrfmvx7m27zycvsoc'},
    'identity:timetable_event': {'mode': 'identity', 'input_repr': "kind='timetable_event'", 'output': '\x1ftimetable_event\x1esystem=CIE\x1equalification=VALUE-QUALIFICATION\x1ezone=VALUE-ZONE\x1ecourse_native_code=VALUE-course_native_code\x1ecomponent=VALUE-COMPONENT\x1edate=VALUE-date\x1esession=VALUE-SESSION', 'public_id': 'tte_5v2gdb7o5cob22nucjflweasjqdbigy6', 'digest': '5v2gdb7o5cob22nucjflweasjqdbigy6'},
    'identity:coverage': {'mode': 'identity', 'input_repr': "kind='coverage'", 'output': '\x1fcoverage\x1escope_kind=VALUE-SCOPE_KIND\x1escope_native_identity={"level":2,"scope":"mvp"}\x1edenominator_kind=VALUE-DENOMINATOR_KIND', 'public_id': 'cov_cxr4enb36h34whrkw32lz6wsz56p4f2d', 'digest': 'cxr4enb36h34whrkw32lz6wsz56p4f2d'},
}

# The same corpus shape extended with the sentinel the repair now encodes.
_CORPUS_UNKNOWN_EXTENSION: list[tuple[str, Any, str]] = [
    ("ext:map-list-unknown", {"a": [UNKNOWN]}, r'{"a":["\u0001"]}'),
    ("ext:list-map-unknown", [{"x": UNKNOWN}, UNKNOWN], r'[{"x":"\u0001"},"\u0001"]'),
    ("ext:unknown-inside-tuple-in-map", {"t": (UNKNOWN, [1, UNKNOWN])},
     r'{"t":["\u0001",[1,"\u0001"]]}'),
]


def _identity_fields(kind: str) -> dict[str, Any]:
    """The exact fields the pre-repair capture used for an identity case."""
    keys = canonical_mod.IDENTITY_KEYS[EntityKind.coerce(kind)]
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


def test_f3_byte_stability_corpus_matches_the_captured_before_outputs():
    assert len(_CORPUS_CASES) == 34
    assert set(_CORPUS_BEFORE) == {name for name, _, _ in _CORPUS_CASES}

    for name, mode, payload in _CORPUS_CASES:
        expected = _CORPUS_BEFORE[name]
        assert expected["mode"] == mode, name
        if mode == "encode":
            assert repr(payload) == expected["input_repr"], name
            assert canonical_mod.encode_value(payload) == expected["output"], name
        elif mode == "normalize":
            key, value = payload
            assert f"{key!r} {value!r}" == expected["input_repr"], name
            assert repr(canonical_mod.normalize_value(key, value)) == expected["output"], name
        else:
            fields = _identity_fields(payload)
            assert f"kind={payload!r}" == expected["input_repr"], name
            assert canonical_mod.canonical_identity_string(
                payload, fields) == expected["output"], name
            assert canonical_mod.public_id(payload, fields) == expected["public_id"], name
            assert canonical_mod.digest_for(payload, fields) == expected["digest"], name

    for name, payload, expected_output in _CORPUS_UNKNOWN_EXTENSION:
        assert canonical_mod.encode_value(payload) == expected_output, name
