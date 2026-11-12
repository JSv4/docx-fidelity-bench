"""Retain source-bound equation diagnostics; no native geometry or full-suite score claim."""
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
import fitz

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from bench.common import digest, identity
from bench.html_artifacts import math_expression_pass
from bench.pdf import correctness, inspect_case_pdf, inspect_companion_pdf, reference_failures

run = Path(sys.argv[1]).resolve()
out = Path(__file__).resolve().parent
manifest = json.loads((run / 'manifest.json').read_text())
reference = json.loads((run / 'reference/bundle.json').read_text())
captures = {name: json.loads((run / name / 'capture.json').read_text())
            for name in ('baseline-strict', 'baseline-visible', 'candidate')}
assert reference['suiteDigest'] == identity(manifest)
builds, assets = {}, {}
for name, source in zip(('baseline', 'candidate'), map(Path, sys.argv[2:4])):
    builds[name] = json.loads((run / f'{name}-build.json').read_text())
    assets[name] = json.loads((run / f'{name}-export-assets.json').read_text())
    assert digest(source / '.docx-bench-build.json') == digest(run / f'{name}-build.json')
    for path, expected in builds[name]['files'].items(): assert digest(source / path) == expected
    for asset in assets[name]['assets']:
        path = source / 'npm/dist' / asset['path']
        assert digest(path) == asset['sha256'] and path.stat().st_size == asset['byteLength']
for name, capture in captures.items():
    build_name = 'candidate' if name == 'candidate' else 'baseline'
    assert capture['candidate'] == builds[build_name]['commit']
    assert capture['sourceTree'] == builds[build_name]['tree']
    assert capture['buildIdentitySha256'] == digest(run / f'{build_name}-build.json')
    assert capture['manifestSha256'] == digest(run / 'manifest.json')
    assert capture['htmlInspectorSha256'] == digest(root / 'bench/html_browser.mjs')
    assert capture['fontPolicy'] == ('permissive-diagnostic' if name == 'baseline-visible' else 'strict')


def retain(name, value):
    payload = value if isinstance(value, bytes) else (json.dumps(value, indent=2) + '\n').encode()
    path = out / (name + '.json.gz')
    path.write_bytes(gzip.compress(payload, mtime=0))
    return {'file': path.name, 'sha256': digest(path), 'jsonSha256': hashlib.sha256(payload).hexdigest()}


def bar_probe(path, info):
    """A dark horizontal filled rule must span the ordered numeric operands, and remain painted."""
    words = {w['text']: w['rect'] for w in info['words']}
    if '27.5' not in words or '9' not in words: return {'passed': False, 'rules': []}
    numerator, denominator = words['27.5'], words['9']
    with fitz.open(path) as document:
        page = document[0]
        rules = []
        for drawing in page.get_drawings():
            rect = drawing['rect']
            if (drawing.get('type') != 'f' or not drawing.get('fill') or max(drawing['fill']) > .1 or
                    drawing.get('fill_opacity') != 1 or not 0 < rect.height <= 2 or rect.width < 3): continue
            if not ((numerator[1] + numerator[3]) / 2 < (rect.y0 + rect.y1) / 2 < (denominator[1] + denominator[3]) / 2
                    and rect.x0 <= min(numerator[0], denominator[0]) + .5
                    and rect.x1 >= max(numerator[2], denominator[2]) - .5): continue
            pix = page.get_pixmap(matrix=fitz.Matrix(4, 4), clip=rect, alpha=False)
            dark = sum(max(pix.samples[i:i + 3]) < 160 for i in range(0, len(pix.samples), pix.n))
            rules.append({'rect': list(rect), 'darkPixels': dark, 'pixels': pix.width * pix.height})
    return {'passed': len(rules) == 1 and rules[0]['darkPixels'] > rules[0]['pixels'] * .5, 'rules': rules}


