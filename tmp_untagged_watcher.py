"""Untagged-questions Jev pipeline watcher (phase 3, chained after round2 watcher).

Phase 0: wait until the round2 watcher finishes ('WATCHER DONE' in its log, or
         process gone) so TypeSafe usage and DB writes stay serialized.
Phase 1: per slug (small -> large): jev batch -> decisions -> dry apply -> apply
         --write. Every API step first waits for the probe; retries when output
         is incomplete; if credits vanish mid-flight it pauses and resumes.
Phase 1b: convergence rounds 2..MAX: export the previous round's changed rows ->
         jev -> decisions -> dry apply -> apply --write, until a round exports
         0 questions (fixed point).
Phase 2: reruns that need no credits: completeness, consistency x2, untagged
         audit, demo JSONs (d1..d5), full pytest.
Status: tmp_untagged_watcher.status.json; per-step logs: tmp_watcher_logs/.

Usage: ./.venv/Scripts/python.exe -X utf8 tmp_untagged_watcher.py
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable
LOG_DIR = ROOT / 'tmp_watcher_logs'
STATUS_PATH = ROOT / 'tmp_untagged_watcher.status.json'
ROUND2_LOG = ROOT / 'tmp_round2_watcher.log'

BATCH_ROOT = 'tmp_jev_untagged_batches'
DEC_ROOT = 'tmp_jev_untagged_decisions'
JEV_TEMPLATE = 'tmp_jev_untagged_{slug}.jsonl'

PROBE_SLEEP = 600
MAX_PROBE_FAILS = 180
JEV_TRIES = 6
ROUND2_POLL = 300
ROUND2_MAX_WAIT_H = 72
MAX_ROUND = 8


def log(msg: str) -> None:
    print(f'[{time.strftime("%F %T")}] {msg}', flush=True)


def probe() -> bool:
    r = subprocess.run(
        [PY, '-X', 'utf8', 'tmp_probe_api.py'], cwd=ROOT,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return r.returncode == 0


def wait_api() -> bool:
    fails = 0
    while fails < MAX_PROBE_FAILS:
        if probe():
            log('API probe OK')
            return True
        fails += 1
        log(f'API unavailable ({fails}/{MAX_PROBE_FAILS}); sleep {PROBE_SLEEP}s')
        time.sleep(PROBE_SLEEP)
    log('API wait budget exhausted')
    return False


def run_step(name: str, args: list[str]) -> tuple[int, Path]:
    LOG_DIR.mkdir(exist_ok=True)
    logf = LOG_DIR / f'{name}.log'
    log('RUN ' + name + ' :: ' + ' '.join(args))
    with open(logf, 'w', encoding='utf-8') as fh:
        r = subprocess.run([PY, '-X', 'utf8'] + args, cwd=ROOT, stdout=fh,
                           stderr=subprocess.STDOUT)
    log(f'  exit={r.returncode} log={logf}')
    return r.returncode, logf


def read_log(logf: Path) -> str:
    return logf.read_text(encoding='utf-8', errors='replace')


def count_choices(path: Path) -> int:
    if not path.exists():
        return 0
    n = 0
    for line in open(path, encoding='utf-8'):
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get('choice'):
            n += 1
    return n


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in open(path, encoding='utf-8') if line.strip())


def count_decisions(dir_: Path) -> int:
    if not dir_.is_dir():
        return 0
    return sum(count_lines(f) for f in sorted(dir_.glob('batch-*.jsonl')))


def batches_lines(dir_: Path) -> int:
    if not dir_.is_dir():
        return 0
    return sum(count_lines(f) for f in sorted(dir_.glob('batch-*.jsonl')))


def round2_running() -> bool:
    try:
        r = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             "Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'python.exe' "
             "-and $_.CommandLine -like '*tmp_round2_watcher*'} | Measure-Object | "
             "Select-Object -ExpandProperty Count"],
            capture_output=True, text=True, timeout=60,
        )
        return int((r.stdout or '0').strip() or 0) > 0
    except Exception as exc:
        log(f'round2 process check failed: {exc}')
        return True  # assume running when unsure


def wait_round2() -> str:
    """Returns 'done' / 'process-gone' / 'timeout'."""
    log('phase 0: waiting for round2 watcher to finish...')
    start = time.time()
    gone_checks = 0
    while True:
        if ROUND2_LOG.exists() and 'WATCHER DONE' in read_log(ROUND2_LOG):
            return 'done'
        if time.time() - start > ROUND2_MAX_WAIT_H * 3600:
            return 'timeout'
        if round2_running():
            gone_checks = 0
        else:
            gone_checks += 1
            log(f'round2 watcher process not found ({gone_checks}/2)')
            if gone_checks >= 2:
                return 'process-gone'
        time.sleep(ROUND2_POLL)


def finish_jev(name: str, slug: str, batches_dir: str, out_path: str,
               expected: int) -> bool:
    out = ROOT / out_path
    for attempt in range(1, JEV_TRIES + 1):
        if not wait_api():
            return False
        rc, logf = run_step(f'{name}_try{attempt}', [
            'tmp_jev_batch.py', '--subject', slug,
            '--batches-dir', batches_dir, '--out', out_path, '--skip-problems',
        ])
        n = count_choices(out)
        log(f'  {slug}: choices {n}/{expected} after try {attempt} (rc={rc})')
        if n >= expected:
            return True
        time.sleep(120)
    return False


def write_decisions(name: str, slug: str, batch_root: str, out_root: str,
                    jev_template: str, expected: int) -> int:
    rc, logf = run_step(name, [
        'tmp_jev_full_decisions.py', '--subject', slug, '--write',
        '--batch-root', batch_root, '--out-root', out_root,
        '--jev-template', jev_template,
    ])
    text = read_log(logf)
    m = re.findall(r'questions=(\d+) keep=(\d+) change=(\d+) problems=(\d+)', text)
    if not m:
        log(f'  {slug}: decisions log has no summary (rc={rc})')
        return -1
    tot, keep, chg, prob = map(int, m[-1])
    n = count_decisions(ROOT / out_root / slug)
    log(f'  {slug}: decisions {n}/{expected} (keep={keep} change={chg} problems={prob})')
    if prob > 0:
        return -1
    return n


def apply_subject(name: str, slug: str, batch_root: str, decisions_root: str,
                  expected: int, write: bool) -> dict:
    args = ['tmp_jev_full_apply.py', '--subject', slug,
            '--batch-root', batch_root, '--decisions-root', decisions_root]
    if write:
        args.append('--write')
    rc, logf = run_step(name, args)
    text = read_log(logf)
    m = re.findall(
        r'TOTAL decisions=(\d+) kept=(\d+) confirmed=(\d+) changed=(\d+) '
        r'errors=(\d+) subject_errors=(\d+)',
        text,
    )
    if not m:
        return {'ok': False, 'rc': rc, 'raw': text[-400:]}
    dec, kept, conf, chg, err, serr = map(int, m[-1])
    return {'ok': rc == 0 and err == 0 and serr == 0 and dec == expected,
            'rc': rc, 'decisions': dec, 'kept': kept, 'confirmed': conf,
            'changed': chg, 'errors': err, 'subject_errors': serr}


def run_demo(name: str, args: list[str], out_json: str) -> int:
    LOG_DIR.mkdir(exist_ok=True)
    log('RUN ' + name + ' :: ' + ' '.join(args))
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    r = subprocess.run([str(ROOT / '.venv' / 'Scripts' / 'examdata.exe')] + args,
                       cwd=ROOT, capture_output=True, env=env)
    out = ROOT / out_json
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(r.stdout)
    if r.stderr:
        (LOG_DIR / f'{name}.err').write_bytes(r.stderr)
    log(f'  exit={r.returncode} bytes={len(r.stdout)} -> {out_json}')
    return r.returncode


def main() -> int:
    started = time.time()
    status: dict = {'phase': 'start', 'subjects': {}}

    # Phase 0: serialize after round2 watcher
    status['phase'] = 'wait_round2'
    how = wait_round2()
    status['round2_wait'] = how
    log(f'round2 wait result: {how}')

    # Phase 1: per-slug pipeline
    manifest = json.loads((ROOT / BATCH_ROOT / 'manifest.json').read_text(encoding='utf-8'))
    slugs = sorted(manifest, key=lambda s: (manifest[s]['questions'], s))
    status['phase'] = 'untagged_jev'
    jev_ok: dict[str, bool] = {}
    for slug in slugs:
        expected = manifest[slug]['questions']
        ok = finish_jev(f'ut_jev_{slug}', slug, f'{BATCH_ROOT}/{slug}/batches',
                        JEV_TEMPLATE.format(slug=slug), expected)
        jev_ok[slug] = ok
        status['subjects'].setdefault(slug, {})['jev_ok'] = ok
        log(f'{slug}: jev {"COMPLETE" if ok else "INCOMPLETE"}')

    status['phase'] = 'untagged_decisions'
    for slug in slugs:
        if not jev_ok.get(slug):
            log(f'{slug}: skip decisions (jev incomplete)')
            continue
        n = write_decisions(f'ut_dec_{slug}', slug, BATCH_ROOT, DEC_ROOT,
                            JEV_TEMPLATE, manifest[slug]['questions'])
        status['subjects'][slug]['decisions'] = n

    status['phase'] = 'untagged_apply'
    for slug in slugs:
        expected = manifest[slug]['questions']
        if count_decisions(ROOT / DEC_ROOT / slug) < expected:
            log(f'{slug}: skip apply (decisions incomplete)')
            continue
        dry = apply_subject(f'ut_dry_{slug}', slug, BATCH_ROOT, DEC_ROOT, expected,
                            write=False)
        log(f'{slug}: dry-run {dry}')
        status['subjects'][slug]['dry'] = dry
        if dry.get('ok'):
            wr = apply_subject(f'ut_write_{slug}', slug, BATCH_ROOT, DEC_ROOT,
                               expected, write=True)
            log(f'{slug}: apply {wr}')
            status['subjects'][slug]['apply'] = wr
        else:
            log(f'{slug}: dry-run NOT clean -> apply skipped')

    # Phase 1b: convergence rounds (re-check changed rows until a fixed point)
    prev_dec = DEC_ROOT
    prev_batch = BATCH_ROOT
    converged_at = None
    for rnd in range(2, MAX_ROUND + 1):
        status['phase'] = f'untagged_round{rnd}'
        out_batches = f'tmp_jev_untagged_batches_r{rnd}'
        rc, logf = run_step(f'ut_r{rnd}_export', [
            'tmp_jev_r2_export.py',
            '--decisions-root', prev_dec,
            '--batch-root', prev_batch,
            '--out-root', out_batches,
        ])
        text = read_log(logf)
        m = re.findall(r'TOTAL round-2 export: (\d+) questions', text)
        total = int(m[-1]) if m else -1
        log(f'untagged round {rnd} export: {total} questions to re-check')
        status[f'untagged_round{rnd}_export_total'] = total
        if total == 0:
            converged_at = rnd - 1
            log(f'UNTAGGED CONVERGED: round {rnd} export empty '
                f'(round {rnd - 1} is the fixed point)')
            break
        if total < 0:
            log('untagged export failed; stopping convergence loop')
            break

        subjects = sorted(p.name for p in (ROOT / out_batches).iterdir() if p.is_dir())
        dec_root = f'tmp_jev_untagged_decisions_r{rnd}'
        status[f'untagged_round{rnd}_subjects'] = subjects
        for slug in subjects:
            exp = batches_lines(ROOT / out_batches / slug / 'batches')
            ok = finish_jev(f'ut_r{rnd}_jev_{slug}', slug,
                            f'{out_batches}/{slug}/batches',
                            f'tmp_jev_untagged_r{rnd}_{slug}.jsonl', exp)
            if not ok:
                log(f'untagged round {rnd} {slug}: jev incomplete -> skipped')
                continue
            n = write_decisions(f'ut_r{rnd}_dec_{slug}', slug, out_batches, dec_root,
                                f'tmp_jev_untagged_r{rnd}_{{slug}}.jsonl', exp)
            if n < exp:
                log(f'untagged round {rnd} {slug}: decisions incomplete -> skipped')
                continue
            dry = apply_subject(f'ut_r{rnd}_dry_{slug}', slug, out_batches, dec_root,
                                exp, write=False)
            log(f'untagged round {rnd} {slug}: dry-run {dry}')
            if dry.get('ok'):
                wr = apply_subject(f'ut_r{rnd}_write_{slug}', slug, out_batches,
                                   dec_root, exp, write=True)
                log(f'untagged round {rnd} {slug}: apply {wr}')
            else:
                log(f'untagged round {rnd} {slug}: dry-run NOT clean -> apply skipped')
        prev_dec = dec_root
        prev_batch = out_batches
    else:
        log(f'untagged max rounds ({MAX_ROUND}) reached without an empty export')
    status['converged_at'] = converged_at

    # Phase 2: no-credit reruns
    status['phase'] = 'reruns'
    run_step('post_completeness', ['tmp_completeness.py'])
    run_step('post_consistency_audit', ['tmp_consistency_audit.py'])
    run_step('post_tag_consistency', ['tmp_tag_consistency.py'])
    run_step('post_untagged_audit', ['tmp_untagged_audit.py', '--n', '2'])
    run_demo('post_demo_d1', ['tag-questions', '--tag', 'WBI11-2.2', '--subject',
                              'ial18-biology', '--year-from', '2025', '--year-to',
                              '2025', '--json'], 'tmp_demo/d1.json')
    run_demo('post_demo_d2', ['tag-questions', '--tag', 'WME01-4.2', '--subject',
                              'ial-maths', '--year-from', '2019', '--year-to', '2019',
                              '--limit', '100', '--json'], 'tmp_demo/d2.json')
    run_demo('post_demo_d3', ['tag-questions', '--tag', 'WME01-4.2', '--subject',
                              'ial-maths', '--limit', '300', '--json'], 'tmp_demo/d3.json')
    run_demo('post_demo_d4', ['tag-questions', '--tag', 'WPH11-9', '--subject',
                              'ial18-physics', '--year-from', '2019', '--year-to',
                              '2019', '--limit', '100', '--json'], 'tmp_demo/d4.json')
    run_demo('post_demo_d5', ['tag-questions', '--tag', 'WME01-4.2', '--subject',
                              'ial18-mathematics', '--limit', '300', '--json'],
             'tmp_demo/d5.json')
    rc, logf = run_step('post_pytest', ['-m', 'pytest', '-q'])
    status['post_pytest_rc'] = rc

    status['phase'] = 'done'
    status['elapsed_hours'] = round((time.time() - started) / 3600, 2)
    STATUS_PATH.write_text(json.dumps(status, indent=2, ensure_ascii=False),
                           encoding='utf-8')
    log('UNTAGGED WATCHER DONE')
    return 0


if __name__ == '__main__':
    sys.exit(main())
