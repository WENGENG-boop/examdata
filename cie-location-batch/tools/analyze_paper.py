"""一次调用完成单卷定位核验的全部本地准备，并打印一份紧凑 JSON 清单。

    python analyze_paper.py <key>        # key 形如 9709/2024/Jun/11

把过去要跑十来次工具、看十来张图的准备阶段收成一次调用：

1. **原件**：只有 QP（paired 卷还包括 MS）确实缺失时才调用
   `run_paper.py <KEY> --stage fetch`，并把它的退出码原样带出；本工具自己
   绝不下载任何东西，也绝不因为 sha 不一致而触发下载。
2. **提案**：`work/proposals/<subject>/<year>-<season>-<paper>.json` 比原件旧或
   不存在时，才跑 `run_paper.py <KEY> --stage propose`（失败退回 `propose.py`）。
3. **初稿**：`indexes/<subject>/<year>-<season>-<paper>/cie-index.json` 已存在时
   **绝不覆盖**，改写 `work/drafts/<subject>/<year>-<season>-<paper>.json` 并把
   `draft_written` 置 false；不存在才跑 `draft_index.py <KEY> --write`。
4. **文字层体检**：逐页判断 QP/MS 内嵌文字层是否可信（见 `text_layer_report`）。
5. **拼版表**：整页总览（4 页/张）+ QP/MS 区域密集表（`stacksheet.py` 的打包
   逻辑，保持宽高比、逐区域标注题号），并把静态服务器 URL 打进清单。

stdout 只有一行 JSON；进度与子进程输出一律走 stderr，所以可以
`python analyze_paper.py <key> > manifest.json`。全程本地、单线程。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import batchlib as B
import paperlib as P
import import_index as I
import propose as R
import sheet as SH
import stacksheet as SS

KEY_RE = re.compile(r"^(\d{4})/(\d{4})/([A-Z][a-z]{2})/(\d{1,2})$")
CAP_RE = re.compile(r"<div class=cap>(.*?)</div>")

EXIT_OK = 0
EXIT_BLOCKED = 1
EXIT_FAILED = 2
EXIT_USAGE = 2

PAGE_COLS = 2             # 整页总览：2 列 -> 每张 4 页
SHEET_BASE = "http://127.0.0.1:8792"
SHEET_REL = "work/sheets"
MAX_REGIONS_PER_ROLE = 400
SUBPROCESS_TIMEOUT = 1800.0

# ---------------------------------------------------------------- 文字层体检
#
# 字形错乱的文字层分三族，逐页取并集判定：
#   A. CID 未映射 / 控制码位当字形索引：抽出大量**控制符/格式符/私用区/未分配
#      码位**（bad_char_ratio）。实测：CID 型错乱页 0.59~0.94；干净页 <= 0.08
#      （9709 m26 MS 里 \x0e/\x10 等格式控制符伪影会顶到 0.07，与轻症错乱页
#      0.05 有重叠，单靠这一项不够）。
#   B. 替换式乱码（自定义编码缺 ToUnicode，整段字形映射到拉丁补充区 + C1）：
#      用 latin1_ratio（U+0080-U+00FF 占比）。实测 9709 m26 QP：正文页
#      0.90~0.94、另两页 0.02/0.31（由 A 项兜住）；干净页 <= 0.07（± ² ¼ 等
#      数学符号字体伪影），中间是安全带。
#   C. 混排异体文字（字形映射到随机脚本，实测 8238 卷出现 ᯏ⨼ঐѱ 这类混排）：
#      用 foreign_ratio 兜底。干净英文/数学页恒为 0，中文卷是 CJK 不受影响。
# 词级信号（含可疑字符的词占比、纯符号长词占比）作为补充：实测干净页
# bad_word_ratio <= 0.17（符号字体私用区码位所致）、soup_word_ratio 恒为 0；
# 乱码页最高 0.60/0.31，但个别页可低到 0.01——只当补充，不当主判据。
# 注意：**不用「单字符词占比」判错乱**——数学卷里 y、3、sin 这类孤立记号本来就
# 占 15%~50%，用它会把 9709 这种正常卷误判。符号长词同理只在占比很高时才可疑。
SUSPECT_CATEGORIES = {"Cc", "Cf", "Cs", "Co", "Cn"}
BAD_CHAR_RATIO = 0.20     # 页级：可疑字符占比
LATIN1_RATIO = 0.20       # 页级：拉丁补充区（U+0080-U+00FF）字符占比
FOREIGN_RATIO = 0.05      # 页级：异体脚本字符占比
BAD_WORD_RATIO = 0.35     # 词级：含可疑字符（>25%）的词占比
SOUP_WORD_RATIO = 0.35    # 词级：纯符号长词占比
MIN_CHARS = 30            # 非空白字符太少时没有可比对的文字层
MIN_WORDS = 20
WORD_BAD_CHAR_RATIO = 0.25
SYMBOL_STRIP = "()[]{},.;:+-*/\\|=<>~^%$#@!?&'\""
# 不会在 CIE 英语/数学卷里合法出现的脚本（希腊文、CJK 是合法内容，不列入）
FOREIGN_SCRIPTS = frozenset((
    "ARABIC", "ARMENIAN", "BALINESE", "BATAK", "BENGALI", "BUGINESE", "CHEROKEE",
    "CYRILLIC", "DEVANAGARI", "ETHIOPIC", "GEORGIAN", "GURMUKHI", "GUJARATI",
    "HANGUL", "HEBREW", "HIRAGANA", "JAVANESE", "KANNADA", "KATAKANA", "KHMER",
    "LAO", "LISU", "MALAYALAM", "MONGOLIAN", "MYANMAR", "NKO", "OGHAM", "ORIYA",
    "RUNIC", "SINHALA", "SUNDANESE", "SYRIAC", "TAMIL", "TELUGU", "THAANA",
    "THAI", "TIBETAN", "VAI", "YI",
))


def _stdout_utf8() -> None:
    enc = (getattr(sys.stdout, "encoding", "") or "").replace("-", "").lower()
    if enc != "utf8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def log(*parts) -> None:
    print(*parts, file=sys.stderr, flush=True)


def tail(text: str, limit: int = 400) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else "…" + text[-limit:]


def load_json(path) -> dict | None:
    try:
        data = json.loads(Path(path).read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


# ---------------------------------------------------------------- 子进程

def run_tool(argv: list[str]) -> tuple[int, str]:
    """在 tools/ 目录下跑一个既有工具，返回 (退出码, stdout+stderr)。"""
    try:
        proc = subprocess.run(
            [sys.executable, *argv], cwd=str(B.TOOLS),
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=SUBPROCESS_TIMEOUT)
    except subprocess.TimeoutExpired:
        return EXIT_FAILED, f"{' '.join(argv)} 超过 {SUBPROCESS_TIMEOUT:.0f}s 未结束"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


# ---------------------------------------------------------------- 文字层体检

def _is_suspect(char: str) -> bool:
    return unicodedata.category(char) in SUSPECT_CATEGORIES


def _is_foreign(char: str) -> bool:
    """不在拉丁/希腊/CJK 体系内的异体脚本字符（随机脚本替换乱码的常见特征）。"""
    try:
        name = unicodedata.name(char)
    except ValueError:
        return False
    return name.split(" ", 1)[0] in FOREIGN_SCRIPTS


def _is_symbol_soup(word: str) -> bool:
    """长度 >=4、不是单一字符重复、去掉括号标点后一个字母/数字都不剩的「词」。"""
    if len(word) < 4 or len(set(word)) <= 1:
        return False
    core = "".join(ch for ch in word if ch not in SYMBOL_STRIP)
    return not any(unicodedata.category(ch)[0] in "LN" for ch in core)


def page_text_quality(page) -> dict:
    text = page.get_text() or ""
    chars = [ch for ch in text if not ch.isspace()]
    words = [w[4] for w in page.get_text("words")]
    bad_chars = sum(1 for ch in chars if _is_suspect(ch))
    latin1 = sum(1 for ch in chars if "\u0080" <= ch <= "\u00ff")
    foreign = sum(1 for ch in chars if _is_foreign(ch))
    bad_words = sum(1 for w in words
                    if sum(1 for ch in w if _is_suspect(ch)) / len(w) > WORD_BAD_CHAR_RATIO)
    soup = sum(1 for w in words if _is_symbol_soup(w))
    return {
        "chars": len(chars),
        "words": len(words),
        "bad_char_ratio": (bad_chars / len(chars)) if chars else 0.0,
        "latin1_ratio": (latin1 / len(chars)) if chars else 0.0,
        "foreign_ratio": (foreign / len(chars)) if chars else 0.0,
        "bad_word_ratio": (bad_words / len(words)) if words else 0.0,
        "soup_word_ratio": (soup / len(words)) if words else 0.0,
    }


def page_is_garbled(quality: dict) -> bool:
    if quality["chars"] >= MIN_CHARS:
        if quality["bad_char_ratio"] >= BAD_CHAR_RATIO:
            return True
        if quality["latin1_ratio"] >= LATIN1_RATIO:
            return True
        if quality["foreign_ratio"] >= FOREIGN_RATIO:
            return True
    if quality["words"] >= MIN_WORDS and max(quality["bad_word_ratio"],
                                             quality["soup_word_ratio"]) >= BAD_WORD_RATIO:
        return True
    return False


def text_layer_report(pdf: Path | None) -> dict:
    """逐页判定文字层可信度，返回 {"clean_pages": [...], "garbled_pages": [...]}。"""
    if pdf is None:
        return {"clean_pages": [], "garbled_pages": []}
    import pymupdf
    clean: list[int] = []
    garbled: list[int] = []
    with pymupdf.open(pdf) as doc:
        for index, page in enumerate(doc):
            target = garbled if page_is_garbled(page_text_quality(page)) else clean
            target.append(index + 1)
    return {"clean_pages": clean, "garbled_pages": garbled}


# ---------------------------------------------------------------- 原件 / 提案 / 初稿

def find_pdfs(key: str) -> tuple[Path | None, Path | None]:
    return I.locate_pdf(key, "qp"), I.locate_pdf(key, "ms")


def missing_roles(key: str, qp, ms) -> list[str]:
    """哪些角色的原件算「缺失」。MS 只在 papers.json 标明 paired 时才要求。"""
    missing = []
    if qp is None:
        missing.append("qp")
    if ms is None:
        entry = P.load_paper(key) or {}
        if entry.get("kind") == "paired" or entry.get("ms"):
            missing.append("ms")
    return missing


def proposal_path(key: str) -> Path:
    subject, year, season, paper = key.split("/")
    return B.WORK / "proposals" / subject / f"{year}-{season}-{paper}.json"


def draft_path_for(key: str) -> Path:
    subject, year, season, paper = key.split("/")
    return B.WORK / "drafts" / subject / f"{year}-{season}-{paper}.json"


def proposal_is_fresh(path: Path, pdfs: list[Path]) -> bool:
    if not path.is_file():
        return False
    stamp = max(p.stat().st_mtime for p in pdfs)
    return path.stat().st_mtime >= stamp


def ensure_proposal(key: str, pdfs: list[Path], warnings: list[str]) -> bool:
    path = proposal_path(key)
    if proposal_is_fresh(path, pdfs):
        log(f"提案已是最新，复用 {path}")
        return True
    code, out = run_tool(["run_paper.py", key, "--stage", "propose"])
    if code != 0:
        warnings.append(f"run_paper.py --stage propose 退出码 {code}：{tail(out)}")
        log(f"run_paper.py --stage propose 退出码 {code}，退回直接跑 propose.py")
        code, out = run_tool(["propose.py", key])
        if code != 0:
            warnings.append(f"propose.py 退出码 {code}：{tail(out)}")
            return path.is_file()
    return path.is_file()


def ensure_draft(key: str, warnings: list[str]) -> tuple[Path, bool]:
    """返回 (初稿路径, 是否写进了 indexes/)。已有索引时绝不覆盖。"""
    index_path = I.index_path(key)
    if index_path.is_file():
        draft = draft_path_for(key)
        draft.parent.mkdir(parents=True, exist_ok=True)
        code, out = run_tool(["draft_index.py", key, "--out", str(draft)])
        if code != 0 or not draft.is_file():
            warnings.append(f"draft_index.py --out 失败（退出码 {code}）：{tail(out)}")
        log(f"已存在索引 {index_path}，初稿改写 {draft}")
        return draft, False
    code, out = run_tool(["draft_index.py", key, "--write"])
    if code != 0 or not index_path.is_file():
        warnings.append(f"draft_index.py --write 失败（退出码 {code}）：{tail(out)}")
    return index_path, True


# ---------------------------------------------------------------- 拼版表

def page_bounds(pdf: Path) -> dict[int, tuple[float, float, float, float]]:
    import pymupdf
    bounds: dict[int, tuple[float, float, float, float]] = {}
    with pymupdf.open(pdf) as doc:
        for index, page in enumerate(doc):
            bounds[index + 1] = P.analysis_bounds(page)
    return bounds


def _bbox_ok(bbox, page: int, bounds) -> bool:
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return False
    if page not in bounds:
        return False
    try:
        x0, y0, x1, y1 = (float(v) for v in bbox)
    except (TypeError, ValueError):
        return False
    box = bounds[page]
    return box[0] <= x0 < x1 <= box[2] and box[1] <= y0 < y1 <= box[3]


class RegionCollector:
    """按 (page, bbox) 去重地收集区域，顺带丢掉越界的框并记警告。"""

    def __init__(self, role: str, bounds: dict, warnings: list[str]):
        self.role = role
        self.bounds = bounds
        self.warnings = warnings
        self.seen: set = set()
        self.spec: list[dict] = []
        self.skipped = 0

    def add(self, label, page, bbox) -> None:
        if len(self.spec) >= MAX_REGIONS_PER_ROLE:
            return
        if not isinstance(page, int) or not isinstance(label, str):
            return
        key = (page, tuple(round(float(v), 1) for v in bbox)) if (
            isinstance(bbox, (list, tuple)) and len(bbox) == 4) else None
        if key is None or key in self.seen:
            return
        if not _bbox_ok(bbox, page, self.bounds):
            self.skipped += 1
            self.warnings.append(
                f"{self.role} 区域 {label} p{page} {bbox} 越界或非法，已跳过（不影响其余区域）")
            return
        self.seen.add(key)
        self.spec.append({"label": label, "role": self.role, "page": page, "bbox": list(bbox)})


def collect_qp_regions(questions, proposal, bounds, warnings) -> list[dict]:
    collector = RegionCollector("qp", bounds, warnings)
    for question in questions:
        label = question.get("question")
        for region in question.get("qp") or []:
            if isinstance(region, dict):
                collector.add(label, region.get("page"), region.get("bbox"))
    for candidate in (proposal or {}).get("question_candidates") or []:
        if not isinstance(candidate, dict):
            continue
        label = candidate.get("question")
        regions = candidate.get("regions")
        if not isinstance(regions, list) or not regions:
            regions = [{"page": candidate.get("page"), "bbox": candidate.get("bbox")}]
        for region in regions:
            if isinstance(region, dict):
                collector.add(label, region.get("page"), region.get("bbox"))
    return collector.spec


def collect_ms_regions(questions, proposal, bounds, warnings) -> list[dict]:
    collector = RegionCollector("ms", bounds, warnings)
    for question in questions:
        label = question.get("question")
        for region in question.get("ms") or []:
            if isinstance(region, dict):
                collector.add(label, region.get("page"), region.get("bbox"))
    for row in (proposal or {}).get("ms_candidates") or []:
        if not isinstance(row, dict) or row.get("page_has_table_header") is False:
            continue
        collector.add(row.get("label"), row.get("page"), row.get("row_bbox"))
    return collector.spec


def url_of(path: Path) -> str:
    return f"{SHEET_BASE}/{SHEET_REL}/{path.name}"


def labels_from_html(path: Path) -> list[str]:
    try:
        html = path.read_text(encoding="utf-8")
    except OSError:
        return []
    labels = []
    for match in CAP_RE.finditer(html):
        label = match.group(1).split(" [")[0].strip()
        if label:
            labels.append(label)
    return labels


def page_sheets(tmp_dir: Path, role: str, key: str, sheets: list[dict],
                warnings: list[str]) -> None:
    pages_dir = tmp_dir / "pages"
    images = sorted(pages_dir.glob(f"{role}-p*.png"),
                    key=lambda p: SH.parse_page_no(p) or 0)
    cells = [{"src": SH.rel_url(image),
              "caption": f"{role} p{SH.parse_page_no(image)}"}
             for image in images if SH.parse_page_no(image) is not None]
    if not cells:
        warnings.append(f"{role} 没有页面渲染图，跳过整页总览表")
        return
    written = SH.write_sheets(cells, PAGE_COLS, f"{SH.slug(key)}-{role}-pages",
                              f"{key} {role} pages")
    _cell, _rows, capacity = SH.cell_geometry(PAGE_COLS)
    for index, path in enumerate(written):
        chunk = cells[index * capacity:(index + 1) * capacity]
        sheets.append({"kind": f"{role}-pages", "url": url_of(path),
                       "labels": [cell["caption"] for cell in chunk]})
    log(f"{role} 整页总览：{len(cells)} 页 / {len(written)} 张表")


def region_sheets(key: str, role: str, spec: list[dict], qp: Path, ms: Path | None,
                  sheets: list[dict], warnings: list[str]) -> None:
    if not spec:
        warnings.append(f"{role} 没有可用的区域，跳过区域密集表")
        return
    name = f"{SH.slug(key)}-{role}-regions"
    try:
        written = SS.build(key, spec, name, {"qp": str(qp),
                                             "ms": str(ms) if ms else None})
    except Exception as exc:  # noqa: BLE001 - 区域表失败只降级，不中断
        warnings.append(f"{role} 区域密集表生成失败：{exc}")
        return
    for path in written:
        sheets.append({"kind": f"{role}-regions", "url": url_of(path),
                       "labels": labels_from_html(path)})
    log(f"{role} 区域密集表：{len(spec)} 个区域 / {len(written)} 张表")


# ---------------------------------------------------------------- 主流程

def blank_manifest(key: str) -> dict:
    return {"key": key, "tmp_dir": None, "qp_pdf": None, "ms_pdf": None,
            "qp_sha256": None, "ms_sha256": None, "qp_pages": None, "ms_pages": None,
            "draft_path": None, "draft_written": None, "question_count": 0,
            "ms_row_count": 0,
            "text_layer": {"qp": {"clean_pages": [], "garbled_pages": []},
                           "ms": {"clean_pages": [], "garbled_pages": []}},
            "sheets": [], "warnings": []}


def emit(manifest: dict) -> None:
    sys.stdout.write(json.dumps(manifest, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> int:
    _stdout_utf8()
    parser = argparse.ArgumentParser(
        description="单卷本地准备：原件检查、提案、初稿、文字层体检、拼版表")
    parser.add_argument("key", help="subject/year/season/paper，如 9709/2024/Jun/11")
    args = parser.parse_args()
    key = args.key.strip()
    manifest = blank_manifest(key)
    warnings = manifest["warnings"]

    if not KEY_RE.match(key) or key.split("/")[2] not in B.SEASONS:
        manifest["error"] = ("key 必须是 subject/year/season/paper，season ∈ "
                             f"{list(B.SEASONS)}，例如 9709/2024/Jun/11")
        emit(manifest)
        return EXIT_USAGE

    tmp_dir = P.paper_tmp(key)
    manifest["tmp_dir"] = str(tmp_dir)

    # 1. 原件
    qp, ms = find_pdfs(key)
    missing = missing_roles(key, qp, ms)
    if missing:
        log(f"缺少原件 {missing}，调用 run_paper.py --stage fetch")
        code, out = run_tool(["run_paper.py", key, "--stage", "fetch"])
        if code != 0:
            manifest["error"] = (f"原件缺失 {missing}，run_paper.py --stage fetch "
                                 f"退出码 {code}")
            warnings.append(f"fetch 失败（退出码 {code}）：{tail(out)}")
            emit(manifest)
            return code or EXIT_FAILED
        qp, ms = find_pdfs(key)
        if qp is None:
            manifest["error"] = "fetch 之后仍然找不到 QP PDF"
            emit(manifest)
            return EXIT_BLOCKED

    manifest["qp_pdf"] = str(qp)
    manifest["ms_pdf"] = str(ms) if ms else None
    if ms is None:
        warnings.append("没有 MS 原件，MS 相关步骤全部跳过")

    pdfs = [p for p in (qp, ms) if p is not None]
    manifest["qp_sha256"] = B.sha256_file(qp)
    manifest["ms_sha256"] = B.sha256_file(ms) if ms else None
    manifest["qp_pages"] = P.validate_pdf(qp)["pages"]
    manifest["ms_pages"] = P.validate_pdf(ms)["pages"] if ms else None

    # 2. 提案
    if not ensure_proposal(key, pdfs, warnings):
        manifest["error"] = f"没有可用的提案 {proposal_path(key)}"
        emit(manifest)
        return EXIT_FAILED

    # 3. 初稿（已有索引绝不覆盖）
    draft_file, draft_written = ensure_draft(key, warnings)
    manifest["draft_path"] = str(draft_file)
    manifest["draft_written"] = draft_written
    index_path = I.index_path(key)
    index_data = load_json(index_path) if index_path.is_file() else None
    draft_data = load_json(draft_file)
    if draft_written:
        manifest["question_count"] = len((draft_data or {}).get("questions") or [])
    elif index_data is not None:
        manifest["question_count"] = len(index_data.get("questions") or [])
    else:
        manifest["question_count"] = len((draft_data or {}).get("questions") or [])
    if draft_data is None:
        warnings.append(f"初稿 {draft_file} 读不出来（不是合法 JSON）")

    proposal = load_json(proposal_path(key))
    manifest["ms_row_count"] = len((proposal or {}).get("ms_candidates") or [])
    if not draft_written and index_data is not None:
        log(f"已有索引保留不动：{index_path}")

    # 4. 文字层体检
    manifest["text_layer"] = {"qp": text_layer_report(qp),
                              "ms": text_layer_report(ms)}
    for role in ("qp", "ms"):
        garbled = manifest["text_layer"][role]["garbled_pages"]
        if garbled:
            shown = "、".join(str(p) for p in garbled[:20])
            warnings.append(
                f"{role.upper()} 文字层错乱页 {garbled}（共 {len(garbled)} 页：{shown}）："
                f"这些页的文字层不可信，纯算法解析跳过（不使用 OCR，也不照抄文字层）")

    # 5. 拼版表
    if not (tmp_dir / "pages").is_dir():
        (tmp_dir / "pages").mkdir(parents=True, exist_ok=True)
    for role, pdf in (("qp", qp), ("ms", ms)):
        if pdf is None:
            continue
        try:
            R.render_doc(pdf, tmp_dir / "pages", role, manifest[f"{role}_pages"], False)
        except Exception as exc:  # noqa: BLE001 - 渲染失败只降级，不中断
            warnings.append(f"{role} 页面渲染失败：{exc}")

    sheets = manifest["sheets"]
    for role, pdf in (("qp", qp), ("ms", ms)):
        if pdf is not None:
            page_sheets(tmp_dir, role, key, sheets, warnings)

    sheet_questions = index_data.get("questions") if (
        not draft_written and index_data and index_data.get("questions")) else None
    if sheet_questions is None:
        sheet_questions = (draft_data or {}).get("questions") or []

    for role, pdf in (("qp", qp), ("ms", ms)):
        if pdf is None:
            continue
        bounds = page_bounds(pdf)
        if role == "qp":
            spec = collect_qp_regions(sheet_questions, proposal, bounds, warnings)
        else:
            spec = collect_ms_regions(sheet_questions, proposal, bounds, warnings)
        region_sheets(key, role, spec, qp, ms, sheets, warnings)

    emit(manifest)
    log(f"完成 {key}：题数 {manifest['question_count']}  MS 行带 "
        f"{manifest['ms_row_count']}  表 {len(sheets)} 张  警告 {len(warnings)} 条")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
