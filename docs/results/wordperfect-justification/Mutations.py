"""Exercise the retained checks against corrupted copies of captured observations."""
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
        kinds = ['shrunken-glyphs', 'wide-glyph', 'short-glyph', 'tall-glyph', 'line-down',
                 'missing', 'duplicate', 'unpainted', 'reordered', 'extra-blank-page']
        if len(original['geometry']) > 1:
            kinds += ['wrong-page', 'missing-last-page', 'duplicate-last-page']
        for kind in kinds:
            changed = copy.deepcopy(original)
            word = changed['words'][0]
            if kind == 'shrunken-glyphs':
                for item in changed['words']:
                    rect = item['rect']; rect[2] = rect[0] + (rect[2] - rect[0]) * .95
                assert not reference_failures(case, changed)
            elif kind == 'wide-glyph': word['rect'][2] += .3
            elif kind == 'short-glyph': word['rect'][3] -= .3
            elif kind == 'tall-glyph': word['rect'][3] += .3
            elif kind == 'line-down': word['rect'][1] += 14; word['rect'][3] += 14
            elif kind == 'missing': changed['words'].pop(0)
            elif kind == 'duplicate': changed['words'].append(copy.deepcopy(word))
            elif kind == 'unpainted': word['inkPixels'] = 0
            elif kind == 'reordered': changed['rawTokens'][0], changed['rawTokens'][1] = changed['rawTokens'][1], changed['rawTokens'][0]
            elif kind == 'extra-blank-page': changed['geometry'].append(copy.deepcopy(changed['geometry'][-1]))
            elif kind == 'wrong-page': next(w for w in changed['words'] if w['page'] == 2)['page'] = 1
            elif kind == 'missing-last-page':
                changed['geometry'].pop(); changed['words'] = [w for w in changed['words'] if w['page'] == 1]
            else: changed['words'] += [copy.deepcopy(w) for w in original['words'] if w['page'] == 2]
            failed = failures(changed)
            assert failed, (case['id'], kind)
            records.append(dict(case=case['id'], mutation=kind, rejected=True, failures=failed))
    return records


if __name__ == '__main__':
    records = verify()
    Path(__file__).with_name('mutations.json').write_text(json.dumps(records, indent=2) + '\n')
    print(f'Rejected all {len(records)} corrupted observations')
