"""Render unchanged native redlines and compose complete pages for the focused comparison."""
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from zipfile import ZipFile
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from bench.common import digest, identity

run = Path(sys.argv[1]).resolve()
validator = Path(sys.argv[2]).resolve()
out = Path(__file__).resolve().parent
manifest = json.loads((root / 'fixtures/redline/manifest.json').read_text())
cases = [c for c in manifest['cases'] if c['id'].startswith(('redline-complete-rewrite-', 'redline-short-rewrite-'))]
reports = {label: json.loads((run / folder / 'result.json').read_text())
           for label, folder in [('Baseline', 'baseline'), ('Authored', 'authored'), ('Candidate', 'candidate')]}
folders = dict(Baseline='baseline', Authored='authored', Candidate='candidate')
for report in reports.values():
    assert report['contract']['suiteDigest'] == identity(manifest)
    assert {c['id'] for c in report['cases']} == {c['id'] for c in cases}
    assert all(c['status'] == 'measured' for c in report['cases'])
builds = {label: json.loads((run / f'{label.lower()}-build/redline-build.json').read_text())
          for label in ('Baseline', 'Candidate')}
for label, build in builds.items():
    assert build['commit'] == reports[label]['candidate']
evidence = dict(scope='Twelve focused cases; native LibreOffice markup previews, no Word parity or full-suite score',
                manifestSha256=digest(root / 'fixtures/redline/manifest.json'), builds=builds,
                metric=reports['Candidate']['contract']['metric'],
                environment=reports['Candidate']['contract']['environment'], cases=[])
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
heading = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 17)
packages = set()
for case in cases:
    cid = case['id']
    for source in [*case['inputs'], case['authored']]:
        assert digest(root / source['path']) == source['sha256']
    packages.update(root / record['path'] for record in [*case['inputs'], case['authored']])
    panels = []
    record = dict(id=cid, sources={r['path']: r['sha256'] for r in [*case['inputs'], case['authored']]}, panels=[])
    for label in ('Baseline', 'Authored', 'Candidate'):
        folder = run / folders[label] / cid
        source = folder / 'candidate-redline.docx'
        result = next(c for c in reports[label]['cases'] if c['id'] == cid)
        assert digest(source) == result['adapter']['outputSha256']
        packages.add(source)
        with tempfile.TemporaryDirectory(prefix='rewrite-preview-') as profile:
            completed = subprocess.run(['libreoffice', '-env:UserInstallation=' + Path(profile).as_uri(), '--headless',
                '--convert-to', 'pdf', '--outdir', str(folder), str(source)], capture_output=True, text=True, check=True)
        pdf = folder / 'candidate-redline.pdf'
        assert pdf.is_file(), completed.stdout + completed.stderr
        subprocess.run(['pdftoppm', '-r', '96', '-png', str(pdf), str(folder / 'page')], check=True, capture_output=True)
        images = sorted(folder.glob('page-*.png'), key=lambda p: int(p.stem.split('-')[-1]))
        text = subprocess.check_output(['pdftotext', '-layout', str(pdf), '-'], text=True)
        with ZipFile(source) as archive:
            document = ET.fromstring(archive.read('word/document.xml'))
        w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        original_text = ' '.join(e.text or '' for e in document.iter() if e.tag in {w + 't', w + 'delText'})
        tokens = lambda value: Counter(re.findall(r'[A-Za-z0-9]+', value))
        visible = tokens(text) == tokens(original_text)
        assert visible, (cid, label, tokens(original_text) - tokens(text), tokens(text) - tokens(original_text))
        panels.append((label, result['score'], images))
        record['panels'].append(dict(renderer=label, sourceSha256=digest(source), pdfSha256=digest(pdf),
            pageRasterSha256=[digest(p) for p in images], completeReviewTextInventory=visible,
            checks=result))
    width = max(Image.open(p).width for _, _, pages in panels for p in pages) + 24
    height = max(sum(Image.open(p).height + 24 for p in pages) for _, _, pages in panels) + 132
    sheet = Image.new('RGB', (width * 3 + 20, height), '#e9eef3')
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 10), cid, font=heading, fill='#16283b')
    draw.text((12, 36), 'Native redlines in LibreOffice; full pages at 96 DPI. No Word parity claim.', font=font, fill='#33475b')
    for index, (label, score, pages) in enumerate(panels):
        x, y = 12 + index * width, 112
        source = reports[label]['candidate']
        draw.text((x, 64), label + (' ' + source[:8] if label != 'Authored' else ' calibration'), font=heading, fill='#16283b')
        draw.text((x, 89), f'Mandatory case checks: {score:g}/100', font=font, fill='#21623c' if score == 100 else '#8b4a15')
        for number, page in enumerate(pages, 1):
            draw.text((x, y), f'Page {number}', font=font, fill='#33475b')
            image = Image.open(page).convert('RGB')
            sheet.paste(image, (x, y + 20))
            y += image.height + 24
    target = out / (cid + '.png')
    sheet.save(target, optimize=True)
    record.update(screenshot=target.name, screenshotSha256=digest(target))
    evidence['cases'].append(record)
validation = json.loads(subprocess.check_output(['dotnet', str(validator / 'bin/OoxmlValidator.dll'),
    *map(str, sorted(packages))], text=True))
assert all(not findings for findings in validation['documents'].values()), validation
evidence['validation'] = validation
evidence['composeSha256'] = digest(Path(__file__))
(out / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
print('Composed', len(cases), 'case sheets; validated', len(packages), 'packages')
