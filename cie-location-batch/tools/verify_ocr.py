"""对一份已定位索引的每个题目区域做本地裁剪 + OCR 核验，写 verification.jsonl。

Windows.Media.Ocr（work/ocr_batch.ps1）辅助检查题号和墨迹。
本工具的通过结果只是自动检查，不能替代提示词第 9 节要求的逐区域
目视核对题干、公式、图形、边界和评分对应。日志如实写明未做截图；
cleanup_paper 的目视证据闸门会阻止仅凭本工具结果删除 PDF。

流程（全程只读本地 PDF，不联网）：
1. 逐题逐区域裁剪 -> tmp/<卷>/crops/
2. 一次 PowerShell 批量 OCR（裁剪图 + 整页图）
3. 逐区域判定：首区域是否印着题号、区域是否有可见墨迹、是否混入下一个非后代题号
4. 整页判定：题号顶层数字是否出现在该页 OCR 里（仅供参考，不单独判失败）
5. 写 verification.jsonl；删除裁剪图

跨页题的续接区域按阅读顺序不会重复题号，所以题号检查只对每题第一个区域强制；
「下一题」取文档顺序里第一个非后代题号，否则父题的区域天然包含子题会被误判。

`--report` 只打印观测结果、不写日志，用于标定。
"""
from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import batchlib as B
import paperlib as P

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OCR_PS1 = B.WORK / "ocr_batch.ps1"
PAGE_ZOOM = 2.5
CROP_ZOOM = 3.0
MIN_CROP_PX = 24


def canon(text: str) -> str:
    """OCR 会把 `(` `)` 读成全角 `（` `）`，先做 NFKC 归一化再比对标签。

    实测：9608 MS p10 的 `11 （ a ）` 只认得出 `11`，认不出 `11(a)`，导致区域被判失败。
    """
    return unicodedata.normalize("NFKC", text or "")


def norm(text: str) -> str:
    return re.sub(r"[^0-9a-z]", "", canon(text).lower())


def label_parts(label: str) -> list[str]:
    return re.findall(r"[0-9]+|[a-z]+", canon(label).lower())


# OCR 常把罗马数字读成阿拉伯数字或竖线：`(i)` -> `(0)`、`(1)`、`(l)`、`(|)`。
# 与 ocr_index.ROMAN_FIX 同源（反向展开），这里只做比对用。
ROMAN_VARIANTS = {
    "i": ("i", "1", "l", "|", "0"),
    "ii": ("ii", "11", "ll", "1i"),
    "iii": ("iii", "111", "1ii"),
    "iv": ("iv", "1v"),
    "vi": ("vi", "v1", "vl"),
}


