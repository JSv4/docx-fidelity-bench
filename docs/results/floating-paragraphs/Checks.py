"""Literal source frames and independently painted picture checks for the Chive cases."""
import math
import tempfile
import xml.etree.ElementTree as ET
from zipfile import ZipFile

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
WP = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'


def inspect_picture_ink(path, info, frames):
    from bench.pdf import rasterize, color_region
    from bench.metrics import read_ppm
    with tempfile.TemporaryDirectory(prefix='chive-pictures-') as folder:
        pages = rasterize(path, folder)
        info['colorRegions'], info['pictureFrames'], info['pictureOutsideCoverage'] = [], [], []
        for index, page in enumerate(pages, 1):
            width, height, pixels = read_ppm(page)
            whole = color_region(width, height, pixels, [38, 102, 144])
            info['colorRegions'].append(dict(page=index, rgb=[38, 102, 144], **whole))
            covered = 0
            for frame in (f for f in frames if f['page'] == index):
                x, y, right, bottom = frame['rect']
                # The authored squares are disjoint. One point around each edge retains
                # the existing raster tolerance while isolating each picture's footprint.
                left, top = max(0, math.floor((x - 1) / .75)), max(0, math.floor((y - 1) / .75))
                right, bottom = min(width, math.ceil((right + 1) / .75)), min(height, math.ceil((bottom + 1) / .75))
                crop = b''.join(pixels[(row * width + left) * 3:(row * width + right) * 3] for row in range(top, bottom))
                region = color_region(right - left, bottom - top, crop, [38, 102, 144])
                if region['boundsPt']:
                    region['boundsPt'] = [v + (left if axis % 2 == 0 else top) * .75 for axis, v in enumerate(region['boundsPt'])]
                info['pictureFrames'].append(dict(page=index, **region)); covered += region['coverage']
            info['pictureOutsideCoverage'].append(dict(page=index, coverage=max(0, whole['coverage'] - covered)))
    return info


def source_frames(path):
    with ZipFile(path) as package:
        document = ET.fromstring(package.read('word/document.xml'))
        styles = ET.fromstring(package.read('word/styles.xml'))
    paper = document.find('.//' + W + 'pgSz')
    assert [int(paper.get(W + k)) / 20 for k in ('w', 'h')] == [432, 594]
    margin = document.find('.//' + W + 'pgMar')
    assert all(margin.get(W + k) == '720' for k in ('top', 'right', 'bottom', 'left'))
    spacing = styles.find('.//' + W + 'spacing')
    assert spacing.get(W + 'lineRule') == 'exact' and spacing.get(W + 'line') == '360'
    assert spacing.get(W + 'before') == spacing.get(W + 'after') == '0'
    frames, preceding_lines = [], 0
    for paragraph in document.find(W + 'body').findall(W + 'p'):
        line = 0
        for element in paragraph.iter():
            if element.tag == W + 'br': line += 1
            if element.tag != WP + 'anchor': continue
            horizontal, vertical = element.find(WP + 'positionH'), element.find(WP + 'positionV')
            assert horizontal.get('relativeFrom') == 'column' and vertical.get('relativeFrom') == 'paragraph'
            assert vertical.find(WP + 'posOffset').text == '0'
            extent = element.find(WP + 'extent')
            assert extent.get('cx') == extent.get('cy') == '609600'
            page = (preceding_lines + line) // 29 + 1
            x = 36 + int(horizontal.find(WP + 'posOffset').text) / 12700
            y = 36 + (preceding_lines % 29 * 18 if page == preceding_lines // 29 + 1 else 0)
            frames.append(dict(page=page, rect=[x, y, x + 48, y + 48]))
        preceding_lines += line + 1
    return frames


def picture_checks(frames, info, html=None):
    pages = list(range(1, len(info['geometry']) + 1))
    checks = [dict(name='picture-ink-page-inventory', passed=
        [r['page'] for r in info.get('colorRegions', []) if r['rgb'] == [38, 102, 144]] == pages)]
    painted_frames = info.get('pictureFrames', [])
    checks.append(dict(name='picture-footprint-count', passed=len(painted_frames) == len(frames)))
    for index, (expected, observed) in enumerate(zip(frames, painted_frames)):
        bounds = observed.get('boundsPt')
        checks.append(dict(name=f'picture-footprint-{index + 1}', passed=observed['page'] == expected['page']
            and bool(bounds) and len(bounds) == 4 and all(math.isfinite(v) and abs(v - target) <= 1
            for v, target in zip(bounds, expected['rect'])) and abs(observed.get('coverage', 0) / 4096 - 1) <= .04))
    outside = info.get('pictureOutsideCoverage', [])
    checks.append(dict(name='no-picture-ink-outside-frames', passed=[r['page'] for r in outside] == pages
        and all(math.isfinite(r['coverage']) and 0 <= r['coverage'] <= .01 for r in outside)))
    for page in pages:
        on_page = [f['rect'] for f in frames if f['page'] == page]
        regions = [r for r in info.get('colorRegions', []) if r['page'] == page and r['rgb'] == [38, 102, 144]]
        observed = regions[0] if len(regions) == 1 else {}
        actual = observed.get('boundsPt')
        if not on_page:
            checks.append(dict(name=f'no-picture-ink-page-{page}', passed=len(regions) == 1
                and actual is None and observed.get('coverage') == 0))
            continue
        bounds = [min(r[0] for r in on_page), min(r[1] for r in on_page),
                  max(r[2] for r in on_page), max(r[3] for r in on_page)]
        coverage = len(on_page) * 64 * 64  # Disjoint 48pt squares at 96 DPI.
        checks.append(dict(name=f'picture-ink-page-{page}', passed=bool(actual) and len(actual) == 4
            and all(math.isfinite(v) and abs(v - expected) <= 1 for v, expected in zip(actual, bounds))
            and abs(observed.get('coverage', 0) / coverage - 1) <= .04))
    if html is not None:
        checks.append(dict(name='html-picture-count', passed=len(html) == len(frames)))
        for index, (expected, actual) in enumerate(zip(frames, html)):
            checks.append(dict(name=f'html-picture-{index + 1}', passed=actual['page'] == expected['page']
                and len(actual['rect']) == 4 and all(math.isfinite(v) and abs(v - target) <= .1
                for v, target in zip(actual['rect'], expected['rect']))))
    return checks
