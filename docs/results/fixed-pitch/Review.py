"""Retain unscored before/after PDFs and verify authored fixed-pitch bounds."""
import gzip
import json
import shutil
import sys
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from bench.common import digest
from bench.pdf import inspect_companion_pdf
from Measurements import failures as measurement_failures

run = Path(sys.argv[1]).resolve()
out = Path(__file__).resolve().parent
manifest = json.loads((run / 'manifest.json').read_text())
assert len(manifest['cases']) == 4
captures = {role: json.loads((run / role / 'capture.json').read_text()) for role in ('baseline', 'candidate')}
builds = {role: json.loads((run / f'{role}-build.json').read_text()) for role in captures}
for role, capture in captures.items():
    assert capture['manifestSha256'] == digest(run / 'manifest.json')
    assert capture['buildIdentitySha256'] == digest(run / f'{role}-build.json')
    assert capture['candidate'] == builds[role]['commit']
    assert capture['sourceTree'] == builds[role]['tree']
    assert capture['fontPolicy'] == 'strict' and capture['sandbox'] is True
    assert {c['id'] for c in capture['cases']} == {c['id'] for c in manifest['cases']}
evidence = dict(scope='Unscored public-export diagnostic. The baseline is unpublished development '
    'commit 7d1026ed, not released main. These independent labels exercise the bounded fixed-pitch '
    'inference from the issue author confirmation of the original Docxodus #1564 line. '
    'No Word captures of these inputs or new fidelity score are claimed.', builds=builds, captures=captures,
    manifestSha256=digest(run / 'manifest.json'), cases=[])
(out / 'manifest.json.gz').write_bytes(gzip.compress((run / 'manifest.json').read_bytes(), mtime=0))
(out / 'pdf').mkdir(exist_ok=True)
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 15)
for case in manifest['cases']:
    cid = case['id']
    assert digest(ROOT / case['input']) == case['sha256']
    entry = dict(id=cid, inputSha256=case['sha256'], renderers={})
    panels, infos = [], {}
    for role in captures:
        record = next(c for c in captures[role]['cases'] if c['id'] == cid)
        folder = run / role / cid
        pdf = folder / 'candidate.pdf'
        assert record['inputSha256'] == case['sha256']
        assert record['status'] == 'delivered' and digest(pdf) == record['pdfSha256']
        assert digest(folder / 'production.json') == record['renderReportSha256']
        assert digest(folder / 'candidate.html') == record['htmlSha256']
        production = json.loads((folder / 'production.json').read_text())
        assert production['source']['rawPackageBytesDigest'] == case['sha256']
        assert production['status'] == 'complete' and production['options']['policy']['strictFonts'] is True
        assert production['options']['reviewProfile'] == case['profile']['review']
        assert production['options']['commentProfile'] == case['profile']['comments']
        info = inspect_companion_pdf(pdf, case['pdfCompanion'])
        infos[role] = info
        failures = measurement_failures(case, info)
        if role == 'candidate':
            assert not failures, (cid, failures)
        target = out / 'pdf' / f'{cid}-{role}.pdf'
        shutil.copy2(pdf, target)
        payload = dict(inspection=info, failures=failures,
            production=production)
        compressed = out / f'{cid}-{role}.json.gz'
        compressed.write_bytes(gzip.compress((json.dumps(payload, indent=2) + '\n').encode(), mtime=0))
        entry['renderers'][role] = dict(pdf=str(target.relative_to(out)), sha256=digest(target),
            facts=compressed.name, factsSha256=digest(compressed), failures=failures)
        document = fitz.open(pdf)
        panel = Image.new('RGB', (1080, 210), 'white')
        draw = ImageDraw.Draw(panel)
        draw.text((12, 8), role.upper(), fill='black', font=font)
        for number, page in enumerate(document):
            # Show all text on the sole page at twice its printed size.
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=fitz.Rect(50, 55, 570, 130))
            image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            panel.paste(image, (20, 45))
            draw.text((1000, 8), f'p{number + 1}', fill='black', font=font)
        panels.append(panel)
    if cid.endswith('narrow-control') or cid.endswith('modern-exact'):
        assert not entry['renderers']['baseline']['failures']
        before, after = infos['baseline']['words'], infos['candidate']['words']
        assert [(w['text'], w['page']) for w in before] == [(w['text'], w['page']) for w in after]
        delta = max(abs(x - y) for a, b in zip(before, after) for x, y in zip(a['rect'], b['rect']))
        assert delta <= .76
        entry['controlMaxCoordinateDeltaPt'] = delta
    else:
        assert entry['renderers']['baseline']['failures'], cid
    sheet = Image.new('RGB', (1080, sum(p.height for p in panels) + 35), '#dddddd')
    ImageDraw.Draw(sheet).text((12, 8), cid, fill='black', font=font)
    for i, panel in enumerate(panels):
        sheet.paste(panel, (0, 35 + i * 210))
    sheet.save(out / f'{cid}.png')
    entry['screenshot'] = f'{cid}.png'
    evidence['cases'].append(entry)
    print(cid, 'baseline failures', len(entry['renderers']['baseline']['failures']), 'candidate PASS')
(out / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
