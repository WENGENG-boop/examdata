"""CLI 参数守卫：非法参数必须在落到查询层之前被拦下。

三类守卫：

1. `review-list --status` 只接受 open / in_progress / done / dismissed——
   未知取值在 `list_reviews` 里只表现为"查不到行"，会被误读成"队列为空"。
2. `search-papers` / `search-questions` 的 `--limit` 下限为 1——
   否则会落到查询层的 `_check_page`，抛的是 ValueError（整屏 traceback），
   而不是一条用法错误。
3. `sample-questions` 必须给出 `--count` 或 `--marks` 之一——
   两个都不给等于"把池子全倒出来"，不是抽题。

这些用例都在参数校验阶段退出，不会连库，空库场景照常可跑。
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from examdata import cli
from examdata.cli import app as cli_app
from examdata.core.config import Settings
from examdata.core.models import (
    Artifact, Base, Board, DocClassification, Document, DocumentRevision,
    FieldOverride, Paper, ParseRun, ProvenanceEdge, Qualification, Question,
    ReviewTask, Subject, ValidationFinding,
)

VALID_STATUSES = ("open", "in_progress", "done", "dismissed")


@pytest.mark.parametrize("as_json", [False, True])
def test_reparse_rollback_exits_unsuccessfully(monkeypatch, as_json):
    import examdata.governance as governance

    @contextmanager
    def private_session():
        yield object()

    monkeypatch.setattr(cli, "init_db", lambda: None)
    monkeypatch.setattr(cli, "session_scope", private_session)
    monkeypatch.setattr(governance, "reparse_documents", lambda *a, **kw: {
        "aborted": True, "reason": "protected data conflict",
    })
    result = CliRunner().invoke(cli_app, ["reparse"] + (["--json"] if as_json else []))
    assert result.exit_code == 1, result.output
    assert "protected data conflict" in result.output
    if as_json:
        assert json.loads(result.output)["aborted"] is True


@pytest.mark.parametrize("status", ["bogus", "pending"])
def test_review_list_rejects_unknown_status(status):
    """非法 --status 退出码为 1，提示里要列出全部合法取值。"""
    result = CliRunner().invoke(cli_app, ["review-list", "--status", status])

    assert result.exit_code == 1, result.output
    assert status in result.output
    for valid in VALID_STATUSES:
        assert valid in result.output


@pytest.mark.parametrize("limit", ["0", "-3"])
def test_search_papers_rejects_non_positive_limit(limit):
    """--limit 非正数由参数层拒绝（click 用法错误码 2），不进入查询层。"""
    result = CliRunner().invoke(cli_app, ["search-papers", "--limit", limit])

    assert result.exit_code == 2, result.output
    assert "--limit" in result.output


@pytest.mark.parametrize("limit", ["0", "-3"])
def test_search_questions_rejects_non_positive_limit(limit):
    result = CliRunner().invoke(cli_app, ["search-questions", "--limit", limit])

    assert result.exit_code == 2, result.output
    assert "--limit" in result.output


def test_sample_questions_requires_count_or_marks():
    """两个目标都不给时退出，而不是退化成"倒出全部叶子题"。"""
    result = CliRunner().invoke(cli_app, ["sample-questions"])

    assert result.exit_code == 1, result.output
    assert "--count" in result.output
    assert "--marks" in result.output


@pytest.mark.parametrize("limit", ["0", "-1"])
def test_review_list_rejects_non_positive_limit(limit):
    result = CliRunner().invoke(cli_app, ["review-list", "--limit", limit])

    assert result.exit_code == 2, result.output
    assert "--limit" in result.output


@pytest.mark.parametrize("option, value", [("--count", "0"), ("--count", "201"), ("--marks", "0"), ("--marks", "301")])
def test_sample_questions_rejects_out_of_range_target(option, value):
    result = CliRunner().invoke(cli_app, ["sample-questions", option, value])

    assert result.exit_code == 1, result.output
    assert option in result.output
