"""Bind source-paper clips to native final references and separate balloon companions."""
import gzip
import hashlib
import json
import math
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from zipfile import ZipFile
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from bench.common import digest, identity
from bench.pdf import inspect_case_pdf, reference_failures, inspect_companion_pdf, companion_checks

run = Path(sys.argv[1]).resolve()
out = Path(__file__).resolve().parent
manifest = json.loads((run / 'manifest.json').read_text())
companion_manifest = json.loads((run / 'companion-manifest.json').read_text())
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


evidence = {'scope': 'Unscored strict-font balloon companions; native source visibility is a separate reference retaining revision tint, not a Word All Markup oracle',
            'manifestSha256': digest(run / 'manifest.json'), 'companionManifestSha256': digest(run / 'companion-manifest.json'),
            'builds': builds, 'rendererAssets': assets, 'captures': captures,
            'referenceBundleSha256': digest(run / 'reference/bundle.json'),
            'referenceBundle': retain('reference-bundle', (run / 'reference/bundle.json').read_bytes()),
            'referenceEnvironment': reference['environment'], 'schema': json.loads((run / 'schema.json').read_text()),
            'cases': []}
for case in manifest['cases']:
    cid = case['id']
    assert evidence['schema']['documents'][case['input']] == []
    with ZipFile(root / case['input']) as package:
        document = ET.fromstring(package.read('word/document.xml'))
    source_labels = [node.text for node in document.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')]
    assert source_labels == ['ElmOpening', 'ElmHost', 'ElmWindowOne', 'ElmWindowTwo', 'ElmWindowThree', 'ElmClosing']
    declared = case['pdfCompanion']
    companion_case = next(c for c in companion_manifest['cases'] if c['id'] == cid)
    assert companion_case['profile'] == declared['profile'] and companion_case['tokens'] == declared['requiredTokens']
    assert companion_case['sha256'] == case['sha256']
    control = cid.endswith('control')
    entry = {'id': cid, 'inputSha256': case['sha256'], 'panels': []}
    panel_data = []
    for name in ('baseline', 'reference', 'candidate'):
        panel = {'renderer': name, 'profile': 'native-default-with-revision-tint' if name == 'reference' else declared['profile']}
        entry['panels'].append(panel)
        folder = run / name / cid
        title = 'LibreOffice 25.8.7.3 - NATIVE' if name == 'reference' else name.title() + ' ' + captures[name]['candidate'][:8] + ' - BALLOONS'
        if name == 'reference':
            ref = reference['cases'][cid]
            assert ref['inputSha256'] == case['sha256'] and ref['eligible']
            pdf = run / name / ref['pdf']
            assert digest(pdf) == ref['pdfSha256']
            info = inspect_case_pdf(pdf, case)
            assert not reference_failures(case, info, 'libreoffice'), cid
            assert Counter(w['text'] for w in info['words']) == Counter(case['tokens'])
            checked = sum(case['tokens'].values())
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
            hidden = declared.get('forbiddenTokens', [])
            warnings = report['warnings']
            assert len(warnings) == len(hidden) and all(w['code'] == 'source_text_clipped' for w in warnings)
            assert len({w['anchorId'] for w in warnings}) == len(hidden)
            panel['report'] = retain(cid + '-' + name + '-report', raw)
            info = inspect_companion_pdf(pdf, declared)
            checks = companion_checks(declared, info)
            assert all(c['passed'] for c in checks), (cid, name, checks)
            assert Counter(w['text'] for w in info['words'] if w['text'].startswith('Elm') and w['text'] != 'Elm') == Counter(case['tokens'])
            panel['checks'] = checks
            checked = sum(declared['requiredTokens'].values())
        assert len(info['geometry']) == 1
        for geometry in info['geometry']:
            assert geometry['media'] == [0, 0, 612, 792]
        for word in info['words']:
            left, top, right, bottom = word['rect']
            assert all(math.isfinite(v) for v in word['rect'])
            assert 0 <= left < right <= 612.25 and 0 <= top < bottom <= 792.25, (cid, name, word)
        panel.update(pdfSha256=digest(pdf), pages=1, checkedLabels=checked,
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
    draw.text((12, 40), '96 DPI. NATIVE references check source visibility; BALLOON companions check inventory, paint and paper bounds. No Word parity.', font=font, fill='#33475b')
    for index, (title, panel, pages) in enumerate(panel_data):
        x, y = 12 + index * width, 144
        draw.text((x, 72), title, font=heading, fill='#16283b')
        if not pages:
            draw.text((x, 100), 'NO PDF: source-fragment verification failed', font=font, fill='#8b4a15')
            continue
        draw.text((x, 100), f'PASS: {panel["checkedLabels"]} labels, {len(pages)} pages', font=font, fill='#21623c')
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
print('Verified seven native references and balloon companions; composed all comparison sheets')
