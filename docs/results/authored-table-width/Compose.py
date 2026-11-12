"""Bind original authored-table-width fixtures to full reports and unchanged full-page review rasters."""
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
from bench.pdf import inspect_case_pdf, reference_failures

run = Path(sys.argv[1]).resolve()
out = Path(__file__).resolve().parent
manifest = json.loads((run / 'manifest.json').read_text())
reference = json.loads((run / 'reference/bundle.json').read_text())
captures = {name: json.loads((run / name / 'capture.json').read_text()) for name in ('baseline', 'candidate')}
expected = {c['id'] for c in manifest['cases']}
assert reference['suiteDigest'] == identity(manifest) and set(reference['cases']) == expected
builds = {name: json.loads((run / f'{name}-build.json').read_text()) for name in captures}
assets = {name: json.loads((run / f'{name}-export-assets.json').read_text()) for name in captures}
for name, capture in captures.items():
    assert capture['fontPolicy'] == 'strict'
    assert capture['manifestSha256'] == digest(run / 'manifest.json')
    assert {c['id'] for c in capture['cases']} == expected
    assert capture['candidate'] == builds[name]['commit'] and capture['sourceTree'] == builds[name]['tree']
    assert capture['buildIdentitySha256'] == digest(run / f'{name}-build.json')
    assert digest(run / f'{name}-export-assets.json') == builds[name]['files']['npm/dist/export-assets.json']
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
    pages_expected = 2 if cid.endswith('center-continuation') else 1
    clipped = cid.endswith('text-clipping')
    entry = {'id': cid, 'inputSha256': case['sha256'], 'panels': []}
    panel_data = []
    for name in ('baseline', 'reference', 'candidate'):
        panel = {'renderer': name}
        entry['panels'].append(panel)
        folder = run / name / cid
        title = 'LibreOffice 25.8.7.3' if name == 'reference' else name.title() + ' ' + captures[name]['candidate'][:8]
        if name == 'reference':
            ref = reference['cases'][cid]
            assert ref['inputSha256'] == case['sha256'] and ref['eligible'] == (not clipped)
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
            assert all(f['verified'] for f in report['fonts'])
            warnings = report['warnings']
            if name == 'candidate' and clipped:
                assert len(warnings) == 1 and warnings[0]['code'] == 'source_table_content_clipped'
                assert warnings[0]['anchorId'].startswith('p:')
            else: assert not warnings
            panel['warnings'] = warnings
            panel['report'] = retain(cid + '-' + name + '-report', raw)
        info = inspect_case_pdf(pdf, case)
        failures = reference_failures(case, info, 'libreoffice')
        if clipped:
            assert bool(failures) == (name != 'baseline'), (cid, name, failures)
        elif name == 'baseline' and (cid.endswith(('center', 'center-continuation', 'center-inferred', 'border-overhang'))):
            assert failures, (cid, name)
        else: assert not failures, (cid, name, failures)
        panel['mandatoryFailures'] = failures
        if not clipped or name == 'baseline':
            assert Counter(w['text'] for w in info['words']) == Counter(case['tokens'])
        else:
            actual = Counter(w['text'] for w in info['words'])
            assert Counter(case['tokens']) - actual == {'baskets': 1}
            assert actual - Counter(case['tokens']) == {}
        assert len(info['geometry']) == pages_expected
        for geometry in info['geometry']:
            assert geometry['media'] == [0, 0, 612, 792]
        expected_left = 51 if 'center' in cid else 32 if cid.endswith('negative-control') else 72
        expected_width = 468 if cid.endswith('percentage-control') else 580 if cid.endswith(('border-overhang', 'text-clipping')) else 510
        labels = [w for w in info['words'] if re.fullmatch(r'Ash\d{2}[AB]|AshComplete', w['text'])]
        assert len(labels) == (49 if pages_expected == 2 else 3)
        for word in info['words']:
            left, top, right, bottom = word['rect']
            assert all(math.isfinite(v) for v in word['rect'])
            assert 0 <= left < right and 0 <= top < bottom <= 792.1, (cid, name, word)
            if not clipped: assert right <= 612.1, (cid, name, word)
        # Every row on every page keeps its column position, including continuation pages.
        if name != 'baseline':
            for word in labels:
                if word['text'] == 'AshComplete': continue
                target = expected_left + (expected_width / 3 if word['text'].endswith('B') else 0)
                assert abs(word['rect'][0] - (target + 1)) < 1.5, (cid, name, word)
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
    draw.text((12, 40), 'All pages at original 96 DPI. Column labels on every page checked; clipped source text is explicitly diagnosed. No visual fidelity score.', font=font, fill='#33475b')
    for index, (title, panel, pages) in enumerate(panel_data):
        x, y = 12 + index * width, 144
        draw.text((x, 72), title, font=heading, fill='#16283b')
        draw.text((x, 100), (('SOURCE CLIP: warning' if panel['renderer'] == 'candidate' else 'SOURCE CLIP: ineligible') if clipped and panel['renderer'] != 'baseline' else 'NARROWED GRID: text retained' if clipped else 'FAIL: placement' if panel['mandatoryFailures'] else 'PASS') + f': {panel["checkedLabels"]} labels, {len(pages)} pages', font=font, fill='#8b4a15' if clipped or panel['mandatoryFailures'] else '#21623c')
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
print('Verified eight table-width cases and composed all-page comparison sheets')
