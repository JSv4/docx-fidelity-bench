"""Measure each #1870 case against its LibreOffice reference, label its 96-DPI page rasters, and bind the evidence.

Usage: python3 docs/results/field-links/Compose.py RUN

RUN holds manifest.json, reference/bundle.json (`bench reference libreoffice --manifest`),
calibration/result.json (`bench run --adapter libreoffice` against that bundle), capture-main/
and capture-fix/ (export-reliability Capture.mjs with --html, then Inspect.py) and each build's
identity record copied as main-docx-bench-build.json and fix-docx-bench-build.json.

Each Docxodus PDF is checked and measured against the LibreOffice reference as `bench run` checks
and measures a candidate: `bench.pdf.correctness` for the mandatory checks (the declared colour
geometry is relative to the reference, so Inspect.py, which checks a PDF against itself, cannot
decide it), and Poppler at 96 DPI on the CropBox with `bench.metrics.page_metrics` for the raster,
the worst page for the case. Each delivered HTML file is read with `bench.html_artifacts.check`,
the inspector `bench run` applies to `marker-attribute` declarations. These are diagnostics of a
borrowed browser, not registered candidate scores. The sheets show the same unchanged pixels, every
page of a case cropped to the box around all three renderers' ink plus a margin.
"""
import json
import re
import shutil
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from bench import html_artifacts, metrics, pdf as bench_pdf
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
    assert capture['htmlInspectorSha256'] == digest(root / 'bench/html_browser.mjs')
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
    """The page measurements `bench run` makes, and the worst page."""
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


def shown(words):
    """Extracted words for the sheet, a leader's dots shortened."""
    return ' | '.join('[leader dots]' if re.fullmatch(r'\.{3,}', w) else w for w in words)


evidence = {'scope': 'Focused unscored public-API diagnostics; no registered candidate score, Word parity or full-suite result',
            'manifestSha256': digest(run / 'manifest.json'), 'referenceBundleSha256': digest(run / 'reference/bundle.json'),
            'referenceRenderer': next(iter(reference['cases'].values()))['renderer'],
            'referenceEnvironment': reference['environment'], 'calibrationResultSha256': digest(run / 'calibration/result.json'),
            'metric': metrics.CONTRACT, 'htmlInspectorVersion': html_artifacts.VERSION, 'builds': builds,
            'captures': captures, 'cases': []}
