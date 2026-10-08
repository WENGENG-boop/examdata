"""examdata.specs 测试：spec 解析（模型 / 共用工具 / 装载 / 批处理），全离线。

覆盖范围：

- `models`：节点树 walk/counts、to_dict/from_dict 往返、validate 各类结构问题；
- `common`：页切片与页码回查、噪声清理、内容区定位、编号块切分、标题提取、
  编号冲突修正（spec 自身编号缺陷）；
- `loader`：把 ParsedSpec 装载进临时 SQLite（单元/主题/知识点节点类型与父子链、
  幂等 upsert、标题裁定、文本截断）、装载前一致性检查（同标签同名 / 冲突 / 缺失）；
- `runner`：`_merge` 合并、`parse_slug` 写文件与错误路径。

全部用临时目录与临时数据库，不依赖本地语料与网络。
"""

from __future__ import annotations

import json
import re

import pymupdf
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core.models import Base, Board, Qualification, Subject, TaxonomyNode
from examdata.specs import ParsedSpec, SpecNode, SpecUnit
from examdata.specs import common, loader, runner


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------


def _mini_spec() -> ParsedSpec:
    child = SpecNode(code="1.1", label="WBI11-1.1", title="Molecules", text="body", page=2)
    topic = SpecNode(code="1", label="WBI11-1", title="Topic", children=[child])
    unit = SpecUnit(code="1", name="Unit 1", unit_key="WBI11", nodes=[topic])
    return ParsedSpec(
        subject="ial18-biology",
        title="Biology",
        parser="test",
        spec_url="https://example.test/spec.pdf",
        spec_sha256="abc123",
        units=[unit],
        issues=["demo issue"],
    )


def test_walk_is_depth_first_and_complete():
    spec = _mini_spec()
    unit = spec.units[0]
    assert [n.label for n in unit.walk()] == ["WBI11-1", "WBI11-1.1"]
    pairs = list(spec.all_nodes())
    assert [(u.unit_key, n.label) for u, n in pairs] == [
        ("WBI11", "WBI11-1"),
        ("WBI11", "WBI11-1.1"),
    ]


def test_counts_reports_units_nodes_leaves_issues():
    assert _mini_spec().counts() == {"units": 1, "nodes": 2, "leaves": 1, "issues": 1}


def test_dict_roundtrip_is_lossless():
    spec = _mini_spec()
    again = ParsedSpec.from_dict(spec.to_dict())
    assert again.to_dict() == spec.to_dict()
    assert again.units[0].nodes[0].children[0].page == 2


def test_validate_passes_for_well_formed_spec():
    assert _mini_spec().validate() == []


def test_validate_flags_empty_spec():
    assert ParsedSpec(subject="s", title="T", parser="p").validate() == ["no units parsed"]


def test_validate_flags_unit_and_node_problems():
    def build(unit_key="WBI11", unit_name="Unit 1", nodes=None):
        unit = SpecUnit(
            code="1",
            name=unit_name,
            unit_key=unit_key,
            nodes=nodes if nodes is not None else [],
        )
        return ParsedSpec(subject="s", title="T", parser="p", units=[unit])

    assert "missing unit_key" in " ".join(build(unit_key="").validate())
    assert "missing name" in " ".join(build(unit_name=" ").validate())

    # 节点 label 与 unit_key 撞车
    collide = build(nodes=[SpecNode(code="", label="WBI11", title="T")])
    assert any("collides with unit key" in p for p in collide.validate())

    # label != unit_key-code
    mismatch = build(nodes=[SpecNode(code="1.1", label="WBI11-9.9", title="T")])
    assert any("!= unit_key-code" in p for p in mismatch.validate())

    # 重复 label
    dup = build(
        nodes=[
            SpecNode(code="1.1", label="WBI11-1.1", title="A"),
            SpecNode(code="1.1", label="WBI11-1.1", title="B"),
        ]
    )
    assert any("duplicate label" in p for p in dup.validate())

    # 非法字符 / 缺标题 / 缺 label
    bad_chars = build(nodes=[SpecNode(code="1.1", label="WBI11-1.1!", title="T")])
    assert any("invalid characters" in p for p in bad_chars.validate())
    no_title = build(nodes=[SpecNode(code="1.1", label="WBI11-1.1", title="  ")])
    assert any("missing title" in p for p in no_title.validate())
    no_label = build(nodes=[SpecNode(code="", label="", title="T")])
    assert any("node without label" in p for p in no_label.validate())


