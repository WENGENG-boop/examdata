#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""Pearson Edexcel 公开真题资源结构探测器（只读）。

用法（Windows PowerShell）：
    $env:PYTHONIOENCODING='utf-8'
    .venv\Scripts\python.exe scripts\probe_edexcel.py

设计约束（与 src/examdata/core/fetch.py 的契约一致）：
  * httpx.Client(trust_env=False)：本机环境变量会注入代理，必须绕开。
  * 每个请求间隔 >= 1.0s（本脚本用 1.1s），单进程串行。
  * 只用公开 GET；不登录、不带 Cookie、不绕过任何访问控制。
  * 请求前先用 urllib.robotparser 判定 robots，命中 Disallow 直接跳过并报告。

发现链路（三层，均已在 research/edexcel.md 实测）：
  1. 家族落地页 -> #sortaz 的 data-ng-init="initSubjectList('<cms-path>','')"
     -> GET /services/pearson/subjectlistaz/GET.servlet?currentPage=<cms-path>
     -> JSON {subjectList:[{title,path,childPages:[...]}]}
  2. 科目页 {cms-path}.html -> data-ng-controller="facetListCtrl" 的
     data-ng-init="init('coursematerials','[tag1, tag2, ...]',...)"  -> facet 标签集
  3. 资源列表 -> GET /services/pearson/algolia/GET.servlet?fq=<tag1 AND tag2 ...>
     -> JSON {searchResults:{algoliaRecords:[{title,url,extension,gating,category,...}]}}
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.robotparser
from collections import Counter
from typing import Any, Optional

import httpx

ORIGIN = "https://qualifications.pearson.com"
ROBOTS_URL = ORIGIN + "/robots.txt"
UA = "Mozilla/5.0 (compatible; examdata-research/0.1; +https://example.invalid/bot)"
RATE_SECONDS = 1.1
TIMEOUT = 45.0

# 家族定义：(URL 路径段, Algolia facet 家族名, 显示名, 落地页)
#
# 重要：URL 路径段与 Algolia 的 Pearson-UK:Qualification-Family 取值**不同名**，
# 例如 URL 是 /edexcel-international-gcses/ 而 facet 是 International-GCSE。
# 混用会得到 0 结果（实测：用 URL 段拼 facet 查询返回 60 字节的空响应）。
FAMILIES = [
    ("edexcel-international-gcses", "International-GCSE",
     "International GCSE (IGCSE)",
     "/en/qualifications/edexcel-international-gcses.html"),
    ("edexcel-international-advanced-levels", "International-Advanced-Level",
     "International A Level (IAL)",
     "/en/qualifications/edexcel-international-advanced-levels.html"),
    ("edexcel-a-levels", "A-Level",
     "GCE A Level",
     "/en/qualifications/edexcel-a-levels.html"),
    ("edexcel-gcses", "GCSE",
     "GCSE",
     "/en/qualifications/edexcel-gcses.html"),
]

# 实测正则
RE_NG_INIT_SUBJECTS = re.compile(
    r"""initSubjectList\(\s*'([^']+)'\s*,""", re.I)
RE_NG_INIT_FACETS = re.compile(
    r"""data-ng-controller="facetListCtrl"[^>]*data-ng-init="init\('([^']*)',\s*'\[([^\]]*)\]'""",
    re.I | re.S)
RE_SITEMAP_LOC = re.compile(r"<loc>([^<]+)</loc>", re.I)
# 科目页 URL 规律：/en/qualifications/{family}/{subject-slug}.html
# servlet 返回的是 CMS 路径 /content/demo/en/qualifications/...，先剥前缀再匹配
RE_CMS_PREFIX = re.compile(r"^/content/[a-z0-9\-]+", re.I)
RE_SUBJECT_PAGE = re.compile(
    r"^/en/qualifications/(?P<family>[a-z0-9\-]+)/(?P<slug>[a-z0-9\-]+)(?:\.html)?$", re.I)


