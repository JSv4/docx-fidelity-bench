from __future__ import annotations
import hashlib
import json
import os
import subprocess
import re
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Word reference tracks. `word` is the provider-neutral track; a capture that names no specific route uses it.
WORD_TRACKS = frozenset({'word', 'word-online', 'word-onedrive', 'word-desktop'})


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def read_json(path):
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError('Duplicate JSON key: ' + key)
            obj[key] = value
        return obj
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs, parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON value: ' + value)))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def execute(args, timeout=120, input=None):
    result = subprocess.run([str(a) for a in args], input=input, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(f'{Path(str(args[0])).name} exited {result.returncode}: {result.stderr[-4000:]}')
    return result.stdout


def contained(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError('Path escapes registry root: ' + str(relative))
    return path


def validate_registry(registry=None):
    registry = registry or read_json(ROOT / 'fixtures/manifest.json')
    if registry.get('schema') != 1 or not isinstance(registry['suite'].get('version'), int) or registry['suite']['version'] < 1:
        raise ValueError('Unknown registry or suite version')
    ids = [c['id'] for c in registry['cases']]
    if len(set(ids)) != len(ids) or len(set(registry['suite']['cases'])) != len(registry['suite']['cases']) or set(ids) != set(registry['suite']['cases']):
        raise ValueError('Duplicate or missing suite member')
    for case in registry['cases']:
        if not re.fullmatch('[a-z][a-z0-9-]{0,79}', case['id']) or not isinstance(case['version'], int) or case['version'] < 1 or case['rights']['license'] != 'MIT' or not case['rights']['author'] or not case['rights']['origin']:
            raise ValueError('Invalid case version or rights record')
        if digest(contained(ROOT, case['input'])) != case['sha256']:
            raise ValueError('Stale input digest: ' + case['id'])
        if digest(contained(ROOT, case['generator']['path'])) != case['generator']['sha256']:
            raise ValueError('Stale generator digest: ' + case['id'])
        if not case['tokens'] or any(not isinstance(n, int) or n < 1 for n in case['tokens'].values()):
            raise ValueError('Invalid token inventory')
        for assertion in case['assertions']:
            versions = {'marker-region': {1, 2}, 'same-page': {1}, 'marker-reference-position': {1}}
            if assertion.get('version') not in versions.get(assertion.get('type'), set()):
                raise ValueError('Unknown assertion type or version')
            if assertion.get('adjudicated', 'word') != 'word':
                raise ValueError('Unknown assertion adjudication')
            if 'adjudicated' in assertion and (assertion['type'] == 'marker-reference-position' or assertion.get('page') == 'reference'):
                raise ValueError('A Word-adjudicated assertion cannot be relative to the reference')
            if assertion['type'] == 'marker-reference-position' or (assertion['type'] == 'marker-region' and assertion['version'] == 2):
                tolerance = assertion.get('tolerancePt')
                if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or not math.isfinite(tolerance) or tolerance < 0 or not isinstance(assertion.get('marker'), str):
                    raise ValueError('Invalid marker tolerance declaration')
    return registry