# ---------------------------------------------------------------------------
# common：文本工具
# ---------------------------------------------------------------------------


def test_page_slices_and_page_of_offset():
    text = "lead<<<PAGE 1>>>one<<<PAGE 2>>>two"
    assert common.page_slices(text) == [(1, "one"), (2, "two")]
    assert common.page_of_offset(text, 0) == 1
    assert common.page_of_offset(text, text.index("one")) == 1
    assert common.page_of_offset(text, text.index("two")) == 2


def test_extract_text_emits_page_markers(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello spec")
    pdf = tmp_path / "mini.pdf"
    doc.save(pdf)
    doc.close()
    text = common.extract_text(pdf)
    assert "<<<PAGE 1>>>" in text
    assert "Hello spec" in text


def test_clean_line_normalizes_nbsp_and_trailing_space():
    assert common.clean_line("abc\u00a0  ") == "abc"


def test_clean_block_drops_furniture_and_page_marks():
    text = (
        "Pearson Edexcel International Advanced Level\n"
        "<<<PAGE 5>>>\n"
        "Real content\n"
        "12\n"
        "© Pearson Education Limited 2024\n"
        "\n\n\n"
        "More"
    )
    assert common.clean_block(text) == "Real content\nMore"


def test_content_span_uses_last_start_and_first_end_after_it():
    text = "TOC Biology content here\nBody\nBiology content here\nDetails\nEND"
    begin, end = common.content_span(text, "Biology content", "END")
    assert begin == text.rindex("Biology content")
    assert end == text.index("END")
    assert common.slice_content(text, "Biology content", "END") == text[begin:end]


def test_content_span_raises_when_markers_missing():
    with pytest.raises(ValueError, match="content start not found"):
        common.content_span("no such marker", "Biology content")
    with pytest.raises(ValueError, match="content end not found"):
        common.content_span("Biology content\nbody", "Biology content", "END")


def test_split_blocks_cuts_on_marker_and_keeps_offsets():
    region = "1.1 First\nbody1\n1.2 Second\nbody2"
    marker_re = re.compile(r"(?m)^(?P<code>\d+\.\d+) ")
    blocks = common.split_blocks(region, marker_re, base_offset=5)
    assert [b.code for b in blocks] == ["1.1", "1.2"]
    assert blocks[0].text == "First\nbody1\n"
    assert blocks[1].text == "Second\nbody2"
    assert blocks[0].offset == 5
    assert blocks[1].offset == 5 + region.index("1.2")


def test_make_node_composes_label():
    node = common.make_node("WBI11", "1.1", "Molecules", "text", page=3)
    assert (node.label, node.code, node.page) == ("WBI11-1.1", "1.1", 3)
    unit_node = common.make_node("WBI11", "", "Unit", "")
    assert unit_node.label == "WBI11"


def test_first_sentence_and_title_from_block():
    assert common.first_sentence("This is one. This is two.") == "This is one."
    assert common.first_sentence("") == ""
    assert common.first_sentence("A" * 200, limit=10) == "A" * 10
    assert common.title_from_block("Short\nSecond part") == "Short Second part"
    assert common.title_from_block("This is a longer title\nbody") == "This is a longer title"
    assert common.title_from_block("") == ""


def test_unit_key_from_codes():
    text = "Unit 1: WBI11/01 content\nUnit 3. WPH11/01"
    assert common.unit_key_from_codes(text, "1") == "WBI11"
    assert common.unit_key_from_codes(text, "3") == "WPH11"
    assert common.unit_key_from_codes("nothing here", "2", default_prefix="DEF") == "DEF"


def test_dedupe_codes_preserves_order():
    assert common.dedupe_codes(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]


def test_find_units_returns_codes_names_offsets():
    region = "Unit 1: Biology\nstuff\nUnit 2: Chemistry"
    unit_re = re.compile(r"Unit (?P<code>\d+): (?P<name>[^\n]+)")
    found = common.find_units(region, unit_re, base_offset=100)
    assert [(c, n) for c, n, _ in found] == [("1", "Biology"), ("2", "Chemistry")]
    assert found[1][2] == 100 + region.index("Unit 2")


def test_cut_regions_yields_consecutive_ranges():
    assert list(common.cut_regions("abcdef", [0, 2, 4])) == [(0, 2), (2, 4), (4, 6)]


def test_marker_blocks_skip_marker_line():
    region = "Head\nA-1 Topic one\nbody a\nA-2 Topic two\nbody b"
    m1, m2 = region.index("A-1"), region.index("A-2")
    out = common.marker_blocks(
        region,
        [(m1, "topic", "A-1", "Topic one"), (m2, "topic", "A-2", "Topic two")],
    )
    assert out[0] == ("topic", "A-1", "Topic one", "body a\n", m1)
    assert out[1] == ("topic", "A-2", "Topic two", "body b", m2)


def test_normalize_code():
    assert common.normalize_code("1 . 2") == "1.2"
    assert common.normalize_code("1–2") == "1-2"
    assert common.normalize_code(" 3.4 ") == "3.4"


def test_resolve_code_conflicts_fixes_topic_mismatch_and_duplicates():
    issues: list[str] = []
    out = common.resolve_code_conflicts(
        ["2.1", "1.2", "1.2"], ["1", "1", None], issues, where="demo"
    )
    assert out == ["1.1", "1.2", "1.3"]
    assert len(issues) == 2
    assert "does not match its topic" in issues[0]
    assert "duplicate code" in issues[1]

    issues2: list[str] = []
    out2 = common.resolve_code_conflicts(["1A", "1A"], [None, None], issues2, where="demo")
    assert out2 == ["1A", "1A.2"]
    assert len(issues2) == 1


# ---------------------------------------------------------------------------
# loader：入库与一致性检查
# ---------------------------------------------------------------------------


@pytest.fixture()
def session(tmp_path):
    engine = create_engine("sqlite:///" + (tmp_path / "specs.db").as_posix())
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Board(key="edexcel", name="Pearson Edexcel"))
        session.flush()
        yield session


