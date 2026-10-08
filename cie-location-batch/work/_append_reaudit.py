import sys
sys.path.insert(0, 'tools')
import batchlib as B

now = B.now_iso()
rec = {
    "kind": "independent_reaudit",
    "at": now,
    "method": "3 个独立只读审计子代理（explore），互不共享结论：①媒体残留 ②学科与目录覆盖 ③索引与服务一致性；全程禁网、禁写",
    "verdict": "PASS 3/3（无 FAIL）",
    "key_numbers": {
        "media": {"batch_root_pdf": 0, "batch_root_images": 0, "batch_root_part": 0,
                   "tmp_files": 0, "tmp_dirs": 213, "service_dir_pdf": 0,
                   "pilot_files": 1, "tmp_dl_files": 0,
                   "artifacts_sample": "8/8 为 Pearson Edexcel（WMA/WBI/WCH/WBS），非本任务范围"},
        "subjects": {"subjects": 205, "third_party_confirmed": 43, "official_seed_codes": 196,
                      "failure_codes": ["0698", "3216"], "catalogue_keys": 16605,
                      "requested_true": 3807, "requested_false": 12798,
                      "status_counts": {"complete": 1705, "no_resources": 1778,
                                        "subject_unavailable": 324,
                                        "subject_unavailable_inferred": 12798},
                      "third_party_each_81": True},
        "indexes": {"indexes": 61, "validate_pass": 61, "service_exists": 61,
                     "identical": 61, "visual_gate_passed": 7,
                     "cleaned_needing_reverification": 54},
    },
    "observations": [
        "几何校验（bbox 对照 PDF 页界）在本次 61/61 校验中被跳过：本地 PDF 已按规程删除；导入时由服务校验、日后取题由服务重下原件复核",
        "errors.jsonl 第 181 行为旧格式（无 kind 字段）；不改写历史",
        "final_audit 记录引用 manifest_generated_at=2026-10-03T05:17:42+0800；manifest 其后于 05:19:55 重新生成（统计相同 61/61/61/7），本记录更正引用",
        "checkpoint.progress 块（requests=1187/cells_done=3360）为最后一次运行中快照，权威值为 totals（3807/3483）；快照不改写",
        "subjects.json third_party_completeness='proven' 为构建时声明（tools/build_subjects.py:119），combo 原始正文未落盘（仅存 url/sha256/entries=43；全盘哈希搜索无命中）——离线无法再验证 43 为全集，如实保留为可复现性缺口",
        "raw_head 对 1244 个 complete 格截断于 500 字符、中文为 JSON 转义（\\uXXXX 形式）；body_sha256 为全量正文哈希，语义自洽；grep 检索需先解码",
        "tmp/ 残留 213 个空目录（63 个卷级，含 2 个冻结卷目录）；文件数 0，符合『仅空目录』；试点目录 review/、review/all-question-crops/ 为空目录",
    ],
    "actions": ["本记录追加后重跑 build_summary.py 刷新派生计数"],
    "no_action_required": True,
}
B.append_jsonl(B.ERRORS, rec)
print('appended independent_reaudit at', now)
