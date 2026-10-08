import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
REVIEW = BASE / ".data/tagging/review-export/ial18-business"
JEV = BASE / "tmp_jev_ial18-business.jsonl"

BATCHES = ["batch-001", "batch-002", "batch-003", "batch-005", "batch-006", "batch-007"]

OVERRIDES = {
    28097: ("WBS14-4.3.3.1(c)", "PED 计算服务于定价决策，属 4Ps 应用；Jev 判定 4.3.3.1(a)（0.45）不贴切"),
    28154: ("WBS11-1.3.5.3(c)", "该计算基于社会目标数据（捐赠餐数），归 1.3.5.3(c) 其他目标（社会目标）；Jev 判定 1.3.3.1(a)（0.25）不符"),
    28334: ("WBS14-4.3.1.1(d)", "与同题型（毛利率计算 28195）保持一致；Jev 判定 4.3.4.1(a)（0.10）不贴切"),
    28314: ("WBS13-3.3.1.2(c)", "Unit 3 无生产方法点；job production 属战术决策，影响人力/实物资源；Jev 判定 3.3.2.2(b)（0.14）不符"),
    28756: ("WBS12-2.3.2.2(b)", "consumer trends 为销售预测影响因素之子项；Jev 判定 2.3.5.1(a)（0.71）不符"),
    28750: ("WBS12-2.3.1.3(b)", "venture capital 列于 2.3.1.3(b) 融资方式；Jev 判定 2.3.1.3(a)（0.73）不符"),
}


def main():
    jev = {}
    with open(JEV, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                jev[r["question_id"]] = r
    assert len(jev) == 83, len(jev)
    total = 0
    n_keep = n_change = 0
    for batch in BATCHES:
        src = REVIEW / "batches" / f"{batch}.jsonl"
        dst = REVIEW / "decisions" / f"{batch}.jsonl"
        out = []
        with open(src, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                qid = item["question_id"]
                cur = [c["code"] for c in item.get("current", [])]
                assert cur, qid
                r = jev[qid]
                choice, conf = r["choice"], r["confidence"]
                if qid in OVERRIDES:
                    code, reason = OVERRIDES[qid]
                    if len(cur) == 1 and cur[0] == code:
                        row = {"question_id": qid, "decision": "keep", "reason": reason}
                    else:
                        row = {"question_id": qid, "decision": "change", "code": code, "reason": reason}
                elif len(cur) == 1 and cur[0] == choice:
                    row = {"question_id": qid, "decision": "keep",
                           "reason": f"Jev 复核确认原标签 {choice}（置信度 {conf}）"}
                elif choice in cur:
                    row = {"question_id": qid, "decision": "change", "code": choice,
                           "reason": f"Jev 判定 {choice}（置信度 {conf}）与题干相符；原标签多选（{'、'.join(cur)}）收敛为单选"}
                else:
                    row = {"question_id": qid, "decision": "change", "code": choice,
                           "reason": f"Jev 判定 {choice}（置信度 {conf}）与题干相符；原标签（{'、'.join(cur)}）不符"}
                out.append(row)
                if row["decision"] == "keep":
                    n_keep += 1
                else:
                    n_change += 1
        with open(dst, "w", encoding="utf-8") as f:
            for row in out:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        total += len(out)
        print(batch, len(out), "->", dst)
    print("total", total, "keep", n_keep, "change", n_change)


if __name__ == "__main__":
    main()