def _flat_spec(
    *,
    unit_key: str = "WBI11",
    node_code: str = "1.1",
    node_title: str = "Molecules",
    node_text: str = "body",
    page: int | None = 5,
    title: str = "Demo spec",
) -> ParsedSpec:
    node = SpecNode(
        code=node_code, label=f"{unit_key}-{node_code}", title=node_title, text=node_text, page=page
    )
    unit = SpecUnit(code="1", name="Unit 1", unit_key=unit_key, nodes=[node])
    return ParsedSpec(subject="ial18-biology", title=title, parser="test", units=[unit])


def _node(session: Session, code: str) -> TaxonomyNode:
    return session.scalar(select(TaxonomyNode).where(TaxonomyNode.code == code))


def test_load_spec_creates_qualification_subject_and_nodes(session):
    stats = loader.load_spec(session, "ial18-biology", _flat_spec())
    assert stats == {"created": 2, "updated": 0}

    board = session.scalar(select(Board).where(Board.key == "edexcel"))
    qual = session.scalar(
        select(Qualification).where(
            Qualification.board_id == board.id, Qualification.key == "edexcel-ial"
        )
    )
    assert qual is not None and qual.name == "Pearson Edexcel International A Level"

    subject = session.scalar(
        select(Subject).where(
            Subject.qualification_id == qual.id, Subject.code == "ial18-biology"
        )
    )
    assert subject is not None
    assert subject.slug == "ial18-biology"
    assert subject.attrs["counts"]["nodes"] == 1

    unit_row = _node(session, "WBI11")
    point_row = _node(session, "WBI11-1.1")
    assert unit_row.node_type == "unit" and unit_row.parent_id is None
    assert point_row.node_type == "point" and point_row.parent_id == unit_row.id
    assert point_row.source == "official"
    assert point_row.attrs["subject"] == "ial18-biology"
    assert point_row.attrs["page"] == 5
    assert point_row.attrs["text"] == "body"


