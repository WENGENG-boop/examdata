import json
import datetime

p = 'ielts-data/runs/20261003T140007Z-repair/checkpoint.json'
c = json.load(open(p, encoding='utf-8'))

c['steps']['S17'] = {
    'status': 'done',
    'completed_at': '2026-10-05',
    'files': [
        'docs/ielts/IELTS_IMPLEMENTATION_RESULT.md',
        'docs/ielts/IELTS_REMAINING_GAPS.md',
        'docs/ielts/EXECUTION_CHECKLIST.md',
        'ielts-data/manifests/rev-8b21015ab64bb73c/coverage.md',
    ],
    'results': {
        'result_report': 'IELTS_IMPLEMENTATION_RESULT.md (32913 B, 11 sections: A01-A16, test exit codes, two-copy hashes, protected boundaries, not_run, recovery commands)',
        'remaining_gaps': 'IELTS_REMAINING_GAPS.md (17288 B, G1-G13: 7 answer slots / 1 asset / 46 unknown / 25+25 missing options-assets / 39 partial / PDF editions / 26 candidate audio / alignment status 33 ids 66 verified / writing-speaking / 2 official decisions / 3 conflicts / S07 leftover)',
        'checklist': 'overview S15-S17 -> done; S17 section filled with files/command/exit_code/evidence/gaps/next_action',
        'coverage_md': 'manifests/rev-8b21015ab64bb73c/coverage.md (45030 chars, 370 units, rendered from coverage.json)',
        'recheck': 'all numbers re-verified this window: coverage units=370 (partial 168/not_extracted 154/unverified 48/complete 0); index 6724 q (attached 6717/missing 6/empty 1; unknown 46; missing_options 25; missing_asset 25; partial 39); full-audit errors=1; audio catalog 362 (320/16/26); alignment 33 files 331 q 66 verified; books_pdf_complete 1-19; book_9.pdf sha256 b25f954d...; book_10.pdf sha256 3f1c53...; changed-files modules 28/tools 27/tests 22/data 3/docs 2=82',
    },
    'evidence_dir': 'ielts-data/runs/20261003T140007Z-repair',
    'evidence': [
        'docs/ielts/IELTS_IMPLEMENTATION_RESULT.md',
        'docs/ielts/IELTS_REMAINING_GAPS.md',
        'docs/ielts/EXECUTION_CHECKLIST.md',
        'ielts-data/manifests/rev-8b21015ab64bb73c/coverage.md',
        'ielts-data/manifests/rev-8b21015ab64bb73c/coverage.json',
        'ielts-data/indexes/rev-8b21015ab64bb73c/questions.json',
        'ielts-data/runs/full-audit/errors.jsonl',
        'ielts-data/runs/20261003T140007Z-repair/audio/audio-catalog.json',
        'ielts-data/runs/20261003T140007Z-repair/alignment/summary.json',
        'ielts-data/runs/20261003T140007Z-repair/changed-files.json',
        'ielts-data/runs/20261003T140007Z-repair/scratch/classify-changed.py',
        'ielts-data/runs/20261003T140007Z-repair/scratch/gaps-extract.py',
        'ielts-data/runs/20261003T140007Z-repair/scratch/gaps-extract2.py',
    ],
}

c['notes']['s17_facts'] = (
    'S17 final: three deliverables + coverage.md complete; all S01-S17 steps done. '
    'Completion semantics reported honestly: code layer resolved (all regressions green), '
    'data layer partial (coverage units complete=0), answer verification partial (only b9t1r 6/40 official + b10t1r compare smoke 38/1/1), '
    'audio alignment partial (66/160 cam21 verified; 33 identities total). '
    'S07 leftover: compare-official not wired into audit-all (manual CLI only).'
)
c['updated_at'] = '2026-10-05'
c['stage'] = 'S17'

json.dump(c, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('checkpoint updated: stage=S17, S17=done')
st = c['steps']
print('steps status:', {k: v.get('status') for k, v in sorted(st.items())})
