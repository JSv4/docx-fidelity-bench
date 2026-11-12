"""Verify every ledger label, retain complete diagnostics, and compose labeled previews."""
import gzip
import json
import math
import subprocess
import sys
from collections import Counter
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from bench.common import digest, identity
from bench.pdf import inspect_case_pdf, reference_failures

run = Path(sys.argv[1]).resolve()
out = Path(__file__).resolve().parent
manifest = json.loads((run / 'manifest.json').read_text())
reference = json.loads((run / 'reference-final/bundle.json').read_text())
captures = {name: json.loads((run / name / 'capture.json').read_text())
            for name in ('baseline-final', 'candidate')}
expected = {c['id'] for c in manifest['cases']}
assert reference['suiteDigest'] == identity(manifest)
assert set(reference['cases']) == expected
builds = {name: json.loads((run / f'{name}-build.json').read_text()) for name in captures}
assets = {name: json.loads((run / f'{name}-export-assets.json').read_text()) for name in captures}
for name, capture in captures.items():
    assert capture['fontPolicy'] == 'strict'
    assert capture['manifestSha256'] == digest(run / 'manifest.json')
    assert {c['id'] for c in capture['cases']} == expected
    assert capture['candidate'] == builds[name]['commit']
    assert capture['sourceTree'] == builds[name]['tree']
    assert capture['buildIdentitySha256'] == digest(run / f'{name}-build.json')
    assert digest(run / f'{name}-export-assets.json') == builds[name]['files']['npm/dist/export-assets.json']
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 16)
heading = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 18)
evidence = {'scope': 'Unscored strict-font public export diagnostics; no Word or full-suite parity claim',
            'manifestSha256': digest(run / 'manifest.json'), 'builds': builds, 'rendererAssets': assets, 'captures': captures,
            'referenceBundleSha256': digest(run / 'reference-final/bundle.json'),
            'referenceEnvironment': reference['environment'], 'schema': json.loads((run / 'schema.json').read_text()),
            'cases': []}


def retain(name, data):
    payload = data if isinstance(data, bytes) else (json.dumps(data, indent=2) + '\n').encode()
    target = out / (name + '.json.gz')
    target.write_bytes(gzip.compress(payload, mtime=0))
    import hashlib
    return {'file': target.name, 'sha256': digest(target), 'jsonSha256': hashlib.sha256(payload).hexdigest()}


