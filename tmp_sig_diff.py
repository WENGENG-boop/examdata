"""对比 locator 签名 before/after（tmp_locator_sig.py 的输出）。

用法: python tmp_sig_diff.py before.json after.json
"""
import json
import sys


def load(path):
    return {(r['doc_id'], r['role']): r for r in json.load(open(path, encoding='utf-8'))}


def sig(r):
    if 'error' in r:
        return ('error', r['error'])
    return ('ok', r['n_paths'], tuple(r['first']), tuple(r['last']), r['n_regions'])


def main() -> None:
    a = load(sys.argv[1])
    b = load(sys.argv[2])
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    print(f'before={len(a)} after={len(b)} only_before={len(only_a)} only_after={len(only_b)}')
    for k in only_a:
        print('ONLY_BEFORE', k, a[k]['slug'])
    for k in only_b:
        print('ONLY_AFTER', k, b[k]['slug'])
    diffs = 0
    for k in sorted(set(a) & set(b)):
        if sig(a[k]) != sig(b[k]):
            diffs += 1
            print('DIFF', k, a[k]['slug'])
            print('  before:', sig(a[k]))
            print('  after :', sig(b[k]))
    print(f'diffs: {diffs}')


if __name__ == '__main__':
    main()
