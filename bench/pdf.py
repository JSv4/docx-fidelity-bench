"""Read physical PDF facts through external qpdf and Poppler executables."""
from __future__ import annotations
import json
import math
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from .common import execute


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


def inspect_pdf(path):
    structure = json.loads(execute(['qpdf', '--json=2', '--json-key=pages', '--json-key=qpdf', path]))
    geometry = geometries(structure)
    xml = execute(['pdftotext', '-bbox-layout', '-enc', 'UTF-8', path, '-'])
    words = []
    for page_no, page in enumerate(ET.fromstring(xml).iter('{http://www.w3.org/1999/xhtml}page'), 1):
        for word in page.iter('{http://www.w3.org/1999/xhtml}word'):
            words.append({'text': ''.join(word.itertext()), 'page': page_no, 'rect': [float(word.get(k)) for k in ('xMin', 'yMin', 'xMax', 'yMax')]})
    fonts_output = execute(['pdffonts', path])
    font_lines = fonts_output.splitlines()[2:]
    fonts = [line.split()[0].split('+')[-1] for line in font_lines if line.strip()]
    return {'geometry': geometry, 'words': words, 'tokens': dict(Counter(w['text'] for w in words)), 'fonts': fonts}


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
    return bool(info['fonts']) and all(any(font.replace('-', '').lower().startswith(family) for family in allowed) for font in info['fonts'])


def inventory_check(info, case):
    return info['tokens'] == case['tokens']


def marker(info, text, occurrence=1):
    matches = [w for w in info['words'] if w['text'] == text]
    if len(matches) != occurrence or occurrence != 1:
        raise ValueError(f'Marker {text!r} must occur exactly once, found {len(matches)}')
    return matches[0]


def correctness(case, reference, candidate):
    checks = [{'name': 'page-count', 'passed': len(reference['geometry']) == len(candidate['geometry'])}, {'name': 'expected-visible-tokens', 'passed': inventory_check(candidate, case), 'missing': dict(Counter(case['tokens']) - Counter(candidate['tokens'])), 'extra': dict(Counter(candidate['tokens']) - Counter(case['tokens']))}, {'name': 'declared-font-families', 'passed': font_check(candidate, case['fonts']), 'observed': candidate['fonts']}]
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
            else:
                a = marker(candidate, assertion['marker'], assertion['occurrence'])
                expected_page = marker(reference, assertion['marker'])['page'] if assertion['page'] == 'reference' else assertion['page']
                l, t, r, b = assertion['rect']
                x, y, xx, yy = a['rect']
                passed = a['page'] == expected_page and l <= x <= xx <= r and t <= y <= yy <= b
            checks.append({'name': 'assertion-' + assertion['type'], 'passed': passed, 'declaration': assertion})
        except ValueError as error:
            checks.append({'name': 'assertion-' + assertion['type'], 'passed': False, 'error': str(error), 'declaration': assertion})
    return checks