evidence['referenceBundle'] = retain('reference-bundle', (run / 'reference-final/bundle.json').read_bytes())
for case in manifest['cases']:
    cid = case['id']
    count = sum(case['tokens'].values())
    entry = {'id': cid, 'inputSha256': case['sha256'], 'labels': count, 'panels': []}
    sheet = Image.new('RGB', (2550, 2290), '#e9eef3')
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 12), cid, font=heading, fill='#16283b')
    draw.text((12, 40), 'First and last full pages at 96 DPI; every label checked on every page. Strict fonts. No fidelity score.', font=font, fill='#33475b')
    for col, name in enumerate(('baseline-final', 'reference-final', 'candidate')):
        x = col * 850 + 12
        folder = run / name / cid
        panel = {'renderer': name}
        entry['panels'].append(panel)
        if name == 'reference-final':
            ref = reference['cases'][cid]
            assert ref['inputSha256'] == case['sha256'] and ref['eligible']
            pdf = run / name / ref['pdf']
            assert digest(pdf) == ref['pdfSha256']
            title = 'LibreOffice reference'
        else:
            capture = captures[name]
            record = next(c for c in capture['cases'] if c['id'] == cid)
            assert record['inputSha256'] == case['sha256']
            title = ('Baseline ' if name == 'baseline-final' else 'Candidate ') + capture['candidate'][:8]
            if record['status'] == 'failed':
                assert name == 'baseline-final' and count == 6000
                assert record['code'] == 'resource_limit' and 'Font observations' in record['message']
                panel['failure'] = record
                draw.text((x, 72), title, font=heading, fill='#16283b')
                draw.text((x, 108), 'NO PDF: font-observation diagnostic limit', font=font, fill='#8b4a15')
                continue
            assert record['status'] == 'delivered'
            pdf = folder / 'candidate.pdf'
            assert digest(pdf) == record['pdfSha256']
            raw_report = (folder / 'production.json').read_bytes()
            assert digest(folder / 'production.json') == record['renderReportSha256']
            report = json.loads(raw_report)
            observation = report['fontObservation']
            summaries = [w for w in report['warnings'] if w['code'] == 'font_observation_limit']
            assert report['options']['policy']['limits']['renderDiagnostics'] == 10000
            assert all(f['verified'] for f in report['fonts'])
            if count == 6000:
                assert observation == {'status': 'unavailable', 'reason': 'diagnostic_limit'}
                assert len(summaries) == 1 and len(report['warnings']) == 1
            else:
                assert observation['status'] == 'observed' and len(observation['uses']) == count
                assert not report['warnings']
            panel['report'] = retain(cid + '-' + name + '-report', raw_report)
            panel['observation'] = {k: v for k, v in observation.items() if k != 'uses'}
            panel['observation']['useCount'] = len(observation.get('uses', []))
            panel['warnings'] = report['warnings']
        info = inspect_case_pdf(pdf, case)
        failures = reference_failures(case, info, 'libreoffice')
        assert not failures, (cid, name, failures)
        assert Counter(w['text'] for w in info['words']) == Counter(case['tokens'])
        assert len(info['geometry']) == math.ceil(count / 54)
        for word in info['words']:
            index = int(word['text'].removeprefix('SpruceEntry')) - 1
            assert word['page'] == index // 54 + 1
            left, top, right, bottom = word['rect']
            assert all(math.isfinite(v) for v in word['rect'])
            assert 0 <= left < right <= 612 and 0 <= top < bottom <= 792
        panel.update(pdfSha256=digest(pdf), pages=len(info['geometry']), labelsWithinPages=count,
                     inspection=retain(cid + '-' + name + '-inspection', info))
        subprocess.run(['pdftoppm', '-r', '96', '-png', str(pdf), str(folder / 'page')], check=True, capture_output=True)
        pages = sorted(folder.glob('page-*.png'), key=lambda p: int(p.stem.split('-')[-1]))
        assert len(pages) == len(info['geometry'])
        panel['pageRasterSha256'] = [digest(p) for p in pages]
        draw.text((x, 72), title, font=heading, fill='#16283b')
        draw.text((x, 100), f'PASS: {count} labels, {len(pages)} pages, all bounds inside pages', font=font, fill='#21623c')
        for row, index in enumerate((0, len(pages) - 1)):
            y = 144 + row * 1080
            draw.text((x, y - 20), f'Page {index + 1}', font=font, fill='#33475b')
            sheet.paste(Image.open(pages[index]).convert('RGB'), (x, y))
        # All-page contact sheet exposes layout anomalies between the readable endpoint pages.
        contact = Image.new('RGB', (1440, math.ceil(len(pages) / 8) * 256 + 40), '#e9eef3')
        contact_draw = ImageDraw.Draw(contact)
        contact_draw.text((8, 8), cid + ' / ' + title + ' / all pages (thumbnails)', font=font, fill='#16283b')
        for i, path in enumerate(pages):
            page = Image.open(path).convert('RGB')
            page.thumbnail((172, 224))
            cx, cy = i % 8 * 180 + 4, i // 8 * 256 + 40
            contact_draw.text((cx, cy), str(i + 1), font=font, fill='#33475b')
            contact.paste(page, (cx, cy + 22))
        target = out / (cid + '-' + name + '-all-pages.png')
        contact.save(target, optimize=True)
        panel['contactSheet'] = {'file': target.name, 'sha256': digest(target)}
    target = out / (cid + '.png')
    sheet.save(target, optimize=True)
    entry['screenshot'] = {'file': target.name, 'sha256': digest(target)}
    evidence['cases'].append(entry)
evidence['tools'] = {str(p.relative_to(root)): digest(p) for p in
                     [Path(__file__), root / 'docs/results/export-reliability/Capture.mjs']}
(out / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
print('Verified every label and composed both ledger sheets')
