#!/usr/bin/env python
"""W5 concurrency probes around the candidate's revision publication.

Three subcommands; every payload is deterministic JSON and documented exit
codes: ``0`` ok | ``1`` error | ``2`` refusal | ``8`` findings.

``race``
    Spawn ``--all-writers`` + ``--mvp-writers`` writer *processes* (default
    2 + 2).  Each writer reads the store itself (the store is freshly created
    by this tool, so every writer observes *no* current pointer), builds its
    catalog, raises a ready flag, waits for the shared start file, and then
    publishes with ``expected_current=None``.  With a correct atomic
    compare-and-swap exactly one writer may win and every other writer must be
    refused as stale; every writer that reports success against the same
    observed pre-state is a lost-update symptom and is recorded (the race is a
    real, schedule-dependent experiment, so its outcome is *observed*, never
    forced).  Reader threads keep validating the store during the whole race
    and must never observe an inconsistent store.  A late writer (built after
    the race) must be refused as stale and must leave the pointer untouched.

``worker``
    The writer process ``race`` spawns (read store -> build -> ready flag ->
    wait -> publish -> result file).  Not usually invoked by hand.

``window-probe``
    A deterministic demonstration of the check-then-act window inside
    ``RevisionPublisher.publish``: the window between the compare-and-swap
    *check* and the pointer ``os.replace`` is widened at runtime by wrapping
    the candidate module's ``_atomic_write`` for one thread only.  Thread T2
    publishes a revision authorized against the seed revision and is held at
    its pointer write; the main thread publishes a different revision; T2 is
    then released and blindly overwrites it.  The candidate file on disk is
    never modified (its sha256 is recorded before and after; the wrapper
    exists only in this process).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import replace as dataclass_replace
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w5_common as w5  # noqa: E402
import migrate  # noqa: E402

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_REFUSAL = 2
EXIT_FINDINGS = 8

RACE_NOTES = [
    "the race is a real experiment on real files: its counters reflect the "
    "observed schedule and are never forced or curated",
    "with a correct atomic compare-and-swap, one writer wins and every other "
    "writer is refused as stale; success_count > 1, a published writer whose "
    "target is not the final pointer, or any crashed writer means the "
    "publication transaction did not complete cleanly",
    "a writer whose publication raises (for example two processes replacing "
    "the same file concurrently) is recorded as status 'crashed' with the "
    "exception text; its leftover .tmp-* files are listed in final.temp_files",
    "reader failures count only reads that failed while a current pointer "
    "existed; reads before the first publication are counted as uninitialized",
]

WINDOW_NOTES = [
    "the blocked window is created by a runtime wrapper around the candidate "
    "module's _atomic_write (thread-scoped), not by editing any candidate file",
    "the final pointer's 'previous' field names the seed revision although a "
    "different revision was current immediately before the overwriting swap: "
    "the pointer chain skips the displaced revision",
]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _reset_dir(path: Path) -> None:
    path = w5.guard_within(path, w5.MIGRATION_ROOT)
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def _proc_kill(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.kill()
        proc.wait()


def _read_pointer(dest_root: Path) -> dict[str, Any] | None:
    pointer_path = dest_root / "catalog" / "current.json"
    return w5.read_json(pointer_path) if pointer_path.is_file() else None


def _revision_names(dest_root: Path) -> list[str]:
    revisions_dir = dest_root / "catalog" / "revisions"
    return sorted(p.stem for p in revisions_dir.glob("*.json")) if revisions_dir.is_dir() else []


# --------------------------------------------------------------------------- #
# race
# --------------------------------------------------------------------------- #
def cmd_race(args: argparse.Namespace) -> int:
    source_root = Path(args.source)
    dest_root = Path(args.dest)
    work = Path(args.work) if args.work else dest_root.with_name(dest_root.name + "--race")

    catalog_area = dest_root / "catalog"
    if catalog_area.exists() and any(p.is_file() for p in catalog_area.rglob("*")):
        w5.dump({"status": "refused",
                 "reason": "the destination already has a catalog area; the race "
                           "requires a store with no observed current revision",
                 "dest_root": str(dest_root)})
        return EXIT_REFUSAL
    adopted = migrate.ensure_dest(dest_root)
    _reset_dir(work)

    specs = ([{"index": i, "scope": "all"} for i in range(args.all_writers)]
             + [{"index": args.all_writers + i, "scope": "mvp"}
                for i in range(args.mvp_writers)])
    tool = str(Path(__file__).resolve())
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    procs: list[dict[str, Any]] = []
    for spec in specs:
        log = (work / f"{spec['index']}.log").open("wb")
        proc = subprocess.Popen(
            [sys.executable, "-B", tool, "worker",
             "--source", str(source_root), "--dest", str(dest_root),
             "--work", str(work), "--index", str(spec["index"]),
             "--scope", spec["scope"], "--ready-timeout", str(args.ready_timeout)],
            stdout=log, stderr=subprocess.STDOUT, env=env)
        procs.append({"spec": spec, "proc": proc, "log": log})

    # wait until every writer is built and ready (or died trying)
    deadline = time.time() + args.ready_timeout
    while True:
        if all((work / f"{p['spec']['index']}.flag").exists() for p in procs):
            break
        dead = [p["spec"]["index"] for p in procs
                if p["proc"].poll() is not None
                and not (work / f"{p['spec']['index']}.flag").exists()]
        if dead:
            for p in procs:
                _proc_kill(p["proc"])
            w5.dump({"status": "error", "reason": "writer(s) exited before becoming ready",
                     "indices": dead, "work": str(work)})
            return EXIT_ERROR
        if time.time() > deadline:
            for p in procs:
                _proc_kill(p["proc"])
            w5.dump({"status": "error", "reason": "timed out waiting for writers to build",
                     "ready_timeout": args.ready_timeout, "work": str(work)})
            return EXIT_ERROR
        time.sleep(0.2)

    # readers validate the store for the whole race
    stop = threading.Event()
    reader_stats = [{"iterations": 0, "uninitialized": 0, "failures": []}
                    for _ in range(args.readers)]

    def reader_loop(idx: int) -> None:
        stats = reader_stats[idx]
        while not stop.is_set():
            try:
                store = w5.read_consistent_store(dest_root)
                stats["iterations"] += 1
            except Exception as exc:  # noqa: BLE001 - recorded, never raised
                if (dest_root / "catalog" / "current.json").exists():
                    if len(stats["failures"]) < 50:
                        stats["failures"].append(f"{type(exc).__name__}: {exc}")
                else:
                    stats["uninitialized"] += 1
            time.sleep(0.01)

    threads = [threading.Thread(target=reader_loop, args=(i,), name=f"reader-{i}")
               for i in range(args.readers)]
    for thread in threads:
        thread.start()

    start_tmp = work / "start.tmp"
    start_tmp.write_text(str(time.time() + args.start_delay), encoding="ascii")
    os.replace(start_tmp, work / "start")

    timeouts: list[int] = []
    for p in procs:
        try:
            p["proc"].wait(timeout=args.writer_timeout)
        except subprocess.TimeoutExpired:
            _proc_kill(p["proc"])
            timeouts.append(p["spec"]["index"])
    time.sleep(0.25)  # readers observe the settled store too
    stop.set()
    for thread in threads:
        thread.join(timeout=30)
    for p in procs:
        p["log"].close()

    writers: list[dict[str, Any]] = []
    for p in procs:
        i = p["spec"]["index"]
        build_path, result_path = work / f"{i}.build.json", work / f"{i}.result.json"
        writers.append({
            "index": i,
            "scope": p["spec"]["scope"],
            "returncode": p["proc"].returncode,
            "log_file": str(work / f"{i}.log"),
            "build": w5.read_json(build_path) if build_path.exists() else None,
            "result": (w5.read_json(result_path) if result_path.exists()
                       else {"status": "no_result", "exit_code": EXIT_ERROR}),
        })

    final_pointer = _read_pointer(dest_root)
    revisions = _revision_names(dest_root)
    temp_files = sorted(p.name for p in (dest_root / "catalog").glob("*.tmp-*"))
    temp_files += sorted(f"revisions/{p.name}" for p in
                         (dest_root / "catalog" / "revisions").glob("*.tmp-*"))
    final_errors: list[str] = []
    try:
        store = w5.read_consistent_store(dest_root)
        final_revision = store["revision"]
        final = {"revision": final_revision,
                 "pointer_sha256": store["pointer_sha256"],
                 "pointer": store["pointer"]}
    except Exception as exc:  # noqa: BLE001 - an unreadable final store is a finding
        final_revision = None
        final = {"revision": None, "pointer_sha256": None, "pointer": final_pointer}
        final_errors.append(f"{type(exc).__name__}: {exc}")

    published = [w for w in writers if w["result"].get("status") == "published"]
    stale = [w for w in writers if w["result"].get("status") == "stale"]
    crashed = [w for w in writers if w["result"].get("status") == "crashed"]
    other = [w for w in writers
             if w["result"].get("status") not in ("published", "stale", "crashed")]
    nonfinal = sorted(w["index"] for w in published
                      if w["result"].get("pointer", {}).get("dataset_revision")
                      != final_revision)
    unreferenced = [r for r in revisions
                    if r != final_revision and final_pointer is not None
                    and r != final_pointer.get("previous")]

    # the late writer: a builder that observed the same empty pre-state, built
    # afterwards, and now tries to publish; it must be refused as stale.
    pointer_sha_before = (w5.sha256_file(dest_root / "catalog" / "current.json")
                          if (dest_root / "catalog" / "current.json").is_file() else None)
    late_build = migrate.build_catalog(source_root, select_scope="all")
    late = migrate.publish_built_catalog(late_build, source_root, dest_root,
                                         select_scope="all", expect_current="none")
    pointer_sha_after = (w5.sha256_file(dest_root / "catalog" / "current.json")
                         if (dest_root / "catalog" / "current.json").is_file() else None)
    late_writer = {
        "status": late["status"],
        "exit_code": late["exit_code"],
        "expected_status": "stale",
        "build_ok": late["build_ok"],
        "candidate_revision": late["candidate_revision"],
        "detail": late.get("detail"),
        "pointer_sha256_before": pointer_sha_before,
        "pointer_sha256_after": pointer_sha_after,
        "pointer_unchanged": pointer_sha_before == pointer_sha_after,
    }

    findings: list[str] = []
    reader_failures = sum(len(r["failures"]) for r in reader_stats)
    if not published:
        findings.append("no writer reported success against the shared pre-state")
    if crashed:
        findings.append(
            f"{len(crashed)} writer(s) crashed instead of receiving a CAS verdict: "
            + "; ".join(str(w["result"].get("detail")) for w in crashed))
    if reader_failures:
        findings.append(f"readers observed {reader_failures} failed read(s) while a "
                        "current pointer existed")
    if timeouts:
        findings.append(f"writer(s) timed out: {timeouts}")
    if final_errors:
        findings.append("final store is unreadable: " + "; ".join(final_errors))
    if len(published) > 1:
        findings.append(f"{len(published)} writers reported success against the same "
                        "observed pre-state (expected at most 1 under an atomic CAS)")
    if nonfinal:
        findings.append(f"published writer(s) {nonfinal} do not match the final pointer")
    if late["status"] != "stale":
        findings.append(f"the late writer was not refused as stale (status "
                        f"{late['status']!r})")
    if not late_writer["pointer_unchanged"]:
        findings.append("the late writer changed the pointer")

    cas_honored = (len(published) == 1 and not crashed and not other
                   and not nonfinal and not final_errors
                   and late["status"] == "stale" and late_writer["pointer_unchanged"])
    result = {
        "schema": "w5.concurrent-publish/1",
        "probe": "race",
        "source_root": str(source_root),
        "dest_root": str(dest_root),
        "work": str(work),
        "adopted": adopted,
        "initial_state": {"pointer": None},
        "writers_planned": specs,
        "writers": writers,
        "counts": {"success": len(published), "stale": len(stale),
                   "crashed": len(crashed), "other": len(other)},
        "final": {**final, "revision_files": revisions,
                  "unreferenced_revisions": unreferenced,
                  "published_writers_with_nonfinal_target": nonfinal,
                  "temp_files": temp_files},
        "readers": {"threads": args.readers, "failures": reader_failures,
                    "per_reader": reader_stats},
        "late_writer": late_writer,
        "cas_honored_under_race": cas_honored,
        "findings": findings,
        "notes": RACE_NOTES,
    }
    if args.out:
        w5.write_json(args.out, result)
    w5.dump(result)
    return EXIT_FINDINGS if findings else EXIT_OK


# --------------------------------------------------------------------------- #
# worker (spawned by race)
# --------------------------------------------------------------------------- #
def cmd_worker(args: argparse.Namespace) -> int:
    source_root = Path(args.source)
    dest_root = Path(args.dest)
    work = Path(args.work)
    index = args.index

    observed = _read_pointer(dest_root)
    observed_revision = observed.get("dataset_revision") if observed else None
    build = migrate.build_catalog(source_root, select_scope=args.scope)
    result = build["result"]
    w5.write_json(work / f"{index}.build.json", {
        "index": index,
        "scope": args.scope,
        "observed_current": observed_revision,
        "build_ok": result.ok,
        "candidate_revision": result.candidate_revision,
        "counts": result.counts,
    })
    (work / f"{index}.flag").write_text("ready\n", encoding="ascii")

    start_file = work / "start"
    deadline = time.time() + args.ready_timeout
    t0: float | None = None
    while t0 is None:
        if time.time() > deadline:
            w5.write_json(work / f"{index}.result.json",
                          {"status": "start_timeout", "exit_code": EXIT_ERROR})
            return EXIT_ERROR
        try:
            t0 = float(start_file.read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            time.sleep(0.02)
    while time.time() < t0:
        time.sleep(0.001)

    try:
        info = migrate.publish_built_catalog(
            build, source_root, dest_root, select_scope=args.scope,
            expect_current=(observed_revision if observed_revision else "none"))
        payload = {k: v for k, v in info.items() if k != "statuses"}
        exit_code = EXIT_OK
    except Exception as exc:  # noqa: BLE001 - a crash is recorded, never hidden
        payload = {"status": "crashed", "exit_code": EXIT_ERROR,
                   "detail": f"{type(exc).__name__}: {exc}"}
        exit_code = EXIT_ERROR
    w5.write_json(work / f"{index}.result.json", payload)
    w5.dump(payload)
    return exit_code


# --------------------------------------------------------------------------- #
# window probe
# --------------------------------------------------------------------------- #
def cmd_window_probe(args: argparse.Namespace) -> int:
    source_root = Path(args.source)
    work = Path(args.work)
    _reset_dir(work)
    migrate.ensure_dest(work)

    api = w5.catalog_api()
    trust = api["trust"]
    from examdata.integration.catalog import revision as revision_module  # noqa: PLC0415

    candidate_file = Path(revision_module.__file__).resolve()
    sha_before = w5.sha256_file(candidate_file)

    built_all = migrate.build_catalog(source_root, select_scope="all")
    built_mvp = migrate.build_catalog(source_root, select_scope="mvp")
    if not (built_all["result"].ok and built_mvp["result"].ok):
        w5.dump({"status": "error", "reason": "a probe build did not pass validation"})
        return EXIT_ERROR
    snap_all = built_all["result"].snapshot
    snap_mvp = built_mvp["result"].snapshot

    # the seed is a *previous state* that contains neither raced revision: the
    # all-scope snapshot minus one problem-free entry (a deterministic choice).
    entries = sorted(snap_all.entries, key=lambda e: e.public_id)
    problem_free = [e for e in entries if not trust.entry_problems(e)]
    if len(problem_free) < 2:
        w5.dump({"status": "error", "reason": "not enough problem-free entries for a seed"})
        return EXIT_ERROR
    dropped = problem_free[-1]
    kept = [e for e in entries if e.public_id != dropped.public_id]
    seed_snapshot = dataclass_replace(
        snap_all, entries=kept, counts=api["counts_for"](kept),
        dataset_revision=api["compute_revision"](kept),
        problems=[p for p in snap_all.problems if p.get("ref") != dropped.public_id])

    publisher = api["RevisionPublisher"](work / "catalog")
    seed_pointer = publisher.publish(seed_snapshot, expected_current=api["ANY_CURRENT"],
                                     now=w5.FIXED_NOW)
    rev_seed = seed_pointer["dataset_revision"]
    rev_t1 = snap_mvp.dataset_revision  # the sneaking publisher's target
    rev_t2 = snap_all.dataset_revision  # the blocked publisher's target
    if len({rev_seed, rev_t1, rev_t2}) != 3:
        w5.dump({"status": "error", "reason": "probe revisions are not distinct",
                 "revisions": [rev_seed, rev_t1, rev_t2]})
        return EXIT_ERROR

    events = {"t2_at_window": threading.Event(), "release_t2": threading.Event()}
    original_atomic_write = revision_module._atomic_write

    def patched_atomic_write(path: Path, text: str) -> None:
        if path.name == "current.json" and threading.current_thread().name == "T2-holder":
            events["t2_at_window"].set()
            events["release_t2"].wait(timeout=args.release_timeout)
        return original_atomic_write(path, text)

    revision_module._atomic_write = patched_atomic_write
    t2_result: dict[str, Any] = {}

    def t2_run() -> None:
        try:
            t2_result["pointer"] = publisher.publish(
                snap_all, expected_current=rev_seed, now=w5.FIXED_NOW)
        except Exception as exc:  # noqa: BLE001 - recorded, never raised
            t2_result["error"] = f"{type(exc).__name__}: {exc}"

    try:
        t2 = threading.Thread(target=t2_run, name="T2-holder")
        t2.start()
        reached = events["t2_at_window"].wait(timeout=args.window_timeout)
        t1_result: dict[str, Any] = {}
        if reached:
            try:
                t1_result["pointer"] = publisher.publish(
                    snap_mvp, expected_current=rev_seed, now=w5.FIXED_NOW)
            except Exception as exc:  # noqa: BLE001 - recorded, never raised
                t1_result["error"] = f"{type(exc).__name__}: {exc}"
        events["release_t2"].set()
        t2.join(timeout=60)
    finally:
        revision_module._atomic_write = original_atomic_write
    sha_after = w5.sha256_file(candidate_file)

    final_pointer = _read_pointer(work)
    revisions = _revision_names(work)
    t1_revision = t1_result.get("pointer", {}).get("dataset_revision")
    t2_revision = t2_result.get("pointer", {}).get("dataset_revision")
    final_revision = final_pointer.get("dataset_revision") if final_pointer else None
    checks = {
        "t2_reached_the_window": reached,
        "t1_published_its_own_revision": t1_revision == rev_t1,
        "t2_returned_pointer_is_its_own_revision": t2_revision == rev_t2,
        "final_pointer_is_the_blocked_publishers_revision": final_revision == rev_t2,
        "final_pointer_previous_names_the_seed_not_the_displaced_revision": (
            final_pointer is not None and final_pointer.get("previous") == rev_seed),
        "displaced_revision_retained_but_unreferenced": (
            rev_t1 in revisions and rev_t1 != final_revision
            and (final_pointer or {}).get("previous") != rev_t1),
        "candidate_file_unchanged": sha_before == sha_after,
    }
    demonstrated = all(checks.values())
    result = {
        "schema": "w5.window-probe/1",
        "probe": "window-probe",
        "source_root": str(source_root),
        "work": str(work),
        "revisions": {"seed": rev_seed, "t1_target": rev_t1, "t2_target": rev_t2,
                      "dropped_entry": dropped.public_id},
        "checks": checks,
        "lost_update_demonstrated": demonstrated,
        "t1": t1_result,
        "t2": t2_result,
        "final": {"pointer": final_pointer, "revision_files": revisions,
                  "unreferenced_revisions": [r for r in revisions
                                             if r != final_revision
                                             and (final_pointer or {}).get("previous") != r]},
        "candidate_module": {"file": str(candidate_file),
                             "sha256_before": sha_before, "sha256_after": sha_after},
        "notes": WINDOW_NOTES,
    }
    if args.out:
        w5.write_json(args.out, result)
    w5.dump(result)
    return EXIT_OK if demonstrated else EXIT_FINDINGS


# --------------------------------------------------------------------------- #
# cli
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    p_race = sub.add_parser("race", help="N writers race one shared pre-state; "
                                         "readers validate the store throughout")
    p_race.add_argument("--source", required=True)
    p_race.add_argument("--dest", required=True,
                        help="the destination store; must have no catalog area yet")
    p_race.add_argument("--work", default=None,
                        help="private work dir (default: <dest>--race)")
    p_race.add_argument("--all-writers", type=int, default=2)
    p_race.add_argument("--mvp-writers", type=int, default=2)
    p_race.add_argument("--readers", type=int, default=3)
    p_race.add_argument("--ready-timeout", type=float, default=900.0)
    p_race.add_argument("--writer-timeout", type=float, default=900.0)
    p_race.add_argument("--start-delay", type=float, default=3.0)
    p_race.add_argument("--out", default=None)
    p_race.set_defaults(func=cmd_race)

    p_worker = sub.add_parser("worker", help=argparse.SUPPRESS)
    p_worker.add_argument("--source", required=True)
    p_worker.add_argument("--dest", required=True)
    p_worker.add_argument("--work", required=True)
    p_worker.add_argument("--index", type=int, required=True)
    p_worker.add_argument("--scope", choices=("all", "mvp"), required=True)
    p_worker.add_argument("--ready-timeout", type=float, default=900.0)
    p_worker.set_defaults(func=cmd_worker)

    p_probe = sub.add_parser("window-probe", help="deterministically demonstrate the "
                                                  "check-then-act publication window")
    p_probe.add_argument("--source", required=True)
    p_probe.add_argument("--work", required=True)
    p_probe.add_argument("--release-timeout", type=float, default=120.0)
    p_probe.add_argument("--window-timeout", type=float, default=120.0)
    p_probe.add_argument("--out", default=None)
    p_probe.set_defaults(func=cmd_window_probe)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
