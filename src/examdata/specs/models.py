"""Spec 解析的数据模型。

一套 spec 解析结果 = 一个 ParsedSpec：若干 Unit，每个 Unit 下挂一棵节点树。
节点可以任意嵌套；`code` 是 spec 上印的编号（如 "1.1"、"1.3.1"），
`label` 是入库用的全局标签（如 "WBI11-1.1"），同一考试局内唯一。

编号规则：
  - `label` 必须等于 `unit_key + "-" + code`（code 为空时等于 unit_key）；
  - `code` 允许字母（如 "1A"）、数字、点、连字符、括号；
  - 同一文件内 label 不得重复。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterator, Optional

SCHEMA_VERSION = "1"

_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._()\-]*$")
_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._()\-]*$")


@dataclass
class SpecNode:
    code: str
    label: str
    title: str
    text: str = ""
    page: Optional[int] = None
    children: list["SpecNode"] = field(default_factory=list)

    def walk(self) -> Iterator["SpecNode"]:
        yield self
        for child in self.children:
            yield from child.walk()

    def to_dict(self) -> dict:
        out = {"code": self.code, "label": self.label, "title": self.title, "text": self.text}
        if self.page is not None:
            out["page"] = self.page
        if self.children:
            out["children"] = [c.to_dict() for c in self.children]
        return out

    @staticmethod
    def from_dict(data: dict) -> "SpecNode":
        return SpecNode(
            code=data.get("code", ""),
            label=data["label"],
            title=data.get("title", ""),
            text=data.get("text", ""),
            page=data.get("page"),
            children=[SpecNode.from_dict(c) for c in data.get("children", [])],
        )


@dataclass
class SpecUnit:
    code: str
    name: str
    unit_key: str
    nodes: list[SpecNode] = field(default_factory=list)

    def walk(self) -> Iterator[SpecNode]:
        for node in self.nodes:
            yield from node.walk()

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "unit_key": self.unit_key,
            "nodes": [n.to_dict() for n in self.nodes],
        }

    @staticmethod
    def from_dict(data: dict) -> "SpecUnit":
        return SpecUnit(
            code=data.get("code", ""),
            name=data.get("name", ""),
            unit_key=data["unit_key"],
            nodes=[SpecNode.from_dict(n) for n in data.get("nodes", [])],
        )


@dataclass
class ParsedSpec:
    subject: str
    title: str
    parser: str
    spec_url: str = ""
    spec_sha256: str = ""
    units: list[SpecUnit] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def all_nodes(self) -> Iterator[tuple[SpecUnit, SpecNode]]:
        for unit in self.units:
            for node in unit.walk():
                yield unit, node

    def counts(self) -> dict[str, int]:
        nodes = list(self.all_nodes())
        return {
            "units": len(self.units),
            "nodes": len(nodes),
            "leaves": sum(1 for _, n in nodes if not n.children),
            "issues": len(self.issues),
        }

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "subject": self.subject,
            "title": self.title,
            "parser": self.parser,
            "spec_url": self.spec_url,
            "spec_sha256": self.spec_sha256,
            "units": [u.to_dict() for u in self.units],
            "issues": list(self.issues),
        }

    @staticmethod
    def from_dict(data: dict) -> "ParsedSpec":
        return ParsedSpec(
            subject=data["subject"],
            title=data.get("title", ""),
            parser=data.get("parser", ""),
            spec_url=data.get("spec_url", ""),
            spec_sha256=data.get("spec_sha256", ""),
            units=[SpecUnit.from_dict(u) for u in data.get("units", [])],
            issues=list(data.get("issues", [])),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
        )

    def validate(self) -> list[str]:
        """结构校验：返回问题列表（空 = 通过）。"""
        problems: list[str] = []
        if not self.units:
            problems.append("no units parsed")
        seen: set[str] = set()
        for unit in self.units:
            if not unit.unit_key:
                problems.append(f"unit {unit.code!r} missing unit_key")
            if not unit.name.strip():
                problems.append(f"unit {unit.code!r} missing name")
            for node in unit.walk():
                if not node.label:
                    problems.append(f"unit {unit.code!r}: node without label")
                    continue
                if node.label == unit.unit_key:
                    problems.append(
                        f"unit {unit.unit_key!r}: node label collides with unit key"
                    )
                if node.label in seen:
                    problems.append(f"duplicate label {node.label!r}")
                seen.add(node.label)
                expected = f"{unit.unit_key}-{node.code}" if node.code else unit.unit_key
                if node.label != expected:
                    problems.append(
                        f"label {node.label!r} != unit_key-code {expected!r}"
                    )
                if not _LABEL_RE.match(node.label):
                    problems.append(f"label {node.label!r} has invalid characters")
                if node.code and not _CODE_RE.match(node.code):
                    problems.append(f"code {node.code!r} has invalid characters")
                if not node.title.strip():
                    problems.append(f"node {node.label!r} missing title")
        return problems