def label_head_match(text: str, qid: str) -> bool:
    """文本开头是不是本题的标签。

    版面惯例：题号只在题首印一次，子题行只印 `(b)`、`(e)` 这样的最后一段，父号在上一行
    甚至上一页。所以既接受完整题号 `4(e)`、`4 (e)`，也接受任意后缀——`(a)(ii)`、
    `(g)(i)`、`(i)`——因为父段可能不在本区域内。

    两种段形：带括号的 `( a )`（OCR 会把括号读成全角并塞进空格，先 NFKC 归一化）和
    裸段 `a`。裸段后面必须是非字母数字，`elephants` 不算 `(e)`；带括号的段天然有
    定界符，所以 `(2)(a)(0)Abilities` 这种「右括号后紧跟字母」仍然算匹配。
    罗马数字在括号里额外接受 OCR 变体，裸段只认原形（裸 `1`、`0` 更可能是分值或年份）。
    """
    t = canon(text).lstrip()
    parts = label_parts(qid)
    if not t or not parts:
        return False

    def alts(part: str) -> str:
        return "|".join(re.escape(v) for v in ROMAN_VARIANTS.get(part, (part,)))

    def seg_open(part: str) -> str:
        """非末段：不设词尾守卫，否则 `10a five` 认不出 `10(a)`。"""
        return rf"(?:\(\s*(?:{alts(part)})\s*\)|{alts(part)})"

    def seg_last(part: str) -> str:
        """末段：裸形后面必须是非字母数字，`elephants` 不算 `(e)`。

        带括号的形天然有定界符，所以 `(2)(a)(0)Abilities` 仍算匹配——OCR 把罗马
        数字 `(i)` 读成 `(0)` 后，右括号紧跟着正文首字母，这是类别 2 失败的直接原因。

        纯数字的 OCR 变体（`0`=`(i)`、`1`=`(i)`）额外禁止后面紧跟 `(` `[`：否则
        `1(a)` 会被当成 `1(a)(i)`。
        """
        forms = []
        for v in ROMAN_VARIANTS.get(part, (part,)):
            esc = re.escape(v)
            if v != part and v.isdigit():
                forms.append(rf"{esc}(?![a-z0-9(\[])")
            else:
                forms.append(rf"{esc}(?![a-z0-9])")
        return rf"(?:\(\s*(?:{alts(part)})\s*\)|(?:{'|'.join(forms)}))"

    def build(seq: list[str]) -> str:
        return r"\s*".join(
            seg_last(p) if i == len(seq) - 1 else seg_open(p)
            for i, p in enumerate(seq))

    if re.match(rf"^\W{{0,3}}{build(parts)}", t, re.I):
        return True
    # 长的后缀优先：`1(g)(i)` 的区域内可能只印着 `(g)(i)` 或 `(i)`。
    for k in range(1, len(parts)):
        if re.match(rf"^\W{{0,3}}{build(parts[k:])}", t, re.I):
            return True
    return False


def index_path_for(key: str) -> Path:
    subject, year, season, paper = key.split("/")
    return B.index_dir(subject, int(year), season, paper) / "cie-index.json"


def locate(key: str, role: str) -> Path | None:
    import import_index as I
    return I.locate_pdf(key, role)


def run_ocr(paths: list[Path], tmp_dir: Path) -> dict[str, list[dict]]:
    """返回 {绝对路径: [{x0,y0,x1,y1,text}, ...]}。"""
    if not paths:
        return {}
    tmp_dir.mkdir(parents=True, exist_ok=True)
    listing = tmp_dir / "_ocr_list.txt"
    outfile = tmp_dir / "_ocr_out.tsv"
    listing.write_text("\n".join(str(p) for p in paths), encoding="utf-8")
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(OCR_PS1), "-List", str(listing), "-Out", str(outfile)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"OCR 失败 rc={proc.returncode} {proc.stdout} {proc.stderr}")
    result: dict[str, list[dict]] = defaultdict(list)
    if not outfile.exists():
        return result
    for line in outfile.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        path, kind = parts[0], parts[1]
        if kind == "ERR":
            result[path].append({"error": parts[2] if len(parts) > 2 else "unknown"})
            continue
        if kind == "SIZE":
            result[path].append({"size": [int(parts[2]), int(parts[3])]})
            continue
        if kind == "LINE" and len(parts) >= 7:
            result[path].append({"x0": float(parts[2]), "y0": float(parts[3]),
                                 "x1": float(parts[4]), "y1": float(parts[5]),
                                 "text": parts[6]})
    return result


def text_of(rows: list[dict]) -> str:
    return " ".join(r["text"] for r in rows if "text" in r)


def size_of(rows: list[dict]) -> list[int] | None:
    for r in rows:
        if "size" in r:
            return r["size"]
    return None


