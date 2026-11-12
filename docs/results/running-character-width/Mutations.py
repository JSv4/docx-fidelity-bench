"""Reject damaged glyph scale, page ownership, source inventory and paint."""
import copy
import gzip
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from bench.pdf import companion_checks, reference_failures
from WidthChecks import checks


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
                    + [c['kind'] for c in checks(case, info) if not c['passed']])
        assert not failures(original)
        kinds = ['narrow-glyph', 'wide-glyph', 'tall-glyph', 'short-glyph', 'line-down',
                 'missing', 'duplicate', 'unpainted', 'extra', 'extra-blank-page', 'swapped-slots', 'body-displaced', 'body-overlap']
        if len(original['geometry']) > 1:
            kinds += ['wrong-page', 'missing-last-page', 'duplicate-page']
        for kind in kinds:
            changed = copy.deepcopy(original)
            word = changed['words'][7]
            if kind in ('body-displaced', 'body-overlap'):
                body = next(w for w in changed['words'] if w['text'] == 'Ledger001')
                delta = 100 if kind == 'body-displaced' else 36 - body['rect'][1]
                body['rect'][1] += delta
                body['rect'][3] += delta
            elif kind in ('narrow-glyph', 'wide-glyph'):
                word['rect'][2] += -.3 if kind == 'narrow-glyph' else .3
                assert not reference_failures(case, changed)
                assert all(c['passed'] for c in companion_checks(case['pdfCompanion'], changed))
            elif kind in ('tall-glyph', 'short-glyph'):
                word['rect'][3] += .3 if kind == 'tall-glyph' else -.3
            elif kind == 'line-down':
                word['rect'][1] += 14
                word['rect'][3] += 14
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
            elif kind == 'extra-blank-page':
                changed['geometry'].append(copy.deepcopy(changed['geometry'][-1]))
            elif kind == 'swapped-slots':
                labels = [w for w in changed['words'] if w['text'].startswith('Sorrel')]
                labels[0]['rect'], labels[1]['rect'] = labels[1]['rect'], labels[0]['rect']
            elif kind == 'wrong-page':
                next(w for w in changed['words'] if w['page'] == 2)['page'] = 1
            elif kind == 'missing-last-page':
                last = len(changed['geometry'])
                changed['geometry'] = changed['geometry'][:-1]
                changed['words'] = [w for w in changed['words'] if w['page'] != last]
            else:
                changed['words'] += [copy.deepcopy(w) for w in original['words'] if w['page'] == 2]
            failed = failures(changed)
            assert failed, (case['id'], kind)
            records.append(dict(case=case['id'], mutation=kind, rejected=True, failures=failed))
    return records


if __name__ == '__main__':
    records = verify()
    Path(__file__).with_name('mutations.json').write_text(json.dumps(records, indent=2) + '\n')
    print(f'Rejected all {len(records)} corrupted observations')
