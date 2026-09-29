"""内容寻址对象存储。

本地实现落盘到 data_dir/artifacts/ab/cd/<sha256><ext>，与 S3/MinIO 的
key 布局保持一致，便于后续切换到对象存储而无需改动调用方。
"""

from __future__ import annotations

import mimetypes
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
        return any(prefix.glob(f"{sha256}*"))

    def put_bytes(self, data: bytes, mime: str | None = None) -> StoredObject:
        digest = sha256_bytes(data)
        if mime is None:
            mime = "application/octet-stream"
        key = self.key_for(digest, mime)
        path = self.path_for_key(key)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            # 原子写：先写临时文件再改名，避免半截文件
            tmp = path.with_suffix(path.suffix + ".part")
            tmp.write_bytes(data)
            tmp.replace(path)
        return StoredObject(
            sha256=digest, size_bytes=len(data), storage_key=key, mime=mime, path=path
        )

    def guess_mime(self, filename: str) -> str | None:
        return mimetypes.guess_type(filename)[0]
