"""对 tmp_fixplan_failed_qp.json 内所有 QP 文档做只读探针:
- 取 current_revision artifact, 统计非首页文本字符数 (判断扫描版)
- 直接调 _anchors(pdf,'qp') 看当前 locator 能否给出锚点
输出 tmp_probe_fixable.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

import pymupdf  # noqa: E402

from examdata.core.config import get_settings  # noqa: E402
from examdata.core.db import get_session_factory, init_db  # noqa: E402
from examdata.core.models import Document, DocumentRevision  # noqa: E402
from examdata.edexcel_papers.pipeline import _artifact_path  # noqa: E402
from examdata.paperqa.locator import _anchors  # noqa: E402


def main() -> None:
    plan = json.load(open(ROOT / 'tmp_fixplan_failed_qp.json', encoding='utf-8'))['plan']
    init_db()
    session = get_session_factory()()
    settings = get_settings()
    out: dict = {}
    try:
        for slug, spec in sorted(plan.items()):
            rows = []
            for doc_id in spec.get('qp') or []:
                doc = session.get(Document, doc_id)
                entry = {'doc': doc_id, 'paper_code': getattr(doc, 'paper_code', None)}
                if doc is None or doc.current_revision_id is None:
                    entry['probe'] = 'no-revision'
                    rows.append(entry)
                    continue
                revision = session.get(DocumentRevision, doc.current_revision_id)
                path = _artifact_path(session, settings, revision.artifact_id) if revision else None
                if path is None:
                    entry['probe'] = 'no-artifact'
                    rows.append(entry)
                    continue
                try:
                    pdf = pymupdf.open(path)
                    chars = sum(
                        len(pdf[i].get_text().strip()) for i in range(1, len(pdf))
                    )
                    entry['chars'] = chars
                    entry['pages'] = len(pdf)
                    try:
                        anchors, end = _anchors(pdf, 'qp')
                        entry['probe'] = 'ok'
                        entry['anchors'] = len(anchors)
                        entry['end'] = list(end)
                    except Exception as exc:
                        entry['probe'] = f'{type(exc).__name__}: {exc}'
                    pdf.close()
                except Exception as exc:
                    entry['probe'] = f'open-fail: {type(exc).__name__}: {exc}'
                rows.append(entry)
            out[slug] = rows
    finally:
        session.close()
    (ROOT / 'tmp_probe_fixable.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    ok = sum(1 for rows in out.values() for r in rows if r.get('probe') == 'ok')
    total = sum(len(rows) for rows in out.values())
    print(f'probe done: ok={ok}/{total}')
    for slug, rows in sorted(out.items()):
        okn = sum(1 for r in rows if r.get('probe') == 'ok')
        print(f'  {slug}: ok={okn}/{len(rows)}')


if __name__ == '__main__':
    main()
