"""Verify source-bound note scaling, continuation geometry and independent footer rounding."""
import gzip
import hashlib
import json
import math
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from WidthChecks import checks as width_checks
from bench.common import digest, identity
from bench.pdf import inspect_case_pdf, reference_failures, inspect_companion_pdf, companion_checks, correctness

run = Path(sys.argv[1]).resolve()
out = Path(__file__).resolve().parent
freeze = json.loads((run / 'freeze.json').read_text())
for name, value in freeze['files'].items(): assert digest(run / name) == value
for name, value in freeze['verifiers'].items(): assert digest(out / name) == value
source_freeze = json.loads((run / 'input-freeze.json').read_text())
for path, expected_hash in source_freeze['inputs'].items(): assert digest(root / path) == expected_hash
manifest = json.loads((run / 'manifest.json').read_text())
reference = json.loads((run / 'reference/bundle.json').read_text())
captures = {name: json.loads((run / name / 'capture.json').read_text()) for name in ('baseline', 'candidate')}
builds = {name: json.loads((run / f'{name}-build.json').read_text()) for name in captures}
assets = {name: json.loads((run / f'{name}-export-assets.json').read_text()) for name in captures}
sources = dict(zip(captures, (Path(p).resolve() for p in sys.argv[2:4])))
expected = {c['id'] for c in manifest['cases']}
assert len(expected) == 8 and set(reference['cases']) == expected
assert reference['suiteDigest'] == identity(manifest) and set(sources) == set(captures)
for name, capture in captures.items():
    assert capture['fontPolicy'] == 'strict' and capture['sandbox'] is True
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
        assert digest(path) == asset['sha256'] and path.stat().st_size == asset['byteLength']


def retain(name, data):
    payload = data if isinstance(data, bytes) else (json.dumps(data, indent=2) + '\n').encode()
    target = out / (name + '.json.gz')
    target.write_bytes(gzip.compress(payload, mtime=0))
    return {'file': target.name, 'sha256': digest(target), 'jsonSha256': hashlib.sha256(payload).hexdigest()}


font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
heading = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 16)
evidence = {'scope': 'Unscored strict-font exports of eight original note/footer sources. The long100% note retains eight native-ideal pitch failures, bound unchanged to baseline. No new Word or full-suite parity claim.',
            'manifestSha256': digest(run / 'manifest.json'), 'manifest': retain('manifest', (run / 'manifest.json').read_bytes()),
            'freeze': freeze, 'sourceFreeze': source_freeze, 'builds': builds, 'rendererAssets': assets, 'captures': captures,
            'referenceBundleSha256': digest(run / 'reference/bundle.json'),
            'referenceBundle': retain('reference-bundle', (run / 'reference/bundle.json').read_bytes()),
            'referenceEnvironment': reference['environment'], 'schema': json.loads((run / 'schema.json').read_text()), 'cases': []}
