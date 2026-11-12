"""Reject damaged pitches, owner geometry, numbering, inventory, order and painted content."""
import copy
import gzip
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from bench.pdf import companion_checks, reference_failures
from Checks import source_contract, control_checks, checks


def verify():
    folder = Path(__file__).resolve().parent
    with gzip.open(folder / 'manifest.json.gz', 'rt') as stream:
        cases = json.load(stream)['cases']
    records = []
    for case in cases:
        cid = case['id']
        with gzip.open(folder / (cid + '-candidate-inspection.json.gz'), 'rt') as stream:
            original = json.load(stream)
        control_id = cid.rsplit('-', 1)[0] + '-natural'
        with gzip.open(folder / (control_id + '-candidate-inspection.json.gz'), 'rt') as stream:
            control = json.load(stream)
        with gzip.open(folder / (control_id + '-baseline-inspection.json.gz'), 'rt') as stream:
            baseline_control = json.load(stream)
        assert all(c['passed'] for c in control_checks(control, baseline_control))
        contract = source_contract(root / case['input'])
        def failures(info):
            return (reference_failures(case, info)
                    + [c['name'] for c in companion_checks(case['pdfCompanion'], info) if not c['passed']]
                    + [c['name'] for c in checks(contract, info, control) if not c['passed']])
        assert not failures(original)
        kinds = ['line-up', 'line-down', 'missing', 'duplicate', 'unpainted', 'extra',
                 'within-slot', 'all-baselines', 'horizontal-shift', 'extra-page', 'reading-order']
        if len(contract['labels']) == 64:
            kinds += ['wrong-page', 'missing-last-page', 'duplicated-page']
        if contract['numbered']:
            kinds += ['missing-number', 'duplicated-number', 'shifted-number']
        for kind in kinds:
            changed = copy.deepcopy(original)
            word = next(w for w in changed['words'] if w['text'] == 'Rue008')
            if kind in ('line-up', 'line-down', 'within-slot'):
                delta = -.8 if kind == 'within-slot' else contract['step'] * (-1 if kind == 'line-up' else 1)
                word['rect'][1] += delta; word['rect'][3] += delta
            elif kind == 'all-baselines':
                for w in changed['words']:
                    w['rect'][1] += .1; w['rect'][3] += .1
            elif kind == 'horizontal-shift':
                word['rect'][0] += .5; word['rect'][2] += .5
            elif kind == 'wrong-page':
                word['page'] += 1
            elif kind == 'missing':
                changed['words'].remove(word)
            elif kind == 'duplicate':
                changed['words'].append(copy.deepcopy(word))
            elif kind == 'unpainted':
                word['inkPixels'] = 0
            elif kind == 'extra':
                extra = copy.deepcopy(word); extra['text'] = 'UnrequestedToken'; changed['words'].append(extra)
            elif kind == 'extra-page':
                changed['geometry'].append(copy.deepcopy(changed['geometry'][-1]))
            elif kind == 'reading-order':
                changed['words'] = list(reversed(changed['words']))
            elif kind == 'missing-last-page':
                last = len(changed['geometry']);changed['geometry'].pop()
                changed['words'] = [w for w in changed['words'] if w['page'] != last]
            elif kind == 'duplicated-page':
                changed['words'] += [copy.deepcopy(w) for w in original['words'] if w['page'] == 2]
            else:
                number = next(w for w in changed['words'] if w['text'] == '1.')
                if kind == 'missing-number': changed['words'].remove(number)
                elif kind == 'duplicated-number': changed['words'].append(copy.deepcopy(number))
                else: number['rect'][0] += .5; number['rect'][2] += .5
            if kind in ('within-slot', 'horizontal-shift', 'all-baselines', 'reading-order', 'shifted-number'):
                assert not reference_failures(case, changed), (cid, kind, 'Must exercise the slot-only gap')
                assert not all(c['passed'] for c in checks(contract, changed, control))
            failed = failures(changed)
            assert failed, (cid, kind)
            records.append(dict(case=cid, mutation=kind, rejected=True, failures=failed))
        paired, shifted_control = copy.deepcopy(original), copy.deepcopy(control)
        for info in (paired, shifted_control):
            for word in info['words']:
                word['rect'][0] += 1; word['rect'][2] += 1
        assert not reference_failures(case, paired)
        assert all(c['passed'] for c in checks(contract, paired, shifted_control))
        failed = [c['name'] for c in control_checks(shifted_control, baseline_control) if not c['passed']]
        assert failed
        records.append(dict(case=cid, mutation='paired-control-horizontal-shift', rejected=True, failures=failed))
    return records


if __name__ == '__main__':
    records = verify()
    Path(__file__).with_name('mutations.json').write_text(json.dumps(records, indent=2) + '\n')
    print(f'Rejected all {len(records)} corrupted observations')