def to_public_path(cms_path: str) -> str:
    """'/content/demo/en/qualifications/x/y' -> '/en/qualifications/x/y'。"""
    return RE_CMS_PREFIX.sub("", cms_path.strip())

_last_request = [0.0]


class Probe:
    """带 robots 判定 + 限速 + 状态码记录的只读抓取器。"""

    def __init__(self) -> None:
        self.client = httpx.Client(
            trust_env=False,                      # 必须：本机 env 会注入代理
            follow_redirects=True,
            timeout=TIMEOUT,
            headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
                "Accept-Language": "en-GB,en;q=0.9",
            },
        )
        self.robots: Optional[urllib.robotparser.RobotFileParser] = None
        self.robots_status: Optional[int] = None
        self.blocked: list[str] = []
        self.log: list[tuple[str, str, str]] = []   # (method, url, note)

    # -- robots ---------------------------------------------------------
    def load_robots(self) -> None:
        r = self.client.get(ROBOTS_URL)
        self.robots_status = r.status_code
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(r.text.splitlines())
        self.robots = rp
        self._note("GET", ROBOTS_URL, "HTTP %s" % r.status_code)

    def allowed(self, url: str) -> bool:
        if self.robots is None:
            return True
        return self.robots.can_fetch(UA, url)

    # -- 限速 -----------------------------------------------------------
    def _throttle(self) -> None:
        wait = RATE_SECONDS - (time.monotonic() - _last_request[0])
        if wait > 0:
            time.sleep(wait)
        _last_request[0] = time.monotonic()

    def _note(self, method: str, url: str, note: str) -> None:
        self.log.append((method, url, note))

    def get(self, url: str, **kw) -> Optional[httpx.Response]:
        if not self.allowed(url):
            self.blocked.append(url)
            self._note("GET", url, "SKIPPED robots-disallowed")
            return None
        self._throttle()
        try:
            r = self.client.get(url, **kw)
        except Exception as exc:                  # noqa: BLE001
            self._note("GET", url, "ERR %s: %s" % (type(exc).__name__, exc))
            return None
        self._note("GET", url, "HTTP %s (%d bytes)" % (r.status_code, len(r.content)))
        return r

    def head(self, url: str) -> Optional[httpx.Response]:
        if not self.allowed(url):
            self.blocked.append(url)
            self._note("HEAD", url, "SKIPPED robots-disallowed")
            return None
        self._throttle()
        try:
            r = self.client.head(url)
        except Exception as exc:                  # noqa: BLE001
            self._note("HEAD", url, "ERR %s: %s" % (type(exc).__name__, exc))
            return None
        self._note("HEAD", url, "HTTP %s ct=%s" % (r.status_code, r.headers.get("content-type")))
        return r

    def get_json(self, url: str, **kw) -> Optional[Any]:
        r = self.get(url, **kw)
        if r is None or r.status_code != 200:
            return None
        try:
            return r.json()
        except Exception as exc:                  # noqa: BLE001
            self._note("JSON", url, "decode failed: %s" % exc)
            return None


# ---------------------------------------------------------------------
# 第 1 层：科目枚举
#
# 实测结论（research/edexcel.md §3.1）：
#   * /services/pearson/subjectlistaz/GET.servlet 的 currentPage 参数**被忽略** ——
#     无论传什么路径，永远返回同一份 IGCSE 的 52 个顶层科目。
#     因此它只能用于 IGCSE，不能作为通用科目枚举入口。
#   * 通用入口是 Algolia 索引上的 cq:Page 记录：
#       filters = 'type:"cq:Page" AND category:"Pearson-UK:Qualification-Family/{FAM}"'
#     返回值里过滤 /en/qualifications/{family}/{slug}.html 即得科目页集合。
# ---------------------------------------------------------------------
ALGOLIA_SERVLET = "/services/pearson/algolia/GET.servlet"
SUBJECTLIST_SERVLET = "/services/pearson/subjectlistaz/GET.servlet"

