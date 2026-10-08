"""Round-2 completion + convergence watcher for the Edexcel Jev tagging pipeline.

Waits for TypeSafe credits (probe loop), then drives:
  A. round-2 Jev for the 6 pending subjects (resume-safe), then decisions + apply
  B. convergence rounds 3..MAX: export previous-round changes -> Jev -> decisions
     -> dry-run apply (gated on errors=0) -> apply --write, until a round exports
     0 questions (fixed point).

Every API-dependent step first waits for the probe to succeed; if credits run
out mid-flight the watcher pauses and resumes when they are restored.

Usage: ./.venv/Scripts/python.exe -X utf8 tmp_round2_watcher.py
Status: tmp_round2_watcher.status.json; per-step logs: tmp_watcher_logs/
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable
LOG_DIR = ROOT / 'tmp_watcher_logs'
STATUS_PATH = ROOT / 'tmp_round2_watcher.status.json'

PENDING_R2 = {
    'ial18-chemistry': 2848,
    'ial18-economics': 443,
    'ial18-it': 494,
    'ial18-mathematics': 2186,
    'ial18-mathematics-extra': 879,
    'ial18-physics': 2202,
}

PROBE_SLEEP = 600
MAX_PROBE_FAILS = 180  # 30h per wait window
MAX_ROUND = 8
JEV_TRIES = 6


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
    n = 0
    for f in sorted(dir_.glob('batch-*.jsonl')):
        n += count_lines(f)
    return n


def batches_lines(dir_: Path) -> int:
    if not dir_.is_dir():
        return 0
    n = 0
    for f in sorted(dir_.glob('batch-*.jsonl')):
        n += count_lines(f)
    return n


def finish_jev(name: str, slug: str, batches_dir: str, out_path: str,
               expected: int) -> bool:
    for attempt in range(1, JEV_TRIES + 1):
        if not wait_api():
            return False
        rc, logf = run_step(f'{name}_try{attempt}', [
            'tmp_jev_batch.py', '--subject', slug,
            '--batches-dir', batches_dir, '--out', out_path, '--skip-problems',
        ])
        n = count_choices(ROOT / out_path)
        log(f'  {slug}: choices {n}/{expected} after try {attempt}')
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
    n = count_decisions(ROOT / out_root / slug)
    log(f'  {slug}: decisions {n}/{expected} (rc={rc})')
    return n


def apply_subject(name: str, slug: str, batch_root: str, decisions_root: str,
                  write: bool) -> dict:
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
    return {'ok': rc == 0 and err == 0 and serr == 0, 'rc': rc, 'decisions': dec,
            'kept': kept, 'confirmed': conf, 'changed': chg, 'errors': err,
            'subject_errors': serr}


def main() -> int:
    started = time.time()
    status: dict = {'phase': 'start', 'subjects': {}}

    # Phase A: complete round-2 jev for the 6 pending subjects
    status['phase'] = 'round2_jev'
    jev_ok: dict[str, bool] = {}
    for slug, expected in PENDING_R2.items():
        bdir = f'tmp_jev_full_batches_r2/{slug}/batches'
        out_path = f'tmp_jev_full_r2_{slug}.jsonl'
        ok = finish_jev(f'r2_jev_{slug}', slug, bdir, out_path, expected)
        jev_ok[slug] = ok
        status['subjects'].setdefault(slug, {})['r2_jev_ok'] = ok
        log(f'{slug}: round2 jev {"COMPLETE" if ok else "INCOMPLETE"}')

    # Phase B: decisions + dry-run/apply for the 6
    status['phase'] = 'round2_decisions'
    for slug, expected in PENDING_R2.items():
        if not jev_ok.get(slug):
            log(f'{slug}: skip decisions (jev incomplete)')
            continue
        n = write_decisions(f'r2_dec_{slug}', slug, 'tmp_jev_full_batches_r2',
                            'tmp_jev_full_decisions_r2',
                            'tmp_jev_full_r2_{slug}.jsonl', expected)
        status['subjects'][slug]['r2_decisions'] = n

    status['phase'] = 'round2_apply'
    for slug, expected in PENDING_R2.items():
        if count_decisions(ROOT / 'tmp_jev_full_decisions_r2' / slug) < expected:
            log(f'{slug}: skip apply (decisions incomplete)')
            continue
        dry = apply_subject(f'r2_dry_{slug}', slug, 'tmp_jev_full_batches_r2',
                            'tmp_jev_full_decisions_r2', write=False)
        log(f'{slug}: round2 dry-run {dry}')
        status['subjects'][slug]['r2_dry'] = dry
        if dry.get('ok'):
            wr = apply_subject(f'r2_write_{slug}', slug, 'tmp_jev_full_batches_r2',
                               'tmp_jev_full_decisions_r2', write=True)
            log(f'{slug}: round2 apply {wr}')
            status['subjects'][slug]['r2_apply'] = wr
        else:
            log(f'{slug}: round2 dry-run NOT clean -> apply skipped')

    # Phase C: convergence rounds
    prev_dec = 'tmp_jev_full_decisions_r2'
    prev_batch = 'tmp_jev_full_batches_r2'
    converged_at = None
    for rnd in range(3, MAX_ROUND + 1):
        status['phase'] = f'round{rnd}'
        out_batches = f'tmp_jev_full_batches_r{rnd}'
        rc, logf = run_step(f'r{rnd}_export', [
            'tmp_jev_r2_export.py',
            '--decisions-root', prev_dec,
            '--batch-root', prev_batch,
            '--out-root', out_batches,
        ])
        text = read_log(logf)
        m = re.findall(r'TOTAL round-2 export: (\d+) questions', text)
        total = int(m[-1]) if m else -1
        log(f'round {rnd} export: {total} questions to re-check')
        status[f'round{rnd}_export_total'] = total
        if total == 0:
            converged_at = rnd - 1
            log(f'CONVERGED: round {rnd} export is empty (round {rnd - 1} is the fixed point)')
            break
        if total < 0:
            log('export failed; stopping convergence loop')
            break

        subjects = sorted(p.name for p in (ROOT / out_batches).iterdir() if p.is_dir())
        dec_root = f'tmp_jev_full_decisions_r{rnd}'
        status[f'round{rnd}_subjects'] = subjects
        for slug in subjects:
            exp = batches_lines(ROOT / out_batches / slug / 'batches')
            ok = finish_jev(f'r{rnd}_jev_{slug}', slug,
                            f'{out_batches}/{slug}/batches',
                            f'tmp_jev_full_r{rnd}_{slug}.jsonl', exp)
            if not ok:
                log(f'round {rnd} {slug}: jev incomplete -> skipped')
                continue
            n = write_decisions(f'r{rnd}_dec_{slug}', slug, out_batches, dec_root,
                                f'tmp_jev_full_r{rnd}_{{slug}}.jsonl', exp)
            if n < exp:
                log(f'round {rnd} {slug}: decisions incomplete -> skipped')
                continue
            dry = apply_subject(f'r{rnd}_dry_{slug}', slug, out_batches, dec_root,
                                write=False)
            log(f'round {rnd} {slug}: dry-run {dry}')
            if dry.get('ok'):
                wr = apply_subject(f'r{rnd}_write_{slug}', slug, out_batches,
                                   dec_root, write=True)
                log(f'round {rnd} {slug}: apply {wr}')
            else:
                log(f'round {rnd} {slug}: dry-run NOT clean -> apply skipped')
        prev_dec = dec_root
        prev_batch = out_batches
    else:
        log(f'max rounds ({MAX_ROUND}) reached without an empty export')

    # final status check dump
    rc, logf = run_step('final_retry_check', ['tmp_retry_check.py'])

    status['converged_at'] = converged_at
    status['phase'] = 'done'
    status['elapsed_hours'] = round((time.time() - started) / 3600, 2)
    STATUS_PATH.write_text(json.dumps(status, indent=2, ensure_ascii=False),
                           encoding='utf-8')
    log('WATCHER DONE')
    return 0


if __name__ == '__main__':
    sys.exit(main())
