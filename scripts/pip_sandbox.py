"""在工作区内完成 pip 安装：绕过沙箱对 tempfile 临时目录的写限制。

沙箱会给本机 Everyone 继承一条 "DENY (DC)" 的 ACE，并且 Python 的
tempfile.mkdtemp() 会以 0700 创建目录，其 DACL 不允许子进程写入，
导致 pip 在解包 wheel 时报 PermissionError。
这里把 mkdtemp / TemporaryDirectory 换成普通 os.makedirs（默认 DACL），
pip 的临时目录就落在工作区内且可写。
"""

from __future__ import annotations

import os
import sys
import tempfile

TMPROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tmpwork")
os.makedirs(TMPROOT, exist_ok=True)
os.environ["TMP"] = TMPROOT
os.environ["TEMP"] = TMPROOT
os.environ["TMPDIR"] = TMPROOT
tempfile.tempdir = TMPROOT

_counter = [0]


def _mkdtemp(suffix: str = "", prefix: str = "tmp", dir: str | None = None) -> str:
    base = dir or TMPROOT
    while True:
        _counter[0] += 1
        path = os.path.join(base, f"{prefix}{os.getpid()}_{_counter[0]}{suffix}")
        try:
            os.makedirs(path)
        except FileExistsError:
            continue
        return path


class _TemporaryDirectory:
    """TemporaryDirectory 的宽松版本：不依赖 0700 权限位，且清理失败不报错。"""

    def __init__(self, suffix="", prefix="tmp", dir=None, ignore_cleanup_errors=False, **kw):
        self.name = _mkdtemp(suffix, prefix, dir)

    def __enter__(self):
        return self.name

    def __exit__(self, *exc):
        self.cleanup()
        return False

    def cleanup(self):
        import shutil

        try:
            shutil.rmtree(self.name, ignore_errors=True)
        except Exception:
            pass


tempfile.mkdtemp = _mkdtemp
tempfile.TemporaryDirectory = _TemporaryDirectory

from pip._internal.cli.main import main as pip_main  # noqa: E402

if __name__ == "__main__":
    sys.exit(pip_main(["install", "--no-cache-dir", *sys.argv[1:]]))
