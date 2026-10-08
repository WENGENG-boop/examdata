"""SQLite 锁竞争处理：错误识别、重试退避、BEGIN IMMEDIATE 开关。

WAL 下「先读后写」的事务升级撞上并发提交会立即失败（SQLITE_BUSY_SNAPSHOT，
busy handler 不生效），批量 CLI 因此改为 BEGIN IMMEDIATE + 重试兜底；
这里锁定这些底层保证的行为。
"""

from __future__ import annotations

import sqlite3
import time

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from examdata.core import db as db_module


def _locked_error() -> OperationalError:
    return OperationalError(
        "INSERT INTO t VALUES (1)", {}, sqlite3.OperationalError("database is locked")
    )


@pytest.fixture()
def session():
    engine = create_engine("sqlite://", future=True)
    with Session(engine) as db:
        yield db
    engine.dispose()


def test_is_locked_error_matches_sqlite_busy_variants():
    assert db_module.is_locked_error(sqlite3.OperationalError("database is locked"))
    assert db_module.is_locked_error(sqlite3.OperationalError("database table is locked"))
    assert not db_module.is_locked_error(sqlite3.OperationalError("no such table: t"))
    assert not db_module.is_locked_error(RuntimeError("synthetic revision failure"))


def test_with_lock_retry_retries_locked_error_then_succeeds(session):
    calls = 0

    def action() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise _locked_error()
        return "ok"

    assert db_module.with_lock_retry(session, action, attempts=4, base_delay=0.01) == "ok"
    assert calls == 3


def test_with_lock_retry_does_not_retry_other_errors(session):
    calls = 0

    def action():
        nonlocal calls
        calls += 1
        raise ValueError("boom")

    with pytest.raises(ValueError):
        db_module.with_lock_retry(session, action, base_delay=0.01)
    assert calls == 1


def test_with_lock_retry_raises_last_locked_error_when_exhausted(session):
    calls = 0

    def action():
        nonlocal calls
        calls += 1
        raise _locked_error()

    with pytest.raises(OperationalError):
        db_module.with_lock_retry(session, action, attempts=3, base_delay=0.01)
    assert calls == 3


def test_read_then_write_upgrade_fails_immediately_in_wal(tmp_path):
    """读快照过期后的首次写升级立即失败、不等 busy_timeout——批量流程因此
    不能让读事务横跨网络窗口（sync_resource 在下载前 commit 的原因）。"""
    db_path = tmp_path / "snap.db"
    setup = sqlite3.connect(db_path)
    setup.execute("PRAGMA journal_mode=WAL")
    setup.execute("CREATE TABLE t (x INTEGER)")
    setup.commit()
    setup.close()

    reader = sqlite3.connect(db_path)
    reader.execute("PRAGMA busy_timeout=1000")
    reader.execute("BEGIN")
    reader.execute("SELECT * FROM t").fetchall()  # 建立读快照

    writer = sqlite3.connect(db_path)
    writer.execute("PRAGMA busy_timeout=1000")
    writer.execute("BEGIN IMMEDIATE")
    writer.execute("INSERT INTO t VALUES (1)")
    writer.commit()
    writer.close()

    started = time.monotonic()
    with pytest.raises(sqlite3.OperationalError, match="locked"):
        reader.execute("INSERT INTO t VALUES (2)")
    assert time.monotonic() - started < 0.5  # 立即失败，而非等满 busy_timeout
    reader.close()


def test_immediate_writes_flag_acquires_write_lock(monkeypatch):
    """flag 开启后 BEGIN IMMEDIATE 立即持写锁：并发写者只能等待。"""
    engine = db_module.get_engine()
    db_path = engine.url.database
    assert db_path and db_path != ":memory:"
    monkeypatch.setattr(db_module, "_immediate_writes", True)

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        probe = sqlite3.connect(db_path)
        try:
            probe.execute("PRAGMA busy_timeout=200")
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                probe.execute("BEGIN IMMEDIATE")
        finally:
            probe.close()


def test_deferred_writes_flag_does_not_hold_write_lock(monkeypatch):
    """flag 关闭时保持 deferred BEGIN：只读事务不挡写锁。"""
    engine = db_module.get_engine()
    db_path = engine.url.database
    assert db_path and db_path != ":memory:"
    monkeypatch.setattr(db_module, "_immediate_writes", False)

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        probe = sqlite3.connect(db_path)
        try:
            probe.execute("PRAGMA busy_timeout=200")
            probe.execute("BEGIN IMMEDIATE")
            probe.execute("ROLLBACK")
        finally:
            probe.close()
