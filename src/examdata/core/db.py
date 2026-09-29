"""数据库会话管理。

本地开发用 SQLite，生产用 PostgreSQL。Schema 保持可移植（不使用任何 Postgres 专有类型），
向量检索通过可插拔的 SimilarityIndex 提供，避免绑定 pgvector。
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings

_engine = None
_SessionLocal: sessionmaker[Session] | None = None


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
                cur.execute("PRAGMA busy_timeout=10000")
                cur.close()

            @event.listens_for(_engine, "begin")
            def _sqlite_begin(conn):  # pragma: no cover - 驱动细节
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
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
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
    models.Base.metadata.create_all(engine)
    _ensure_added_columns(engine)
