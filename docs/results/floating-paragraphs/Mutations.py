"""Reject lost text, wrong page ownership, omitted pictures and removed float exclusions."""
import copy
import gzip
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from bench.pdf import correctness
from Checks import picture_checks

out = Path(__file__).resolve().parent


def verify():
    manifest = json.loads(gzip.decompress((out / 'manifest.json.gz').read_bytes()))
    evidence = json.loads((out / 'evidence.json').read_text())
    records = []
    for case in manifest['cases']:
        entry = next(e for e in evidence['cases'] if e['id'] == case['id'])
        panel = next(p for p in entry['panels'] if p['renderer'] == 'candidate')
        ref = next(p for p in entry['panels'] if p['renderer'] == 'reference')
        load = lambda item: json.loads(gzip.decompress((out / item['file']).read_bytes()))
        info, reference, html = load(panel['inspection']), load(ref['inspection']), load(panel['pictures'])['pictures']
        frames = entry['sourceFrames']
        def check(name, observed, pictures, primary=True):
            assertions = correctness(case, reference, observed)
            supplementary = picture_checks(frames, observed, pictures)
            rejected = not all(c['passed'] for c in assertions + supplementary)
            assert rejected and (not primary or not all(c['passed'] for c in assertions)), (case['id'], name)
            records.append(dict(case=case['id'], mutation=name, rejected=True,
                primaryRejected=not all(c['passed'] for c in assertions)))
        assert all(c['passed'] for c in correctness(case, reference, info) + picture_checks(frames, info, html))
        for name in ('missing-label', 'duplicate-label', 'wrong-text-page', 'wrong-line-slot'):
            changed = copy.deepcopy(info)
            word = next(w for w in changed['words'] if w['text'] == 'Chive001')
            if name == 'missing-label': changed['words'].remove(word); changed['tokens']['Chive001'] -= 1
            elif name == 'duplicate-label': changed['words'].append(copy.deepcopy(word)); changed['tokens']['Chive001'] += 1
            elif name == 'wrong-text-page': word['page'] += 1
            else: word['rect'][1] += 18; word['rect'][3] += 18
            check(name, changed, html)
        if frames:
            for name in ('missing-picture-ink', 'wrong-picture-page', 'shifted-picture', 'duplicate-html-picture'):
                changed, pictures = copy.deepcopy(info), copy.deepcopy(html)
                region = next(r for r in changed['colorRegions'] if r['coverage'] > 0)
                if name == 'missing-picture-ink': region['coverage'] = 0; pictures.pop(0)
                elif name == 'wrong-picture-page': region['page'] += 1; pictures[0]['page'] += 1
                elif name == 'shifted-picture':
                    for axis in (1, 3): region['boundsPt'][axis] += 18; pictures[0]['rect'][axis] += 18
                else: pictures.append(copy.deepcopy(pictures[0]))
                check(name, changed, pictures, name != 'duplicate-html-picture')
        blank = next((r for r in info['colorRegions'] if r['coverage'] == 0), None)
        if blank:
            changed = copy.deepcopy(info)
            region = next(r for r in changed['colorRegions'] if r['page'] == blank['page'])
            region.update(boundsPt=[276, 36, 324, 84], coverage=4096)
            check('extra-pdf-picture-on-unowned-page', changed, html, primary=False)
        if 'square' in case['id'] or 'tight' in case['id']:
            for name, label, shift in [('removed-wrap-exclusion', 'Chive001', -48), ('unending-wrap-exclusion', 'Chive004', 48)]:
                changed = copy.deepcopy(info)
                word = next(w for w in changed['words'] if w['text'] == label)
                for axis in (0, 2): word['rect'][axis] += shift
                check(name, changed, html)
        if case['id'].endswith('multiple'):
            changed, pictures = copy.deepcopy(info), copy.deepcopy(html)
            changed['colorRegions'][0]['coverage'] /= 2
            pictures.pop(1)
            check('one-of-two-same-page-pictures-lost', changed, pictures)
            changed = copy.deepcopy(info)
            changed['pictureFrames'][0]['coverage'] *= .75
            changed['pictureOutsideCoverage'][0]['coverage'] = 1024
            check('same-union-wrong-picture-footprint', changed, html, primary=False)
    return records


if __name__ == '__main__':
    records = verify()
    (out / 'mutations.json').write_text(json.dumps(records, indent=2) + '\n')
    print(f'Rejected {len(records)} observation mutations')
