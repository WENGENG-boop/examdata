"""数据库会话管理。

本地开发用 SQLite，生产用 PostgreSQL。Schema 保持可移植（不使用任何 Postgres 专有类型），
向量检索通过可插拔的 SimilarityIndex 提供，避免绑定 pgvector。
"""

from __future__ import annotations

import functools
import time
from contextlib import contextmanager
from typing import Callable, Iterator, TypeVar

from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings

_engine = None
_SessionLocal: sessionmaker[Session] | None = None

# 批量 CLI 进程的开关：事务改为 BEGIN IMMEDIATE，并放宽 busy_timeout。
# WAL 下「先读后写」的事务升级撞上并发写者会立即失败（SQLITE_BUSY_SNAPSHOT /
# SQLITE_BUSY，busy handler 不生效），多进程批量跑时慢者会被饿死；
# BEGIN IMMEDIATE 在事务开始就取写锁，等待交给 busy_timeout。
# 只在批量命令入口调用，API 与既有单进程流程保持 deferred BEGIN 不变。
_immediate_writes = False
_busy_timeout_ms = 10000


def enable_immediate_writes(*, busy_timeout_ms: int = 30000) -> None:
    """批量命令入口调用：BEGIN IMMEDIATE + 更长的锁等待窗口。"""
    global _immediate_writes, _busy_timeout_ms
    _immediate_writes = True
    _busy_timeout_ms = busy_timeout_ms


def is_locked_error(exc: BaseException) -> bool:
    """SQLite 锁竞争错误。SQLITE_BUSY 与 SQLITE_BUSY_SNAPSHOT 都报 database is locked。"""
    message = str(exc).lower()
    return "database is locked" in message or "database table is locked" in message


_T = TypeVar("_T")


def with_lock_retry(
    session: Session,
    action: Callable[[], _T],
    *,
    attempts: int = 6,
    base_delay: float = 0.25,
    max_delay: float = 4.0,
) -> _T:
    """执行 ``action``；遇 SQLite 锁竞争时回滚会话并指数退避重试。

    action 需要可重复执行：调用方应保证其副作用幂等（重新 SELECT/upsert）。
    非锁错误原样抛出；重试耗尽后抛最后一个锁错误。
    """
    for attempt in range(attempts):
        try:
            return action()
        except OperationalError as exc:
            if not is_locked_error(exc) or attempt == attempts - 1:
                raise
            session.rollback()
            time.sleep(min(base_delay * (2**attempt), max_delay))
    raise AssertionError("unreachable")


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        url = settings.database_url
        connect_args = {}
        if url.startswith("sqlite"):
            # 允许跨线程使用（worker 场景）
            connect_args = {"check_same_thread": False}
            # 确保目录存在
            settings.ensure_dirs()
        _engine = create_engine(url, future=True, connect_args=connect_args)

        if url.startswith("sqlite"):
            # pysqlite 默认会在 DML 前隐式 BEGIN，导致 SAVEPOINT（嵌套事务）
            # 状态错乱，表现为 "unable to open database file"。
            # 官方配方：关闭隐式 BEGIN，改由 SQLAlchemy 显式发 BEGIN。
            @event.listens_for(_engine, "connect")
            def _sqlite_on_connect(dbapi_conn, _record):  # pragma: no cover - 驱动细节
                dbapi_conn.isolation_level = None
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA synchronous=NORMAL")
                # Windows 上文件可能被短暂占用，给 SQLite 重试窗口
                cur.execute(f"PRAGMA busy_timeout={_busy_timeout_ms}")
                # 语句日志等临时数据放内存：Git Bash 下 TMP=/tmp 对原生 SQLite 无效
                # （解析为不存在的 C:\tmp），带外键检查的 DELETE 建临时文件失败会报
                # "unable to open database file"。
                cur.execute("PRAGMA temp_store=MEMORY")
                cur.close()

            @event.listens_for(_engine, "begin")
            def _sqlite_begin(conn):  # pragma: no cover - 驱动细节
                if _immediate_writes:
                    conn.exec_driver_sql("BEGIN IMMEDIATE")
                else:
                    conn.exec_driver_sql("BEGIN")

    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    """事务性会话：正常提交，异常回滚。"""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# 已发布过的模型上后加的列。SQLAlchemy 的 create_all 只建缺失的表，
# 不会给已存在的表补列，因此新列必须在启动时显式补上。
# 这是过渡方案：正式迁移走 Alembic（见 pyproject 待办），
# 在此之前用这份清单保证"升级代码后不需要重建数据库"。
_ADDED_COLUMNS: list[tuple[str, str, str]] = [
    # (表名, 列名, 列定义)
    ("field_override", "attrs", "JSON"),
    ("review_task", "parse_run_id", "INTEGER"),
]


def _ensure_added_columns(engine) -> list[str]:
    """给已存在的表补上后加的列。幂等。返回实际执行的变更。"""
    from sqlalchemy import inspect, text

    applied: list[str] = []
    with engine.begin() as conn:
        inspector = inspect(conn)
        existing_tables = set(inspector.get_table_names())
        for table, column, ddl in _ADDED_COLUMNS:
            if table not in existing_tables:
                continue  # 表还不存在时 create_all 会带着新列一起建
            columns = {c["name"] for c in inspector.get_columns(table)}
            if column in columns:
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
            applied.append(f"{table}.{column}")
    return applied


def init_db() -> None:
    """建表 + 补齐后加的列。

    Phase 1 用 create_all；正式迁移引入 Alembic 之前，
    _ADDED_COLUMNS 负责让已有数据库平滑升级。
    """
    from . import models  # noqa: F401  确保模型已注册

    engine = get_engine()
    # 多进程并发跑批时，别的进程可能长时间持有写锁；create_all 与补列都幂等，
    # 撞锁退避重试，避免进程在启动阶段直接失败。
    for attempt in range(8):
        try:
            models.Base.metadata.create_all(engine)
            _ensure_added_columns(engine)
            return
        except OperationalError as exc:
            if not is_locked_error(exc) or attempt == 7:
                raise
            time.sleep(min(0.5 * (2**attempt), 8.0))


@functools.lru_cache(maxsize=1)
def ensure_initialized() -> None:
    """进程内只初始化一次，供 API 的每请求依赖调用。

    API 的每个请求都会走到数据库依赖：create_all + 补列虽然幂等，
    但没有必要每请求都跑一遍，因此把首次调用的结果缓存下来。
    CLI 仍在命令开头直接调 init_db()，语义不变。
    """
    init_db()
