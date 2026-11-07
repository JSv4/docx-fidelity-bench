"""Bind independent VML line fixtures to native/public renders and existing measurement contracts."""
import gzip
import hashlib
import json
import math
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from bench.common import digest, identity
from bench.pdf import correctness, inspect_case_pdf, reference_failures

run = Path(sys.argv[1]).resolve()
out = Path(__file__).resolve().parent
manifest = json.loads((run / 'manifest.json').read_text())
reference = json.loads((run / 'reference/bundle.json').read_text())
captures = {name: json.loads((run / name / 'capture.json').read_text()) for name in ('baseline', 'candidate')}
expected = {c['id'] for c in manifest['cases']}
assert reference['suiteDigest'] == identity(manifest) and set(reference['cases']) == expected
builds = {name: json.loads((run / f'{name}-build.json').read_text()) for name in captures}
assets = {name: json.loads((run / f'{name}-export-assets.json').read_text()) for name in captures}
sources = dict(zip(('baseline', 'candidate'), (Path(p).resolve() for p in sys.argv[2:4])))
assert set(sources) == set(captures), 'Supply exact baseline and candidate source directories'
for name, capture in captures.items():
    assert capture['fontPolicy'] == 'strict'
    assert capture['manifestSha256'] == digest(run / 'manifest.json')
    assert {c['id'] for c in capture['cases']} == expected
    assert capture['candidate'] == builds[name]['commit'] and capture['sourceTree'] == builds[name]['tree']
    assert capture['buildIdentitySha256'] == digest(run / f'{name}-build.json')
    assert digest(run / f'{name}-export-assets.json') == builds[name]['files']['npm/dist/export-assets.json']
    source = sources[name]
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip() == builds[name]['commit']
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=source, text=True).strip() == builds[name]['tree']
    assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=source, text=True)
    for path, expected_hash in builds[name]['files'].items():
        assert digest(source / path) == expected_hash, (name, path)
    for asset in assets[name]['assets']:
        path = source / 'npm/dist' / asset['path']
        assert digest(path) == asset['sha256'] and path.stat().st_size == asset['byteLength'], (name, asset['path'])
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
heading = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 16)


def retain(name, data):
    payload = data if isinstance(data, bytes) else (json.dumps(data, indent=2) + '\n').encode()
    target = out / (name + '.json.gz')
    target.write_bytes(gzip.compress(payload, mtime=0))
    return {'file': target.name, 'sha256': digest(target), 'jsonSha256': hashlib.sha256(payload).hexdigest()}


evidence = {'scope': 'Unscored strict-font public export diagnostics; no Word or full-suite parity claim',
            'manifestSha256': digest(run / 'manifest.json'), 'builds': builds, 'rendererAssets': assets, 'captures': captures,
            'referenceBundleSha256': digest(run / 'reference/bundle.json'),
            'referenceBundle': retain('reference-bundle', (run / 'reference/bundle.json').read_bytes()),
            'referenceEnvironment': reference['environment'], 'schema': json.loads((run / 'schema.json').read_text()),
            'cases': []}
