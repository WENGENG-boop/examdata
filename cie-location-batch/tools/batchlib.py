"""CIE 定位批次共享状态层。

只做三件事：路径常量、原子 JSON 读写、追加式日志。
所有脚本共用，保证重启后状态不丢。
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

BATCH_ROOT = Path("C:/Users/weo/Desktop/api/cie-location-batch")
REPO = Path("C:/Users/weo/Desktop/api/examdata")
SEED_DISCOVERY = Path("C:/Users/weo/Desktop/api/cie_all_discovery.json")
SERVICE_DATA_DIR = Path("C:/Users/weo/Desktop/api/examdata/.pytest_cache/callable-api")
BASE_URL = "http://127.0.0.1:8000"
SOURCE = "https://cie.fraft.cn"
RENUM_URL = f"{SOURCE}/obj/Common/Fetch/renum"
COMBO_URL = f"{SOURCE}/obj/Common/Subject/combo"

YEAR_START = 2000
YEAR_END = 2026
SEASONS = ("Mar", "Jun", "Nov")
SEASON_LETTER = {"Mar": "m", "Jun": "s", "Nov": "w"}
LETTER_SEASON = {"m": "Mar", "s": "Jun", "w": "Nov"}

INDEXES = BATCH_ROOT / "indexes"
TMP = BATCH_ROOT / "tmp"
TOOLS = BATCH_ROOT / "tools"
WORK = BATCH_ROOT / "work"

SUBJECTS = BATCH_ROOT / "subjects.json"
GRID = BATCH_ROOT / "catalogue-grid.json"
PAPERS = BATCH_ROOT / "papers.json"
CHECKPOINT = BATCH_ROOT / "checkpoint.json"
ERRORS = BATCH_ROOT / "errors.jsonl"
VERIFICATION = BATCH_ROOT / "verification.jsonl"
CLEANUP = BATCH_ROOT / "cleanup.jsonl"
SUMMARY = BATCH_ROOT / "summary.json"

REPO_SRC = str(REPO / "src")

UPSTREAM_MUTEX = "Global\\examdata_cie_upstream"
SCAN_STALE_SECONDS = 180
SCAN_ACTIVE_STAGES = {"scan_launched", "scanning_full", "scanning_probe", "scanning"}


@contextlib.contextmanager
def upstream_lock(timeout: float = 900.0, name: str = UPSTREAM_MUTEX):
    """跨进程互斥，保证任何时刻只有一个进程访问上游（扫描或下载）。

    用 Windows 具名互斥体；进程异常退出时内核自动释放，不会留下死锁。
    """
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CreateMutexW.argtypes = (wintypes.LPCVOID, wintypes.BOOL, wintypes.LPCWSTR)
    kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel32.ReleaseMutex.argtypes = (wintypes.HANDLE,)
    handle = kernel32.CreateMutexW(None, False, name)
    if not handle:
        raise OSError(f"CreateMutexW 失败: {ctypes.get_last_error()}")
    wait = kernel32.WaitForSingleObject(handle, int(timeout * 1000))
    if wait not in (0x00000000, 0x00000080):  # WAIT_OBJECT_0 / WAIT_ABANDONED
        kernel32.CloseHandle(handle)
        raise TimeoutError(f"等待上游互斥体超时（{timeout}s）")
    try:
        yield
    finally:
        kernel32.ReleaseMutex(handle)
        kernel32.CloseHandle(handle)


def scan_active() -> dict:
    """扫描进程是否还在跑（用 checkpoint 的新鲜度判断，避免误判）。"""
    ck = read_json(CHECKPOINT, {}) or {}
    stage = ck.get("stage") or ""
    if stage not in SCAN_ACTIVE_STAGES:
        return {"active": False, "stage": stage}
    try:
        age = time.time() - CHECKPOINT.stat().st_mtime
    except OSError:
        return {"active": False, "stage": stage}
    return {"active": age < SCAN_STALE_SECONDS, "stage": stage, "age_seconds": round(age, 1),
            "cell": ck.get("current_cell")}


def ensure_dirs() -> None:
    for p in (BATCH_ROOT, INDEXES, TMP, TOOLS, WORK):
        p.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def atomic_write_json(path: Path, payload, *, attempts: int = 60) -> None:
    # Windows 上 os.replace 在目标文件被其他进程短暂打开时抛 WinError 5，退避重试
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".part")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        for i in range(attempts):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if i == attempts - 1:
                    raise
                time.sleep(min(0.05 * (i + 1), 0.5))
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_bytes().decode("utf-8"))


def read_jsonl(path: Path) -> list:
    """逐行读 JSONL；空行与坏行跳过，不抛异常。"""
    if not path.exists():
        return []
    out = []
    for line in path.read_bytes().decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
    with open(path, "ab") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())


def append_many_jsonl(path: Path, records) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "ab") as fh:
        for rec in records:
            fh.write((json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8"))
        fh.flush()
        os.fsync(fh.fileno())


def set_checkpoint(**fields) -> None:
    state = read_json(CHECKPOINT, {}) or {}
    state.update(fields)
    state["updated_at"] = now_iso()
    atomic_write_json(CHECKPOINT, state)


def paper_key(subject: str, year: int, season: str, paper: str) -> str:
    return f"{subject}/{year}/{season}/{paper}"


def paper_dir(subject: str, year: int, season: str, paper: str) -> Path:
    return TMP / subject / f"{year}-{season}-{paper}"


def index_dir(subject: str, year: int, season: str, paper: str) -> Path:
    return INDEXES / subject / f"{year}-{season}-{paper}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def free_bytes(path: Path = BATCH_ROOT) -> int:
    return shutil.disk_usage(str(path)).free


def dir_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def setup_repo_import() -> None:
    if REPO_SRC not in sys.path:
        sys.path.insert(0, REPO_SRC)
