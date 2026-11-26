"""Label each #1862 case's 96-DPI page rasters, measure them, and bind the focused public-API evidence.

Usage: python3 docs/results/split-direction-marks/Compose.py RUN

RUN holds manifest.json, reference/bundle.json (`bench reference libreoffice --manifest`),
calibration/result.json (`bench run --adapter libreoffice` against that bundle), capture-main/
and capture-fix/ (export-reliability Capture.mjs then Inspect.py) and each build's identity
record copied as main-docx-bench-build.json and fix-docx-bench-build.json.

Each Docxodus PDF is measured against the LibreOffice reference exactly as `bench run` measures
a page: Poppler at 96 DPI on the CropBox, `bench.metrics.page_metrics`, the worst page for the
case. These are diagnostics of a borrowed browser, not registered candidate scores. The sheets
show the same unchanged pixels, every page of a case cropped to the box around all three
renderers' ink plus a margin.
"""
import json
import shutil
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from bench import metrics, pdf as bench_pdf
from bench.common import digest, identity

run = Path(sys.argv[1]).resolve()
out = Path(__file__).resolve().parent
manifest = json.loads((run / 'manifest.json').read_text())
reference = json.loads((run / 'reference/bundle.json').read_text())
calibration = json.loads((run / 'calibration/result.json').read_text())
captures = {name: json.loads((run / f'capture-{name}' / 'inspected.json').read_text()) for name in ('main', 'fix')}
expected = {case['id'] for case in manifest['cases']}
assert reference['suiteDigest'] == identity(manifest) and set(reference['cases']) == expected
assert calibration['contract']['referenceDigest'] == identity(reference)
assert {case['id'] for case in calibration['cases']} == expected
calibrated = {case['id']: case for case in calibration['cases']}
builds = {}
for name, capture in captures.items():
    assert {case['id'] for case in capture['cases']} == expected
    assert capture['inspectionManifestSha256'] == digest(run / 'manifest.json')
    record = run / f'{name}-docx-bench-build.json'
    builds[name] = json.loads(record.read_text())
    assert digest(record) == capture['buildIdentitySha256']
    assert builds[name]['commit'] == capture['candidate'] and builds[name]['tree'] == capture['sourceTree']

font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
bold = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 16)
INK, MARGIN, GAP = 231, 24, 16


def rasters(pdf_path, folder):
    shutil.rmtree(folder, ignore_errors=True)
    return bench_pdf.rasterize(pdf_path, folder)


def raster(reference_pages, candidate_pages):
    """The page measurements `bench run` makes, worst page first in importance."""
    pages = []
    for i in range(max(len(reference_pages), len(candidate_pages))):
        if i >= len(reference_pages) or i >= len(candidate_pages):
            pages.append({'score': 0.0, 'unmatched': 'reference' if i >= len(candidate_pages) else 'candidate'})
            continue
        rw, rh, rp = metrics.read_ppm(reference_pages[i])
        cw, ch, cp = metrics.read_ppm(candidate_pages[i])
        if not metrics.canvas_compatible((rw, rh), (cw, ch)):
            pages.append({'score': 0.0, 'dimensionsMismatch': [[rw, rh], [cw, ch]]})
            continue
        width, height = max(rw, cw), max(rh, ch)
        measured = metrics.page_metrics(metrics.union_canvas(rp, rw, rh, width, height),
                                        metrics.union_canvas(cp, cw, ch, width, height), width, height)
        pages.append({key: measured[key] for key in ('score', 'ssim', 'inkF1', 'precision', 'recall', 'close')})
    worst = min(pages, key=lambda page: page['score'])
    return {'pages': pages, 'rasterScore': worst['score'], 'worstPage': pages.index(worst) + 1,
            'close': all(page.get('close', False) for page in pages)}


def ink_box(image):
    return image.convert('RGB').point(lambda v: 255 if v < INK else 0).convert('L').getbbox()


evidence = {'scope': 'Focused unscored public-API diagnostics; no registered candidate score, Word parity or full-suite result',
            'manifestSha256': digest(run / 'manifest.json'), 'referenceBundleSha256': digest(run / 'reference/bundle.json'),
            'referenceRenderer': next(iter(reference['cases'].values()))['renderer'],
            'referenceEnvironment': reference['environment'], 'calibrationResultSha256': digest(run / 'calibration/result.json'),
            'metric': metrics.CONTRACT, 'builds': builds, 'captures': captures, 'cases': []}