for case in manifest['cases']:
    cid = case['id']
    pages_expected = 1
    entry = {'id': cid, 'inputSha256': case['sha256'], 'panels': []}
    panel_data = []
    for name in ('baseline', 'reference', 'candidate'):
        panel = {'renderer': name}
        entry['panels'].append(panel)
        folder = run / name / cid
        title = 'LibreOffice 25.8.7.3' if name == 'reference' else name.title() + ' ' + captures[name]['candidate'][:8]
        if name == 'reference':
            ref = reference['cases'][cid]
            assert ref['inputSha256'] == case['sha256'] and ref['eligible']
            panel['referenceEligible'] = ref['eligible']
            pdf = run / name / ref['pdf']
            assert digest(pdf) == ref['pdfSha256']
        else:
            record = next(c for c in captures[name]['cases'] if c['id'] == cid)
            assert record['inputSha256'] == case['sha256']
            assert record['status'] == 'delivered'
            pdf = folder / 'candidate.pdf'
            assert digest(pdf) == record['pdfSha256']
            raw = (folder / 'production.json').read_bytes()
            assert digest(folder / 'production.json') == record['renderReportSha256']
            report = json.loads(raw)
            assert report['status'] == 'complete'
            assert report['source']['rawPackageBytesDigest'] == case['sha256']
            assert report['bindings']['pdfDigest'] == digest(pdf)
            assert report['options']['policy']['strictFonts'] is True
            assert report['fonts'] and all(f['verified'] for f in report['fonts'])
            assert report['environment']['verification'] == 'browserObserved'
            assert report['environment']['observed']['browserBuild'] == captures[name]['browserVersion']
            warnings = report['warnings']
            expected_warning = name == 'baseline' and not cid.endswith('text-control')
            assert [w['code'] for w in warnings] == (['unsupported_content_placeholder'] if expected_warning else [])
            assert len(report['unsupportedContent']) == int(expected_warning)
            panel['warnings'] = warnings
            panel['report'] = retain(cid + '-' + name + '-report', raw)
        info = inspect_case_pdf(pdf, case)
        reference_info = reference['cases'][cid]['inspection']
        failures = [c['name'] for c in correctness(case, reference_info, info) if not c['passed']]
        if name == 'reference':
            assert not reference_failures(case, info, 'libreoffice')
        control = cid.endswith('text-control')
        assert bool(failures) == (name == 'baseline' and not control), (cid, name, failures)
        panel['mandatoryFailures'] = failures
        expected_tokens = Counter(case['tokens'])
        if name == 'baseline' and not control:
            expected_tokens['[SHAPE]'] = 1
        assert Counter(w['text'] for w in info['words']) == expected_tokens, (cid, name, info['tokens'])
        assert len(info['geometry']) == pages_expected
        for geometry in info['geometry']:
            assert geometry['media'] == [0, 0, 612, 792]
        labels = info['words']
        for word in labels:
            left, top, right, bottom = word['rect']
            assert all(math.isfinite(v) for v in word['rect'])
            assert 0 <= left < right <= 612.1 and 0 <= top < bottom <= 792.1, (cid, name, word)
        if cid.endswith(('hidden-stroke', 'text-control')):
            # The existing geometry metric requires positive ink, so absence is supplementary.
            diagnostic_case = dict(case, assertions=case['assertions'] + [dict(
                type='color-reference-geometry', version=1, page=1, rgb=[38, 124, 113],
                tolerancePt=1.5, coverageTolerance=.08)])
            absent = inspect_case_pdf(pdf, diagnostic_case)['colorRegions']
            assert len(absent) == 1 and absent[0]['boundsPt'] is None and absent[0]['coverage'] == 0
            panel['supplementaryAbsentPaint'] = absent[0]
        panel.update(pdfSha256=digest(pdf), pages=pages_expected, checkedLabels=len(labels),
                     inspection=retain(cid + '-' + name + '-inspection', info))
        subprocess.run(['pdftoppm', '-r', '96', '-png', str(pdf), str(folder / 'page')], check=True, capture_output=True)
        pages = sorted(folder.glob('page-*.png'), key=lambda p: int(p.stem.split('-')[-1]))
        assert len(pages) == pages_expected
        panel['pageRasterSha256'] = [digest(p) for p in pages]
        panel_data.append((title, panel, pages))
    width = max(Image.open(p).width for _, _, pages in panel_data for p in pages) + 24
    height = max(sum(Image.open(p).height + 26 for p in pages) for _, _, pages in panel_data) + 144
    sheet = Image.new('RGB', (width * 3 + 12, height), '#e9eef3')
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 12), cid, font=heading, fill='#16283b')
    draw.text((12, 40), 'Full pages at original 96 DPI. Text positions, color bounds/coverage and physical pen widths checked. No fidelity score.', font=font, fill='#33475b')
    for index, (title, panel, pages) in enumerate(panel_data):
        x, y = 12 + index * width, 144
        draw.text((x, 72), title, font=heading, fill='#16283b')
        status = 'FAIL: geometry or text' if panel['mandatoryFailures'] else 'PASS'
        draw.text((x, 100), status + f': {panel["checkedLabels"]} labels, {len(pages)} pages',
                  font=font, fill='#8b4a15' if panel['mandatoryFailures'] else '#21623c')
        for page_number, path in enumerate(pages, 1):
            draw.text((x, y - 20), f'Page {page_number}', font=font, fill='#33475b')
            page = Image.open(path).convert('RGB')
            sheet.paste(page, (x, y))
            y += page.height + 26
    target = out / (cid + '.png')
    sheet.save(target, optimize=True)
    entry['screenshot'] = {'file': target.name, 'sha256': digest(target)}
    evidence['cases'].append(entry)
evidence['tools'] = {str(p.relative_to(root)): digest(p) for p in
                     [Path(__file__), root / 'docs/results/export-reliability/Capture.mjs']}
(out / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
print('Verified nine VML line cases and composed all-page comparison sheets')