baseline_contract = json.loads((run / 'baseline-contract.json').read_text())
reference_contract = json.loads((run / 'reference-contract.json').read_text())
for case in manifest['cases']:
    cid = case['id']
    assert digest(root / case['input']) == case['sha256']
    assert evidence['schema']['documents'][case['input']] == []
    entry = {'id': cid, 'inputSha256': case['sha256'], 'panels': []}
    panel_data = []
    for name in ('baseline', 'reference', 'candidate'):
        folder = run / name / cid
        panel = {'renderer': name}
        if name == 'reference':
            ref = reference['cases'][cid]
            assert ref['inputSha256'] == case['sha256']
            pdf = run / name / ref['pdf']
            assert digest(pdf) == ref['pdfSha256']
            info = inspect_companion_pdf(pdf, case['pdfCompanion'])
            checks = companion_checks(case['pdfCompanion'], info)
            assert all(c['passed'] for c in checks)
            panel['checks'] = checks
            failures = reference_failures(case, info, 'libreoffice')
            assert failures == ref['ineligibleChecks']
            assert ref['eligible'] is True
            title = 'LibreOffice 25.8.7.3'
        else:
            record = next(c for c in captures[name]['cases'] if c['id'] == cid)
            assert record['inputSha256'] == case['sha256'] and record['status'] == 'delivered'
            pdf = folder / 'candidate.pdf'
            assert digest(pdf) == record['pdfSha256']
            raw = (folder / 'production.json').read_bytes()
            assert digest(folder / 'production.json') == record['renderReportSha256']
            report = json.loads(raw)
            assert report['status'] == 'complete' and not report['unsupportedContent'] and not report['warnings']
            assert report['source']['rawPackageBytesDigest'] == case['sha256']
            assert report['bindings']['pdfDigest'] == digest(pdf)
            assert report['options']['policy']['strictFonts'] is True
            assert report['options']['reviewProfile'] == 'final' and report['options']['commentProfile'] == 'hidden'
            assert report['fonts'] and all(f['verified'] for f in report['fonts'])
            assert report['environment']['verification'] == 'browserObserved'
            assert report['environment']['observed']['browserBuild'] == captures[name]['browserVersion']
            assert digest(folder / 'candidate.html') == record['htmlSha256']
            panel.update(report=retain(cid + '-' + name + '-report', raw), htmlSha256=record['htmlSha256'])
            info = inspect_companion_pdf(pdf, case['pdfCompanion'])
            checks = companion_checks(case['pdfCompanion'], info)
            assert all(c['passed'] for c in checks)
            panel['checks'] = checks
            failures = reference_failures(case, info, 'libreoffice')
            assert not failures, (cid, name, failures)
            title = name.title() + ' ' + captures[name]['candidate'][:8]
        panel['primaryChecks'] = correctness(case, reference['cases'][cid]['inspection'], info)
        primary_failures = [c['name'] for c in panel['primaryChecks'] if not c['passed']]
        assert primary_failures == (['page-count','physical-geometry-page-3'] if name == 'baseline' and cid == 'footnote-character-width-400-150' else []), (cid,name,primary_failures)
        panel['widthChecks'] = width_checks(case, info)
        failed = [c for c in panel['widthChecks'] if not c['passed']]
        if name == 'reference':
            assert panel['widthChecks'] == reference_contract[cid] and not failed
        elif name == 'baseline':
            assert panel['widthChecks'] == baseline_contract[cid]
        elif cid == 'footnote-character-width-400-100':
            assert failed == [c for c in baseline_contract[cid] if not c['passed']]
            assert len(failed) == 8 and all(c['kind'] == 'line-pitch' for c in failed)
        else:
            assert not failed, (cid,name,failed)
        assert Counter(w['text'] for w in info['words']) == Counter(case['tokens'])
        assert len(info['geometry']) > 0
        assert all(g['media'] == [0, 0, 612, 792] for g in info['geometry'])
        for word in info['words']:
            left, top, right, bottom = word['rect']
            assert all(math.isfinite(v) for v in word['rect']) and 0 <= left < right <= 612 and 0 <= top < bottom <= 792
        words = {w['text']: w for w in info['words']}
        panel['firstWordWidthPt'] = words['Sorrel001']['rect'][2] - words['Sorrel001']['rect'][0]
        panel['pageCount'] = len(info['geometry'])
        panel['firstPageWords'] = sum(w['page'] == 1 for w in info['words'])
        target = out / 'pdf' / (cid + '-' + name + '.pdf')
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(pdf, target)
        panel.update(pdf=str(target.relative_to(out)), pdfSha256=digest(target), mandatoryFailures=failures,
                     inspection=retain(cid + '-' + name + '-inspection', info))
        rasters = []
        panel['pageRasterSha256'] = []
        for page in range(1, panel['pageCount'] + 1):
            raster_path = folder / f'page-{page}'
            subprocess.run(['pdftoppm', '-r', '96', '-f', str(page), '-l', str(page), '-singlefile', '-png', str(pdf), str(raster_path)], check=True, capture_output=True)
            panel['pageRasterSha256'].append(digest(raster_path.with_suffix('.png')))
            rasters.append(Image.open(raster_path.with_suffix('.png')).convert('RGB'))
        panel_data.append((title, panel, rasters))
        entry['panels'].append(panel)
    baseline_info = json.loads(gzip.decompress((out / (cid + '-baseline-inspection.json.gz')).read_bytes()))
    candidate_info = json.loads(gzip.decompress((out / (cid + '-candidate-inspection.json.gz')).read_bytes()))
    if cid.endswith('-100'):
        assert baseline_info['geometry'] == candidate_info['geometry']
        assert baseline_info['words'] == candidate_info['words']
        baseline_panel, _, candidate_panel = entry['panels']
        assert baseline_panel['pageRasterSha256'] == candidate_panel['pageRasterSha256']
        entry['unchangedUnscaledControl'] = True
    if cid.startswith('story-drift-footer-'):
        baseline_body = [w for w in baseline_info['words'] if w['text'].startswith('Harbor')]
        candidate_body = [w for w in candidate_info['words'] if w['text'].startswith('Harbor')]
        assert baseline_body == candidate_body
        entry['unchangedBodyGeometry'] = True
    width, height = panel_data[0][2][0].size
    rows = max(len(pages) for _, _, pages in panel_data)
    sheet = Image.new('RGB', ((width + 24) * 3, rows * (height + 28) + 150), '#e9eef3')
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 12), cid, font=heading, fill='#16283b')
    draw.text((12, 40), 'All pages at unchanged96DPI. Source-derived scale/line/placement checks; long100% retains the known pitch limit. No new Word claim.', font=font, fill='#33475b')
    for i, (title, panel, rasters) in enumerate(panel_data):
        x = 12 + i * (width + 24)
        draw.text((x, 70), title, font=heading, fill='#16283b')
        draw.text((x, 96), ('FAIL' if panel['mandatoryFailures'] or not all(c['passed'] for c in panel['widthChecks']) else 'PASS') + f": authored checks; {sum(case['tokens'].values())} source tokens painted", font=font, fill='#8b4a15' if panel['mandatoryFailures'] or not all(c['passed'] for c in panel['widthChecks']) else '#21623c')
        draw.text((x, 120), f"{panel['pageCount']} pages; {panel['firstPageWords']} words on page 1; glyph span {panel['firstWordWidthPt']:.3f} pt", font=font, fill='#33475b')
        for page, raster in enumerate(rasters):
            assert raster.size == (width, height)
            y = 150 + page * (height + 28)
            draw.text((x, y), f'Page {page + 1}', font=font, fill='#33475b')
            sheet.paste(raster, (x, y + 24))
    target = out / (cid + '.png')
    sheet.save(target, optimize=True)
    entry['screenshot'] = {'file': target.name, 'sha256': digest(target)}
    evidence['cases'].append(entry)
evidence['summary'] = {'pdfs': 24, 'tokens': sum(sum(c['tokens'].values()) for c in manifest['cases']) * 3,
    'pages': sum(p['pageCount'] for c in evidence['cases'] for p in c['panels']),
    'strictAuthoredPassing': {name: sum(not p['mandatoryFailures'] and all(c['passed'] for c in p['widthChecks'])
        for c in evidence['cases'] for p in c['panels'] if p['renderer'] == name)
        for name in ('baseline', 'reference', 'candidate')}}
evidence['tools'] = {str(p.relative_to(root)): digest(p) for p in [Path(__file__), Path(__file__).with_name('WidthChecks.py'), Path(__file__).with_name('Mutations.py'), root / 'docs/results/export-reliability/Capture.mjs']}
(out / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
print(json.dumps(evidence['summary'],indent=2))
