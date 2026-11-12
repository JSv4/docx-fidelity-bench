"""Verify original Poppy story-minimum fixtures, source-bound exports and unchanged page rasters."""
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
from Checks import source_contract, control_checks, checks as story_checks
from bench.common import digest, identity
from bench.pdf import correctness, reference_failures, inspect_companion_pdf, companion_checks

run = Path(sys.argv[1]).resolve()
out = Path(__file__).resolve().parent
freeze = json.loads((run / 'freeze.json').read_text())
for name, value in freeze['files'].items(): assert digest(run / name) == value
for name, value in freeze['verifiers'].items(): assert digest(out / name) == value
manifest = json.loads((run / 'manifest.json').read_text())
reference = json.loads((run / 'reference-final/bundle.json').read_text())
captures = {name: json.loads((run / name / 'capture.json').read_text()) for name in ('baseline', 'candidate')}
builds = {name: json.loads((run / f'{name}-build.json').read_text()) for name in captures}
assets = {name: json.loads((run / f'{name}-export-assets.json').read_text()) for name in captures}
sources = dict(zip(captures, (Path(p).resolve() for p in sys.argv[2:4])))
expected = {c['id'] for c in manifest['cases']}
assert len(expected) == 16 and set(reference['cases']) == expected
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
evidence = {'scope': 'Unscored strict-font public exports. Sixteen native controls; running/note source line pitches, same-owner natural-control geometry and complete painted inventories only. No new Word or full-suite parity claim.',
            'manifestSha256': digest(run / 'manifest.json'), 'manifest': retain('manifest', (run / 'manifest.json').read_bytes()),
            'initialManifest': retain('initial-manifest', (run / 'initial-manifest.json').read_bytes()),
            'initialReference': retain('initial-reference', (run / 'initial-reference.json').read_bytes()),
            'beforeReviewManifest': retain('before-review-manifest', (run / 'before-review-manifest.json').read_bytes()),
            'beforeReviewReference': retain('before-review-reference', (run / 'before-review-reference.json').read_bytes()),
            'preBaselineFreeze': retain('pre-baseline-freeze', (run / 'pre-baseline-freeze.json').read_bytes()),
            'freeze': freeze, 'builds': builds, 'rendererAssets': assets, 'captures': captures,
            'referenceBundleSha256': digest(run / 'reference-final/bundle.json'),
            'referenceBundle': retain('reference-bundle', (run / 'reference-final/bundle.json').read_bytes()),
            'referenceEnvironment': reference['environment'], 'schema': json.loads((run / 'schema.json').read_text()), 'cases': []}