for case in manifest['cases']:
    cid = case['id']
    ref = reference['cases'][cid]
    assert ref['inputSha256'] == case['sha256'] and ref['eligible']
    reference_pdf = run / 'reference' / ref['pdf']
    reference_pages = rasters(reference_pdf, run / 'raster' / cid / 'reference')
    calibration_case = calibrated[cid]
    panels = [{'renderer': ref['renderer']['version'].split(' ')[0] + ' ' + ref['renderer']['version'].split(' ')[1] + ' reference',
               'pdf': reference_pdf, 'failures': ref['ineligibleChecks'], 'pages': reference_pages,
               'words': [w['text'] for w in ref['inspection']['words'] if w['text']],
               'measurement': {'calibrationScore': calibration_case['score'], 'close': calibration_case['close']}}]
    for name in ('main', 'fix'):
        record = next(c for c in captures[name]['cases'] if c['id'] == cid)
        assert record['inputSha256'] == case['sha256'] and record['status'] == 'delivered'
        folder = run / f'capture-{name}' / cid
        candidate_pdf = folder / 'candidate.pdf'
        assert digest(candidate_pdf) == record['pdfSha256']
        pages = rasters(candidate_pdf, run / 'raster' / cid / name)
        measured = raster(reference_pages, pages)
        failures = record['mandatoryPdfFailures']
        measured.update(caseScore=0.0 if failures else measured['rasterScore'], close=measured['close'] and not failures)
        panels.append({'renderer': f'Docxodus {name} {captures[name]["candidate"][:8]}', 'pdf': candidate_pdf,
                       'failures': failures, 'pages': pages, 'measurement': measured,
                       'words': [w['text'] for w in json.loads((folder / 'inspection.json').read_text())['words'] if w['text']]})
    images = {id(panel): [Image.open(page).convert('RGB') for page in panel['pages']] for panel in panels}
    size = images[id(panels[0])][0].size
    assert all(image.size == size for group in images.values() for image in group), 'one crop needs one page size'
    boxes = [box for group in images.values() for box in map(ink_box, group) if box]
    crop = (max(0, min(b[0] for b in boxes) - MARGIN), max(0, min(b[1] for b in boxes) - MARGIN),
            min(size[0], max(b[2] for b in boxes) + MARGIN), min(size[1], max(b[3] for b in boxes) + MARGIN))
    columns = max(len(panel['pages']) for panel in panels)
    cell_w, cell_h = crop[2] - crop[0], crop[3] - crop[1]
    row_h = 110 + cell_h + 22
    sheet = Image.new('RGB', (max(24 + columns * (cell_w + GAP), 780), 64 + len(panels) * row_h), '#e9eef3')
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 10), cid, font=bold, fill='#16283b')
    draw.text((12, 34), f'Pages at 96 DPI, cropped to x {crop[0]}-{crop[2]}, y {crop[1]}-{crop[3]} px, '
              'the box around every renderer\'s ink.', font=font, fill='#33475b')
    y = 64
    for panel in panels:
        failures, measured = panel['failures'], panel['measurement']
        draw.text((12, y), panel['renderer'], font=bold, fill='#16283b')
        draw.text((12, y + 22), 'Mandatory PDF checks: ' + ('PASS' if not failures else 'FAIL: ' + ', '.join(failures)),
                  font=font, fill='#21623c' if not failures else '#8b2a15')
        if 'calibrationScore' in measured:
            line = f'LibreOffice calibration: {measured["calibrationScore"]:.2f}' + (', close' if measured['close'] else '')
        else:
            worst = measured['pages'][measured['worstPage'] - 1]
            line = (f'Raster vs LibreOffice: {measured["rasterScore"]:.2f} (page {measured["worstPage"]}: SSIM '
                    f'{worst.get("ssim", 0):.4f}, ink F1 {worst.get("inkF1", 0):.4f}); '
                    + ('close' if measured['close'] else 'not close'))
        draw.text((12, y + 42), line, font=font, fill='#33475b')
        draw.text((12, y + 62), 'Extracted words: ' + ' | '.join(panel['words']), font=font, fill='#33475b')
        for index, image in enumerate(images[id(panel)]):
            x = 12 + index * (cell_w + GAP)
            draw.text((x, y + 84), f'Page {index + 1}', font=font, fill='#33475b')
            sheet.paste(image.crop(crop), (x, y + 104))
        y += row_h
    target = out / (cid + '.png')
    sheet.save(target, optimize=True)
    evidence['cases'].append({'id': cid, 'inputSha256': case['sha256'], 'screenshot': target.name,
        'screenshotSha256': digest(target), 'cropPx': list(crop),
        'panels': [{'renderer': panel['renderer'], 'pdfSha256': digest(panel['pdf']), 'failures': panel['failures'],
                    'words': panel['words'], 'measurement': panel['measurement'],
                    'pageRasterSha256': [digest(page) for page in panel['pages']]} for panel in panels]})
evidence['tools'] = {name: digest(root / name) for name in ['docs/results/export-reliability/Capture.mjs',
    'docs/results/export-reliability/Inspect.py', 'docs/results/split-direction-marks/Compose.py']}
(out / 'evidence.json').write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + '\n')
for entry in evidence['cases']:
    print(entry['id'] + ': ' + '; '.join(
        f"{p['renderer']} {'pass' if not p['failures'] else 'FAIL'} "
        + (f"calibration {p['measurement']['calibrationScore']:.2f}" if 'calibrationScore' in p['measurement']
           else f"raster {p['measurement']['rasterScore']:.2f} case {p['measurement']['caseScore']:.2f} "
                f"{'close' if p['measurement']['close'] else 'not close'}")
        for p in entry['panels']))
