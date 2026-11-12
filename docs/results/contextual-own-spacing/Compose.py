"""Verify original Oak spacing fixtures, source-bound exports and unchanged page rasters."""
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
from bench.common import digest, identity
from bench.pdf import inspect_case_pdf, reference_failures, inspect_companion_pdf, companion_checks

run = Path(sys.argv[1]).resolve()
out = Path(__file__).resolve().parent
manifest = json.loads((run / 'manifest.json').read_text())
reference = json.loads((run / 'reference/bundle.json').read_text())
captures = {name: json.loads((run / name / 'capture.json').read_text()) for name in ('baseline', 'candidate')}
builds = {name: json.loads((run / f'{name}-build.json').read_text()) for name in captures}
assets = {name: json.loads((run / f'{name}-export-assets.json').read_text()) for name in captures}
sources = dict(zip(captures, (Path(p).resolve() for p in sys.argv[2:4])))
expected = {c['id'] for c in manifest['cases']}
assert len(expected) == 9 and set(reference['cases']) == expected
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
evidence = {'scope': 'Unscored strict-font public exports. Seven eligible native body references; two native textbox discrepancies. No new Word or full-suite parity claim.',
            'manifestSha256': digest(run / 'manifest.json'), 'manifest': retain('manifest', (run / 'manifest.json').read_bytes()),
            'builds': builds, 'rendererAssets': assets, 'captures': captures,
            'referenceBundleSha256': digest(run / 'reference/bundle.json'),
            'referenceBundle': retain('reference-bundle', (run / 'reference/bundle.json').read_bytes()),
            'referenceEnvironment': reference['environment'], 'schema': json.loads((run / 'schema.json').read_text()), 'cases': []}
failing_baseline = {'after-first', 'before-second', 'neighbor-wins-control', 'drawing-first', 'vml-first'}
for case in manifest['cases']:
    cid = case['id']
    kind = cid.removeprefix('contextual-own-')
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
            assert ref['eligible'] == (kind not in ('drawing-first', 'vml-first'))
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
            assert bool(failures) == (name == 'baseline' and kind in failing_baseline), (cid, name, failures)
            title = name.title() + ' ' + captures[name]['candidate'][:8]
        assert Counter(w['text'] for w in info['words']) == Counter(case['tokens'])
        assert len(info['geometry']) == 1 and info['geometry'][0]['media'] == [0, 0, 612, 792]
        for word in info['words']:
            left, top, right, bottom = word['rect']
            assert all(math.isfinite(v) for v in word['rect']) and 0 <= left < right <= 612 and 0 <= top < bottom <= 792
        words = {w['text']: w for w in info['words']}
        panel['stepsPt'] = [words[b]['rect'][1] - words[a]['rect'][1] for a, b in [('OakFirst', 'OakSecond'), ('OakSecond', 'OakEnd')]]
        target = out / 'pdf' / (cid + '-' + name + '.pdf')
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(pdf, target)
        panel.update(pdf=str(target.relative_to(out)), pdfSha256=digest(target), mandatoryFailures=failures,
                     inspection=retain(cid + '-' + name + '-inspection', info))
        subprocess.run(['pdftoppm', '-r', '96', '-singlefile', '-png', str(pdf), str(folder / 'page')], check=True, capture_output=True)
        panel['pageRasterSha256'] = digest(folder / 'page.png')
        panel_data.append((title, panel, Image.open(folder / 'page.png').convert('RGB')))
        entry['panels'].append(panel)
    width, height = panel_data[0][2].size
    sheet = Image.new('RGB', ((width + 24) * 3, height + 150), '#e9eef3')
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 12), cid, font=heading, fill='#16283b')
    draw.text((12, 40), 'Full pages at unchanged 96 DPI. Authored spacing/position checks; no Word or full-suite score.', font=font, fill='#33475b')
    for i, (title, panel, raster) in enumerate(panel_data):
        x = 12 + i * (width + 24)
        draw.text((x, 70), title, font=heading, fill='#16283b')
        draw.text((x, 96), ('FAIL' if panel['mandatoryFailures'] else 'PASS') + ': authored position checks; all 3 labels painted', font=font, fill='#8b4a15' if panel['mandatoryFailures'] else '#21623c')
        draw.text((x, 120), 'Steps: ' + ', '.join(f'{v:.2f} pt' for v in panel['stepsPt']), font=font, fill='#33475b')
        sheet.paste(raster, (x, 150))
    target = out / (cid + '.png')
    sheet.save(target, optimize=True)
    entry['screenshot'] = {'file': target.name, 'sha256': digest(target)}
    evidence['cases'].append(entry)
evidence['tools'] = {str(p.relative_to(root)): digest(p) for p in [Path(__file__), root / 'docs/results/export-reliability/Capture.mjs']}
(out / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
print('Verified nine inputs, 27 PDFs, 81 labels, both build/asset manifests and nine review sheets')