for case in manifest['cases']:
    cid = case['id']
    ref = reference['cases'][cid]
    assert ref['inputSha256'] == case['sha256'] and ref['eligible']
    reference_pdf = run / 'reference' / ref['pdf']
    reference_info = bench_pdf.inspect_case_pdf(reference_pdf, case)
    reference_pages = rasters(reference_pdf, run / 'raster' / cid / 'reference')
    calibration_case = calibrated[cid]
    version = ref['renderer']['version'].split(' ')
    panels = [{'renderer': f'{version[0]} {version[1]} reference', 'pdf': reference_pdf, 'failures': ref['ineligibleChecks'],
               'pages': reference_pages, 'words': [w['text'] for w in reference_info['words'] if w['text']],
               'measurement': {'calibrationScore': calibration_case['score'], 'close': calibration_case['close']}}]
    for name in ('main', 'fix'):
        record = next(c for c in captures[name]['cases'] if c['id'] == cid)
        assert record['inputSha256'] == case['sha256'] and record['status'] == 'delivered'
        folder = run / f'capture-{name}' / cid
        candidate_pdf, candidate_html = folder / 'candidate.pdf', folder / 'candidate.html'
        assert digest(candidate_pdf) == record['pdfSha256'] and digest(candidate_html) == record['htmlSha256']
        candidate_info = bench_pdf.inspect_case_pdf(candidate_pdf, case)
        checks = bench_pdf.correctness(bench_pdf.binding_case(case, 'libreoffice'), reference_info, candidate_info)
        failures = [check['name'] for check in checks if not check['passed']]
        html = html_artifacts.check(candidate_html.read_text(encoding='utf-8'), case['htmlAssertions'])
        pages = rasters(candidate_pdf, run / 'raster' / cid / name)
        measured = raster(reference_pages, pages)
        measured.update(caseScore=0.0 if failures else measured['rasterScore'], close=measured['close'] and not failures)
        colour = next(r for r in candidate_info.get('colorRegions', []))
        panels.append({'renderer': f'Docxodus {name} {captures[name]["candidate"][:8]}', 'pdf': candidate_pdf,
                       'html': candidate_html, 'failures': failures, 'pages': pages, 'measurement': measured,
                       'htmlChecks': html, 'blueInk': colour,
                       'words': [w['text'] for w in candidate_info['words'] if w['text']]})
    panels[0]['blueInk'] = next(r for r in reference_info.get('colorRegions', []))
    images = {id(panel): [Image.open(page).convert('RGB') for page in panel['pages']] for panel in panels}
    size = images[id(panels[0])][0].size
    assert all(image.size == size for group in images.values() for image in group), 'one crop needs one page size'
    boxes = [box for group in images.values() for box in map(ink_box, group) if box]
    crop = (max(0, min(b[0] for b in boxes) - MARGIN), max(0, min(b[1] for b in boxes) - MARGIN),
            min(size[0], max(b[2] for b in boxes) + MARGIN), min(size[1], max(b[3] for b in boxes) + MARGIN))
    columns = max(len(panel['pages']) for panel in panels)
    cell_w, cell_h = crop[2] - crop[0], crop[3] - crop[1]
    width = max(24 + columns * (cell_w + GAP), 1000)
    measure = ImageDraw.Draw(Image.new('RGB', (1, 1)))

    def wrapped(text):
        lines, line = [], ''
        for word in text.split(' '):
            trial = (line + ' ' + word).strip()
            if line and measure.textlength(trial, font=font) > width - 24:
                lines.append(line)
                line = word
            else:
                line = trial
        return lines + [line]

    for panel in panels:
        failures, measured = panel['failures'], panel['measurement']
        lines = [('Mandatory PDF checks: ' + ('PASS' if not failures else 'FAIL: ' + ', '.join(failures)),
                  '#21623c' if not failures else '#8b2a15')]
        if 'calibrationScore' in measured:
            lines.append((f'LibreOffice calibration: {measured["calibrationScore"]:.2f}' +
                          (', close' if measured['close'] else ''), '#33475b'))
        else:
            worst = measured['pages'][measured['worstPage'] - 1]
            lines.append((f'Raster vs LibreOffice: {measured["rasterScore"]:.2f} (page {measured["worstPage"]}: SSIM '
                          f'{worst.get("ssim", 0):.4f}, ink F1 {worst.get("inkF1", 0):.4f}, precision '
                          f'{worst.get("precision", 0):.4f}, recall {worst.get("recall", 0):.4f}); '
                          + ('close' if measured['close'] else 'not close'), '#33475b'))
            links = [f'{c["marker"]} -> {c["actual"] or "no link"}' + ('' if c['passed'] else f' (expected {c["expected"]})')
                     for c in panel['htmlChecks']]
            lines.append(('Delivered HTML links: ' + '; '.join(links),
                          '#21623c' if all(c['passed'] for c in panel['htmlChecks']) else '#8b2a15'))
        blue = panel['blueInk']
        bounds = ', '.join(f'{v:.2f}' for v in blue['boundsPt']) if blue['boundsPt'] else 'none'
        lines.append((f'Hyperlink-style blue (0563C1) ink: bounds {bounds} pt, coverage {blue["coverage"]:.1f} px',
                      '#33475b'))
        lines.append(('Extracted words: ' + shown(panel['words']), '#33475b'))
        panel['lines'] = [(text, colour) for line, colour in lines for text in wrapped(line)]
    heights = [22 + 20 * len(panel['lines']) + 24 + cell_h + 22 for panel in panels]
    sheet = Image.new('RGB', (width, 64 + sum(heights)), '#e9eef3')
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 10), cid, font=bold, fill='#16283b')
    draw.text((12, 34), f'Pages at 96 DPI, cropped to x {crop[0]}-{crop[2]}, y {crop[1]}-{crop[3]} px, '
              'the box around every renderer\'s ink.', font=font, fill='#33475b')
    y = 64
    for panel, height in zip(panels, heights):
        draw.text((12, y), panel['renderer'], font=bold, fill='#16283b')
        for index, (text, colour) in enumerate(panel['lines']):
            draw.text((12, y + 22 + 20 * index), text, font=font, fill=colour)
        top = y + 22 + 20 * len(panel['lines'])
        for index, image in enumerate(images[id(panel)]):
            x = 12 + index * (cell_w + GAP)
            draw.text((x, top), f'Page {index + 1}', font=font, fill='#33475b')
            sheet.paste(image.crop(crop), (x, top + 20))
        y += height
    target = out / (cid + '.png')
    sheet.save(target, optimize=True)
    evidence['cases'].append({'id': cid, 'inputSha256': case['sha256'], 'screenshot': target.name,
        'screenshotSha256': digest(target), 'cropPx': list(crop),
        'panels': [{'renderer': panel['renderer'], 'pdfSha256': digest(panel['pdf']), 'failures': panel['failures'],
                    'words': panel['words'], 'measurement': panel['measurement'], 'blueInk': panel['blueInk'],
                    **({'htmlSha256': digest(panel['html']), 'htmlChecks': panel['htmlChecks']} if 'html' in panel else {}),
                    'pageRasterSha256': [digest(page) for page in panel['pages']]} for panel in panels]})
evidence['tools'] = {name: digest(root / name) for name in ['docs/results/export-reliability/Capture.mjs',
    'docs/results/export-reliability/Inspect.py', 'docs/results/field-links/Compose.py']}
(out / 'evidence.json').write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + '\n')
for entry in evidence['cases']:
    print(entry['id'] + ': ' + '; '.join(
        f"{p['renderer']} {'pass' if not p['failures'] else 'FAIL ' + ','.join(p['failures'])}"
        + (f" calibration {p['measurement']['calibrationScore']:.2f}" if 'calibrationScore' in p['measurement']
           else f" raster {p['measurement']['rasterScore']:.2f} case {p['measurement']['caseScore']:.2f} "
                f"{'close' if p['measurement']['close'] else 'not close'} html "
                f"{sum(c['passed'] for c in p['htmlChecks'])}/{len(p['htmlChecks'])}")
        for p in entry['panels']))
