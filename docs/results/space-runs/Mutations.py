"""Reject placement, spacing, inventory and paint corruption independently of the broad slots."""
import copy
import gzip
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from bench.pdf import companion_checks, reference_failures
from Checks import source_contract, checks


def verify():
    folder = Path(__file__).resolve().parent
    with gzip.open(folder / 'manifest.json.gz', 'rt') as stream:
        cases = json.load(stream)['cases']
    records = []
    for case in cases:
        cid = case['id']
        with gzip.open(folder / (cid + '-candidate-inspection.json.gz'), 'rt') as stream:
            original = json.load(stream)
        control_id = f"space-run-{int(cid.split('-')[2])}-control"
        with gzip.open(folder / (control_id + '-candidate-inspection.json.gz'), 'rt') as stream:
            control = json.load(stream)
        contract = source_contract(root / case['input'])
        def failures(info):
            return (reference_failures(case, info)
                    + [c['name'] for c in companion_checks(case['pdfCompanion'], info) if not c['passed']]
                    + [c['name'] for c in checks(contract, info, control) if not c['passed']])
        assert not failures(original)
        for kind in ['line-up', 'line-down', 'missing', 'duplicate', 'unpainted', 'extra',
                     'within-slot', 'all-baselines', 'space-collapse', 'wrong-page']:
            changed = copy.deepcopy(original)
            word = next(w for w in changed['words'] if w['text'] == 'Clover08')
            if kind in ('line-up', 'line-down', 'within-slot'):
                delta = 1 if kind == 'within-slot' else contract['step'] * (-1 if kind == 'line-up' else 1)
                word['rect'][1] += delta; word['rect'][3] += delta
            elif kind == 'all-baselines':
                for w in changed['words']:
                    w['rect'][1] += 1; w['rect'][3] += 1
            elif kind == 'space-collapse':
                following = next(w for w in changed['words'] if w['text'] == 'settled.'
                    and w['page'] == word['page'] and abs(w['rect'][1] - word['rect'][1]) < .02)
                following['rect'][0] -= .5; following['rect'][2] -= .5
            elif kind == 'wrong-page':
                word['page'] += 1
            elif kind == 'missing':
                changed['words'].remove(word)
            elif kind == 'duplicate':
                changed['words'].append(copy.deepcopy(word))
            elif kind == 'unpainted':
                word['inkPixels'] = 0
            else:
                extra = copy.deepcopy(word); extra['text'] = 'UnrequestedToken'; changed['words'].append(extra)
            if kind in ('within-slot', 'space-collapse'):
                assert not reference_failures(case, changed), 'Must exercise the slot-only gap'
                assert not all(c['passed'] for c in checks(contract, changed, control))
            failed = failures(changed)
            assert failed, (cid, kind)
            records.append(dict(case=cid, mutation=kind, rejected=True, failures=failed))
    return records


if __name__ == '__main__':
    records = verify()
    Path(__file__).with_name('mutations.json').write_text(json.dumps(records, indent=2) + '\n')
    print(f'Rejected all {len(records)} corrupted observations')