font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 15)
heading = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 18)
evidence = {'scope': 'Unscored source/structure/paint diagnostics; no Word typography or native geometry parity claim',
            'builds': builds, 'assets': assets, 'captures': captures, 'manifestSha256': digest(run / 'manifest.json'),
            'manifest': retain('manifest', (run / 'manifest.json').read_bytes()),
            'reference': retain('reference-bundle', (run / 'reference/bundle.json').read_bytes()),
            'schema': json.loads((run / 'schema.json').read_text()), 'cases': []}
for case in manifest['cases']:
    cid = case['id']; control = cid.endswith('control')
    assert digest(root / case['input']) == case['sha256']
    assert evidence['schema']['documents'][case['input']] == []
    entry = {'id': cid, 'inputSha256': case['sha256'], 'panels': []}
    for name in ('baseline-strict', 'baseline-visible', 'candidate', 'reference'):
        panel = {'renderer': name}; entry['panels'].append(panel)
        if name == 'reference':
            ref = reference['cases'][cid]
            assert ref['inputSha256'] == case['sha256'] and ref['eligible'] == control
            path = run / 'reference' / ref['pdf']
            assert digest(path) == ref['pdfSha256']
            panel['referenceEligible'] = ref['eligible']
        else:
            capture = next(c for c in captures[name]['cases'] if c['id'] == cid)
            assert capture['inputSha256'] == case['sha256']
            if name == 'baseline-strict' and not control:
                assert capture['status'] == 'failed' and capture['code'] == 'resource_policy_failure'
                assert capture['phase'] == 'font_loading'
                panel['refusal'] = capture
                continue
            assert capture['status'] == 'delivered'
            folder = run / name / cid
            path = folder / 'candidate.pdf'
            assert digest(path) == capture['pdfSha256']
            report = json.loads((folder / 'production.json').read_text())
            assert digest(folder / 'production.json') == capture['renderReportSha256']
            assert report['source']['rawPackageBytesDigest'] == case['sha256'] and report['bindings']['pdfDigest'] == digest(path)
            assert report['options']['policy']['strictFonts'] == (name != 'baseline-visible')
            assert report['status'] == 'complete' and report['options']['reviewProfile'] == 'final'
            placeholder = name == 'baseline-visible' and not control
            assert len(report['unsupportedContent']) == int(placeholder)
            assert [w['code'] for w in report['warnings']] == (['unsupported_content_placeholder', 'font_unavailable'] if placeholder else [])
            if not placeholder: assert all(f['verified'] for f in report['fonts'])
            assert digest(folder / 'candidate.html') == capture['htmlSha256']
            assert digest(folder / 'html-browser.json') == capture['htmlFactsSha256']
            facts = json.loads((folder / 'html-browser.json').read_text())
            assert facts['htmlSha256'] == capture['htmlSha256']
            if not control:
                assert len(facts['observations']) == 1
                panel['mathStructurePass'] = math_expression_pass(case['htmlAssertions'][0], facts['observations'][0], 0)
                assert panel['mathStructurePass'] == (name == 'candidate')
            panel['facts'] = retain(cid + '-' + name + '-html-facts', facts)
            panel['report'] = retain(cid + '-' + name + '-report', report)
        info = inspect_case_pdf(path, case)
        failures = [c['name'] for c in correctness(case, info, info) if not c['passed']]
        assert bool(failures) == (not control and name in ('baseline-visible', 'reference')), (cid, name, failures)
        if name == 'reference': assert reference_failures(case, info, 'libreoffice') == reference['cases'][cid]['ineligibleChecks']
        assert len(info['geometry']) == 1 and info['geometry'][0]['media'] == [0, 0, 612, 792]
        for word in info['words']:
            left, top, right, bottom = word['rect']
            assert all(math.isfinite(v) for v in word['rect']) and 0 <= left < right <= 612 and 0 <= top < bottom <= 792
        if name == 'baseline-visible' and not control:
            assert info['tokens'] == {'MapleBegin': 1, '[MATH]': 1, 'MapleEnd': 1}
        if name == 'candidate' or control:
            assert info['tokens'] == case['tokens']
            paint = inspect_companion_pdf(path, {'requiredTokens': case['tokens']})
            assert all(w['inkPixels'] > 0 for w in paint['words'])
            panel['sourcePaint'] = paint['words']
        if 'fraction-' in cid and not control and name == 'candidate':
            panel['fractionBar'] = bar_probe(path, info)
            assert panel['fractionBar']['passed']
        target = out / f'{cid}-{name}.pdf'; shutil.copyfile(path, target)
        panel.update(pdf=target.name, pdfSha256=digest(target), mandatoryFailures=failures,
                     inspection=retain(cid + '-' + name + '-inspection', info))
    # Full-page thumbnails and labeled equation crops retain the original page raster.
    sheet = Image.new('RGB', (1536, 760), '#edf1f5'); draw = ImageDraw.Draw(sheet)
    draw.text((16, 12), cid, font=heading, fill='black')
    draw.text((16, 40), 'Local diagnostic. Equation crops below full-page thumbnails; no native geometry score.', font=font, fill='black')
    names = [('baseline-visible', 'Before (permissive control)' if control else 'Before (permissive placeholder)'), ('reference', 'LibreOffice (font substitution)' if not control else 'LibreOffice control'),
             ('candidate', 'After (strict fonts)')]
    for column, (name, title) in enumerate(names):
        panel = next(p for p in entry['panels'] if p['renderer'] == name)
        path = out / panel['pdf']
        with fitz.open(path) as document:
            pix = document[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            raster = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
        x = column * 512
        draw.text((x + 12, 78), title, font=font, fill='black')
        thumb = raster.copy(); thumb.thumbnail((280, 380))
        sheet.paste(thumb, (x + (512 - thumb.width) // 2, 110))
        info = inspect_case_pdf(path, case)
        words = [w for w in info['words'] if w['text'] not in ('MapleBegin', 'MapleEnd')]
        box = [max(0, min(w['rect'][0] for w in words) - 10), max(0, min(w['rect'][1] for w in words) - 10),
               min(612, max(w['rect'][2] for w in words) + 10), min(792, max(w['rect'][3] for w in words) + 10)]
        # If a neighboring label enters the crop, include it completely instead of slicing its letters.
        for word in info['words']:
            rect = word['rect']
            if rect[0] < box[2] and rect[2] > box[0] and rect[1] < box[3] and rect[3] > box[1]:
                box = [min(box[0], rect[0] - 3), min(box[1], rect[1] - 3), max(box[2], rect[2] + 3), max(box[3], rect[3] + 3)]
        crop = raster.crop(tuple(round(v * 2) for v in box)); crop.thumbnail((480, 220))
        # Integer enlargement makes the small formula readable without repainting its pixels.
        scale = min(3, 480 // crop.width, 220 // crop.height)
        if scale > 1: crop = crop.resize((crop.width * scale, crop.height * scale), Image.Resampling.NEAREST)
        sheet.paste(crop, (x + (512 - crop.width) // 2, 510))
        panel['cropPt'] = box
    target = out / (cid + '.png'); sheet.save(target)
    entry['reviewSheet'] = {'file': target.name, 'sha256': digest(target)}
    evidence['cases'].append(entry)
negative = run / 'zero-bar.pdf'
info = inspect_case_pdf(negative, next(c for c in manifest['cases'] if c['id'] == 'plain-math-fraction-inline'))
assert not bar_probe(negative, info)['passed']
shutil.copyfile(negative, out / 'zero-bar.pdf')
evidence['negativeBar'] = {'file': 'zero-bar.pdf', 'sha256': digest(out / 'zero-bar.pdf'), 'probe': bar_probe(negative, info)}
(out / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
print('Verified 8 inputs, 26 PDFs, 6 MathML trees, 2 painted fraction bars, 8 review sheets, and zero-bar negative')
