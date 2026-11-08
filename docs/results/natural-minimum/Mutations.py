"""Reject damaged placement, page ownership, text inventories and paint."""
import copy
import gzip
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from bench.pdf import companion_checks, reference_failures
from MinimumPitch import checks


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
        kinds = ['line-up', 'line-down', 'within-slot-up', 'missing', 'duplicate', 'unpainted', 'extra', 'extra-blank-page']
        if case['id'].startswith('natural-minimum-64-'):
            kinds += ['wrong-page', 'missing-last-page', 'duplicate-page']
        for kind in kinds:
            changed = copy.deepcopy(original)
            word = next(w for w in changed['words'] if w['text'] == 'Oxlip08')
            if kind in ('line-up', 'line-down'):
                delta = 2355 / 2048 * 20 * (-1 if kind == 'line-up' else 1)
                word['rect'][1] += delta
                word['rect'][3] += delta
            elif kind == 'within-slot-up':
                word['rect'][1] -= .8
                word['rect'][3] -= .8
                assert not reference_failures(case, changed)
                assert all(c['passed'] for c in companion_checks(case['pdfCompanion'], changed))
            elif kind == 'extra-blank-page':
                changed['geometry'].append(copy.deepcopy(changed['geometry'][-1]))
            elif kind == 'missing':
                changed['words'].remove(word)
            elif kind == 'duplicate':
                changed['words'].append(copy.deepcopy(word))
            elif kind == 'unpainted':
                word['inkPixels'] = 0
            elif kind == 'extra':
                extra = copy.deepcopy(word)
                extra['text'] = 'UnrequestedToken'
                changed['words'].append(extra)
            elif kind == 'wrong-page':
                next(w for w in changed['words'] if w['text'] == 'Oxlip29')['page'] = 1
            elif kind == 'missing-last-page':
                last = len(changed['geometry'])
                changed['geometry'] = changed['geometry'][:-1]
                changed['words'] = [w for w in changed['words'] if w['page'] != last]
            else:
                changed['words'] += [copy.deepcopy(w) for w in original['words'] if w['page'] == 2]
            failed = failures(changed)
            assert failed, (case['id'], kind)
            if kind in ('within-slot-up', 'extra-blank-page'):
                assert any(not c['passed'] for c in checks(case, changed)), (case['id'], kind)
            records.append(dict(case=case['id'], mutation=kind, rejected=True, failures=failed))
    return records


if __name__ == '__main__':
    records = verify()
    Path(__file__).with_name('mutations.json').write_text(json.dumps(records, indent=2) + '\n')
    print(f'Rejected all {len(records)} corrupted observations')
