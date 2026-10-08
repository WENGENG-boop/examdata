"""构建 Edexcel 逐科「考试发放资料」机器可读 JSON（subjects_edexcel.json）。

范围全集 = 258 个实测科目页 / 233 个唯一 slug（第一遍 150 ok + 83 失败页经隔离

- `edexcel_sweep.json` / `edexcel_sweep_progress.json`：第一遍逐页结果；
- `edexcel_failed_page_classes.json` + `edexcel_live_pages_recovery.json`：83 失败页
  分类与记录级恢复（25 live + 58 dead；dead 中 56 ok + 2 无可用 facet）；
- `edexcel_capped_final.json`：3 个 capped 科（递归分区终稿）；
- `edexcel_dup_variants_sweep.json`：25 个家族变体页补齐；
- `edexcel_page_records.json`：cq:Page 记录快照（恢复来源）；
- `edexcel_downloads.json`：2 个实拿 PDF（含 sha256）；
- catalog.json：仓库统一接口 catalog 条目（edexcel 2 条），按 URL 归一匹配
  integrated_items。

每科取源优先级：capped_final → recovery.live → recovery.dead → first_pass(ok)。
输出对齐 subjects_cie.json：schema_version/board/generated_at/scope_zh/method_zh/
sources/coverage/material_registry/subjects，subjects 按 slug 排序。
"""

from __future__ import annotations

import collections
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(r"C:/Users/weo/Desktop/api")
EVID = ROOT / "tmp_materials_probe" / "evidence"
CATALOG = ROOT / "examdata" / "src" / "examdata" / "materials" / "data" / "catalog.json"
OUT = ROOT / "examdata" / "src" / "examdata" / "materials" / "data" / "subjects_edexcel.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def norm_url(raw: str) -> str:
    s = unquote(str(raw or "").strip()).lower()
    for scheme in ("https://qualifications.pearson.com", "http://qualifications.pearson.com"):
        if s.startswith(scheme):
            s = s[len(scheme):]
            break
    return s.split("#", 1)[0].split("?", 1)[0]


def title_of(row: dict) -> str:
    return str(row.get("title") or "")


def compact_row(slug: str, source: str, row: dict) -> dict:
    out = {"slug": slug, "source": source}
    for k in ("title", "url", "gated", "size", "extension", "doc_type", "series", "unit", "spec_code"):
        if row.get(k) is not None:
            out[k] = row[k]
    return out