failing_baseline = {c['id'].removeprefix('minimum-story-') for c in manifest['cases'] if c['id'].endswith('-minimum')}
for case in manifest['cases']:
    cid = case['id']
    kind = cid.removeprefix('minimum-story-')
    assert digest(root / case['input']) == case['sha256']
    assert evidence['schema']['documents'][case['input']] == []
    contract = source_contract(root / case['input'])
    entry = {'contract': contract, 'id': cid, 'inputSha256': case['sha256'], 'panels': []}
    panel_data = []
    for name in ('baseline', 'reference', 'candidate'):
        folder = run / ('reference-final' if name == 'reference' else name) / cid
        panel = {'renderer': name}
        if name == 'baseline':
            record = next(c for c in captures[name]['cases'] if c['id'] == cid)
            assert record['inputSha256'] == case['sha256']
            if record['status'] == 'failed':
                assert contract['owner'] == 'footnote' and cid.endswith('-minimum')
                assert record['code'] == 'pagination_failure' and record['phase'] == 'running_story_placement'
                assert record['message'] == 'A footnote continuation is clipped in the final page tree.'
                panel.update(status='refused', refusal=record, passed=False, pageCount=0)
                blank = Image.new('RGB', (816, 1056), 'white')
                draw = ImageDraw.Draw(blank)
                draw.text((20, 40), 'No PDF produced', font=heading, fill='#8b4a15')
                draw.text((20, 80), record['message'], font=font, fill='#33475b')
                panel_data.append(('Baseline ' + captures[name]['candidate'][:8], panel, [blank]))
                entry['panels'].append(panel)
                continue
        if name == 'reference':
            ref = reference['cases'][cid]
            assert ref['inputSha256'] == case['sha256']
            pdf = run / 'reference-final' / ref['pdf']
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
            title = name.title() + ' ' + captures[name]['candidate'][:8]
        control_id = cid.rsplit('-', 1)[0] + '-natural'
        control_case = next(c for c in manifest['cases'] if c['id'] == control_id)
        control_path = (run / 'reference-final' / reference['cases'][control_id]['pdf']) if name == 'reference' else run / name / control_id / 'candidate.pdf'
        control_info = inspect_companion_pdf(control_path, control_case['pdfCompanion'])
        panel['primaryChecks'] = correctness(case, reference['cases'][cid]['inspection'], info)
        failures = [c['name'] for c in panel['primaryChecks'] if not c['passed']]
        panel['metricChecks'] = story_checks(contract, info, control_info)
        if name == 'candidate':
            baseline_control = inspect_companion_pdf(run / 'baseline' / control_id / 'candidate.pdf', control_case['pdfCompanion'])
            panel['metricChecks'] += control_checks(control_info, baseline_control)
        panel['passed'] = not failures and all(c['passed'] for c in panel['checks'] + panel['metricChecks'])
        assert panel['passed'] == (name != 'baseline' or kind not in failing_baseline), (cid, name, [c for c in panel['metricChecks'] if not c['passed']])
        assert Counter(w['text'] for w in info['words']) == Counter(case['tokens'])
        assert all(g['media'] == [0, 0, 612, 792] for g in info['geometry'])
        for word in info['words']:
            left, top, right, bottom = word['rect']
            assert all(math.isfinite(v) for v in word['rect']) and 0 <= left < right <= 612 and 0 <= top < bottom <= 792
        panel['pageCount'] = len(info['geometry'])
        panel['paintedWords'] = len(info['words'])
        panel['firstPageLines'] = sum(w['page'] == 1 and w['text'].startswith('Poppy') for w in info['words'])
        panel['storyLabelsByPage'] = [[w['text'] for w in info['words'] if w['page'] == page
            and w['text'].startswith('Poppy')] for page in range(1, panel['pageCount'] + 1)]
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
    width, height = panel_data[0][2][0].size
    rows = max(len(pages) for _, _, pages in panel_data)
    sheet = Image.new('RGB', ((width + 24) * 3, rows * (height + 28) + 150), '#e9eef3')
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 12), cid, font=heading, fill='#16283b')
    draw.text((12, 40), 'All pages at unchanged 96 DPI. Natural line pitch, repeated/continued story ownership and all token geometry checked; baseline refusals labeled.', font=font, fill='#33475b')
    for i, (title, panel, rasters) in enumerate(panel_data):
        x = 12 + i * (width + 24)
        draw.text((x, 70), title, font=heading, fill='#16283b')
        draw.text((x, 96), ('PASS' if panel['passed'] else 'FAIL') + ': complete source and natural-control checks', font=font, fill='#21623c' if panel['passed'] else '#8b4a15')
        draw.text((x, 120), f"{panel['pageCount']} PDF pages; {panel.get('paintedWords', 0)} painted words", font=font, fill='#33475b')
        for page, raster in enumerate(rasters):
            assert raster.size == (width, height)
            y = 150 + page * (height + 28)
            draw.text((x, y), f'Page {page + 1}' if panel['pageCount'] else 'Export refused', font=font, fill='#33475b')
            sheet.paste(raster, (x, y + 24))
    target = out / (cid + '.png')
    sheet.save(target, optimize=True)
    entry['screenshot'] = {'file': target.name, 'sha256': digest(target)}
    evidence['cases'].append(entry)
evidence['tools'] = {str(p.relative_to(root)): digest(p) for p in [Path(__file__), Path(__file__).with_name('Checks.py'), root / 'docs/results/export-reliability/Capture.mjs']}
(out / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
print('Verified', len(evidence['cases']), 'inputs,', sum(p['pageCount'] > 0 for c in evidence['cases'] for p in c['panels']), 'PDFs,', sum(p['pageCount'] for c in evidence['cases'] for p in c['panels']), 'pages and all metric/build/asset checks')
