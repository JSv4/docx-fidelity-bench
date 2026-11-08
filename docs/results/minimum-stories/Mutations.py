"""Exercise content, page, paint, pitch, marker and paired-control failure contracts."""
import copy
import gzip
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from bench.pdf import companion_checks, correctness
from Checks import source_contract, control_checks, checks


def verify():
    folder = Path(__file__).resolve().parent
    def read(name):
        with gzip.open(folder / (name + '.json.gz'), 'rt') as stream:
            return json.load(stream)
    records = []
    for case in read('manifest')['cases']:
        cid = case['id']
        original = read(cid + '-candidate-inspection')
        reference = read(cid + '-reference-inspection')
        control_id = cid.rsplit('-', 1)[0] + '-natural'
        control = read(control_id + '-candidate-inspection')
        baseline = read(control_id + '-baseline-inspection')
        contract = source_contract(root / case['input'])
        def failures(info):
            return ([c['name'] for c in correctness(case, reference, info) if not c['passed']]
                    + [c['name'] for c in companion_checks(case['pdfCompanion'], info) if not c['passed']]
                    + [c['name'] for c in checks(contract, info, control) if not c['passed']])
        assert not failures(original)
        assert all(c['passed'] for c in control_checks(control, baseline))
        kinds = ['line-up', 'line-down', 'missing', 'duplicate', 'unpainted', 'extra',
                 'all-baselines', 'horizontal-shift', 'extra-page', 'reading-order', 'missing-body']
        if len(original['geometry']) > 1:
            kinds += ['wrong-page', 'missing-last-page', 'duplicated-page']
        if contract['owner'] in ('footnote', 'endnote'):
            kinds += ['missing-marker', 'duplicated-marker', 'shifted-marker']
        for kind in kinds:
            changed = copy.deepcopy(original)
            word = next(w for w in changed['words'] if w['text'] == 'Poppy008')
            if kind in ('line-up', 'line-down'):
                delta = contract['step'] * (-1 if kind == 'line-up' else 1)
                word['rect'][1] += delta; word['rect'][3] += delta
            elif kind == 'all-baselines':
                for w in changed['words']:
                    w['rect'][1] += 1; w['rect'][3] += 1
            elif kind == 'horizontal-shift':
                word['rect'][0] += 1; word['rect'][2] += 1
            elif kind == 'wrong-page':
                word['page'] = word['page'] % len(changed['geometry']) + 1
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
                last = len(changed['geometry']); changed['geometry'].pop()
                changed['words'] = [w for w in changed['words'] if w['page'] != last]
            elif kind == 'duplicated-page':
                changed['words'] += [copy.deepcopy(w) for w in original['words'] if w['page'] == 2]
            elif kind == 'missing-body':
                changed['words'] = [w for w in changed['words'] if w['text'] != 'Garden001']
            else:
                number = next(w for w in changed['words'] if w['text'] in ('1', 'i'))
                if kind == 'missing-marker': changed['words'].remove(number)
                elif kind == 'duplicated-marker': changed['words'].append(copy.deepcopy(number))
                else: number['rect'][0] += 1; number['rect'][2] += 1
            failed = failures(changed)
            assert failed, (cid, kind)
            records.append(dict(case=cid, mutation=kind, rejected=True, failures=failed))
        paired, shifted_control = copy.deepcopy(original), copy.deepcopy(control)
        for info in (paired, shifted_control):
            for word in info['words']:
                word['rect'][0] += 1; word['rect'][2] += 1
        assert all(c['passed'] for c in checks(contract, paired, shifted_control))
        failed = [c['name'] for c in control_checks(shifted_control, baseline) if not c['passed']]
        assert failed
        records.append(dict(case=cid, mutation='paired-control-horizontal-shift', rejected=True, failures=failed))
    return records


if __name__ == '__main__':
    records = verify()
    Path(__file__).with_name('mutations.json').write_text(json.dumps(records, indent=2) + '\n')
    print(f'Rejected all {len(records)} corrupted observations')