def main() -> None:
    all_pages = load(EVID / "edexcel_all_pages.json")
    sweep = load(EVID / "edexcel_sweep.json")
    progress = load(EVID / "edexcel_sweep_progress.json")["subjects"]
    classes = load(EVID / "edexcel_failed_page_classes.json")["pages"]
    recovery = load(EVID / "edexcel_live_pages_recovery.json")
    capped = load(EVID / "edexcel_capped_final.json")
    dup = load(EVID / "edexcel_dup_variants_sweep.json")
    downloads = load(EVID / "edexcel_downloads.json")
    catalog = load(CATALOG)

    capped_subjects = capped["subjects"]
    live = recovery["live"]
    dead = recovery["dead"]

    # ---- 状态归一 ----
    first_pass_ok = sorted(s for s, v in progress.items() if v.get("status") == "ok" and s not in capped_subjects)
    live_ok = sorted(live)
    dead_ok = sorted(s for s, v in dead.items() if v.get("status") == "ok")
    dead_gap = sorted(s for s, v in dead.items() if v.get("status") != "ok")
    capped_keys = sorted(capped_subjects)

    assert len(first_pass_ok) + len(capped_keys) + len(live) + len(dead) == len(progress), "source partition mismatch"
    assert not (set(first_pass_ok) | set(capped_keys) | set(live) | set(dead)) - set(progress)
    assert len(dead_gap) == 2 and set(dead_gap) <= set(dead), "unexpected dead gap set"

    # ---- all_pages 按 slug 分组（家族变体页清单） ----
    pages_by_slug: dict[str, list[dict]] = collections.defaultdict(list)
    for p in all_pages["pages"]:
        pages_by_slug[p["slug"]].append(p)

    # ---- 变体页按 slug 分组 ----
    variants_by_slug: dict[str, list[dict]] = collections.defaultdict(list)
    for key, v in dup["variants"].items():
        variants_by_slug[v["slug"]].append(v)

    # ---- 合并材料行（用于注册表关键词扫描与 catalog URL 匹配） ----
    merged_rows: list[tuple[str, str, dict]] = []

    def add_rows(slug: str, source: str, rows) -> None:
        for row in rows or []:
            merged_rows.append((slug, source, row))

    for slug in first_pass_ok:
        add_rows(slug, "progress", progress[slug].get("materials"))
    for slug, v in live.items():
        add_rows(slug, "live", v.get("materials"))
    for slug, v in dead.items():
        add_rows(slug, "dead", v.get("materials"))
    for slug, v in capped_subjects.items():
        add_rows(slug, "capped", v.get("materials"))
    for key, v in dup["variants"].items():
        add_rows(v["slug"], "variant", v.get("materials"))

    seen_row: set[tuple[str, str]] = set()
    rows_dedup: list[tuple[str, str, dict]] = []
    for slug, source, row in merged_rows:
        k = (slug, norm_url(row.get("url") or "") or str(row.get("title")))
        if k in seen_row:
            continue
        seen_row.add(k)
        rows_dedup.append((slug, source, row))

    # ---- catalog URL 索引（integrated_items 匹配） ----
    catalog_items = catalog.get("items", [])
    cat_url_index: dict[str, str] = {}
    for item in catalog_items:
        if item.get("board") != "edexcel":
            continue
        for ver in item.get("versions") or []:
            if ver.get("url"):
                cat_url_index[norm_url(ver["url"])] = item["id"]

    integrated_by_slug: dict[str, set[str]] = collections.defaultdict(set)
    integrated_rows_by_item: dict[str, list[dict]] = collections.defaultdict(list)
    for slug, source, row in rows_dedup:
        item_id = cat_url_index.get(norm_url(row.get("url") or ""))
        if item_id:
            integrated_by_slug[slug].add(item_id)
            integrated_rows_by_item[item_id].append(compact_row(slug, source, row))

    # ---- 关键词谓词（注册表） ----
    def rows_where(pred) -> list[dict]:
        out = []
        for slug, source, row in rows_dedup:
            try:
                if pred(row):
                    out.append(compact_row(slug, source, row))
            except Exception:  # noqa: BLE001
                continue
        return out

    def f_formula(row: dict) -> bool:
        return bool(
            re.search(r"formulae", title_of(row), re.I)
            or str(row.get("doc_type") or "") == "Mathematical-Formulae-and-Statistical-Tables"
        )

    def f_periodic(row: dict) -> bool:
        return "periodic" in (title_of(row) + " " + str(row.get("url") or "")).lower()

    def f_data_booklet(row: dict) -> bool:
        return "data booklet" in title_of(row).lower()

    def f_physics_formulae(row: dict) -> bool:
        return bool(re.search(r"data, formulae", title_of(row), re.I))

    def f_stat_tables(row: dict) -> bool:
        return str(row.get("doc_type") or "") == "Statistical-formulae-and-tables" or (
            "statistical formulae" in title_of(row).lower()
        )

    def f_insert(row: dict) -> bool:
        t = title_of(row).lower()
        return "insert" in t or "source booklet" in t

    def f_pre_release(row: dict) -> bool:
        return str(row.get("doc_type") or "") == "Pre-release-material" or "pre-release" in title_of(row).lower()

    formula_rows = rows_where(f_formula)
    periodic_rows = rows_where(f_periodic)
    data_booklet_rows = rows_where(f_data_booklet)
    physics_formula_rows = rows_where(lambda r: f_physics_formulae(r) and r.get("slug") == "physics-2015") or rows_where(f_physics_formulae)
    stat_table_rows = rows_where(f_stat_tables)
    insert_rows = rows_where(f_insert)
    pre_release_rows = rows_where(f_pre_release)

    def rows_for_item(item_id: str) -> list[dict]:
        return integrated_rows_by_item.get(item_id, [])

    def mk_registry_entry(**kw) -> dict:
        return kw

    def cap(rows: list[dict], n: int = 60) -> dict:
        uniq: dict[tuple, dict] = {}
        for r in rows:
            key = (r.get("slug"), r.get("url"))
            uniq.setdefault(key, r)
        rows = list(uniq.values())
        return {"observed_count": len(rows), "observed_rows": rows[:n], "truncated": len(rows) > n}

    REGISTRY = {
        "ial18_maths_formula_book": mk_registry_entry(
            name_zh="IAL 数学公式与统计表（Mathematical Formulae and Statistical Tables, Issue 2）",
            name_en="Pearson Edexcel International Advanced Level Mathematics/Further Mathematics and Pure Mathematics Mathematical Formulae and Statistical Tables (Issue 2)",
            candidate_facing=True,
            form_zh="独立 PDF 小册子；考试时考生使用（Pearson 官方说明随考务发放；具体以考场安排为准）",
            public_obtainable="yes",
            public_note_zh="官网公开 PDF 实测下载 HTTP 200；与 catalog 条目 URL 归一后完全一致",
            integrated="yes",
            integrated_items=["edexcel-ial-maths-formula-book"],
            integration_zh="catalog 条目 edexcel-ial-maths-formula-book（access=public，subjects=['ial18-mathematics','ial-maths']）；/api/v1/materials/edexcel-ial-maths-formula-book/content 实测取回 1731630B",
            version_note_zh="实测文件为 Issue 2（PDF 首页）；版本以官网现行链接为准，未发现并存旧版",
            evidence=[
                {
                    "kind": "official-download",
                    "ref": "edexcel_downloads.json 第 1 条（实测取回）",
                    "url": "https://qualifications.pearson.com/content/dam/pdf/International%20Advanced%20Level/Mathematics/2018/Specification-and-Sample-Assessment/IAL-Mathematics-Formula-Book.pdf",
                    "http": 200,
                    "bytes": 1731630,
                    "sha256": "0c30bf2b83910e6ae6053a6c699a049cd05b02f54b6c3417eb9d8905d1a6d8ac",
                    "pages": 34,
                    "label": "IAL Mathematics/Further Mathematics and Pure Mathematics Mathematical Formulae and Statistical Tables (Issue 2)",
                },
                {
                    "kind": "servlet-record",
                    "ref": "mathematics-2018 材料行（记录级）",
                    "quote": "doc_type=Mathematical-Formulae-and-Statistical-Tables（servlet 记录，公开路径）",
                },
            ],
            **cap([r for r in formula_rows if r.get("slug") in ("mathematics-2018", "mathematics-2017")] + rows_for_item("edexcel-ial-maths-formula-book")),
        ),
        "ial18_chemistry_data_booklet": mk_registry_entry(
            name_zh="IAL 化学数据手册（Data Booklet - IAL Chemistry 2018）",
            name_en="Data Booklet - IAL Chemistry 2018 (Issue 1, March 2019)",
            candidate_facing=True,
            form_zh="独立 PDF；考试时考生使用",
            public_obtainable="yes",
            public_note_zh="官网公开 PDF 实测下载 HTTP 200；与 catalog 条目 URL 归一后完全一致",
            integrated="yes",
            integrated_items=["edexcel-ial-chemistry-data-booklet"],
            integration_zh="catalog 条目 edexcel-ial-chemistry-data-booklet（access=public，subjects=['ial18-chemistry']）；content 端点实测取回 2542080B",
            version_note_zh="实测文件为 Issue 1 March 2019（文件名）；未发现并存旧版",
            evidence=[
                {
                    "kind": "official-download",
                    "ref": "edexcel_downloads.json 第 2 条（实测取回）",
                    "url": "https://qualifications.pearson.com/content/dam/pdf/International%20Advanced%20Level/Chemistry/2018/Teaching-and-Learning-Materials/IAL_Chemistry%202018_Data_booklet_Issue_1_March%202019.pdf",
                    "http": 200,
                    "bytes": 2542080,
                    "sha256": "a372a93daa9716ad902d3e3ea885469b46538ab79218b580027d5638e6d7dee7",
                    "label": "Data Booklet - IAL Chemistry 2018",
                },
                {"kind": "servlet-record", "ref": "chemistry-2018 材料行：doc_type=Booklet，公开路径"},
            ],
            **cap(rows_for_item("edexcel-ial-chemistry-data-booklet") + [r for r in data_booklet_rows if r.get("slug") == "chemistry-2018"]),
        ),
        "al15_chemistry_data_booklet": mk_registry_entry(
            name_zh="A Level 化学数据手册（9CH0 / 8CH0）",
            name_en="A Level Chemistry Data Booklet - 9CH0 / AS Chemistry Data Booklet - 8CH0",
            candidate_facing=True,
            form_zh="独立 PDF；9CH0（Issue 2 Summer 2017，12 页）与 8CH0 AS（Issue 1 Summer 2016，8 页）两份均经 Fetcher 实测下载 HTTP 200（2026-10-05）",
            public_obtainable="yes",
            public_note_zh="两条记录行（记录级全集，未截断）均实测下载 HTTP 200；sha256/页数见 evidence",
            integrated="no",
            integration_zh="未接入（本轮只补实测证据、不扩 catalog；如需可按实测 URL 加条目）",
            evidence=[
                {"kind": "servlet-record", "ref": "chemistry-2015 材料行 2 条（记录级 → 已逐份实测）"},
                {
                    "kind": "official-download",
                    "ref": "edexcel_gap3_supplement.json · 9CH0",
                    "url": "https://qualifications.pearson.com/content/dam/pdf/A%20Level/Chemistry/2015/teaching-and-learning-materials/a-level-chemistry-data-booklet-9ch0.pdf",
                    "http": 200,
                    "bytes": 1006191,
                    "sha256": "09b40d7fe3f477e8314c74a10609db4d3caaf07385bbe9631873b5af99d8975b",
                    "pages": 12,
                    "label": "Pearson Edexcel Level 3 Advanced Level GCE in Chemistry (9CH0) Data Booklet Issue 2 Summer 2017",
                },
                {
                    "kind": "official-download",
                    "ref": "edexcel_gap3_supplement.json · 8CH0 AS",
                    "url": "https://qualifications.pearson.com/content/dam/pdf/A%20Level/Chemistry/2015/teaching-and-learning-materials/GCE_Chemistry_Data_Booklet_8CH0_Advanced_Subsidiary.pdf",
                    "http": 200,
                    "bytes": 489551,
                    "sha256": "b26d3ca37233d9ac93f60018dcbfc76534abce278ca65fa6016f152287c58555",
                    "pages": 8,
                    "label": "Pearson Edexcel Level 3 Advanced Subsidiary GCE in Chemistry (8CH0) Data Booklet Issue 1 Summer 2016",
                },
            ],
            **cap([r for r in data_booklet_rows if r.get("slug") == "chemistry-2015"]),
        ),
        "chemistry_periodic_table": mk_registry_entry(
            name_zh="元素周期表（独立文件）",
            name_en="Periodic table (standalone file)",
            candidate_facing=True,
            form_zh="独立文件；chemistry-2008 记录的唯一 1 行 Information-sheet 实测下载 HTTP 200（1 页周期表 PDF，2026-10-05）；Edexcel 各现行化学 spec 未见独立周期表文件，考卷内或随卷发放形态未证实",
            public_obtainable="yes",
            public_note_zh="唯一公开路径材料行实测下载 HTTP 200（2026-10-05）；新版 spec 未记录到独立文件",
            integrated="no",
            integration_zh="未接入（本轮只补实测证据、不扩 catalog）",
            evidence=[
                {"kind": "servlet-record", "ref": "chemistry-2008 材料行：'Periodic table' Information-sheet（记录级 → 已实测）"},
                {
                    "kind": "official-download",
                    "ref": "edexcel_gap3_supplement.json · chemistry-2008",
                    "url": "https://qualifications.pearson.com/content/dam/pdf/A%20Level/Chemistry/2013/Teaching%20and%20learning%20materials/periodic_table_black.pdf",
                    "http": 200,
                    "bytes": 957645,
                    "sha256": "59361a42365664bb696f3b295866ab58af5de473ffb748e07e7fbdf1b87aad36",
                    "pages": 1,
                    "label": "The Periodic Table of Elements（1 页周期表 PDF）",
                },
            ],
            **cap(periodic_rows),
        ),
        "physics_data_formulae_list": mk_registry_entry(
            name_zh="物理数据、公式与关系式清单（List of Data, Formulae and Relationships）",
            name_en="A level / AS Physics - List of Data, Formulae and Relationships",
            candidate_facing=True,
            form_zh="独立 PDF；9PH0 A level（Issue 3 November 2022，8 页）与 8PH0 AS（Issue 2 November 2022，4 页）两份均经 Fetcher 实测下载 HTTP 200（2026-10-05）",
            public_obtainable="yes",
            public_note_zh="A level 与 AS 两条记录行（记录级全集）均实测下载 HTTP 200；随卷/考场使用形态未证实",
            integrated="no",
            integration_zh="未接入（本轮只补实测证据、不扩 catalog）",
            evidence=[
                {"kind": "servlet-record", "ref": "physics-2015 材料行 2 条（记录级 → 已逐份实测）"},
                {
                    "kind": "official-download",
                    "ref": "edexcel_gap3_supplement.json · 9PH0",
                    "url": "https://qualifications.pearson.com/content/dam/pdf/A%20Level/Physics/2015/Specification%20and%20sample%20assessments/a-level-physics-data-formulae-relationships.pdf",
                    "http": 200,
                    "bytes": 299004,
                    "sha256": "3677323b1a40147f68992893baa4ec0e2ac016a27f6b801136940a418fd03180",
                    "pages": 8,
                    "label": "Pearson Edexcel Level 3 Advanced Level GCE in Physics (9PH0) List of data, formulae and relationships Issue 3 November 2022",
                },
                {
                    "kind": "official-download",
                    "ref": "edexcel_gap3_supplement.json · 8PH0",
                    "url": "https://qualifications.pearson.com/content/dam/pdf/A%20Level/Physics/2015/Specification%20and%20sample%20assessments/P53451A_GCE_Physics_Data_Booklet_8PH0.pdf",
                    "http": 200,
                    "bytes": 550902,
                    "sha256": "99623bd0e4e226068e99db6d4d4041cd55a9203ec8aeb19bb18820d76e1d8bac",
                    "pages": 4,
                    "label": "Pearson Edexcel Level 3 Advanced Subsidiary GCE in Physics (8PH0) List of data, formulae and relationships Issue 2 November 2022",
                },
            ],
            **cap(physics_formula_rows),
        ),
        "statistics_formulae_tables": mk_registry_entry(
            name_zh="统计公式与表格（Formulae and Statistical Tables）",
            name_en="Statistical Formulae and Tables（含 A3/A4 大字版）/ Formulae and Statistical Tables",
            candidate_facing=True,
            form_zh="独立 PDF；statistics-2017 主版（32 页）+ A3 24pt 大字版（257 页）+ A4 18pt 大字版（257 页）与 psychology-2015 amended（8 页，May-June 2026 起）共 4 行均经 Fetcher 实测下载 HTTP 200（2026-10-05）",
            public_obtainable="yes",
            public_note_zh="4 条记录行（含大字版变体，记录级全集）均实测下载 HTTP 200；sha256/页数见 evidence",
            integrated="no",
            integration_zh="未接入（本轮只补实测证据、不扩 catalog）",
            evidence=[
                {"kind": "servlet-record", "ref": "statistics-2017 3 行 + psychology-2015 1 行（记录级 → 已逐份实测）"},
                {
                    "kind": "official-download",
                    "ref": "edexcel_gap3_supplement.json · statistics-2017 主版",
                    "url": "https://qualifications.pearson.com/content/dam/pdf/A%20Level/statistics/2017/Specification%20and%20Sample%20assessment%20material/Statistical-formulae-and-tables.pdf",
                    "http": 200,
                    "bytes": 1550546,
                    "sha256": "ff83bed07cb46bf3cf3f6f75eae4551bbbfd647a50b942d9bb40b2e11f68e5f8",
                    "pages": 32,
                    "label": "Level 3 Advanced Subsidiary and Advanced GCE in Statistics (8ST0/9ST0) Statistical formulae and tables",
                },
                {
                    "kind": "official-download",
                    "ref": "edexcel_gap3_supplement.json · statistics-2017 A3 24pt",
                    "url": "https://qualifications.pearson.com/content/dam/pdf/A%20Level/statistics/2017/Specification%20and%20Sample%20assessment%20material/q-24pt-a3-mathematical-formulae-and-statistics-tables.pdf",
                    "http": 200,
                    "bytes": 499900,
                    "sha256": "a7a2b87d085978fce8ca0c8f96a2ef4a73aae922da45fa6e277ef8a2ab58ec28",
                    "pages": 257,
                    "label": "Statistics 大字版（A3 24pt）",
                },
                {
                    "kind": "official-download",
                    "ref": "edexcel_gap3_supplement.json · statistics-2017 A4 18pt",
                    "url": "https://qualifications.pearson.com/content/dam/pdf/A%20Level/statistics/2017/Specification%20and%20Sample%20assessment%20material/x-18pt-a4-mathematical-formulae-and-statistics-tables.pdf",
                    "http": 200,
                    "bytes": 752580,
                    "sha256": "cd49f9f7a10c6c1c7931069323a54a47337c747e05a84df46c03a61c2b5128fa",
                    "pages": 257,
                    "label": "Statistics 大字版（A4 18pt）",
                },
                {
                    "kind": "official-download",
                    "ref": "edexcel_gap3_supplement.json · psychology-2015 amended",
                    "url": "https://qualifications.pearson.com/content/dam/pdf/A%20Level/Psychology/2015/specification-and-sample-assessments/amended-formulae-and-statistical-tables-for-summer-2026.pdf",
                    "http": 200,
                    "bytes": 118548,
                    "sha256": "59d502e97292358449e46e68f92af9ab2c0a9a6616dbff245a481339d29b51b4",
                    "pages": 8,
                    "label": "Level 3 GCE Psychology Advanced and Advanced Subsidiary Formulae and Statistical Tables（May-June 2026 Assessment Window & Beyond）",
                },
            ],
            **cap(stat_table_rows),
        ),
        "source_booklet_insert": mk_registry_entry(
            name_zh="随卷 insert / source booklet（阅读材料、来源册）",
            name_en="Insert / Source booklet provided with the QP",
            candidate_facing=True,
            form_zh="随卷材料；官网按系列发布公开 PDF（记录到 accounting 源册、music-technology insert、英语 insert booklet、history 来源 insert 等）",
            public_obtainable="partial",
            public_note_zh="记录级证据显示多科存在公开 insert/source booklet 文件；各科公开范围与最新系列覆盖未逐份实测",
            integrated="no",
            integration_zh="未接入（记录级；可按需扩展动态定位）",
            evidence=[{"kind": "servlet-record", "ref": "多科材料行（title 含 Insert / Source booklets）"}],
            **cap(insert_rows),
        ),
        "pre_release_materials": mk_registry_entry(
            name_zh="考前预发材料（Pre-release Material）",
            name_en="Pre-release Material",
            candidate_facing=True,
            form_zh="定时/按系列公开发布的预发材料（business-2015、economics-b-2015 等新 spec 记录到公开与门禁并存）",
            public_obtainable="partial",
            public_note_zh="记录级：June 系列历年预发材料部分公开、部分位于 secure/silver 门禁（如 June 2022/2026 部分行 gated=true）；未逐份实测",
            integrated="no",
            integration_zh="未接入",
            evidence=[{"kind": "servlet-record", "ref": "business-2015 / economics-b-2015 等材料行"}],
            **cap(pre_release_rows),
        ),
        "gated_policy_note": mk_registry_entry(
            name_zh="门禁材料（secure/silver）处理策略",
            name_en="Gated materials (secure/silver) policy",
            candidate_facing=False,
            form_zh="URL 位于 /content/dam/secure/...；robots 禁止且实际跳登录，未请求",
            public_obtainable="no",
            public_note_zh="实测（第一遍 + 恢复）记录到门禁材料行，一律只登记不请求（不绕登录墙）",
            integrated="no",
            integration_zh="不适用",
            evidence=[{"kind": "policy", "ref": "Fetcher robots 前置判定 + 未请求门禁 URL"}],
            **cap([]),
        ),
    }

    # ---- 主表 ----
    coverage = {
        "pages_total": all_pages.get("total", len(all_pages["pages"])),
        "slugs": len(pages_by_slug),
        "family_counts": sweep.get("family_counts"),
        "first_pass": {"ok": 150, "page_failed": 83},
        "failed_pages": {"live_no_facet": 25, "dead_404": 58},
        "recovery": {
            "live_ok": len(live_ok),
            "dead_ok": len(dead_ok),
            "dead_gap": len(dead_gap),
            "gap_slugs": dead_gap,
            "gap_note_zh": "记录 tags 中无 Specification-Code / Qualification-Subject，无法构造基查询；经 2026-10-05 记录级复核，两页均为非科目信息页（2016/2017 更新新闻页、视频教程页），已排除出科目材料口径",
        },
        "capped_final": {
            "subjects": capped_keys,
            "queries_used": capped.get("budget", {}).get("used"),
            "complete_all": all(v.get("complete") for v in capped_subjects.values()),
            "unresolved_all": sorted({u for v in capped_subjects.values() for u in (v.get("unresolved") or [])}),
            "superseded_first_pass_rows": {s: len(progress[s].get("materials") or []) for s in capped_keys},
        },
        "dup_variants": {
            "page_entries": dup["summary"]["variants"],
            "slugs": len(variants_by_slug),
            "ok": dup["summary"]["ok"],
            "material_rows": dup["summary"]["material_rows"],
        },
        "final_source_distribution": {
            "first_pass_ok": len(first_pass_ok),
            "capped_final": len(capped_keys),
            "recovery_live": len(live_ok),
            "recovery_dead_ok": len(dead_ok),
            "gap": len(dead_gap),
        },
        "materials_merged": {
            "rows": len(merged_rows),
            "rows_dedup": len(rows_dedup),
            "unique_urls": len({norm_url(r.get("url") or "") for _, _, r in rows_dedup if r.get("url")}),
            "gated_rows": sum(1 for _, _, r in rows_dedup if r.get("gated")),
            "gated_unique_urls": len({norm_url(r.get("url") or "") for _, _, r in rows_dedup if r.get("gated") and r.get("url")}),
        },
        "no_material_evidence": [s for s in dead_gap],
        "no_material_evidence_note_zh": "以上两项经 2026-10-05 记录级复核均为非科目信息页（新闻/告示页与视频教程页，见 edexcel_page_records.json），不属科目材料口径；科目级页面中无材料记录者按 subjects 内各科材料行为空判定",
    }

    sources = {
        "edexcel_all_pages": {"path": "tmp_materials_probe/evidence/edexcel_all_pages.json", "sha256": file_sha256(EVID / "edexcel_all_pages.json"), "pages": len(all_pages["pages"])},
        "edexcel_sweep": {"path": "tmp_materials_probe/evidence/edexcel_sweep.json", "sha256": file_sha256(EVID / "edexcel_sweep.json")},
        "edexcel_sweep_progress": {"path": "tmp_materials_probe/evidence/edexcel_sweep_progress.json", "sha256": file_sha256(EVID / "edexcel_sweep_progress.json"), "subjects": len(progress)},
        "edexcel_failed_page_classes": {"path": "tmp_materials_probe/evidence/edexcel_failed_page_classes.json", "sha256": file_sha256(EVID / "edexcel_failed_page_classes.json")},
        "edexcel_page_records": {"path": "tmp_materials_probe/evidence/edexcel_page_records.json", "sha256": file_sha256(EVID / "edexcel_page_records.json")},
        "edexcel_live_pages_recovery": {"path": "tmp_materials_probe/evidence/edexcel_live_pages_recovery.json", "sha256": file_sha256(EVID / "edexcel_live_pages_recovery.json"), "live": len(live), "dead": len(dead)},
        "edexcel_capped_final": {"path": "tmp_materials_probe/evidence/edexcel_capped_final.json", "sha256": file_sha256(EVID / "edexcel_capped_final.json"), "subjects": len(capped_subjects)},
        "edexcel_dup_variants_sweep": {"path": "tmp_materials_probe/evidence/edexcel_dup_variants_sweep.json", "sha256": file_sha256(EVID / "edexcel_dup_variants_sweep.json"), "variants": len(dup["variants"])},
        "edexcel_downloads": {"path": "tmp_materials_probe/evidence/edexcel_downloads.json", "sha256": file_sha256(EVID / "edexcel_downloads.json"), "files": len(downloads)},
        "materials_catalog": {"path": "examdata/src/examdata/materials/data/catalog.json", "sha256": file_sha256(CATALOG), "edexcel_items": [i["id"] for i in catalog_items if i.get("board") == "edexcel"]},
    }

    subjects: dict[str, dict] = {}
    for slug in sorted(progress):
        page_entries = [
            {
                "family": p.get("family"),
                "level": p.get("level"),
                "url": p.get("url"),
                "version_year": p.get("version_year"),
            }
            for p in sorted(pages_by_slug.get(slug, []), key=lambda p: (str(p.get("family")), str(p.get("url"))))
        ]
        variants = variants_by_slug.get(slug) or []
        variant_block = [
            {
                "family": v.get("family"),
                "level": v.get("level"),
                "page_url": v.get("page_url"),
                "match": v.get("match"),
                "status": v.get("status"),
                "n_records": v.get("n_records"),
                "capped": v.get("capped"),
                "doc_types": v.get("doc_types"),
                "public_count": v.get("public_count"),
                "gated_count": v.get("gated_count"),
                "materials": v.get("materials") or [],
                "materials_count": len(v.get("materials") or []),
            }
            for v in variants
        ]

        if slug in capped_subjects:
            c = capped_subjects[slug]
            source = "capped_final"
            materials = c.get("materials") or []
            concl = [
                "capped 终稿（第一遍 1000 条截断）：递归分区 {q} 次查询 / {nleaves} 个叶节点（各 <1000 证明完整），unresolved {u}；终稿 {n} 条记录（公开 {p} / 门禁 {g}），"
                "材料 {m} 行".format(
                    q=c.get("queries"), nleaves=len(c.get("leaves") or []), u=len(c.get("unresolved") or []),
                    n=c.get("n_records"), m=len(materials), p=c.get("public_count"), g=c.get("gated_count"),
                ),
                "取代第一遍部分结果（{x} 行）".format(x=len(progress[slug].get("materials") or [])),
            ]
            if c.get("base_note"):
                concl.append("基查询说明：" + str(c["base_note"]))
            body = {
                "slug": slug,
                "family": c.get("family"),
                "level": progress[slug].get("level"),
                "page_url": progress[slug].get("page_url"),
                "status": "ok",
                "source": source,
                "page_entries": page_entries,
                "base_tag": c.get("base_tag"),
                "n_records": c.get("n_records"),
                "complete": c.get("complete"),
                "queries": c.get("queries"),
                "doc_types": c.get("doc_types"),
                "public_count": c.get("public_count"),
                "gated_count": c.get("gated_count"),
                "materials": materials,
                "integrated_items": sorted(integrated_by_slug.get(slug, set())),
                "superseded_first_pass_materials_count": len(progress[slug].get("materials") or []),
            }
        elif slug in live:
            v = live[slug]
            source = "recovery_live"
            materials = v.get("materials") or []
            concl = [
                "第一遍页面 facet 缺失；经 servlet cq:Page 记录恢复（match={m}）：{n} 条记录（公开 {p} / 门禁 {g}），材料 {mm} 行".format(
                    m=v.get("match"), n=v.get("n_records"), mm=len(materials), p=v.get("public_count"), g=v.get("gated_count"),
                )
            ]
            body = {
                "slug": slug,
                "family": v.get("family"),
                "level": progress[slug].get("level"),
                "page_url": v.get("page_url"),
                "status": "ok",
                "source": source,
                "page_kind": v.get("page_kind"),
                "match": v.get("match"),
                "base_fq": v.get("base_fq"),
                "n_records": v.get("n_records"),
                "capped": v.get("capped"),
                "doc_types": v.get("doc_types"),
                "public_count": v.get("public_count"),
                "gated_count": v.get("gated_count"),
                "materials": materials,
                "integrated_items": sorted(integrated_by_slug.get(slug, set())),
                "page_entries": page_entries,
            }
        elif slug in dead:
            v = dead[slug]
            materials = v.get("materials") or []
            if v.get("status") == "ok":
                source = "recovery_dead_ok"
                concl = [
                    "页面已删（HTTP 404）；经 servlet cq:Page 记录恢复（match={m}）：{n} 条记录（公开 {p} / 门禁 {g}），材料 {mm} 行".format(
                        m=v.get("match"), n=v.get("n_records"), mm=len(materials), p=v.get("public_count"), g=v.get("gated_count"),
                    ),
                    "页面本体不可再访问，结论仅代表 servlet 记录（记录级，非页面级）",
                ]
                body = {
                    "slug": slug,
                    "family": v.get("family"),
                    "level": progress[slug].get("level"),
                    "page_url": v.get("page_url"),
                    "status": "ok",
                    "source": source,
                    "page_kind": v.get("page_kind"),
                    "match": v.get("match"),
                    "base_fq": v.get("base_fq"),
                    "n_records": v.get("n_records"),
                    "capped": v.get("capped"),
                    "doc_types": v.get("doc_types"),
                    "public_count": v.get("public_count"),
                    "gated_count": v.get("gated_count"),
                    "materials": materials,
                    "integrated_items": sorted(integrated_by_slug.get(slug, set())),
                    "page_entries": page_entries,
                }
            else:
                source = "recovery_dead_gap"
                concl = [
                    "页面已删（HTTP 404），且 servlet 记录无 Specification-Code / Qualification-Subject 可用 facet → 无法构造基查询。",
                    "2026-10-05 记录级复核：该页为非科目信息页（新闻/告示页或视频教程页，证据见 edexcel_page_records.json），排除出科目材料口径；本项不作为科目结论登记。",
                ]
                body = {
                    "slug": slug,
                    "family": v.get("family"),
                    "level": progress[slug].get("level"),
                    "page_url": v.get("page_url"),
                    "status": "record_no_usable_facet",
                    "source": source,
                    "page_kind": v.get("page_kind"),
                    "match": v.get("match"),
                    "picked": v.get("picked"),
                    "page_entries": page_entries,
                    "integrated_items": [],
                }
        else:
            v = progress[slug]
            materials = v.get("materials") or []
            source = "first_pass"
            concl = [
                "第一遍直查：{n} 条记录（HTTP {h}；公开 {p} / 门禁 {g}），材料 {mm} 行".format(
                    n=v.get("n_records"), h=v.get("servlet_status"), mm=len(materials), p=v.get("public_count"), g=v.get("gated_count"),
                ),
                "页面与 servlet 查询均在第一遍实测完成（非截断）" if not v.get("capped") else "第一遍查询命中 1000 上限（capped）",
            ]
            body = {
                "slug": slug,
                "family": v.get("family"),
                "level": v.get("level"),
                "page_url": v.get("page_url"),
                "status": "ok",
                "source": source,
                "n_records": v.get("n_records"),
                "capped": v.get("capped"),
                "doc_types": v.get("doc_types"),
                "public_count": v.get("public_count"),
                "gated_count": v.get("gated_count"),
                "materials": materials,
                "integrated_items": sorted(integrated_by_slug.get(slug, set())),
                "page_entries": page_entries,
            }
            if v.get("notes"):
                body["notes"] = v.get("notes")

        if variant_block:
            concl.append(
                "另有 {k} 个家族变体页单独复核：{detail}（逐条见 variants）".format(
                    k=len(variant_block),
                    detail="；".join(
                        "{f} {st} n={n} 材料{m}".format(f=b["family"], st=b["status"], n=b.get("n_records"), m=b["materials_count"])
                        for b in variant_block
                    ),
                )
            )
            body["variants"] = variant_block

        body["conclusion_zh"] = "；".join(c.rstrip("。") for c in concl) + "。"
        subjects[slug] = body

    out = {
        "schema_version": "1",
        "board": "edexcel",
        "generated_at": date.today().isoformat(),
        "scope_zh": (
            "范围全集 = 实测 {pt} 个科目页（{sl} 个唯一 slug）：第一遍 {ok} ok + {fail} 页失败；"
            "失败页经 servlet cq:Page 记录恢复（{live} live + {dead} dead，dead 中 {gap} 个经记录复核为非科目信息页、已排除出科目材料口径）；"
            "{cap} 个 capped 科递归分区终稿；{dup} 个家族变体页补齐。"
        ).format(
            pt=coverage["pages_total"], sl=coverage["slugs"], ok=150, fail=83,
            live=len(live), dead=len(dead), gap=len(dead_gap), cap=len(capped_keys), dup=dup["summary"]["variants"],
        ),
        "method_zh": (
            "逐科结论由四类实测证据合成：①第一遍逐页抓取 + servlet 基查询；②83 失败页的 servlet cq:Page 记录级恢复；"
            "③3 个 capped 科递归分区查询终稿；④20 个 slug 的 25 个家族变体页补齐。材料行来自 servlet algolia 记录（title/url/gated/doc_type/series 等），"
            "门禁（secure/silver）URL 只登记不请求。integrated_items 由材料行 URL 与 catalog 条目 URL 归一后匹配得出。"
            "注册表逐项给出证据等级：记录级全集经 Fetcher 实测取回标 yes（见 evidence），未逐份实测的材料类按记录级标 partial，门禁类只登记，未臆断。"
        ),
        "sources": sources,
        "coverage": coverage,
        "material_registry": REGISTRY,
        "subjects": subjects,
    }

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("written", OUT, OUT.stat().st_size)
    print("subjects:", len(subjects))
    print("coverage:", json.dumps(coverage, ensure_ascii=False, indent=1))
    print("registry counts:", {k: v.get("observed_count") for k, v in REGISTRY.items()})
    print("integrated items:", {k: len(v) for k, v in integrated_by_slug.items()})
    for item_id, rows in integrated_rows_by_item.items():
        print("  ", item_id, "->", [(r["slug"], r["source"]) for r in rows])


if __name__ == "__main__":
    main()
