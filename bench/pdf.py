"""Read physical PDF facts through external qpdf and Poppler executables."""
from __future__ import annotations
import json
import math
import re
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
    if word_font_bindings is not None:
        from .word_fonts import qualify
        from .common import ROOT, contained
        info = qualify(path, contained(ROOT, case['input']), info, word_font_bindings,
                       font_contract, case['fonts'])
    return info


def inspect_pdf(path):
    structure = json.loads(execute(['qpdf', '--json=2', '--json-key=pages', '--json-key=qpdf', path]))
    geometry = geometries(structure)
    words = bbox_words(execute(['pdftotext', '-bbox-layout', '-enc', 'UTF-8', path, '-']))
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
            if assertion['type'] == 'same-page':
                anchors = [marker(candidate, m) for m in assertion['markers']]
                passed = len({a['page'] for a in anchors}) == 1
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
