import sys, json
sys.path.insert(0, 'tools')
import batchlib as B

now = B.now_iso()
print('now =', now)

corr = {
    "kind": "checkpoint_totals_correction",
    "field": "checkpoint.totals.requests",
    "old": 1310,
    "new": 3807,
    "defect": "scan_catalogue.py 的 processed 计数器每次运行从 0 起算；结束行『实际请求 1310 次』只覆盖最后一次运行(scan-2026-10-01T125832)，遗漏 run1(120118) 与 12:00 预检的请求",
    "evidence": {
        "method": "按 catalogue-grid.json 每格 evidence.fetched_at 时间窗统计，并核对 requested=true 计数",
        "windows": {"pre_run_probe_12:00": 4, "run1_12:01-12:53": 2493, "run2_12:58-13:26": 1310, "sum": 3807},
        "requested_true_cells": 3807,
        "reconcile": "3807 = 实测完成格 3483 + 业务拒绝格 324；推断格 12798 为 requested=false，不计入",
        "run2_counter_matches_window": "run2 结束行 1310 与其时间窗 1310 格一致，表明 run2 无重复请求",
        "raw_http_requests": "去重后 3807；另有 1 次重复请求（run1 于 9489|2021|Jun 本地 IO 崩溃时请求已发出未落盘，run2 重试，见 scan_crashed_local_io 记录）及分类修正复探（11:59:27 对 0262|2000|Mar，见 classification_correction 记录），均不计入 3807",
    },
    "scope": "仅修正该派生计数字段；不改变任何格状态、身份或 HTTP 停止记录；本记录后仅改动 totals.requests 一个字段",
    "at": now,
}
B.append_jsonl(B.ERRORS, corr)
print('appended checkpoint_totals_correction')

cp = B.read_json(B.CHECKPOINT)
assert cp['totals']['requests'] == 1310, cp['totals']['requests']
cp['totals']['requests'] = 3807
B.atomic_write_json(B.CHECKPOINT, cp)
print('checkpoint.totals.requests = 3807 (done)')

audit = {
    "kind": "final_audit",
    "at": now,
    "trigger": "用户终审指令：审查 PDF 删除情况、学科覆盖与全部目标；审查→列计划→修改→再审查",
    "scope": [
        "媒体残留：批次目录/临时目录/服务目录/试点目录的 PDF 与图片",
        "学科与目录：205 科登记、43 科第三方全集 3483 格、162 科 324 探查、12798 推断格",
        "61 个已清理卷索引：schema 校验、服务读回一致性、视觉门禁覆盖率",
        "历史 premature_cleanup 与题号缺口",
    ],
    "findings": {
        "media": {
            "batch_root_pdf": 0, "batch_root_images": 0, "tmp_files": 0,
            "service_dir_pdf": 0, "pilot_dir": "仅 9709/2024-Jun-11/cie-index.json",
            "tmp_dl": "空",
            "note": "examdata/.data/artifacts 内 1406 个 PDF 属另一条 edexcel 流水线，不在本任务删除范围",
        },
        "schema": {"tool": "tools/validate_index.py", "indexes": 61, "passed": 61, "failed": 0},
        "service": {"count": 61, "in_service": 61, "identical": 61, "visual_gate_passed": 7,
                     "manifest": "service-index-manifest.json",
                     "manifest_generated_at": "2026-10-03T05:17:42+0800"},
        "visual_gate": {
            "regions_total": 3658, "verified": 3585, "failed": 0, "without_record": 73,
            "missing_visual_evidence": 3007, "self_declared_unverified": 2680,
            "papers_passed": 7, "papers_gap": 54, "gap_regions": 3080,
            "root_cause": "54 卷记录为 OCR-only（method=local_crop+Windows.Media.Ocr(zh-Hans-CN)，无 index_sha256），不满足目视证据门禁（要求 method∈{browser_visual_snapshot,local_image_visual}、checks 三项 true、index_sha256 与当前索引一致）；历史记录不补造，需重下原件重验（联网冻结中）",
            "list_ref": "summary.json#/unresolved/cleaned_needing_reverification",
        },
        "numbering": {
            "0495/2026/Jun/11": "2(a)、3(a) 子子题号不连续（缺 ['ii']）",
            "8386/2025/Jun/11": "缺顶层题号 1（现有 6 题，最大号 7）",
            "8386/2026/Jun/12": "缺顶层题号 1（现有 5 题）",
            "8386/2026/Jun/13": "缺顶层题号 1（现有 5 题）",
        },
        "premature_cleanup": "9 键均在 54 卷缺口内：0472/2026/Jun/11 全部记录作废；8386/2025/Jun/11、8386/2026/Jun/12、8386/2026/Jun/13、0495/2026/Jun/11、8238/2026/Jun/12、9618/2026/Jun/11、9707/2015/Nov/11、9868/2026/Jun/12 无 method 记录",
        "subjects": {"registered": 205, "third_party_confirmed": 43, "third_party_completeness": "proven",
                      "official_only": 162, "probe_cells": 324, "inferred_cells": 12798},
        "catalogue": {"expected": 16605, "requested_true": 3807, "done": 3483,
                       "business_rejected": 324, "failed": 0, "unqueried": 0},
    },
    "corrections": ["checkpoint.totals.requests 1310→3807（见 checkpoint_totals_correction，本记录同批落盘）"],
    "actions": [
        "停止残留 http.server 8899 后台任务（所服务图片已全删，纯残留）",
        "重跑 service_audit.py 刷新 service-index-manifest.json",
        "validate_index.py 校验 61/61 通过",
        "重建 summary.json 等派生状态（本记录后立即执行）",
    ],
    "blockers": {
        "network_frozen": "0472/2024/Jun/11 HTTP 502，needs_user_resume=true；54 卷视觉重验、13816 卷未处理均需网络授权",
        "frozen_papers": ["0472/2024/Jun/11 (download_failed)", "8238/2024/Nov/23 (download_interrupted)"],
    },
    "resolved": False,
    "next": [
        "待用户授权联网后：重下 54 卷原件补视觉核验→重导入→读回→清理",
        "继续 13816 卷可靠 QP 的下载/解析/定位/验证/导入/清理",
        "处理 0472/2024/Jun/11 与 8238/2024/Nov/23 冻结卷",
    ],
}
B.append_jsonl(B.ERRORS, audit)
print('appended final_audit')
