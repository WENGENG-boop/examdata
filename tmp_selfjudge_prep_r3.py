"""r3 pack generator: reuses tmp_selfjudge_prep logic with the r3 batch root.

Usage:
  python tmp_selfjudge_prep_r3.py --slug ial18-physics [--force]
Packs are written to tmp_selfjudge/r3/{slug}/{UNIT}-pNN.txt (same format as r2).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tmp_selfjudge_prep as base

base.SETS = {'r3': 'tmp_jev_full_batches_r3'}

if __name__ == '__main__':
    sys.argv = [sys.argv[0]] + sys.argv[1:] + ['--set', 'all']
    base.main()