def test_load_spec_assigns_topic_and_subtopic_types(session):
    leaf = SpecNode(code="1.1.1", label="WBI11-1.1.1", title="Leaf")
    sub = SpecNode(code="1.1", label="WBI11-1.1", title="Sub", children=[leaf])
    top = SpecNode(code="1", label="WBI11-1", title="Top", children=[sub])
    spec = ParsedSpec(
        subject="s",
        title="T",
        parser="p",
        units=[SpecUnit(code="1", name="U", unit_key="WBI11", nodes=[top])],
    )
    stats = loader.load_spec(session, "ial18-biology", spec)
    assert stats == {"created": 4, "updated": 0}
    assert _node(session, "WBI11-1").node_type == "topic"
    assert _node(session, "WBI11-1.1").node_type == "subtopic"
    assert _node(session, "WBI11-1.1.1").node_type == "point"
    assert _node(session, "WBI11-1.1.1").parent_id == _node(session, "WBI11-1.1").id


def test_load_spec_is_idempotent_and_updates(session):
    loader.load_spec(session, "ial18-biology", _flat_spec())
    stats = loader.load_spec(session, "ial18-biology", _flat_spec(title="Renamed"))
    assert stats == {"created": 0, "updated": 2}
    assert len(session.scalars(select(TaxonomyNode)).all()) == 2
    subject = session.scalar(select(Subject).where(Subject.code == "ial18-biology"))
    assert subject.title == "Renamed"


def test_load_spec_applies_title_overrides(session):
    spec = _flat_spec(unit_key="WFM01", node_code="5", node_title="Matrix algebra integration")
    loader.load_spec(session, "ial18-maths", spec)
    row = _node(session, "WFM01-5")
    assert row.name == "Matrix algebra"
    assert row.attrs["title_alt"] == ["Matrix algebra integration"]


def test_load_spec_caps_node_text(session):
    loader.load_spec(session, "ial18-biology", _flat_spec(node_text="x" * 5000))
    assert _node(session, "WBI11-1.1").attrs["text"] == "x" * loader.TEXT_CAP


def test_load_spec_requires_board(tmp_path):
    engine = create_engine("sqlite:///" + (tmp_path / "empty.db").as_posix())
    Base.metadata.create_all(engine)
    with Session(engine) as bare:
        with pytest.raises(RuntimeError, match="board"):
            loader.load_spec(bare, "ial18-biology", _flat_spec())