def ink_fraction(png: Path) -> float | None:
    """裁剪图里非白像素占比，用来区分「空白答题区」和「有内容的区域」。"""
    try:
        import pymupdf
        pm = pymupdf.Pixmap(str(png))
        if pm.n > 3:
            pm = pymupdf.Pixmap(pm, 0)
        samples = pm.samples
        if not samples:
            return None
        dark = 0
        for b in samples:
            if b < 200:
                dark += 1
        return dark / len(samples)
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("key")
    parser.add_argument("--index")
    parser.add_argument("--roles", default="")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--no-pages", action="store_true")
    parser.add_argument("--keep-crops", action="store_true")
    args = parser.parse_args()

    key = args.key
    index_file = Path(args.index) if args.index else index_path_for(key)
    data = json.loads(index_file.read_bytes().decode("utf-8"))
    questions = [q for q in (data.get("questions") or []) if isinstance(q, dict)]
    roles = [r for r in (args.roles.split(",") if args.roles else
                         [d.get("role") for d in (data.get("documents") or [])]) if r]

    tmp_dir = P.paper_tmp(key)
    crops_dir = tmp_dir / "crops"
    pages_dir = tmp_dir / "pages"

    pdfs: dict[str, Path] = {}
    for role in roles:
        path = locate(key, role)
        if path is not None:
            pdfs[role] = path
    missing = [r for r in roles if r not in pdfs]

    jobs: list[tuple[str, str, str, int, list[float]]] = []
    crop_paths: list[Path] = []
    problems_before: list[str] = []

    for question in questions:
        qid = question.get("question")
        if not isinstance(qid, str):
            continue
        for role in roles:
            if role not in pdfs:
                continue
            regions = question.get(role) or []
            for i, region in enumerate(regions):
                page_no = region.get("page")
                bbox = region.get("bbox")
                out = crops_dir / f"{qid.replace('/', '_')}__{role}__p{page_no}__{i}.png"
                try:
                    P.crop_region(pdfs[role], page_no, bbox, out, zoom=CROP_ZOOM)
                except Exception as exc:
                    problems_before.append(f"{qid}/{role}/p{page_no}: 裁剪失败 {exc}")
                    continue
                jobs.append((qid, role, "region", page_no, bbox))
                crop_paths.append(out)

    pages: dict[int, Path] = {}
    if not args.no_pages:
        for role in roles:
            if role not in pdfs:
                continue
            import pymupdf
            with pymupdf.open(pdfs[role]) as pdf:
                total = pdf.page_count
            for page_no in range(1, total + 1):
                out = pages_dir / f"{role}-p{page_no:03d}-z{PAGE_ZOOM}.png"
                if not out.exists():
                    P.render_page(pdfs[role], page_no, out, zoom=PAGE_ZOOM)
                pages[(role, page_no)] = out

    ocr_inputs = list(crop_paths) + list(pages.values())
    ocr = run_ocr(ocr_inputs, tmp_dir)

    # 整页 OCR 行的显示态坐标：裁剪图只有一块，OCR 常在边界上丢字；整页渲染留白多、
    # 上下文完整，用它给「区域顶端是不是本题的标签行」做第二意见。
    import pymupdf
    rot: dict[tuple[str, int], object] = {}
    for role, path in pdfs.items():
        with pymupdf.open(path) as pdf:
            for page_no in range(1, pdf.page_count + 1):
                rot[(role, page_no)] = pdf[page_no - 1].rotation_matrix
    page_rows: dict[tuple[str, int], list[dict]] = {}
    for rk, png in pages.items():
        page_rows[rk] = [{"y0": r["y0"] / PAGE_ZOOM, "text": r["text"]}
                         for r in ocr.get(str(png), []) if "text" in r]

    def page_label_at_top(role: str, page_no: int, bbox: list[float],
                          qid: str) -> str | None:
        mat = rot.get((role, page_no))
        if mat is None:
            return None
        r = pymupdf.Rect(bbox) * mat
        for row in page_rows.get((role, page_no), []):
            if not (-3.0 <= row["y0"] - r.y0 <= 28.0):
                continue
            if label_head_match(row["text"], qid):
                return row["text"][:40]
        return None

    def label_at_top_text_layer(role: str, page_no: int, bbox: list[float],
                                qid: str) -> str | None:
        # OCR 对加粗题号（15/16/…/22）有稳定漏检，而这些 PDF 的文字层数字是权威的；
        # 只在裁剪 OCR 与整页 OCR 都失败后做最后兜底，乱码文字层自然匹配不上。
        try:
            with pymupdf.open(pdfs[role]) as pdf:
                page = pdf[page_no - 1]
                mat = page.rotation_matrix
                r = pymupdf.Rect(bbox) * mat
                words = []
                for w in page.get_text("words"):
                    wr = pymupdf.Rect(w[:4]) * mat
                    if not (-5.0 <= wr.y0 - r.y0 <= 45.0):
                        continue
                    if wr.x1 < r.x0 - 5.0 or wr.x0 > r.x1 + 5.0:
                        continue
                    words.append((round(wr.y0, 1), wr.x0, w[4]))
                if not words:
                    return None
                words.sort(key=lambda t: (t[0], t[1]))
                # 同一行里不同字体的 y0 能差零点几 pt（q22 的 '22' 与同行正文差 0.36pt），
                # 先按 y0 聚行、行内按 x0 排序，避免行内正文被排到行首标签之前。
                lines: list[list[tuple[float, float, str]]] = []
                for w in words:
                    if lines and w[0] - lines[-1][0][0] <= 3.5:
                        lines[-1].append(w)
                    else:
                        lines.append([w])
                ordered: list[tuple[float, float, str]] = []
                for ln in lines:
                    ln.sort(key=lambda t: t[1])
                    ordered.extend(ln)
                joined = " ".join(t[2] for t in ordered)
                if label_head_match(joined, qid):
                    return joined[:40]
        except Exception:
            pass
        return None

    # 题目顺序 -> 下一题题号。父题的区域天然包含自己的子题，所以「下一题」必须是
    # 文档顺序里第一个**非后代**题号，否则每个父题都会被误判为混入下一题。
    order = [q.get("question") for q in questions if isinstance(q.get("question"), str)]
    nxt: dict[str, str | None] = {}
    for i, qid in enumerate(order):
        following = None
        for other in order[i + 1:]:
            if not other.startswith(qid + "("):
                following = other
                break
        nxt[qid] = following

    records = []
    if args.report:
        print("QID\tROLE\tPAGE\tBBOX\tNORM_HEAD\tTEXT_HEAD")

    index_of_job = 0
    for question in questions:
        qid = question.get("question")
        if not isinstance(qid, str):
            continue
        parts = label_parts(qid)
        full = norm(qid)
        # 子子题（如 1(a)(ii)）在版面上单独成行时只印最后一段「(ii)」，父段在上一行、
        # 不在本区域内；用整段 'aii' 去比对首区域必然落空，所以按最后一段判定。
        tail = parts[-1] if len(parts) > 1 else ""
        for role in roles:
            if role not in pdfs:
                continue
            regions = question.get(role) or []
            for i, region in enumerate(regions):
                page_no = region.get("page")
                bbox = region.get("bbox")
                out = crops_dir / f"{qid.replace('/', '_')}__{role}__p{page_no}__{i}.png"
                if index_of_job < len(jobs) and jobs[index_of_job][:3] == (qid, role, "region"):
                    index_of_job += 1
                rows = ocr.get(str(out), [])
                text = text_of(rows)
                head = norm(text)[:80]
                size = size_of(rows)
                checks: dict[str, object] = {}
                issues: list[str] = []
                is_first = (i == 0)
                checks["head"] = head[:60]
                checks["region_index"] = i
                checks["region_count"] = len(regions)
                checks["rendered"] = bool(size)
                if not size:
                    issues.append("裁剪图没有渲染成功或 OCR 无输出")
                else:
                    checks["pixels"] = size
                    if min(size) < MIN_CROP_PX:
                        issues.append(f"裁剪图过小 {size}")
                checks["ocr_lines"] = len([r for r in rows if "text" in r])
                checks["text_chars"] = len(text)
                ink = ink_fraction(out) if out.exists() else None
                if ink is not None:
                    checks["ink_fraction"] = round(ink, 5)
                # 只有该题的第一个区域必须印着题号；跨页续接区域按阅读顺序不会重复题号。
                if is_first:
                    ok_label = label_head_match(text, qid)
                    checks["label_in_crop"] = ok_label
                    page_label = page_label_at_top(role, page_no, bbox, qid) \
                        if not args.no_pages else None
                    if page_label:
                        checks["page_label_at_top"] = page_label
                        ok_label = True
                    if not ok_label:
                        tl_head = label_at_top_text_layer(role, page_no, bbox, qid)
                        if tl_head:
                            checks["label_in_text_layer"] = tl_head
                            ok_label = True
                    checks["label_present"] = ok_label
                    if not ok_label:
                        issues.append(f"首区域开头没有出现题号 {qid!r}（OCR 前 80 字：{head[:40]!r}）")
                else:
                    checks["continuation_region"] = True
                if len(text.strip()) < 2 and (ink is None or ink < 0.005):
                    issues.append("裁剪区域既没有 OCR 文字也没有可见墨迹")
                following = nxt.get(qid)
                if following and is_first and not checks.get("label_present"):
                    # 首区域已经确认印着本题题号，就不可能同时又以下一题的题号开头；
                    # 而「下一题题号出现在正文里」全是假阳性（`3 marks`、`stage 2`）。
                    # 所以只在首区域自己的标签没找到时，才用下一题标签做诊断。
                    # 续接区域（i>0）本来就接着上一页写，开头出现任何正文都不算问题。
                    head_row = next((r["text"] for r in rows if "text" in r), "")
                    hit_next = label_head_match(head_row, following)
                    checks["next_label_in_head"] = bool(hit_next)
                    if hit_next:
                        issues.append(f"裁剪区域开头混入了下一题 {following!r}")
                if not args.no_pages:
                    page_key = (role, page_no)
                    prows = ocr.get(str(pages.get(page_key, "")), [])
                    ptext = norm(text_of(prows))
                    checks["top_on_page"] = bool(parts and parts[0] in ptext)
                records.append({
                    "at": B.now_iso(), "key": key, "question": qid, "role": role,
                    "page": page_no, "bbox": bbox,
                    "checks": checks, "issues": issues,
                    "method": "local_crop+Windows.Media.Ocr(zh-Hans-CN); 未做 page.visual.snapshot",
                    "checked_at": B.now_iso(),
                })
                if args.report:
                    print(f"{qid}\t{role}\tp{page_no}\t{bbox}\t{head[:40]}\t{text[:70]!r}")

    for role in missing:
        records.append({
            "at": B.now_iso(), "key": key, "question": "__documents__", "role": role,
            "page": 0, "bbox": None,
            "checks": {"document_present": False},
            "issues": [f"索引声明了 {role} 但临时目录里找不到对应 PDF"],
            "method": "local_crop+Windows.Media.Ocr(zh-Hans-CN)",
            "checked_at": B.now_iso(),
        })

    failed = sum(1 for r in records if r["issues"])
    if not args.report:
        for record in records:
            B.append_jsonl(B.VERIFICATION, record)

    if not args.keep_crops:
        removed = 0
        for path in crop_paths:
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
        print(f"删除裁剪图 {removed}/{len(crop_paths)}")

    print(json.dumps({
        "key": key, "index": str(index_file),
        "questions": len(questions), "roles": roles, "missing_roles": missing,
        "regions_checked": len(records), "regions_failed": failed,
        "crop_failures": problems_before[:10],
        "records_written": 0 if args.report else len(records),
    }, ensure_ascii=False, indent=2))
    return 0 if not problems_before else 1


if __name__ == "__main__":
    raise SystemExit(main())
