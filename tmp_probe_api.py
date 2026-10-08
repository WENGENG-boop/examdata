"""Probe TypeSafe API with a real systemone-format request.

Exit 0 -> API usable (HTTP 200). Exit 1 -> not usable (402 billing, 5xx, ...).
Exit 2 -> no API key in env.
"""
import os
import sys

import httpx

key = os.environ.get('TYPESAFE_API_KEY') or ''
if not key:
    sys.exit(2)

payload = {
    'state': {'exam': 'probe'},
    'model': 'jev-latest',
    'questions': {
        'q0': {
            'type': 'choice',
            'instructions': {
                'task': 'Choose the matching option.',
                'unit': 'U1', 'unit_name': 'Probe', 'paper': 'probe',
                'question_number': '1', 'marks': 1,
                'context': '', 'question_text': 'probe',
            },
            'criteria': {'A': 'option a', 'B': 'option b'},
        }
    },
}

try:
    r = httpx.post(
        'https://api.typesafe.ai/v1/systemone',
        headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
        json=payload,
        timeout=30,
    )
    sys.exit(0 if r.status_code == 200 else 1)
except Exception:
    sys.exit(1)
