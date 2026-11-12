"""Retain unscored before/after PDFs and verify authored mixed-line bounds."""
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
from bench.pdf import inspect_case_pdf, reference_failures
from Measurements import failures as measurement_failures

run = Path(sys.argv[1]).resolve()
out = Path(__file__).resolve().parent
manifest = json.loads((run / 'manifest.json').read_text())
assert len(manifest['cases']) == 6
captures = {role: json.loads((run / role / 'capture.json').read_text()) for role in ('baseline', 'candidate')}
builds = {role: json.loads((run / f'{role}-build.json').read_text()) for role in captures}
for role, capture in captures.items():
    assert capture['manifestSha256'] == digest(run / 'manifest.json')
    assert capture['buildIdentitySha256'] == digest(run / f'{role}-build.json')
    assert capture['candidate'] == builds[role]['commit']
    assert capture['sourceTree'] == builds[role]['tree']
    assert capture['fontPolicy'] == 'strict' and capture['sandbox'] is True
    assert {c['id'] for c in capture['cases']} == {c['id'] for c in manifest['cases']}
evidence = dict(scope='Unscored public-export diagnostic. Baseline is the previous unpublished development build, '
    'not released main. Authored line/ink bounds follow independent Liberation Serif metrics and the Word '
    'minimum-baseline observation documented in Docxodus TestFiles/LineSpacingWord. No Word capture of '
    'these benchmark inputs or new fidelity score is claimed.', builds=builds, captures=captures,
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
        assert record['status'] == 'delivered' and digest(pdf) == record['pdfSha256']
        assert digest(folder / 'production.json') == record['renderReportSha256']
        assert digest(folder / 'candidate.html') == record['htmlSha256']
        info = inspect_case_pdf(pdf, case)
        infos[role] = info
        failures = reference_failures(case, info) + measurement_failures(case, info)
        if role == 'candidate':
            assert not failures, (cid, failures)
        target = out / 'pdf' / f'{cid}-{role}.pdf'
        shutil.copy2(pdf, target)
        payload = dict(inspection=info, failures=failures,
            production=json.loads((folder / 'production.json').read_text()))
        compressed = out / f'{cid}-{role}.json.gz'
        compressed.write_bytes(gzip.compress((json.dumps(payload, indent=2) + '\n').encode(), mtime=0))
        entry['renderers'][role] = dict(pdf=str(target.relative_to(out)), sha256=digest(target),
            facts=compressed.name, factsSha256=digest(compressed), failures=failures)
        document = fitz.open(pdf)
        panel = Image.new('RGB', (330, 45 + 720 * len(document)), 'white')
        draw = ImageDraw.Draw(panel)
        draw.text((12, 8), role.upper(), fill='black', font=font)
        for number, page in enumerate(document):
            # Show the complete narrow text column and full page height on every page.
            pix = page.get_pixmap(matrix=fitz.Matrix(1, 1), clip=fitz.Rect(30, 40, 300, 760))
            image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            panel.paste(image, (20, 45 + number * 720))
            draw.text((230, 50 + number * 720), f'p{number + 1}', fill='black', font=font)
        panels.append(panel)
    if cid.endswith('natural-control'):
        assert not entry['renderers']['baseline']['failures']
        before, after = infos['baseline']['words'], infos['candidate']['words']
        assert [(w['text'], w['page']) for w in before] == [(w['text'], w['page']) for w in after]
        delta = max(abs(x - y) for a, b in zip(before, after) for x, y in zip(a['rect'], b['rect']))
        assert delta <= .76
        entry['naturalControlMaxCoordinateDeltaPt'] = delta
    else:
        assert entry['renderers']['baseline']['failures'], cid
    sheet = Image.new('RGB', (660, max(p.height for p in panels) + 35), '#dddddd')
    ImageDraw.Draw(sheet).text((12, 8), cid, fill='black', font=font)
    for i, panel in enumerate(panels):
        sheet.paste(panel, (i * 330, 35))
    sheet.save(out / f'{cid}.png')
    entry['screenshot'] = f'{cid}.png'
    evidence['cases'].append(entry)
    print(cid, 'baseline failures', len(entry['renderers']['baseline']['failures']), 'candidate PASS')
(out / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