# 每个家族最多取多少条 cq:Page 记录（实测最大 1041，取 2000 足够）
CQ_PAGE_PAGE_SIZE = 2000


def discover_subjects_algolia(p: Probe) -> dict[str, list[dict]]:
    """通用入口：Algolia cq:Page -> 科目页 URL 集合。"""
    out: dict[str, list[dict]] = {}
    for family, facet_family, label, landing in FAMILIES:
        fq = 'type:"cq:Page" AND category:"Pearson-UK:Qualification-Family/%s"' % facet_family
        data = p.get_json(ORIGIN + ALGOLIA_SERVLET,
                          params={"fq": fq, "hitsPerPage": str(CQ_PAGE_PAGE_SIZE)})
        recs = ((data or {}).get("searchResults") or {}).get("algoliaRecords") or []
        prefix = "/en/qualifications/%s/" % family
        seen: dict[str, dict] = {}
        for rec in recs:
            u = (rec.get("url") or "").strip()
            if not u.startswith(prefix) or not u.endswith(".html"):
                continue
            tail = u[len(prefix):]
            if "/" in tail:                       # 只取一级科目页
                continue
            slug = tail[:-len(".html")]
            if not re.fullmatch(r"[a-z0-9\-]+", slug, re.I):
                continue
            mv = re.search(r"-(\d{4})(?:-|$)", slug)
            seen.setdefault(slug, {
                "title": (rec.get("title") or slug).strip(),
                "slug": slug,
                "page_url": ORIGIN + u,
                "version_year": int(mv.group(1)) if mv else None,
            })
        out[family] = sorted(seen.values(), key=lambda x: x["slug"])
        print("  [%s] Algolia cq:Page -> %d 个科目页" % (label, len(out[family])))
    return out


def discover_subjects_subjectlistaz(p: Probe) -> dict[str, list[dict]]:
    """辅助入口：subjectlistaz servlet（实测仅对 IGCSE 有效，作为旁证/对照）。"""
    out: dict[str, list[dict]] = {}
    for family, facet_family, label, landing in FAMILIES:
        r = p.get(ORIGIN + landing)
        if r is None or r.status_code != 200:
            out[family] = []
            continue
        m = RE_NG_INIT_SUBJECTS.search(r.text)
        if not m:
            out[family] = []
            continue
        cms_path = m.group(1)
        data = p.get_json(ORIGIN + SUBJECTLIST_SERVLET, params={"currentPage": cms_path})
        seen: dict[str, dict] = {}
        for item in (data or {}).get("subjectList") or []:
            for node in [item] + list(item.get("childPages") or []):
                path = (node.get("path") or "").strip()
                mm = RE_SUBJECT_PAGE.match(to_public_path(path))
                if not mm or mm.group("family") != family:
                    continue
                slug = mm.group("slug")
                seen.setdefault(slug, {"slug": slug,
                                       "title": (node.get("title") or slug).strip(),
                                       "page_url": ORIGIN + to_public_path(path) + ".html"})
        out[family] = sorted(seen.values(), key=lambda x: x["slug"])
        print("  [%s] subjectlistaz(cms=%s) -> %d 个科目页"
              % (label, cms_path, len(out[family])))
    return out


def subjects_from_sitemap(p: Probe) -> dict[str, set[str]]:
    """旁证：sitemap1.xml 的 URL 集合（robots 允许，但覆盖不全）。"""
    r = p.get(ORIGIN + "/en/sitemap1.xml")
    if r is None or r.status_code != 200:
        return {}
    locs = RE_SITEMAP_LOC.findall(r.text)
    res: dict[str, set[str]] = {}
    for u in locs:
        m = RE_SUBJECT_PAGE.match(u.replace(ORIGIN, ""))
        if m:
            res.setdefault(m.group("family"), set()).add(m.group("slug"))
    return res


# ---------------------------------------------------------------------
# 第 2 层：科目页 -> facet 标签
# ---------------------------------------------------------------------
def subject_facet_tags(p: Probe, page_url: str) -> Optional[list[str]]:
    r = p.get(page_url)
    if r is None or r.status_code != 200:
        return None
    m = RE_NG_INIT_FACETS.search(r.text)
    if not m:
        return None
    return [t.strip() for t in m.group(2).split(",") if t.strip()]