def _write_parsed(dirpath, slug: str, unit_key: str, code: str, title: str) -> None:
    node = SpecNode(code=code, label=f"{unit_key}-{code}", title=title)
    unit = SpecUnit(code="1", name="Unit 1", unit_key=unit_key, nodes=[node])
    payload = ParsedSpec(subject="demo", title="Demo", parser="p", units=[unit]).to_dict()
    (dirpath / f"{slug}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def test_check_specs_accepts_same_label_same_title(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "PARSED_DIR", tmp_path)
    _write_parsed(tmp_path, "alpha", "WBI11", "1.1", "Molecules")
    _write_parsed(tmp_path, "beta", "WBI11", "1.1", "Molecules")
    problems, notes = loader.check_specs(["alpha", "beta"])
    assert problems == [] and notes == []


def test_check_specs_flags_conflicting_titles(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "PARSED_DIR", tmp_path)
    _write_parsed(tmp_path, "alpha", "WBI11", "1.1", "Molecules")
    _write_parsed(tmp_path, "beta", "WBI11", "1.1", "Something else")
    problems, _ = loader.check_specs(["alpha", "beta"])
    assert any("冲突" in p for p in problems)


def test_check_specs_notes_override_resolved_version_diff(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "PARSED_DIR", tmp_path)
    _write_parsed(tmp_path, "old", "WFM01", "5", "Matrix algebra integration")
    _write_parsed(tmp_path, "new", "WFM01", "5", "Matrix algebra")
    problems, notes = loader.check_specs(["old", "new"])
    assert problems == []
    assert any("WFM01-5" in n for n in notes)


def test_check_specs_reports_missing_and_invalid(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "PARSED_DIR", tmp_path)
    problems, _ = loader.check_specs(["ghost"])
    assert any("缺失" in p for p in problems)
    _write_parsed(tmp_path, "bad", "WBI11", "1.1", "  ")
    problems, _ = loader.check_specs(["bad"])
    assert any("[validate]" in p for p in problems)


def test_merged_slugs_skips_shard_suffixes(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "PARSED_DIR", tmp_path)
    for name in ("a.json", "b-0.json", "c-1.json", "d-2.json", "e-3.json", "f.json"):
        (tmp_path / name).write_text("{}", encoding="utf-8")
    assert loader.merged_slugs() == ["a", "f"]


# ---------------------------------------------------------------------------
# runner：批处理
# ---------------------------------------------------------------------------


def _demo_parser(text, meta):
    meta = meta or {}
    unit_key = meta.get("unit_key", "WBI11")
    node = SpecNode(code="1.1", label=f"{unit_key}-1.1", title=text.strip())
    unit = SpecUnit(code="1", name="Unit 1", unit_key=unit_key, nodes=[node])
    return ParsedSpec(
        subject=meta.get("slug", "demo"),
        title="Demo",
        parser="demo",
        spec_sha256=meta.get("sha256", ""),
        units=[unit],
    )


def test_merge_concatenates_units_issues_and_sha():
    a = ParsedSpec(subject="a", title="A", parser="x", spec_sha256="aaa", units=[SpecUnit(code="1", name="U1", unit_key="WBI11")], issues=["i1"])
    b = ParsedSpec(subject="b", title="B", parser="x", spec_sha256="bbb", units=[SpecUnit(code="2", name="U2", unit_key="WBI12")], issues=["i2"])
    merged = runner._merge("demo", [a, b])
    assert merged.parser == "merge"
    assert merged.subject == "demo"
    assert merged.title == "A"
    assert merged.spec_sha256 == "aaa;bbb"
    assert [u.unit_key for u in merged.units] == ["WBI11", "WBI12"]
    assert merged.issues == ["i1", "i2"]


def test_parse_slug_writes_shards_and_merged(tmp_path, monkeypatch):
    text_dir = tmp_path / "text"
    text_dir.mkdir()
    out_dir = tmp_path / "out"
    (text_dir / "demo-0.txt").write_text("Topic A", encoding="utf-8")
    (text_dir / "demo-1.txt").write_text("Topic B", encoding="utf-8")
    monkeypatch.setattr(runner, "TEXT_DIR", text_dir)
    monkeypatch.setattr(runner, "OUT_DIR", out_dir)
    monkeypatch.setattr(runner, "PARSERS", {"demo": _demo_parser})

    manifest = {
        "demo-0": {"unit_key": "WBI11", "sha256": "s0"},
        "demo-1": {"unit_key": "WBI12", "sha256": "s1"},
    }
    ok, lines = runner.parse_slug("demo", manifest, write=True)
    assert ok, lines
    merged = json.loads((out_dir / "demo.json").read_text(encoding="utf-8"))
    assert len(merged["units"]) == 2
    assert merged["spec_sha256"] == "s0;s1"
    assert (out_dir / "demo-0.json").exists()
    assert (out_dir / "demo-1.json").exists()


def test_parse_slug_no_write_leaves_no_files(tmp_path, monkeypatch):
    text_dir = tmp_path / "text"
    text_dir.mkdir()
    (text_dir / "demo-0.txt").write_text("Topic A", encoding="utf-8")
    out_dir = tmp_path / "out"
    monkeypatch.setattr(runner, "TEXT_DIR", text_dir)
    monkeypatch.setattr(runner, "OUT_DIR", out_dir)
    monkeypatch.setattr(runner, "PARSERS", {"demo": _demo_parser})

    ok, _ = runner.parse_slug("demo", {"demo-0": {}}, write=False)
    assert ok
    assert not out_dir.exists()


def test_parse_slug_error_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "PARSERS", {"demo": _demo_parser})
    assert runner.parse_slug("nope", {}) == (False, ["nope: no parser registered"])
    assert runner.parse_slug("demo", {}) == (False, ["demo: no spec files in manifest"])


def test_parse_slug_isolates_parser_failure(tmp_path, monkeypatch):
    text_dir = tmp_path / "text"
    text_dir.mkdir()
    (text_dir / "demo-0.txt").write_text("x", encoding="utf-8")

    def boom(text, meta):
        raise ValueError("boom")

    monkeypatch.setattr(runner, "TEXT_DIR", text_dir)
    monkeypatch.setattr(runner, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(runner, "PARSERS", {"demo": boom})
    ok, lines = runner.parse_slug("demo", {"demo-0": {}}, write=True)
    assert not ok
    assert any("PARSE FAIL ValueError: boom" in line for line in lines)
    assert not (tmp_path / "out").exists()
