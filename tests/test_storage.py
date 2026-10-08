"""内容寻址存储的存在性判定测试。

`exists()` 同时决定"写入是否跳过"与"读取能否命中"：一旦把原子写的
中间文件（`<sha256>*.part`）算成已存在的对象，写入会被跳过、读取会
拿到半截文件。这里只覆盖这条边界，store 的 root 用 tmp_path，不碰
开发库的 .data/artifacts。
"""

from __future__ import annotations

from pathlib import Path

from examdata.core.ids import sha256_bytes
from examdata.core.storage import ContentAddressedStore

# --------------------------------------------------------------------------
# 布局与定位
# --------------------------------------------------------------------------


def test_key_layout_is_two_level_prefix(tmp_path):
    """root/aa/bb/<sha256><ext>：测试按此前缀定位文件，布局变了要立刻发现。"""
    store = ContentAddressedStore(root=tmp_path)
    digest = "ab" + "cd" + "0" * 60
    key = store.key_for(digest, "application/pdf")
    assert key == f"ab/cd/{digest}.pdf"
    assert store.path_for_key(key) == tmp_path / "ab" / "cd" / f"{digest}.pdf"


# --------------------------------------------------------------------------
# exists() 的三种状态
# --------------------------------------------------------------------------


def test_unknown_digest_is_absent(tmp_path):
    store = ContentAddressedStore(root=tmp_path)
    assert not store.exists(sha256_bytes(b"never stored"))


def test_partial_file_alone_is_not_present(tmp_path):
    """只见到 .part 说明写入未完成，不能算对象已存在。"""
    store = ContentAddressedStore(root=tmp_path)
    digest = sha256_bytes(b"interrupted upload")
    path = store.path_for_key(store.key_for(digest, "application/pdf"))
    path.parent.mkdir(parents=True)
    path.with_suffix(path.suffix + ".part").write_bytes(b"%PDF-1.7 truncated")
    assert not store.exists(digest)


def test_finished_file_is_present(tmp_path):
    store = ContentAddressedStore(root=tmp_path)
    digest = sha256_bytes(b"complete upload")
    path = store.path_for_key(store.key_for(digest, "application/pdf"))
    path.parent.mkdir(parents=True)
    path.write_bytes(b"%PDF-1.7 complete")
    assert store.exists(digest)


# --------------------------------------------------------------------------
# 误判的实际后果：写入被跳过
# --------------------------------------------------------------------------


def test_interrupted_write_does_not_block_a_later_put(tmp_path):
    """残留 .part 时 put_bytes 必须真的落盘，而不是因误判已存在而跳过。"""
    store = ContentAddressedStore(root=tmp_path)
    data = b"%PDF-1.7 real content"
    digest = sha256_bytes(data)
    path = store.path_for_key(store.key_for(digest, "application/pdf"))
    path.parent.mkdir(parents=True)
    path.with_suffix(path.suffix + ".part").write_bytes(b"%PDF-1.7 truncated")

    obj = store.put_bytes(data, "application/pdf")

    assert obj.sha256 == digest
    assert path.read_bytes() == data
    assert store.exists(digest)
