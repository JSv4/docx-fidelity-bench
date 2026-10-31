"""Read physical PDF facts through external qpdf and Poppler executables."""
from __future__ import annotations
import json
import math
import re
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from .common import WORD_TRACKS, execute

# Unicode bidirectional formatting controls (UAX #9 explicit marks, embeddings, overrides and
# isolates). They steer direction and are invisible, so a renderer that inserts them around LTR
# text in an RTL paragraph has not added or removed a visible word. They are removed from
# comparison text only; each affected word keeps its raw extraction in `raw`.
BIDI_CONTROLS = frozenset('\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069')


def visible_text(text):
    return ''.join(ch for ch in text if ch not in BIDI_CONTROLS)


def geometries(document):
    objects = document['qpdf'][1]
    def resolve(value):
        for _ in range(100):
            if isinstance(value, str) and 'obj:' + value in objects:
                value = objects['obj:' + value]['value']
            else:
                return value
        raise ValueError('Cyclic PDF object reference')
    def inherited(page, key, default=None):
        visited = set()
        for _ in range(100):
            page = resolve(page)
            if not isinstance(page, dict):
                raise ValueError('Invalid PDF page dictionary')
            if key in page:
                return resolve(page[key])
            parent = page.get('/Parent')
            if parent is None:
                return default
            if parent in visited:
                raise ValueError('Cyclic PDF page tree')
            visited.add(parent)
            page = parent
        raise ValueError('Excessive PDF page inheritance')
    result = []
    for item in document['pages']:
        page = item['object']
        media = inherited(page, '/MediaBox')
        crop = inherited(page, '/CropBox', media)
        rotation = inherited(page, '/Rotate', 0)
        unit = resolve(resolve(page).get('/UserUnit', 1))
        if not isinstance(unit, (float, int)) or not math.isfinite(unit) or unit <= 0 or rotation % 90:
            raise ValueError('Invalid PDF rotation or UserUnit')
        boxes = []
        for box in (media, crop):
            box = resolve(box)
            if not isinstance(box, list) or len(box) != 4 or any(not isinstance(n, (int, float)) or not math.isfinite(n) for n in box) or box[2] <= box[0] or box[3] <= box[1]:
                raise ValueError('Invalid physical page box')
            boxes.append([n * unit for n in box])
        result.append({'media': boxes[0], 'crop': boxes[1], 'rotation': rotation % 360, 'userUnit': unit})
    if not result:
        raise ValueError('PDF contains no pages')
    return result


PDF_TEXT_POLICIES = frozenset({'isolated-dot-leaders-v1'})
PDF_TEXT_POLICY_VERSION = 1


def normalize_text(info, policy):
    """Keep raw words/geometry and omit declared isolated leader glyphs from token counts only.

    Never split a word, infer coordinates, or change the raster. Glued leader/content words remain
    ordinary words and fail the exact inventory. Source validation forbids authored ellipses under
    this opt-in policy, so an authored punctuation word cannot disappear as decoration.
    """
    if policy is None:
        return info
    if not isinstance(policy, str) or policy not in PDF_TEXT_POLICIES:
        raise ValueError('Unknown PDF text normalization policy')
    decorative = [w for w in info['words'] if re.fullmatch(r'\.{3,}', w['text'])]
    tokens = dict(Counter(w['text'] for w in info['words']
                          if w['text'] and not re.fullmatch(r'\.{3,}', w['text'])))
    return dict(info, tokens=tokens, decorativeWords=decorative, pdfTextNormalization=policy)


def inspect_case_pdf(path, case, *, word_font_bindings=None, font_contract=None):
    info = normalize_text(inspect_pdf(path), case.get('pdfTextNormalization'))
    declarations = [a for a in case.get('assertions', []) if a['type'] in ('color-reference-geometry', 'color-geometry')]
    if declarations:
        from .metrics import read_ppm
        with tempfile.TemporaryDirectory(prefix='bench-color-') as folder:
            pages = rasterize(path, folder)
            info['colorRegions'] = []
            for declaration in declarations:
                page = declaration['page']
                observed = {'page': page, 'rgb': declaration['rgb'], 'boundsPt': None, 'coverage': 0}
                if page <= len(pages):
                    observed.update(color_region(*read_ppm(pages[page - 1]), declaration['rgb']))
                info['colorRegions'].append(observed)
    if word_font_bindings is not None:
        from .word_fonts import qualify
        from .common import ROOT, contained
        info = qualify(path, contained(ROOT, case['input']), info, word_font_bindings,
                       font_contract, case['fonts'])
    return info


