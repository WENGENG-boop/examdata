"""为目视核验切片生成子代理任务说明书（纯离线）。

用法: python mk_prompt.py s02 [s03 ...]
读 review/worklist-<slice>.json 与对应 cie-index.json，写 review/prompts/prompt-<slice>.txt。
子代理只需 Read 该文件并照做；观测/完成文件路径也写在里面。
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

BATCH = r"C:/Users/weo/Desktop/api/cie-location-batch"
AUD = os.path.join(BATCH, "work/coordinate-audit-2026-10-05")
REVIEW = os.path.join(AUD, "review")
PROMPTS = os.path.join(REVIEW, "prompts")
BASE = "http://127.0.0.1:8792/work/coordinate-audit-2026-10-05/"


def index_path(key: str) -> str:
    subj, year, season, paper = key.split("/")
    return os.path.join(BATCH, "indexes", subj, f"{year}-{season}-{paper}", "cie-index.json")


def build(slice_id: str) -> str:
    wl = json.load(open(os.path.join(REVIEW, f"worklist-{slice_id}.json"), encoding="utf-8"))
    key, role = wl["paper"], wl["role"]
    index = json.load(open(index_path(key), encoding="utf-8"))
    items = wl["items"]
    regions = [r for r in items if r["kind"] == "region"]
    pairs = [r for r in items if r["kind"] == "page_pair"]
    qs = [q["question"] for q in index["questions"]]

    bypg = defaultdict(list)
    for q in index["questions"]:
        for r in q.get(role) or []:
            bypg[r["page"]].append(q["question"])

    role_cn = "QP（卷面）" if role == "qp" else "MS（评分方案）"
    lines: list[str] = []
    A = lines.append
    A(f"任务：对 `{key}` 剑桥 CIE 试卷的 {role_cn} 索引区域做\"逐区域目视核验\"，"
      f"共 {len(items)} 个工作项（{len(regions)} 个区域裁剪图 + {len(pairs)} 张页对图）。")
    A("你是核验执行人；唯一可用的看图途径是浏览器快照；**禁止**凭文件名/索引数据臆测或编造观察。")
    A("")
    A("## 效率约束（务必遵守）")
    A("- 你**只有一件事要做**：逐张看图 → 写观察。**不要**读仓库源码、不要 grep 历史日志、"
      "不要新建/重渲染/检查/修补图片、不要调查渲染管线或文件时间戳。")
    A("- 遇到\"这张图看起来方向不对/可疑\"：先按下方\"图片情况\"的既定结论处理（方向已确证），"
      "最多重拍一次；仍不可读就如实记 issues 并继续下一项。**不要**为任何单张图反复推理。")
    A("- 目标节奏：每项 1-2 次浏览器调用 + 1 次 obs 追加写入。")
    A("")
    A("## 环境与文件（全部已存在，不要新建目录）")
    A(f"- 工作清单（每项含 seq/file/url/question/role/page/bbox）："
      f"`{AUD.replace(chr(92), '/')}/review/worklist-{slice_id}.json`")
    A(f"- 你的输出1（逐项观察）：`{AUD.replace(chr(92), '/')}/review/obs-{slice_id}.jsonl`")
    A(f"- 你的输出2（结束时）：同目录 `done-{slice_id}.json`")
    A(f"- 图片经静态服提供，worklist 里 `url` 字段已给好（`{BASE}...`）。")
    A("")
    A("## 浏览器操作配方（严格照做，可省大量时间；本会话已验证）")
    A("1. 先用 `mcp__desktop_browser__run`（`protocol:\"kimi.browser/1.0.0\"`, "
      "`operation:\"browser.get_state\"`，无其他参数）取到 `activeTabId`（预期形如 `panel-tab-1822`）。"
      "之后所有调用都带这个 `tabId`。**不要新建 tab**。若操作报控制类错误（TAB_NOT_CONTROLLED），"
      "先 `browser.activate_tab`（tabId=该 tab）再重试。")
    A("2. 取图模式（管线已\"热\"时）：同一消息内先 `tab.navigate`（url=新图 URL, tabId），"
      "紧接 `page.visual.snapshot`（tabId），一次消息取一张图，通常 ~0.4s 成功。")
    A("3. **冷启动特例**：若长时间没人用浏览器，第一次 `page.visual.snapshot` 会 ~10 秒超时并报 "
      "`PAGE_NOT_READY`——这正常，后台截图还在进行。不要在同一消息里立刻重试（会 0 秒\"忙\"失败）；"
      "用 Bash 跑 `sleep 12`，**在下一次工具轮**再拍通常即成功。")
    A("4. 若不 navigate 直接重复 snapshot，会瞬时返回缓存（同一张旧图）——不算新视图，别拿它凑数。")
    A("5. 每消息浏览器调用控制在 ~4 个以内（约 1-2 个视图/消息），看 1-2 张图就把观察写入 obs 文件"
      "（Write mode=append），交替进行。")
    A("6. 不要用 `page.wait_for`（对独立图片页无效，必 15s 超时）。整图会自动缩放适配视口。"
      "若拍到的图是空白/加载中，`sleep 2` 后重拍一次。")
    A("7. 连续 3 次真实失败（非冷启动情形）→ 该项记 `checks` 全 false + issues 说明，跳过继续，"
      "最后在简报中列出。")
    A("")
    A("## 图片情况")
    A("- 快照分辨率 2000×1125（viewport 1280×720 @dsf2），文字可读。")
    rot = set()
    vman = os.path.join(AUD, "visual", key.replace("/", "_"), "manifest.json")
    if os.path.isfile(vman):
        for m in json.load(open(vman, encoding="utf-8")).get("regions", []):
            if m.get("role") == role and m.get("page_rotation_original") is not None:
                rot.add(int(m["page_rotation_original"]))
    rotated = sorted(r for r in rot if r % 360)
    if rot:
        A("- 该 " + role.upper() + " 文档原件**实测页旋转**：" +
          "、".join(f"{r}°" for r in sorted(rot)) + "。")
    if rotated and not [r for r in rot if r % 360 == 0]:
        A("- 文件名带 `-disp` 的 region 图已给成**阅读方向**；页对图也已按阅读方向渲染"
          "（可能横向、较宽）。")
        A("- **方向已确证，不要再排查**：渲染脚本用 `page.get_pixmap()`（自动应用 /Rotate），"
          "所有 `-disp` 区域图与页对图都已是阅读方向。**不要**为方向问题反复渲染、比对、推理或改脚本；"
          "直接看图、写观察。若某张图确实不可读，如实记 issues 并继续下一项。")
    elif rotated:
        A("- 本角色部分页有旋转（" + "、".join(f"{r}°" for r in rotated) +
          "），因此部分 region 图文件名带 `-disp`（阅读方向），部分是未旋转裁剪。")
    else:
        A("- 本角色页无旋转；region 图即未旋转坐标裁剪，方向与原件一致。")
    A("- 不要凭\"应该是扫描件/应该有乱码\"之类假设推断内容；一切以你实际看到的图像为准。")
    A("- region 图（如 `" + (regions[0]["file"].split("/")[-1] if regions else "region.png") +
      "`）紧贴索引 bbox。图中可能出现**细红色矩形框**：那是渲染工具的辅助标记"
      "（其他区域红框叠加），不是原件内容，忽略即可；但若图缘恰好把文字/表格切断，如实记录进 issues。")
    A(f"- 页对图：`pairs/{key.replace('/', '_')}/{role}-pair-XX-XX.png`，两整页并排（左页在前），"
      f"顶部有 `<{key}> <role> pN` 小字标签。")
    A("")
    A("## 逐项要求")
    A("")
    A(f"### region 项（seq {regions[0]['seq']}-{regions[-1]['seq']}）")
    A("看图后写观察，重点：")
    if role == "qp":
        A("- `observed`（≥50 字，客观、可复查）：题号标签原文加引号（如 \"1 (a)\"）；至少一段 ≤20 字的"
          "原文引用；可见的 [n] 分值；依赖的图表/材料；四边边界检查结论（无半截文字/表格被切）。")
        A("- `checks`: `content_complete`（本区域内容完整即 true；若该题跨页续接，要在 observed 说明"
          "\"该题另有区域在 pN\"之类）、`boundary_checked`、`role_matches`（qp 图应是题面而非评分）。")
    else:
        A("- `observed`（≥50 字，客观、可复查）：可见的评分表标题/行标签原文加引号（如 \"Question 1(a)\"、"
          "\"Answer\"、\"Marks\"、\"Guidance\"）；至少一段 ≤20 字的原文引用（评分点文字或答案要点）；"
          "可见的分数/分值标注；四边边界检查结论（无半截文字/表格被切）；若为续页要说明"
          "\"该评分表续自/续至 pN\"。")
        A("- `checks`: `content_complete`、`boundary_checked`、`role_matches`（ms 图应是评分内容而非题面）。")
        A("- **特别要求（空 MS 判定）**：若该区域内**看不到任何针对该题的评分点/得分说明**"
          "（例如只有题面复述、只有页眉页脚、或空白），必须如实写出并给出证据（引述所见内容），"
          "在 `issues` 记为 `no_marking_content`。不得因为区域非空就当作有评分。")
    A("- 异常（图不对题、被切、题号找不到、题号与文件名/索引不符）→ 对应 check 置 false，"
      "`issues` 写具体问题。**任何情况都不要自行改动图片/索引/其他文件**。")
    A("")
    A(f"### 页对图项（seq {pairs[0]['seq']}-{pairs[-1]['seq']}）")
    A("这是\"漏建索引\"检查。该 " + role.upper() + " 文档索引含 " + str(len(qs)) + " 条题号：")
    A("`" + ", ".join(qs) + "`")
    A("")
    A("索引页码分布（该页应可见的题号/评分表标签）：")
    npages = max(bypg) if bypg else 0
    for p in range(1, npages + 1):
        labels = bypg.get(p)
        A(f"- p{p}: " + (", ".join(labels) if labels else "（索引中无题）"))
    A("- 在该页对图上逐页列出**肉眼可见的所有题号/评分表标签原文**，与上方预期对照。")
    A("- `observed`（≥50 字）：逐页描述——页面性质（封面/说明页/正文/评分表页/空白页）、可见标签、"
      "重要版面事实（分值、作答线、表格、图）、页脚卷编号（以所见为准，用于确认卷身份）。")
    A("- `missing_questions`：预期题号在应出现的页上完全找不到且无合理解释才列入；否则 []。")
    A("- 特别注意：**确认最后一道题（" + qs[-1] + "）的" +
      ("题面" if role == "qp" else "评分表") + "确实存在**，以及是否有任何索引外的题号"
      "（如多出的编号）或题号跳缺；有则写入 observed + issues。")
    A("")
    A("## 输出格式（严格，UTF-8，无围栏）")
    A(f"obs-{slice_id}.jsonl 每行一个 JSON：")
    A("region 行（seq/file/question/role/page/bbox 从 worklist **原样复制**）：")
    A('{"kind":"region","seq":%d,"file":"%s","question":"%s","role":"%s","page":%d,"bbox":%s,'
      '"observed":"...","checks":{"content_complete":true,"boundary_checked":true,"role_matches":true},'
      '"issues":[]}' % (regions[0]["seq"], regions[0]["file"], regions[0]["question"], role,
                        regions[0]["page"], json.dumps(regions[0]["bbox"])))
    A("page_pair 行：")
    A('{"kind":"page_pair","seq":%d,"file":"%s","pages":%s,"role":"%s","observed":"...",'
      '"missing_questions":[],"issues":[]}' % (pairs[0]["seq"], pairs[0]["file"],
                                               json.dumps(pairs[0]["pages"]), role))
    A(f"- 每 8-12 项追加写一次（Write mode=append）。seq {items[0]['seq']}..{items[-1]['seq']} "
      "必须全覆盖、不重不漏。")
    A(f'- 全部完成后写 done-{slice_id}.json：{{"slice":"{slice_id}","expected":{len(items)},'
      f'"viewed":{len(items)},"suspects":[{{"seq":N,"note":"..."}}],"notes":"...","browser_ok":true}}')
    A("")
    A("## 禁止")
    A("- 禁写 `verification.jsonl`、禁改索引/图片/其他任何文件；禁调 examdata CLI 或 :8000 服务；"
      "禁新建浏览器 tab。")
    A("- 不许编造：没看清或失败就如实写进 issues/suspects。")
    A("")
    A("## 最后回报（给上级的简报表，中文）")
    A("1) 覆盖 viewed/expected；2) 浏览器全程可用性、冷启动次数；3) suspects 列表（seq+一句话）；"
      "4) 任何影响核验质量的问题；5) done 文件路径。")
    return "\n".join(lines) + "\n"


def main() -> int:
    os.makedirs(PROMPTS, exist_ok=True)
    for sid in sys.argv[1:]:
        text = build(sid)
        out = os.path.join(PROMPTS, f"prompt-{sid}.txt")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"{sid}: {len(text)} chars -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
