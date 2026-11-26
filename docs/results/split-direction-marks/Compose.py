"""Label each #1862 case's 96-DPI page rasters and bind the focused public-API evidence.

Usage: python3 docs/results/split-direction-marks/Compose.py RUN

RUN holds manifest.json, reference/bundle.json (`bench reference libreoffice --manifest`),
capture-main/ and capture-fix/ (export-reliability Capture.mjs then Inspect.py) and each
build's identity record copied as main-docx-bench-build.json and fix-docx-bench-build.json.
Every page keeps its original pixels; a case's pages are cropped to one rectangle, the
union of every renderer's ink plus a margin, and the whole page outside it is checked blank.
"""
import json
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from bench.common import digest, identity

run = Path(sys.argv[1]).resolve()
out = Path(__file__).resolve().parent
manifest = json.loads((run / 'manifest.json').read_text())
reference = json.loads((run / 'reference/bundle.json').read_text())
captures = {name: json.loads((run / f'capture-{name}' / 'inspected.json').read_text()) for name in ('main', 'fix')}
expected = {case['id'] for case in manifest['cases']}
assert reference['suiteDigest'] == identity(manifest) and set(reference['cases']) == expected
builds = {}
for name, capture in captures.items():
    assert {case['id'] for case in capture['cases']} == expected
    assert capture['inspectionManifestSha256'] == digest(run / 'manifest.json')
    record = run / f'{name}-docx-bench-build.json'
    builds[name] = json.loads(record.read_text())
    assert digest(record) == capture['buildIdentitySha256']
    assert builds[name]['commit'] == capture['candidate'] and builds[name]['tree'] == capture['sourceTree']

font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
bold = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 16)
INK, MARGIN, GAP = 231, 24, 16


def ink_box(image):
    mask = image.convert('RGB').point(lambda v: 255 if v < INK else 0).convert('L')
    return mask.getbbox()


evidence = {'scope': 'Focused unscored public-API diagnostics; no candidate score, Word parity or full-suite result',
            'manifestSha256': digest(run / 'manifest.json'), 'referenceBundleSha256': digest(run / 'reference/bundle.json'),
            'referenceRenderer': next(iter(reference['cases'].values()))['renderer'],
            'referenceEnvironment': reference['environment'], 'builds': builds, 'captures': captures, 'cases': []}
for case in manifest['cases']:
    cid = case['id']
    ref = reference['cases'][cid]
    assert ref['inputSha256'] == case['sha256'] and ref['eligible']
    panels = []
    for name in ('reference', 'main', 'fix'):
        if name == 'reference':
            folder, pdf, failures = run / 'reference' / cid, run / 'reference' / ref['pdf'], ref['ineligibleChecks']
            words = ref['inspection']['words']
            title = ref['renderer']['version'].split(' ')[0] + ' ' + ref['renderer']['version'].split(' ')[1] + ' reference'
        else:
            record = next(c for c in captures[name]['cases'] if c['id'] == cid)
            assert record['inputSha256'] == case['sha256'] and record['status'] == 'delivered'
            folder = run / f'capture-{name}' / cid
            pdf, failures = folder / 'candidate.pdf', record['mandatoryPdfFailures']
            assert digest(pdf) == record['pdfSha256']
            words = json.loads((folder / 'inspection.json').read_text())['words']
            title = f'Docxodus {name} {captures[name]["candidate"][:8]}'
        for old in folder.glob('sheet-page-*.png'):
            old.unlink()
        subprocess.run(['pdftoppm', '-r', '96', '-png', str(pdf), str(folder / 'sheet-page')], check=True, capture_output=True)
        pages = sorted(folder.glob('sheet-page-*.png'), key=lambda p: int(p.stem.split('-')[-1]))
        panels.append((title, failures, pdf, pages, [w['text'] for w in words if w['text']]))
    boxes = [ink_box(Image.open(p)) for *_, pages, _ in panels for p in pages]
    boxes = [b for b in boxes if b]
    size = Image.open(panels[0][3][0]).size
    crop = (max(0, min(b[0] for b in boxes) - MARGIN), max(0, min(b[1] for b in boxes) - MARGIN),
            min(size[0], max(b[2] for b in boxes) + MARGIN), min(size[1], max(b[3] for b in boxes) + MARGIN))
    columns = max(len(pages) for *_, pages, _ in panels)
    cell_w, cell_h = crop[2] - crop[0], crop[3] - crop[1]
    row_h = 90 + cell_h + 22
    sheet = Image.new('RGB', (max(24 + columns * (cell_w + GAP), 760), 64 + len(panels) * row_h), '#e9eef3')
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 10), cid, font=bold, fill='#16283b')
    draw.text((12, 34), f'Pages at 96 DPI, cropped to x {crop[0]}-{crop[2]}, y {crop[1]}-{crop[3]} px; '
              'every page is blank outside the crop.', font=font, fill='#33475b')
    y = 64
    for title, failures, pdf, pages, texts in panels:
        verdict = 'PASS' if not failures else 'FAIL: ' + ', '.join(failures)
        draw.text((12, y), title, font=bold, fill='#16283b')
        draw.text((12, y + 22), 'PDF checks: ' + verdict, font=font, fill='#21623c' if not failures else '#8b2a15')
        draw.text((12, y + 42), 'Extracted words: ' + ' | '.join(texts), font=font, fill='#33475b')
        for index, path in enumerate(pages):
            page = Image.open(path).convert('RGB')
            assert page.size == size, 'pages must share one size to share a crop'
            outside = page.copy()
            outside.paste('white', crop)
            assert ink_box(outside) is None, f'ink outside the crop: {path}'
            x = 12 + index * (cell_w + GAP)
            draw.text((x, y + 64), f'Page {index + 1}', font=font, fill='#33475b')
            sheet.paste(page.crop(crop), (x, y + 84))
        y += row_h
    target = out / (cid + '.png')
    sheet.save(target, optimize=True)
    evidence['cases'].append({'id': cid, 'inputSha256': case['sha256'], 'screenshot': target.name,
        'screenshotSha256': digest(target), 'cropPx': list(crop),
        'panels': [{'renderer': title, 'pdfSha256': digest(pdf), 'failures': failures, 'words': texts,
                    'pageRasterSha256': [digest(p) for p in pages]} for title, failures, pdf, pages, texts in panels]})
evidence['tools'] = {name: digest(root / name) for name in ['docs/results/export-reliability/Capture.mjs',
    'docs/results/export-reliability/Inspect.py', 'docs/results/split-direction-marks/Compose.py']}
(out / 'evidence.json').write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + '\n')
print('\n'.join(f"{c['id']}: " + ', '.join(f"{p['renderer']} {'pass' if not p['failures'] else 'fail'}" for p in c['panels'])
                for c in evidence['cases']))
