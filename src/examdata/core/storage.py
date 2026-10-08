"""内容寻址对象存储。

本地实现落盘到 data_dir/artifacts/ab/cd/<sha256><ext>，与 S3/MinIO 的
key 布局保持一致，便于后续切换到对象存储而无需改动调用方。
"""

from __future__ import annotations

import mimetypes
import os
import tempfile
import logging
from dataclasses import dataclass
from pathlib import Path

from .config import get_settings
from .ids import sha256_bytes

_EXT_BY_MIME = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "text/html": ".html",
    "application/json": ".json",
}


@dataclass
class StoredObject:
    sha256: str
    size_bytes: int
    storage_key: str
    mime: str | None
    path: Path
    created: bool = False


class ContentAddressedStore:
    """按内容哈希存储，天然去重。"""

    def __init__(self, root: Path | None = None) -> None:
        settings = get_settings()
        self.root = root or settings.artifacts_dir
        self.root.mkdir(parents=True, exist_ok=True)

    def key_for(self, sha256: str, mime: str | None = None) -> str:
        ext = _EXT_BY_MIME.get((mime or "").split(";")[0].strip(), "")
        return f"{sha256[:2]}/{sha256[2:4]}/{sha256}{ext}"

    def path_for_key(self, storage_key: str) -> Path:
        return self.root / storage_key

    def exists(self, sha256: str) -> bool:
        prefix = self.root / sha256[:2] / sha256[2:4]
        if not prefix.exists():
            return False
        # .part 是原子写的中间文件：只见到它就说明写入未完成，不算已存在
        return any(p for p in prefix.glob(f"{sha256}*") if p.suffix != ".part")

    def put_bytes(self, data: bytes, mime: str | None = None) -> StoredObject:
        digest = sha256_bytes(data)
        if mime is None:
            mime = "application/octet-stream"
        key = self.key_for(digest, mime)
        path = self.path_for_key(key)
        created = False
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".part", delete=False) as stream:
                tmp = Path(stream.name)
                stream.write(data)
            try:
                try:
                    os.link(tmp, path)  # publish atomically without replacing another writer's object
                    created = True
                except FileExistsError:
                    pass
            finally:
                tmp.unlink(missing_ok=True)
        return StoredObject(
            sha256=digest, size_bytes=len(data), storage_key=key, mime=mime, path=path, created=created
        )

    def guess_mime(self, filename: str) -> str | None:
        return mimetypes.guess_type(filename)[0]



def _object_lock_key(digest: str) -> int:
    return int.from_bytes(bytes.fromhex(digest[:16]), "big", signed=True)


def lock_transaction_object(session, digest: str) -> None:
    """Serialize PostgreSQL parser writers for a shared content-addressed object."""
    if session.get_bind().dialect.name == "postgresql":
        from sqlalchemy import select, func
        session.execute(select(func.pg_advisory_xact_lock(_object_lock_key(digest))))


def track_transaction_file(session, stored: StoredObject) -> None:
    """Clean newly published, unreferenced objects when the owning outer transaction ends.

    Savepoint failure waits until the outer transaction completes so uncommitted sibling
    references cannot be mistaken for orphans. Pre-existing objects are never candidates.
    """
    if not stored.created:
        return
    from sqlalchemy import event, select
    from .models import Artifact, Asset
    transaction = session.get_transaction()
    if transaction is None:
        raise RuntimeError("File tracking requires an active database transaction")
    batches = session.info.setdefault("parse_transaction_files", {})
    batches.setdefault(transaction, []).append(stored)
    if session.info.get("parse_file_cleanup_registered"):
        return
    session.info["parse_file_cleanup_registered"] = True

    def cleanup(db, ended):
        if ended.parent is not None:
            return
        objects = db.info["parse_transaction_files"].pop(ended, [])
        if not objects:
            return
        try:
            engine = db.get_bind()
            if engine.dialect.name == "sqlite":
                connection = engine.raw_connection()
                try:
                    connection.execute("BEGIN IMMEDIATE")
                    referenced = {row[0] for row in connection.execute("SELECT storage_key FROM artifact UNION SELECT storage_key FROM asset")}
                    for obj in objects:
                        if obj.storage_key not in referenced and obj.path.is_file() and sha256_bytes(obj.path.read_bytes()) == obj.sha256:
                            obj.path.unlink()
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
                finally:
                    connection.close()
            else:
                from sqlalchemy import func
                # Lock in deterministic order, including the reference check and unlink.
                with engine.begin() as conn:
                    for obj in sorted(objects, key=lambda item: item.sha256):
                        conn.execute(select(func.pg_advisory_xact_lock(_object_lock_key(obj.sha256))))
                        referenced = conn.scalar(select(Asset.id).where(Asset.storage_key == obj.storage_key).limit(1))
                        artifact = conn.scalar(select(Artifact.id).where(Artifact.storage_key == obj.storage_key).limit(1))
                        if referenced is None and artifact is None and obj.path.is_file() and sha256_bytes(obj.path.read_bytes()) == obj.sha256:
                            obj.path.unlink()
        except Exception as exc:
            # The database may already be committed; do not pretend commit rolled back.
            db.info.setdefault("parse_file_cleanup_errors", []).append(f"{type(exc).__name__}: {exc}")
            logging.getLogger(__name__).error("Parse file cleanup failed: %s", type(exc).__name__)

    event.listen(session, "after_transaction_end", cleanup)