def color_region(width, height, pixels, rgb):
    """Measure only the declared ink blended over white, including antialias coverage.

    Channel agreement rejects black text and unrelated colors. Bounds stay in the unshifted
    96-DPI CropBox coordinate system; no candidate diagnostics or image-resource counts are used.
    """
    xs, ys, coverage = [], [], 0.0
    for index in range(width * height):
        sample = pixels[index * 3:index * 3 + 3]
        if sample[0] == sample[1] == sample[2]: continue
        alpha = [(255 - sample[c]) / (255 - rgb[c]) for c in range(3)]
        amount = sum(alpha) / 3
        if amount < 0.05 or max(alpha) - min(alpha) > 0.015 or amount > 1.015:
            continue
        xs.append(index % width); ys.append(index // width); coverage += min(1, amount)
    return {'boundsPt': [min(xs) * .75, min(ys) * .75, (max(xs) + 1) * .75, (max(ys) + 1) * .75] if xs else None,
            'coverage': coverage}


def color_geometry_pass(declaration, reference, candidate):
    def observation(info):
        matches = [r for r in info.get('colorRegions', []) if r['page'] == declaration['page'] and r['rgb'] == declaration['rgb']]
        return matches[0] if len(matches) == 1 else None
    r = declaration if declaration['type'] == 'color-geometry' else observation(reference)
    c = observation(candidate)
    if not r or not c or not r['boundsPt'] or not c['boundsPt'] or r['coverage'] <= 0 or c['coverage'] <= 0:
        return False
    return (all(abs(a - b) <= declaration['tolerancePt'] for a, b in zip(r['boundsPt'], c['boundsPt'])) and
            abs(c['coverage'] / r['coverage'] - 1) <= declaration['coverageTolerance'])


def inspect_pdf(path, crop_box=False):
    structure = json.loads(execute(['qpdf', '--json=2', '--json-key=pages', '--json-key=qpdf', path]))
    geometry = geometries(structure)
    words = bbox_words(execute(['pdftotext', *(['-cropbox'] if crop_box else []), '-bbox-layout', '-enc', 'UTF-8', path, '-']))
    fonts_output = execute(['pdffonts', path])
    font_lines = fonts_output.splitlines()[2:]
    fonts = [line.split()[0].split('+')[-1] for line in font_lines if line.strip()]
    return {'geometry': geometry, 'words': words, 'tokens': dict(Counter(w['text'] for w in words if w['text'])), 'fonts': fonts}


def bbox_words(xml):
    words = []
    for page_no, page in enumerate(ET.fromstring(xml).iter('{http://www.w3.org/1999/xhtml}page'), 1):
        for word in page.iter('{http://www.w3.org/1999/xhtml}word'):
            raw = ''.join(word.itertext())
            entry = {'text': visible_text(raw), 'page': page_no, 'rect': [float(word.get(k)) for k in ('xMin', 'yMin', 'xMax', 'yMax')]}
            if entry['text'] != raw:
                entry['raw'] = raw
            words.append(entry)
    return words


def rasterize(pdf, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    execute(['pdftoppm', '-r', '96', '-cropbox', pdf, folder / 'page'], timeout=180)
    paths = sorted(folder.glob('page-*.ppm'), key=lambda p: int(p.stem.split('-')[-1]))
    if not paths:
        raise ValueError('Rasterizer produced no pages')
    return paths


def font_check(info, families):
    allowed = [family.replace(' ', '').lower() for family in families]
    bindings = info.get('verifiedWordFontBindings', {})
    return bool(info['fonts']) and all(
        any(font.replace('-', '').lower().startswith(family) for family in allowed) or
        bindings.get(font, {}).get('family', '').replace(' ', '').lower() in allowed
        for font in info['fonts'])


def inventory_check(info, case):
    optional = case.get('clippedTokens', {})
    return ({word: count for word, count in info['tokens'].items() if word not in optional} == case['tokens']
            and all(0 <= info['tokens'].get(word, 0) <= count for word, count in optional.items()))


def marker(info, text, occurrence=1):
    matches = [w for w in info['words'] if w['text'] == text]
    if len(matches) != occurrence or occurrence != 1:
        raise ValueError(f'Marker {text!r} must occur exactly once, found {len(matches)}')
    return matches[0]


def binding_case(case, track, reproduces_reference=False):
    """The case as it binds a capture on `track`.

    An assertion marked `"adjudicated": "word"` records layout measured in Word reference PDFs that
    LibreOffice is known not to follow. It binds every candidate and every Word reference. It does
    not bind a LibreOffice capture: neither when deciding a LibreOffice reference's eligibility, nor
    when LibreOffice itself is measured against a LibreOffice track as a calibration
    (`reproduces_reference`).
    """
    if track in WORD_TRACKS or not reproduces_reference:
        return case
    return dict(case, assertions=[a for a in case['assertions'] if a.get('adjudicated') != 'word'])


def reference_failures(case, info, track='libreoffice'):
    """Name every mandatory check a reference capture fails against its own declaration.

    A reference is measured as its own candidate: its visible tokens, fonts and declared feature
    assertions must hold. Reference-relative positions are trivially satisfied; absolute regions
    and same-page groups are not, so a capture that violates the fixture's declared layout is
    ineligible rather than the standard every candidate is judged against. Word-adjudicated
    assertions apply only on Word tracks (see `binding_case`).
    """
    case = binding_case(case, track, reproduces_reference=True)
    return [check['name'] for check in correctness(case, info, info) if not check['passed']]


def inspect_companion_pdf(path, declaration):
    """Bind dark source-word extraction to paint in the same physical-page raster."""
    from . import metrics
    info = inspect_pdf(path, crop_box=True)
    with tempfile.TemporaryDirectory(dir=Path(path).parent) as folder:
        rasters = rasterize(path, folder)
        if len(rasters) != len(info['geometry']):
            raise ValueError('Companion PDF raster page coverage differs')
        for page, raster in enumerate(rasters, 1):
            width, height, pixels = metrics.read_ppm(raster)
            # These declarations require dark source text. A pale note/highlight fill is
            # nonwhite but cannot stand in for a printed glyph; require all RGB channels dark.
            ink = bytearray(int(max(pixels[i:i+3]) < 160) for i in range(0, len(pixels), 3))
            for word in info['words']:
                if word['page'] != page or word['text'] not in declaration['requiredTokens']: continue
                x0, y0, x1, y1 = [n * 96 / 72 for n in word['rect']]
                word['inkPixels'] = sum(ink[y * width + x] for y in range(max(0, math.floor(y0)), min(height, math.ceil(y1)))
                                        for x in range(max(0, math.floor(x0)), min(width, math.ceil(x1))))
    return info


def companion_checks(declaration, info):
    """Check authored source text in a second print profile, without a layout reference.

    Renderer-generated labels may differ; every declared source token must occur exactly as
    often as authored and have positive bounds wholly within its physical PDF CropBox.
    """
    required = declaration['requiredTokens']
    words = [w for w in info['words'] if w['text'] in required]
    observed = Counter(w['text'] for w in (info['words'] if declaration.get('exactInventory') else words))
    outside = []
    for word in words:
        geometry = info['geometry'][word['page'] - 1]
        page = geometry['crop']
        x0, y0, x1, y1 = word['rect']
        width, height = page[2] - page[0], page[3] - page[1]
        if geometry.get('rotation', 0) % 180: width, height = height, width
        if not (0 <= x0 < x1 <= width + .25 and 0 <= y0 < y1 <= height + .25):
            outside.append(word)
    box = [0, 0, *declaration['pageSizePt']]
    paper_matches = bool(info['geometry']) and all(g.get('rotation', 0) == 0 and all(
        len(g[k]) == 4 and all(abs(a - b) <= .25 for a, b in zip(g[k], box)) for k in ('media', 'crop'))
        for g in info['geometry'])
    return [{'name': 'companion-pdf-paper-geometry', 'passed': paper_matches, 'expected': box},
            {'name': 'companion-pdf-source-tokens', 'passed': observed == required,
             'missing': dict(Counter(required) - observed), 'extra': dict(observed - Counter(required))},
            {'name': 'companion-pdf-source-bounds', 'passed': not outside, 'outside': outside},
            {'name': 'companion-pdf-source-paint', 'passed': bool(words) and all(w.get('inkPixels', 0) > 0 for w in words),
             'unpainted': [w for w in words if w.get('inkPixels', 0) <= 0]}]


def correctness(case, reference, candidate):
    checks = [{'name': 'page-count', 'passed': len(reference['geometry']) == len(candidate['geometry'])}, {'name': 'expected-visible-tokens', 'passed': inventory_check(candidate, case), 'missing': dict(Counter(case['tokens']) - Counter(candidate['tokens'])), 'extra': dict(Counter(candidate['tokens']) - Counter(case['tokens'])), 'normalizedRaw': dict(Counter(w['raw'] for w in candidate['words'] if 'raw' in w))}, {'name': 'declared-font-families', 'passed': font_check(candidate, case['fonts']), 'observed': candidate['fonts']}]
    if case.get('clippedTokens'):
        checks[1]['clippedTokens'] = case['clippedTokens']
        checks[1]['observedClippedTokens'] = {word: candidate['tokens'].get(word, 0) for word in case['clippedTokens']}
        checks[1]['extra'] = dict(Counter(candidate['tokens']) - Counter(case['tokens']) - Counter(case['clippedTokens']))
    if case.get('pdfTextNormalization'):
        checks[1]['decorativeWords'] = candidate.get('decorativeWords', [])
        checks.append({'name': 'declared-pdf-text-normalization',
                       'passed': candidate.get('pdfTextNormalization') == case['pdfTextNormalization']})
    for i in range(max(len(reference['geometry']), len(candidate['geometry']))):
        passed = i < len(reference['geometry']) and i < len(candidate['geometry'])
        if passed:
            r, c = reference['geometry'][i], candidate['geometry'][i]
            passed = r['rotation'] == c['rotation'] and all(abs(a - b) <= 0.25 for name in ('media', 'crop') for a, b in zip(r[name], c[name]))
        checks.append({'name': f'physical-geometry-page-{i+1}', 'passed': passed})
    for assertion in case['assertions']:
        try:
            if assertion['type'] in ('color-reference-geometry', 'color-geometry'):
                passed = color_geometry_pass(assertion, reference, candidate)
            elif assertion['type'] == 'same-page':
                anchors = [marker(candidate, m) for m in assertion['markers']]
                passed = len({a['page'] for a in anchors}) == 1
            elif assertion['type'] == 'non-overlapping-markers':
                first, second = [marker(candidate, label) for label in assertion['markers']]
                for word in (first, second):
                    rect = word['rect']
                    if (not isinstance(rect, list) or len(rect) != 4 or
                            any(type(n) not in (int, float) or not math.isfinite(n) for n in rect) or
                            rect[2] <= rect[0] or rect[3] <= rect[1] or type(word['page']) is not int or
                            not 1 <= word['page'] <= len(candidate['geometry'])):
                        raise ValueError('Marker separation requires finite positive bounds on a physical page')
                passed = first['page'] != second['page'] or any(
                    min(first['rect'][axis + 2], second['rect'][axis + 2]) -
                    max(first['rect'][axis], second['rect'][axis]) <= assertion['tolerancePt'] for axis in (0, 1))
            elif assertion['type'] == 'marker-reference-position':
                a = marker(candidate, assertion['marker'])
                expected = marker(reference, assertion['marker'])
                tolerance = assertion['tolerancePt']
                passed = a['page'] == expected['page'] and all(abs(x - y) <= tolerance for x, y in zip(a['rect'][:2], expected['rect'][:2]))
            else:
                a = marker(candidate, assertion['marker'], assertion['occurrence'])
                expected_page = marker(reference, assertion['marker'])['page'] if assertion['page'] == 'reference' else assertion['page']
                l, t, r, b = assertion['rect']
                x, y, xx, yy = a['rect']
                tolerance = assertion['tolerancePt'] if assertion['version'] == 2 else 0
                passed = a['page'] == expected_page and l - tolerance <= x <= xx <= r + tolerance and t - tolerance <= y <= yy <= b + tolerance
            checks.append({'name': 'assertion-' + assertion['type'], 'passed': passed, 'declaration': assertion})
        except ValueError as error:
            checks.append({'name': 'assertion-' + assertion['type'], 'passed': False, 'error': str(error), 'declaration': assertion})
    return checks
