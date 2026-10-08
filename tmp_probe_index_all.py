"""对 tmp_fixplan_failed_qp.json 内所有 QP 文档做 index_questions 只读探针:
修复后哪些文档现在能整体建索引（真实可重切集）。输出 tmp_probe_index_all.json。
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

from examdata.core.config import get_settings  # noqa: E402
from examdata.core.db import get_session_factory, init_db  # noqa: E402
from examdata.core.models import Document, DocumentRevision  # noqa: E402
from examdata.edexcel_papers.pipeline import _artifact_path  # noqa: E402
from examdata.paperqa.locator import index_questions  # noqa: E402


def main() -> None:
    plan = json.load(open(ROOT / 'tmp_fixplan_failed_qp.json', encoding='utf-8'))['plan']
    init_db()
    session = get_session_factory()()
    settings = get_settings()
    out: dict = {}
    started = time.time()
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
                    data = open(path, 'rb').read()
                    idx = index_questions(data, 'qp')
                    entry['probe'] = 'INDEX_OK'
                    entry['q'] = len(idx)
                except Exception as exc:
                    entry['probe'] = f'{type(exc).__name__}: {str(exc)[:90]}'
                rows.append(entry)
                print(f'  [{slug}] {doc_id}: {entry["probe"]}', flush=True)
            out[slug] = rows
    finally:
        session.close()
    (ROOT / 'tmp_probe_index_all.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    ok = sum(1 for rows in out.values() for r in rows if r.get('probe') == 'INDEX_OK')
    total = sum(len(rows) for rows in out.values())
    print(f'index probe done: OK={ok}/{total} elapsed={round(time.time() - started, 1)}s')
    for slug, rows in sorted(out.items()):
        okn = sum(1 for r in rows if r.get('probe') == 'INDEX_OK')
        print(f'  {slug}: OK={okn}/{len(rows)}')


if __name__ == '__main__':
    main()
