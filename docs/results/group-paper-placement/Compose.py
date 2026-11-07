"""Bind original group coordinates to independently authored source visibility and public exports."""
import gzip
import hashlib
import json
import math
import subprocess
import sys
import shutil
from html.parser import HTMLParser
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from zipfile import ZipFile
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from bench.common import digest, identity
from SourceCoordinates import verify as verify_source, output_checks
from bench.pdf import inspect_case_pdf, reference_failures, inspect_companion_pdf, companion_checks, correctness

run = Path(sys.argv[1]).resolve()
out = Path(__file__).resolve().parent
manifest = json.loads((run / 'manifest.json').read_text())
companion_manifest = json.loads((run / 'companion-manifest.json').read_text())
reference = json.loads((run / 'reference/bundle.json').read_text())
captures = {name: json.loads((run / name / 'capture.json').read_text()) for name in ('baseline', 'candidate')}
expected = {c['id'] for c in manifest['cases']}
assert len(expected) == 9
source_coordinates = json.loads((run / 'source-coordinates.json').read_text())
freeze = json.loads((run / 'freeze.json').read_text())
for path, expected_hash in freeze['files'].items():
    assert digest(run / path) == expected_hash, path
for path, expected_hash in freeze['verifiers'].items():
    assert digest(out / path) == expected_hash, path
assert reference['suiteDigest'] == identity(manifest) and set(reference['cases']) == expected
builds = {name: json.loads((run / f'{name}-build.json').read_text()) for name in captures}
assets = {name: json.loads((run / f'{name}-export-assets.json').read_text()) for name in captures}
sources = dict(zip(('baseline', 'candidate'), (Path(p).resolve() for p in sys.argv[2:4])))
assert set(sources) == set(captures), 'Supply exact baseline and candidate source directories'
for name, capture in captures.items():
    assert capture['fontPolicy'] == 'strict'
    assert capture['manifestSha256'] == digest(run / 'companion-manifest.json')
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



class SourceText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.text = [], {}

    def handle_starttag(self, tag, attrs):
        anchor = dict(attrs).get('data-source-anchor-id')
        self.stack.append((tag, anchor))
        if anchor:
            self.text.setdefault(anchor, '')

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, text):
        for _, anchor in reversed(self.stack):
            if anchor:
                self.text[anchor] += text
                break


evidence = {'scope': 'Unscored strict-font public exports. Literal authored coordinates govern clipping. LibreOffice group normalization is diagnostic and may be ineligible. No Word parity or full-suite score.',
            'manifestSha256': digest(run / 'manifest.json'), 'companionManifestSha256': digest(run / 'companion-manifest.json'),
            'builds': builds, 'rendererAssets': assets, 'captures': captures,
            'referenceBundleSha256': digest(run / 'reference/bundle.json'),
            'referenceBundle': retain('reference-bundle', (run / 'reference/bundle.json').read_bytes()),
            'manifest': retain('manifest', (run / 'manifest.json').read_bytes()),
            'companionManifest': retain('companion-manifest', (run / 'companion-manifest.json').read_bytes()),
            'sourceCoordinates': retain('source-coordinates', source_coordinates), 'freeze': freeze,
            'referenceEnvironment': reference['environment'], 'schema': json.loads((run / 'schema.json').read_text()),
            'cases': []}
