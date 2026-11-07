"""Verify the frozen Chive contract and retain every page of each available renderer."""
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from bench.common import digest, identity
from bench.pdf import inspect_case_pdf, inspect_companion_pdf, companion_checks, correctness, reference_failures
from Checks import source_frames, picture_checks, inspect_picture_ink

run = Path(sys.argv[1]).resolve()
out = Path(__file__).resolve().parent
manifest = json.loads((run / 'manifest.json').read_text())
reference = json.loads((run / 'reference/bundle.json').read_text())
frames = json.loads((run / 'source-frames.json').read_text())
freeze = json.loads((run / 'freeze.json').read_text())
for name, value in freeze['files'].items(): assert digest(run / name) == value
for name, value in freeze['verifiers'].items(): assert digest(out / name) == value
captures = {name: json.loads((run / name / 'capture.json').read_text()) for name in ('baseline', 'candidate')}
builds = {name: json.loads((run / f'{name}-build.json').read_text()) for name in captures}
assets = {name: json.loads((run / f'{name}-export-assets.json').read_text()) for name in captures}
sources = dict(zip(captures, (Path(p).resolve() for p in sys.argv[2:4])))
expected = {c['id'] for c in manifest['cases']}
assert len(expected) == 12 and set(reference['cases']) == expected and set(frames) == expected
assert reference['suiteDigest'] == identity(manifest) and set(sources) == set(captures)
for name, capture in captures.items():
    assert capture['fontPolicy'] == 'strict' and capture['sandbox'] is True
    assert capture['manifestSha256'] == digest(run / 'manifest.json')
    assert {c['id'] for c in capture['cases']} == expected
    assert capture['candidate'] == builds[name]['commit'] and capture['sourceTree'] == builds[name]['tree']
    assert capture['buildIdentitySha256'] == digest(run / f'{name}-build.json')
    assert digest(run / f'{name}-export-assets.json') == builds[name]['files']['npm/dist/export-assets.json']
    source = sources[name]
    for ref, value in [('HEAD', builds[name]['commit']), ('HEAD^{tree}', builds[name]['tree'])]:
        assert subprocess.check_output(['git', 'rev-parse', ref], cwd=source, text=True).strip() == value
    assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=source, text=True)
    for path, value in builds[name]['files'].items(): assert digest(source / path) == value
    for asset in assets[name]['assets']:
        path = source / 'npm/dist' / asset['path']
        assert digest(path) == asset['sha256'] and path.stat().st_size == asset['byteLength']


def retain(name, data):
    payload = data if isinstance(data, bytes) else (json.dumps(data, indent=2) + '\n').encode()
    target = out / (name + '.json.gz')
    target.write_bytes(gzip.compress(payload, mtime=0))
    return dict(file=target.name, sha256=digest(target), jsonSha256=hashlib.sha256(payload).hexdigest())


font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
heading = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 16)
evidence = dict(scope='Unscored strict-font public exports. Native-corresponding source ownership, line slots, wrapping and painted pictures. No Word or whole-suite parity claim.',
    manifest=retain('manifest', (run / 'manifest.json').read_bytes()), manifestSha256=digest(run / 'manifest.json'),
    referenceBundle=retain('reference-bundle', (run / 'reference/bundle.json').read_bytes()),
    sourceFrames=retain('source-frames', frames), freeze=freeze, builds=builds, rendererAssets=assets, captures=captures,
    schema=json.loads((run / 'schema.json').read_text()), cases=[])
