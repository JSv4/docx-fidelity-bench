"""Reject corrupted line placement, inventories and paint in retained observations."""
import copy
import gzip
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from bench.pdf import companion_checks, reference_failures
from Pitch import checks


def verify():
    folder = Path(__file__).resolve().parent
    with gzip.open(folder / 'manifest.json.gz', 'rt') as stream:
        cases = json.load(stream)['cases']
    records = []
    for case in cases:
        with gzip.open(folder / (case['id'] + '-candidate-inspection.json.gz'), 'rt') as stream:
            original = json.load(stream)
        def failures(info):
            return (reference_failures(case, info)
                    + [c['name'] for c in companion_checks(case['pdfCompanion'], info) if not c['passed']]
                    + ['line-pitch' for c in checks(case, info) if not c['passed']])
        assert not failures(original)
        for kind in ['line-up', 'line-down', 'missing', 'duplicate', 'unpainted', 'extra'] + (
                ['within-slot'] if case['id'].startswith('empty-run-2-') else []):
            changed = copy.deepcopy(original)
            word = next(w for w in changed['words'] if w['text'] == 'Mallow08')
            if kind in ('line-up', 'line-down', 'within-slot'):
                delta = 10 if kind == 'within-slot' else checks(case, original)[0]['expectedPt'] * (-1 if kind == 'line-up' else 1)
                word['rect'][1] += delta
                word['rect'][3] += delta
            elif kind == 'missing':
                changed['words'].remove(word)
            elif kind == 'duplicate':
                changed['words'].append(copy.deepcopy(word))
            elif kind == 'unpainted':
                word['inkPixels'] = 0
            else:
                extra = copy.deepcopy(word)
                extra['text'] = 'UnrequestedToken'
                changed['words'].append(extra)
            if kind == 'within-slot':
                assert not reference_failures(case, changed), 'Must exercise the original slot-only gap'
                assert not all(c['passed'] for c in checks(case, changed))
            failed = failures(changed)
            assert failed, (case['id'], kind)
            records.append(dict(case=case['id'], mutation=kind, rejected=True, failures=failed))
    return records


if __name__ == '__main__':
    records = verify()
    Path(__file__).with_name('mutations.json').write_text(json.dumps(records, indent=2) + '\n')
    print(f'Rejected all {len(records)} corrupted observations')
