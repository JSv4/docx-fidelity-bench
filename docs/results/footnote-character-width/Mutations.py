"""Reject damage without hiding the unchanged unscaled control's pitch diagnostics."""
import copy
import gzip
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from bench.pdf import companion_checks, reference_failures
from WidthChecks import checks, source


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
                + [c for c in companion_checks(case['pdfCompanion'], info) if not c['passed']]
                + [c for c in checks(case, info) if not c['passed']])
        prior = failures(original)
        def diagnostic_id(failure):
            if isinstance(failure,str): return failure
            return tuple(failure.get(key) for key in ('kind','name','page','label','previous','current'))
        prior_ids = {diagnostic_id(f) for f in prior}
        if case['id'] == 'footnote-character-width-400-100':
            assert len(prior) == 8 and all(c['kind'] == 'line-pitch' for c in prior)
        else:
            assert not prior
        kinds = ['narrow-glyph','wide-glyph','tall-glyph','short-glyph','line-down','missing','duplicate',
            'unpainted','extra','extra-blank-page','swapped-slots','body-displaced','body-overlap','body-height']
        if len(original['geometry']) > 1: kinds += ['wrong-page','missing-last-page','duplicate-page']
        if case['id'].startswith('story-drift-footer-'): kinds += ['independent-story-drift']
        if case['id'] == 'footnote-character-width-400-150': kinds += ['note-above-body-band']
        for kind in kinds:
            changed = copy.deepcopy(original)
            word = next(w for w in changed['words'] if w['text'] == 'Sorrel007')
            if kind in ('narrow-glyph','wide-glyph'):
                word['rect'][2] += -.3 if kind == 'narrow-glyph' else .3
            elif kind in ('tall-glyph','short-glyph'):
                word['rect'][3] += .3 if kind == 'tall-glyph' else -.3
            elif kind == 'line-down':
                word['rect'][1] += 14; word['rect'][3] += 14
            elif kind == 'missing': changed['words'].remove(word)
            elif kind == 'duplicate': changed['words'].append(copy.deepcopy(word))
            elif kind == 'unpainted': word['inkPixels'] = 0
            elif kind == 'extra':
                extra = copy.deepcopy(word); extra['text'] = 'UnrequestedToken'; changed['words'].append(extra)
            elif kind == 'extra-blank-page': changed['geometry'].append(copy.deepcopy(changed['geometry'][-1]))
            elif kind == 'swapped-slots':
                labels = [w for w in changed['words'] if w['text'].startswith('Sorrel')]
                labels[0]['rect'],labels[1]['rect'] = labels[1]['rect'],labels[0]['rect']
            elif kind in ('body-displaced','body-overlap','body-height'):
                body = next(w for w in changed['words'] if w['text'].startswith('Harbor'))
                if kind == 'body-height': body['rect'][3] += .3
                else:
                    delta = 1 if kind == 'body-displaced' else 700-body['rect'][1]
                    body['rect'][1] += delta; body['rect'][3] += delta
            elif kind == 'wrong-page': next(w for w in changed['words'] if w['page'] == 2)['page'] = 1
            elif kind == 'missing-last-page':
                last = len(changed['geometry']); changed['geometry'] = changed['geometry'][:-1]
                changed['words'] = [w for w in changed['words'] if w['page'] != last]
            elif kind == 'duplicate-page': changed['words'] += [copy.deepcopy(w) for w in original['words'] if w['page'] == 2]
            elif kind == 'independent-story-drift':
                for w in changed['words']:
                    if w['text'].startswith('Sorrel'): w['rect'][1] += .25; w['rect'][3] += .25
            else:
                contract = source(case); pitch = contract['pitch']; index = 0
                for page,rows in enumerate((48,47,5),1):
                    for row in range(rows):
                        for slot in range(4):
                            index += 1
                            w = next(w for w in changed['words'] if w['text'] == f'Sorrel{index:03d}')
                            w['page'] = page; top = 720-(rows-row)*pitch
                            w['rect'] = [72+slot*10*contract['advance'],top,
                                72+(slot*10+9)*contract['advance'],top+pitch]
                assert all(c['passed'] for c in checks(case,changed) if c['kind'] != 'note-band-bounds')
            failed = failures(changed)
            additional = [f for f in failed if diagnostic_id(f) not in prior_ids]
            assert additional, (case['id'],kind)
            records.append(dict(case=case['id'],mutation=kind,rejected=True,priorFailureCount=len(prior),
                newFailures=additional,failures=failed))
    return records


if __name__ == '__main__':
    records = verify()
    Path(__file__).with_name('mutations.json').write_text(json.dumps(records,indent=2)+'\n')
    print(f'Rejected all {len(records)} corrupted observations')
