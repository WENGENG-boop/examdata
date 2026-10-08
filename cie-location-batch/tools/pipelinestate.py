"""`papers.json` 的旁路镜像，用于对抗并发整体重写。

背景（实测）：扫描进程会周期性把 `papers.json` 整个重写一遍，本工具写入的条目
会在 2 秒内被整条丢弃（写入后立即读存在，2 秒后消失）。本模块把同一份阶段状态
额外写入 `work/state.json`（扫描进程不碰该文件），并在 `papers.json` 丢条目时
提供回退读取与恢复。

`set_stage` / `patch` 是 `paperlib` 同名函数的替代：先写镜像，再尽力写 `papers.json`。
`entry` 优先返回 `papers.json` 的条目，丢失时回退到镜像并说明来源。
"""
from __future__ import annotations

import batchlib as B
import paperlib as P

STATE = B.WORK / "state.json"


def load_all() -> dict:
    data = B.read_json(STATE, {})
    return data if isinstance(data, dict) else {}


def load(key: str) -> dict | None:
    entry = load_all().get(key)
    return entry if isinstance(entry, dict) else None


def update(key: str, **fields) -> dict:
    state = load_all()
    entry = state.get(key)
    if not isinstance(entry, dict):
        entry = {"key": key}
    entry.update(fields)
    entry["mirror_at"] = B.now_iso()
    state[key] = entry
    B.atomic_write_json(STATE, state)
    return entry


def set_stage(key: str, stage: str, **fields) -> dict:
    update(key, stage=stage, stage_at=B.now_iso(), **fields)
    return P.set_stage(key, stage, **fields)


def patch(key: str, **fields) -> dict:
    update(key, **fields)
    return P.patch_paper(key, **fields)


def entry(key: str) -> tuple[dict, str]:
    """返回 (条目, 来源)。优先 `papers.json`，丢条目时回退到镜像。"""
    live = P.load_paper(key)
    if live:
        return live, "papers.json"
    mirrored = load(key)
    if mirrored:
        return mirrored, "work/state.json"
    return {}, "none"


def restore(key: str) -> dict:
    """把镜像合并回 `papers.json`（镜像字段优先），返回合并后的条目。"""
    mirrored = load(key)
    live = P.load_paper(key)
    if not mirrored:
        return live or {}
    merged = dict(live or {})
    merged.update(mirrored)
    merged.pop("mirror_at", None)
    merged["key"] = key
    payload = {k: v for k, v in merged.items() if k != "key"}
    return P.patch_paper(key, **payload)
