"""Print full spec point text for given codes.

usage: python spec_text.py <subject-json-name> <CODE> [CODE...]
"""
import json
import sys

name = sys.argv[1]
codes = set(sys.argv[2:])
d = json.load(open(f'.data/specs/parsed/{name}.json', encoding='utf-8'))
for unit in d['units']:
    for node in unit['nodes']:
        for ch in node.get('children', []):
            if ch.get('label') in codes:
                print('###', ch['label'], '| page', ch.get('page'))
                print(ch['text'])
                print()