for case in manifest['cases']:
    cid = case['id']
    assert evidence['schema']['documents'][case['input']] == []
    with ZipFile(root / case['input']) as package:
        document = ET.fromstring(package.read('word/document.xml'))
    source_labels = [node.text for node in document.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')]
    assert source_labels == ['SedgeOpen', 'SedgeHost', 'SedgeNear', 'SedgeFar', 'SedgeClose']
    declared = case['pdfCompanion']
    companion_case = next(c for c in companion_manifest['cases'] if c['id'] == cid)
    assert companion_case['profile'] == declared['profile'] and companion_case['tokens'] == declared['requiredTokens']
    assert companion_case['sha256'] == case['sha256']
    control = cid.endswith('control')
    entry = {'id': cid, 'inputSha256': case['sha256'], 'sourceCoordinates': verify_source(root / case['input'], case), 'panels': []}
    assert entry['sourceCoordinates'] == source_coordinates[cid]
    panel_data = []
    for name in ('baseline', 'reference', 'candidate'):
        panel = {'renderer': name, 'profile': 'native-default-with-revision-tint' if name == 'reference' else declared['profile']}
        entry['panels'].append(panel)
        folder = run / name / cid
        title = 'LibreOffice 25.8.7.3 - NATIVE' if name == 'reference' else name.title() + ' ' + captures[name]['candidate'][:8] + (' - BALLOONS' if declared['profile'].get('commentColumnPlacement') == 'balloons' else ' - FINAL')
        if name == 'reference':
            ref = reference['cases'][cid]
            assert ref['inputSha256'] == case['sha256']
            pdf = run / name / ref['pdf']
            assert digest(pdf) == ref['pdfSha256']
            info = inspect_case_pdf(pdf, case)
            failures = reference_failures(case, info, 'libreoffice')
            assert ref['eligible'] == (not failures)
            panel.update(eligible=ref['eligible'], referenceFailures=failures)
            checked = len(info['words'])
        else:
            record = next(c for c in captures[name]['cases'] if c['id'] == cid)
            assert record['inputSha256'] == case['sha256']
            if record['status'] == 'failed':
                assert name == 'baseline' and not control
                assert record['code'] == 'output_verification_failure' and 'has no measurable fragment' in record['message']
                panel['failure'] = record
                panel_data.append((title, panel, []))
                continue
            assert record['status'] == 'delivered' and (name != 'baseline' or control)
            pdf = folder / 'candidate.pdf'
            assert digest(pdf) == record['pdfSha256']
            raw = (folder / 'production.json').read_bytes()
            assert digest(folder / 'production.json') == record['renderReportSha256']
            report = json.loads(raw)
            assert report['status'] == 'complete' and not report['unsupportedContent']
            assert report['source']['rawPackageBytesDigest'] == case['sha256']
            assert report['bindings']['pdfDigest'] == digest(pdf)
            assert report['options']['policy']['strictFonts'] is True
            for key, value in declared['profile'].items():
                assert report['options'][{'review': 'reviewProfile', 'comments': 'commentProfile'}.get(key, key)] == value
            assert report['fonts'] and all(f['verified'] for f in report['fonts'])
            assert report['environment']['verification'] == 'browserObserved'
            assert report['environment']['observed']['browserBuild'] == captures[name]['browserVersion']
            html = folder / 'candidate.html'
            assert digest(html) == record['htmlSha256']
            geometry = json.loads((folder / 'group-geometry.json').read_text())
            assert geometry['htmlSha256'] == digest(html)
            assert geometry['browserVersion'] == captures[name]['browserVersion']
            assert set(geometry['framesPt']) == set(entry['sourceCoordinates']['framesPt'])
            for label, expected_frame in entry['sourceCoordinates']['framesPt'].items():
                assert all(abs(a - b) < 0.1 for a, b in zip(geometry['framesPt'][label], expected_frame)), (cid, label, geometry)
            panel['groupGeometry'] = retain(cid + '-' + name + '-group-geometry', geometry)
            parser = SourceText()
            parser.feed(html.read_text())
            anchors = {label: [anchor for anchor, text in parser.text.items() if text.strip() == label]
                       for label in ['SedgeNear', 'SedgeFar']}
            assert all(len(ids) == 1 for ids in anchors.values()), (cid, name, anchors)
            panel['sourceTextAnchors'] = anchors
            panel['htmlSha256'] = digest(html)
            hidden = declared.get('forbiddenTokens', [])
            warnings = report['warnings']
            assert {w['anchorId'] for w in warnings} == {anchors[label][0] for label in hidden}

            assert len(warnings) == len(hidden) and all(w['code'] == 'source_text_clipped' for w in warnings)
            assert len({w['anchorId'] for w in warnings}) == len(hidden)
            panel['report'] = retain(cid + '-' + name + '-report', raw)
            info = inspect_companion_pdf(pdf, declared)
            checks = companion_checks(declared, info)
            checks += output_checks(entry['sourceCoordinates'], info['words'], geometry['sourcePaperOnPhysicalPt'])
            if declared['profile'].get('commentColumnPlacement') != 'balloons':
                checks += correctness(case, info, info)
            assert all(c['passed'] for c in checks), (cid, name, checks)
            assert Counter(w['text'] for w in info['words'] if w['text'].startswith('Sedge')) == Counter(case['tokens'])
            panel['checks'] = checks
            checked = sum(declared['requiredTokens'].values())
        assert len(info['geometry']) == 1
        for geometry in info['geometry']:
            assert geometry['media'] == [0, 0, 612, 792]
        for word in info['words']:
            left, top, right, bottom = word['rect']
            assert all(math.isfinite(v) for v in word['rect'])
            assert 0 <= left < right <= 612.25 and 0 <= top < bottom <= 792.25, (cid, name, word)
        retained_pdf = out / 'pdf' / (cid + '-' + name + '.pdf')
        retained_pdf.parent.mkdir(exist_ok=True)
        shutil.copyfile(pdf, retained_pdf)
        panel.update(pdf=str(retained_pdf.relative_to(out)), pdfSha256=digest(pdf), pages=1, checkedLabels=checked,
                     inspection=retain(cid + '-' + name + '-inspection', info))
        subprocess.run(['pdftoppm', '-r', '96', '-png', str(pdf), str(folder / 'page')], check=True, capture_output=True)
        pages = sorted(folder.glob('page-*.png'), key=lambda p: int(p.stem.split('-')[-1]))
        assert len(pages) == 1
        panel['pageRasterSha256'] = [digest(p) for p in pages]
        panel_data.append((title, panel, pages))
    width = max(Image.open(p).width for _, _, pages in panel_data for p in pages) + 24
    height = max(sum(Image.open(p).height + 26 for p in pages) for _, _, pages in panel_data) + 144
    sheet = Image.new('RGB', (width * 3 + 12, height), '#e9eef3')
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 12), cid, font=heading, fill='#16283b')
    draw.text((12, 40), '96 DPI. Authored group coordinates; native normalization is diagnostic. No Word parity.', font=font, fill='#33475b')
    for index, (title, panel, pages) in enumerate(panel_data):
        x, y = 12 + index * width, 144
        draw.text((x, 72), title, font=heading, fill='#16283b')
        if not pages:
            draw.text((x, 100), 'NO PDF: source-fragment verification failed', font=font, fill='#8b4a15')
            continue
        draw.text((x, 100), ('DIAGNOSTIC: native normalization differs' if panel.get('eligible') is False else f'PASS: {panel["checkedLabels"]} labels, {len(pages)} pages'), font=font, fill='#8b4a15' if panel.get('eligible') is False else '#21623c')
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
                     [Path(__file__), out / 'SourceCoordinates.py', out / 'Geometry.mjs', root / 'docs/results/export-reliability/Capture.mjs']}
(out / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
print('Verified nine original coordinate proofs, source-bound PDFs and nine comparison sheets')