def select_facet_tags(tags: list[str]) -> list[str]:
    """把科目页给出的标签集压缩成一组互不冲突的查询标签。

    实测（research/edexcel.md §3.2）：科目页会给出多个 *互斥* 的
    Specification-Code 变体（A Level 数学 2017 实测有 6 个）。全 AND 起来会只剩
    1 条记录（只匹配到科目页自身），因为没有任何文档同时带全部变体。

    实测的互斥对（A Level 数学 2017，均返回 1 条）：
        al17-maths          x  A-Level/2017       -> 1
        al17-maths          x  2017               -> 1
        A-Level/2017        x  maths-2017-as-al   -> 1

    规则：保留 Qualification-Family + Qualification-Subject，
    外加**最具体的单个 Specification-Code**（斜杠最多者）。
    实测最具体者（A-Level/2017/al17-maths）给出 27 条；
    其余变体分别给 2 / 10 / 701 / 815 条 —— 都过宽或过窄。
    """
    family = [t for t in tags if t.startswith("Pearson-UK:Qualification-Family/")]
    subject = [t for t in tags if t.startswith("Pearson-UK:Qualification-Subject/")]
    spec = [t for t in tags if t.startswith("Pearson-UK:Specification-Code/")]

    picked = list(family) + list(subject)
    if spec:
        # 最具体 = 段数最多；同段数时取字符串最短（避开 A-Level/2017 这类泛化前缀）
        picked.append(max(spec, key=lambda t: (t.count("/"), -len(t))))
    return picked


# ---------------------------------------------------------------------
# 第 3 层：facet 标签 -> 资源列表
# ---------------------------------------------------------------------
ALGOLIA_HITS_CAP = 1000     # 实测 servlet 的 hitsPerPage 上限


def fetch_resources(p: Probe, tags: list[str],
                    hits_per_page: int = ALGOLIA_HITS_CAP) -> list[dict]:
    """按 facet 标签查资源；达到 1000 上限时打印告警。

    实测：servlet 的 page 参数被忽略，无法翻页 —— 只能靠 hitsPerPage，
    硬上限 1000。超过 1000 条的科目必须按 Exam-Series / Document-Type 拆分。
    """
    fq = " AND ".join('category:"%s"' % t for t in tags)
    api = ORIGIN + "/services/pearson/algolia/GET.servlet"
    data = p.get_json(api, params={"fq": fq, "hitsPerPage": str(hits_per_page)})
    if not data:
        return []
    recs = (data.get("searchResults") or {}).get("algoliaRecords") or []
    if len(recs) >= hits_per_page:
        print("    !! 命中 %d 条 = hitsPerPage 上限，结果可能被截断"
              "（page 参数无效，需按考季分片）" % len(recs))
    return recs


def classify(rec: dict) -> dict:
    """从 category 数组抽统一字段（不依赖锚文本解析）。"""
    cat = rec.get("category") or []
    def pick(prefix: str) -> Optional[str]:
        for c in cat:
            if c.startswith(prefix + "/"):
                return c.split("/", 1)[1]
        return None
    url = rec.get("url") or ""
    return {
        "doc_type": pick("Pearson-UK:Document-Type"),
        "exam_series": pick("Pearson-UK:Exam-Series"),
        "unit": pick("Pearson-UK:Unit"),
        "subject": pick("Pearson-UK:Qualification-Subject"),
        "spec_code": pick("Pearson-UK:Specification-Code"),
        "category": pick("Pearson-UK:Category"),
        "gated": "secure/silver" in url or "secure/gold" in url,
        "ext": (rec.get("extension") or "").upper(),
    }