for case in manifest['cases']:
    cid = case['id']
    assert digest(root / case['input']) == case['sha256']
    assert evidence['schema']['documents'][case['input']] == []
    assert source_frames(root / case['input']) == frames[cid]
    ref = reference['cases'][cid]
    ref_pdf = run / 'reference' / ref['pdf']
    assert ref['inputSha256'] == case['sha256'] and digest(ref_pdf) == ref['pdfSha256']
    ref_info = inspect_picture_ink(ref_pdf, inspect_case_pdf(ref_pdf, case), frames[cid])
    assert ref['eligible'] and not ref['ineligibleChecks'] and not reference_failures(case, ref_info, 'libreoffice')
    entry = dict(id=cid, inputSha256=case['sha256'], sourceFrames=frames[cid], panels=[])
    panel_data = []
    control = cid.endswith(('none-after-0', 'plain-control'))
    for name in ('baseline', 'reference', 'candidate'):
        folder = run / name / cid
        panel = dict(renderer=name)
        entry['panels'].append(panel)
        title = 'LibreOffice 25.8.7.3' if name == 'reference' else name.title() + ' ' + captures[name]['candidate'][:8]
        geometry = None
        if name == 'reference':
            pdf, info = ref_pdf, ref_info
        else:
            record = next(c for c in captures[name]['cases'] if c['id'] == cid)
            assert record['inputSha256'] == case['sha256']
            if record['status'] == 'failed':
                assert name == 'baseline' and not control
                assert record['code'] == 'pagination_failure' and 'clipped' in record['message'].lower(), record
                panel['failure'] = record
                panel_data.append((title, panel, []))
                continue
            assert record['status'] == 'delivered' and (name != 'baseline' or control)
            pdf = folder / 'candidate.pdf'
            assert digest(pdf) == record['pdfSha256']
            raw = (folder / 'production.json').read_bytes()
            assert digest(folder / 'production.json') == record['renderReportSha256']
            report = json.loads(raw)
            assert report['status'] == 'complete' and not report['warnings'] and not report['unsupportedContent']
            assert report['source']['rawPackageBytesDigest'] == case['sha256'] and report['bindings']['pdfDigest'] == digest(pdf)
            assert report['options']['policy']['strictFonts'] is True
            assert report['options']['reviewProfile'] == 'final' and report['options']['commentProfile'] == 'hidden'
            assert report['fonts'] and all(f['verified'] for f in report['fonts'])
            assert report['environment']['verification'] == 'browserObserved'
            assert report['environment']['observed']['browserBuild'] == captures[name]['browserVersion']
            geometry = json.loads((folder / 'pictures.json').read_text())
            assert geometry['htmlSha256'] == digest(folder / 'candidate.html') == record['htmlSha256']
            assert geometry['browserVersion'] == captures[name]['browserVersion']
            panel.update(report=retain(cid + '-' + name + '-report', raw),
                pictures=retain(cid + '-' + name + '-pictures', geometry), htmlSha256=record['htmlSha256'])
            info = inspect_picture_ink(pdf, inspect_case_pdf(pdf, case), frames[cid])
        checks = correctness(case, ref_info, info)
        painted = inspect_companion_pdf(pdf, case['pdfCompanion'])
        checks += companion_checks(case['pdfCompanion'], painted)
        checks += picture_checks(frames[cid], info, geometry['pictures'] if geometry else None)
        assert all(c['passed'] for c in checks), (cid, name, [c for c in checks if not c['passed']])
        target = out / 'pdf' / (cid + '-' + name + '.pdf')
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(pdf, target)
        panel.update(pdf=str(target.relative_to(out)), pdfSha256=digest(target), pages=len(info['geometry']), checks=checks,
            inspection=retain(cid + '-' + name + '-inspection', info), painted=retain(cid + '-' + name + '-painted', painted))
        subprocess.run(['pdftoppm', '-r', '96', '-png', str(pdf), str(folder / 'page')], check=True, capture_output=True)
        pages = sorted(folder.glob('page-*.png'), key=lambda p: int(p.stem.split('-')[-1]))
        assert len(pages) == panel['pages']
        panel['pageRasterSha256'] = [digest(p) for p in pages]
        panel_data.append((title, panel, pages))
    width = max(Image.open(p).width for _, _, pages in panel_data for p in pages) + 24
    height = max(sum(Image.open(p).height + 26 for p in pages) for _, _, pages in panel_data) + 144
    sheet = Image.new('RGB', (width * 3 + 12, height), '#e9eef3')
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 12), cid, font=heading, fill='#16283b')
    draw.text((12, 40), 'All pages at unchanged 96 DPI. Source ownership, wrapping and painted pictures; no Word parity claim.', font=font, fill='#33475b')
    for index, (title, panel, pages) in enumerate(panel_data):
        x, y = 12 + index * width, 144
        draw.text((x, 72), title, font=heading, fill='#16283b')
        draw.text((x, 100), f'PASS: {len(pages)} pages' if pages else 'NO PDF: paragraph clipping detected', font=font, fill='#21623c' if pages else '#8b4a15')
        for number, path in enumerate(pages, 1):
            draw.text((x, y - 20), f'Page {number}', font=font, fill='#33475b')
            page = Image.open(path).convert('RGB'); sheet.paste(page, (x, y)); y += page.height + 26
    target = out / (cid + '.png'); sheet.save(target, optimize=True)
    entry['screenshot'] = dict(file=target.name, sha256=digest(target)); evidence['cases'].append(entry)
evidence['tools'] = {str(p.relative_to(root)): digest(p) for p in [Path(__file__), out / 'Checks.py', out / 'Geometry.mjs', root / 'docs/results/export-reliability/Capture.mjs']}
(out / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
print('Verified twelve cases, all retained PDFs and pages, both build/asset bindings and twelve comparison sheets')
