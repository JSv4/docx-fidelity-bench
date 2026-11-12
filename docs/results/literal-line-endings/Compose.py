"""Compose unchanged full-page rasters and bind the focused public-API evidence."""
import json
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from bench.common import digest, identity

run = Path(sys.argv[1]).resolve()
manifest = json.loads((run / 'manifest.json').read_text())
reference = json.loads((run / 'reference-final-v5/bundle.json').read_text())
captures = {name: json.loads((run / name / 'inspected.json').read_text()) for name in ('baseline-v5', 'candidate-v5')}
expected = {case['id'] for case in manifest['cases']}
assert reference['suiteDigest'] == identity(manifest)
assert set(reference['cases']) == expected
for capture in captures.values():
    assert {case['id'] for case in capture['cases']} == expected
    assert capture['inspectionManifestSha256'] == digest(run / 'manifest.json')
out = Path(__file__).resolve().parent
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
heading = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 17)
evidence = {'scope': 'Focused unscored public-API diagnostics; no Word parity or full-suite score',
            'manifestSha256': digest(run / 'manifest.json'), 'referenceBundleSha256': digest(run / 'reference-final-v5/bundle.json'),
            'referenceEnvironment': reference['environment'], 'captures': captures,
            'schema': json.loads((run / 'schema.json').read_text()), 'cases': []}
evidence['strictCaptures'] = {name: json.loads((run / name / 'capture.json').read_text()) for name in ('baseline-strict-v5', 'candidate-strict-v5')}
evidence['builds'] = {name: {'identity': json.loads((run / f'{name}-docx-bench-build.json').read_text()),
                           'rendererAssets': json.loads((run / f'{name}-export-assets.json').read_text())}
                      for name in captures}
for name, capture in captures.items():
    build = evidence['builds'][name]['identity']
    assert build['commit'] == capture['candidate'] and build['tree'] == capture['sourceTree']
    assert digest(run / f'{name}-docx-bench-build.json') == capture['buildIdentitySha256']
    strict = evidence['strictCaptures'][name.replace('-v5', '-strict-v5')]
    assert strict['fontPolicy'] == 'strict'
    assert strict['manifestSha256'] == digest(run / 'manifest.json')
    assert {case['id'] for case in strict['cases']} == expected
    for key in ('candidate', 'sourceTree', 'buildIdentitySha256', 'executableSha256', 'fontContract'):
        assert strict[key] == capture[key]
    assert {case['id']: case['inputSha256'] for case in strict['cases']} == {
        case['id']: case['sha256'] for case in manifest['cases']}
for case in manifest['cases']:
    cid = case['id']
    ref = reference['cases'][cid]
    assert ref['inputSha256'] == case['sha256']
    panels = []
    for name in ('baseline-v5', 'reference-final-v5', 'candidate-v5'):
        folder = run / name / cid
        if name == 'reference-final-v5':
            pdf = run / name / ref['pdf']
            failures = ref['ineligibleChecks']
            title = 'LibreOffice reference'
        else:
            record = next(c for c in captures[name]['cases'] if c['id'] == cid)
            assert record['inputSha256'] == case['sha256'] and record['status'] == 'delivered'
            pdf = folder / 'candidate.pdf'
            assert digest(pdf) == record['pdfSha256']
            failures = record['mandatoryPdfFailures']
            title = name.split('-')[0].title() + ' ' + captures[name]['candidate'][:8] + ' (permissive)'
            assert captures[name]['fontPolicy'] == 'permissive-diagnostic'
            report = folder / 'production.json'
            assert digest(report) == record['renderReportSha256']
            record['renderReport'] = json.loads(report.read_text())
        subprocess.run(['pdftoppm', '-r', '96', '-png', str(pdf), str(folder / 'page')], check=True, capture_output=True)
        images = sorted(folder.glob('page-*.png'), key=lambda p: int(p.stem.split('-')[-1]))
        panels.append((title, failures, pdf, images))
    width = max(Image.open(p).width for _, _, _, images in panels for p in images) + 24
    height = max(sum(Image.open(p).height + 24 for p in images) for _, _, _, images in panels) + 130
    sheet = Image.new('RGB', (width * 3 + 20, height), '#e9eef3')
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 10), cid, font=heading, fill='#16283b')
    draw.text((12, 36), 'Full pages at 96 DPI. Permissive previews; strict outcomes recorded separately. No fidelity score.', font=font, fill='#33475b')
    for index, (title, failures, _, images) in enumerate(panels):
        x, y = 12 + index * width, 115
        draw.text((x, 65), title, font=heading, fill='#16283b')
        draw.text((x, 90), 'PDF checks: ' + ('PASS' if not failures else 'FAIL — line placement'), font=font,
                  fill='#21623c' if not failures else '#8b4a15')
        for number, path in enumerate(images, 1):
            draw.text((x, y), f'Page {number}', font=font, fill='#33475b')
            page = Image.open(path).convert('RGB')
            sheet.paste(page, (x, y + 20))
            y += page.height + 24
    target = out / (cid + '.png')
    sheet.save(target, optimize=True)
    evidence['cases'].append({'id': cid, 'inputSha256': case['sha256'], 'screenshot': target.name,
        'screenshotSha256': digest(target), 'panels': [{'renderer': title, 'pdfSha256': digest(pdf),
        'failures': failures, 'pageRasterSha256': [digest(p) for p in images]} for title, failures, pdf, images in panels]})
evidence['tools'] = {name: digest(root / name) for name in ['docs/results/export-reliability/Capture.mjs',
    'docs/results/export-reliability/Inspect.py', 'docs/results/literal-line-endings/Compose.py']}
(out / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
print('Composed', len(evidence['cases']), 'case sheets')