# ---------------------------------------------------------------------
def main() -> int:
    p = Probe()
    print("=" * 78)
    print("Pearson Edexcel 公开真题结构探测")
    print("UA: %s" % UA)
    print("限速: %.1fs/请求   trust_env=False" % RATE_SECONDS)
    print("=" * 78)

    # --- 0. robots ---
    print("\n[0] robots.txt")
    p.load_robots()
    print("    %s -> HTTP %s" % (ROBOTS_URL, p.robots_status))
    raw = p.robots and p.robots  # noqa: F841
    key_paths = [
        ORIGIN + "/en/qualifications/edexcel-international-gcses.html",
        ORIGIN + "/services/pearson/subjectlistaz/GET.servlet",
        ORIGIN + "/services/pearson/algolia/GET.servlet",
        ORIGIN + "/content/dam/pdf/past-papers.json",
        ORIGIN + "/content/dam/pdf/International%20GCSE/Economics/2017/exam-materials/4ec1-01-que-20220525.pdf",
        ORIGIN + "/content/dam/secure/silver/all-uk-and-international/international-gcse/economics/2017/exam-materials/4ec1-01-pef-20260122.pdf",
    ]
    for u in key_paths:
        print("    %-5s %s" % (p.allowed(u), u.replace(ORIGIN, "")))

    # --- 1. 科目枚举 ---
    print("\n[1a] 科目枚举 · 主入口（Algolia cq:Page，四家族通用）")
    fams = discover_subjects_algolia(p)
    total = sum(len(v) for v in fams.values())
    print("     合计: %d 个科目页" % total)

    print("\n[1b] 科目枚举 · 对照入口（subjectlistaz servlet，实测 currentPage 被忽略）")
    fams_sl = discover_subjects_subjectlistaz(p)
    for family, _ff, label, _u in FAMILIES:
        a, b = len(fams.get(family, ())), len(fams_sl.get(family, ()))
        if b == 0:
            flag = "  <-- servlet 完全不可用（currentPage 被忽略，永远只回 IGCSE）"
        elif a != b:
            flag = "  <-- 不一致：servlet 返回的是 IGCSE 家族，不是 %s" % family
        else:
            flag = "  <-- 一致"
        print("     %-40s algolia=%-4d servlet=%-4d%s" % (family, a, b, flag))

    sm = subjects_from_sitemap(p)
    if sm:
        print("\n[1c] sitemap1.xml 旁证（覆盖不全，仅作交叉校验）：")
        for family, _ff, _label, _u in FAMILIES:
            print("      %-42s %d" % (family, len(sm.get(family, ()))))

    # --- 2/3. 目标科目 ---
    target = None
    for s in fams.get("edexcel-international-gcses", []):
        if s["slug"] == "international-gcse-economics-2017":
            target = s
            break
    if target is None and fams.get("edexcel-international-gcses"):
        target = fams["edexcel-international-gcses"][0]
    if target is None:
        print("\n!! 未枚举到任何 IGCSE 科目，无法继续")
        return 1

    print("\n[2] 目标科目: %s" % target["title"])
    print("    页面: %s" % target["page_url"])
    raw_tags = subject_facet_tags(p, target["page_url"])
    if not raw_tags:
        print("    !! 未解析出 facetListCtrl 标签集")
        return 1
    print("    页面给出的全部标签 (%d 个):" % len(raw_tags))
    for t in raw_tags:
        print("      tag: %s" % t)
    tags = select_facet_tags(raw_tags)
    print("    压缩后用于查询 (%d 个，互斥变体已去重):" % len(tags))
    for t in tags:
        print("      fq: category:\"%s\"" % t)

    print("\n[3] 资源列表（/services/pearson/algolia/GET.servlet?fq=...）")
    recs = fetch_resources(p, tags)
    print("    返回 %d 条记录" % len(recs))

    rows = []
    for rec in recs:
        c = classify(rec)
        rows.append({
            "title": rec.get("title"),
            "url": ORIGIN + (rec.get("url") or ""),
            "size": rec.get("size"),
            **c,
        })

    print("\n    文件类型分布:")
    for k, v in Counter(r["doc_type"] or "(none)" for r in rows).most_common():
        print("      %-32s %d" % (k, v))
    print("    考季分布（前 12）:")
    for k, v in Counter(r["exam_series"] or "(none)" for r in rows).most_common(12):
        print("      %-20s %d" % (k, v))
    print("    公开 vs 门禁（/content/dam/secure/*）:")
    for k, v in Counter("secure(需登录)" if r["gated"] else "public" for r in rows).most_common():
        print("      %-18s %d" % (k, v))
    print("    扩展名:")
    for k, v in Counter(r["ext"] or "(none)" for r in rows).most_common():
        print("      %-8s %d" % (k, v))

    print("\n    前 15 条（URL + 标题）:")
    for r in rows[:15]:
        print("      %-62s" % (r["title"] or "")[:62])
        print("        %s" % r["url"])
        print("        doc_type=%s series=%s unit=%s gated=%s size=%s"
              % (r["doc_type"], r["exam_series"], r["unit"], r["gated"], r["size"]))

    # --- 3b. A Level 交叉验证（暴露 facet 互斥问题） ---
    print("\n[3b] A Level 交叉验证（facet 变体互斥，验证 select_facet_tags）")
    al = [s for s in fams.get("edexcel-a-levels", []) if s["slug"] == "mathematics-2017"]
    if al:
        al_raw = subject_facet_tags(p, al[0]["page_url"])
        if al_raw:
            al_tags = select_facet_tags(al_raw)
            print("    %s 页面给出 %d 个标签 -> 压缩为 %d 个"
                  % (al[0]["slug"], len(al_raw), len(al_tags)))
            print("    全 AND（错误做法）-> %d 条"
                  % len(fetch_resources(p, al_raw)))
            al_recs = fetch_resources(p, al_tags)
            print("    压缩后（正确做法）-> %d 条" % len(al_recs))
    else:
        print("    [skip] 未枚举到 edexcel-a-levels/mathematics-2017")

    # --- 4. 实际可达性（区分公开档与登录墙） ---
    print("\n[4] 文件可达性抽检（HEAD）")
    public = [r for r in rows if not r["gated"] and r["ext"] == "PDF"]
    gated = [r for r in rows if r["gated"] and r["ext"] == "PDF"]
    for r in public[:2]:
        resp = p.head(r["url"])
        print("    public  HTTP %s  %s" % (resp.status_code if resp else "N/A", r["url"][-70:]))
    for r in gated[:1]:
        resp = p.head(r["url"])
        print("    secure  HTTP %s  %s" % (resp.status_code if resp else "N/A", r["url"][-70:]))

    # --- 5. 请求日志 ---
    print("\n[5] 请求日志（%d 条）" % len(p.log))
    for method, url, note in p.log:
        print("    %-4s %-8s %s" % (method, note.split(" ")[0], url.replace(ORIGIN, "")))
    if p.blocked:
        print("\n    robots 拦截: %d 条" % len(p.blocked))
        for u in p.blocked:
            print("      %s" % u)

    # --- 6. 机器可读摘要 ---
    summary = {
        "robots_status": p.robots_status,
        "subject_pages_algolia": {k: len(v) for k, v in fams.items()},
        "subject_pages_subjectlistaz": {k: len(v) for k, v in fams_sl.items()},
        "subject_pages_sitemap": {k: len(v) for k, v in sm.items()},
        "subject_pages_total": total,
        "target": target["slug"],
        "target_facet_tags_raw": raw_tags,
        "target_facet_tags_used": tags,
        "resource_count": len(rows),
        "doc_types": dict(Counter(r["doc_type"] or "(none)" for r in rows)),
        "public_count": sum(1 for r in rows if not r["gated"]),
        "secure_count": sum(1 for r in rows if r["gated"]),
        "requests": len(p.log),
        "robots_blocked": len(p.blocked),
    }
    print("\n[6] SUMMARY_JSON")
    print(json.dumps(summary, ensure_ascii=False, indent=1))

    p.client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
