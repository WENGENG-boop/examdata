"""定向重切 v2: 对 tmp_fixplan_failed_qp.json 内文档跑完整切分。

- QP pass 先（force=True），MS pass 后（force=True）；qp_index 用该科全部 QP 文档建。
- 每文档独立 try/except: 失败回滚并记录, 不中断整体。
- 外层 with_lock_retry 镜像 split_subject 的锁重试。

用法: python tmp_fixsplit.py [slug ...]   （默认全部）
输出: tmp_fixsplit_result.json
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

from examdata.core.config import get_settings  # noqa: E402
from examdata.core.db import (  # noqa: E402
    enable_immediate_writes,
    get_session_factory,
    init_db,
    with_lock_retry,
)
from examdata.core.models import DocumentRevision  # noqa: E402
from examdata.edexcel_papers.pipeline import (  # noqa: E402
    DOC_MARK_SCHEME,
    DOC_QUESTION_PAPER,
    SplitSummary,
    _documents,
    _paper_code_of,
    _split_ms,
    _split_qp,
    _subject,
)


def _doc_summary(summary: SplitSummary) -> dict:
    return {
        'papers': summary.papers, 'questions': summary.questions,
        'mark_schemes': summary.mark_schemes, 'ms_entries': summary.ms_entries,
        'ms_matched': summary.ms_matched, 'ms_unmatched': summary.ms_unmatched,
        'skipped': summary.skipped, 'conflicts': summary.conflicts,
        'failed': summary.failed, 'errors': list(summary.errors),
    }


def main() -> None:
    args = list(sys.argv[1:])
    plan = json.load(open(ROOT / 'tmp_fixplan_failed_qp.json', encoding='utf-8'))['plan']
    slugs = sorted(plan) if not args or args == ['all'] else args

    enable_immediate_writes()
    init_db()
    session = get_session_factory()()
    settings = get_settings()

    result: dict = {}
    started = time.time()
    try:
        for slug in slugs:
            spec = plan.get(slug)
            if spec is None:
                print(f'!! {slug}: not in plan, skipped', flush=True)
                continue
            subject = _subject(session, slug)
            if subject is None:
                print(f'!! {slug}: subject not in db', flush=True)
                continue
            summary = SplitSummary()
            per_doc = []

            qp_docs = _documents(session, subject.id, DOC_QUESTION_PAPER, None, None)
            qp_index = {}
            for doc in qp_docs:
                revision = session.get(DocumentRevision, doc.current_revision_id)
                code = _paper_code_of(doc, revision)
                if code:
                    qp_index[(doc.subject_id, doc.series_id, code)] = doc

            plan_qp = set(spec.get('qp') or [])
            for doc in qp_docs:
                if doc.id not in plan_qp:
                    continue
                before = (summary.papers, summary.questions, summary.failed)
                try:
                    with_lock_retry(
                        session,
                        lambda d=doc: _split_qp(
                            session, settings, d, summary, force=True, slug=slug
                        ),
                        attempts=10,
                    )
                except Exception as exc:
                    session.rollback()
                    summary.failed += 1
                    summary.errors.append(f'document {doc.id}: {exc}')
                after = (summary.papers, summary.questions, summary.failed)
                per_doc.append({'role': 'qp', 'doc': doc.id,
                                'ok': after[0] > before[0],
                                'delta_q': after[1] - before[1],
                                'failed': after[2] > before[2]})
                print(f'  [{slug}] qp {doc.id}: q+{after[1] - before[1]}'
                      f'{" FAILED" if after[2] > before[2] else ""}', flush=True)

            cache: dict = {}
            plan_ms = set(spec.get('ms') or [])
            ms_docs = _documents(session, subject.id, DOC_MARK_SCHEME, None, None)
            for doc in ms_docs:
                if doc.id not in plan_ms:
                    continue
                before = (summary.mark_schemes, summary.ms_entries, summary.failed)
                try:
                    with_lock_retry(
                        session,
                        lambda d=doc: _split_ms(
                            session, settings, d, qp_index, summary, cache,
                            force=True, slug=slug,
                        ),
                        attempts=10,
                    )
                except Exception as exc:
                    session.rollback()
                    summary.failed += 1
                    summary.errors.append(f'document {doc.id}: {exc}')
                after = (summary.mark_schemes, summary.ms_entries, summary.failed)
                per_doc.append({'role': 'ms', 'doc': doc.id,
                                'ok': after[0] > before[0],
                                'delta_e': after[1] - before[1],
                                'failed': after[2] > before[2]})
                print(f'  [{slug}] ms {doc.id}: e+{after[1] - before[1]}'
                      f'{" FAILED" if after[2] > before[2] else ""}', flush=True)

            result[slug] = {'summary': _doc_summary(summary), 'docs': per_doc}
            print(f'== {slug}: papers+{summary.papers} q+{summary.questions} '
                  f'ms+{summary.mark_schemes} entries+{summary.ms_entries} '
                  f'failed={summary.failed}', flush=True)
    finally:
        session.close()

    out = {'elapsed_s': round(time.time() - started, 1), 'subjects': result}
    (ROOT / 'tmp_fixsplit_result.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    total_failed = sum(v['summary']['failed'] for v in result.values())
    print(f'DONE elapsed={out["elapsed_s"]}s failed={total_failed}', flush=True)


if __name__ == '__main__':
    main()
