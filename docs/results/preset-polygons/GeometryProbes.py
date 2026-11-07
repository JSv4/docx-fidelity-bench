"""Supplementary source-positioned paint probes, separate from benchmark metrics.

The literal expectations were checked against the published preset guide paths,
independently of Docxodus, and calibrated against native LibreOffice PDFs.
Coordinates use the authored 73 x 41pt shape frame, not detected paint bounds.
"""
import subprocess
import tempfile
from pathlib import Path
from PIL import Image

TRIANGLE_POINTS = [(.3, .25), (.45, .25), (.6, .25), (.7, .25), (.2, .8), (.8, .8)]
STAR_POINTS = [(.25, .25), (.5, .12), (.75, .25), (.15, .4), (.85, .4),
               (.5, .5), (.5, .85), (.3, .7), (.7, .7)]
TEAL, COPPER = [46, 123, 115], [180, 106, 62]


def declarations(case_id):
    kind = case_id.removeprefix('preset-polygon-')
    if kind == 'rectangle-control':
        return [(90 + 73 * x, 144 + 41 * y, TEAL, True) for x, y in TRIANGLE_POINTS]
    groups = []
    if kind.startswith('triangle') or kind in ('group', 'nested-group'):
        expected = ([False, True, True, False, True, True] if kind == 'triangle' else
                    [False, False, True, True, True, True] if kind == 'triangle-flipped' else
                    [True, True, False, False, True, True])
        groups.append((90, 144, TEAL, TRIANGLE_POINTS, expected))
    if kind.startswith('star') or kind in ('group', 'nested-group'):
        grouped = kind in ('group', 'nested-group')
        expected = [False, True, False, True, True, True, False,
                    kind != 'star-adjusted', kind != 'star-adjusted']
        groups.append((180 if grouped else 90, 164 if grouped else 144,
                       COPPER if grouped else TEAL, STAR_POINTS, expected))
    assert groups, case_id
    return [(left + 73 * x, top + 41 * y, rgb, filled)
            for left, top, rgb, points, expected in groups
            for (x, y), filled in zip(points, expected)]


def inspect(pdf, case_id):
    # 288 DPI gives four samples per point. The 3x3 patch avoids a single-pixel oracle.
    with tempfile.TemporaryDirectory() as scratch:
        prefix = Path(scratch) / 'page'
        subprocess.run(['pdftoppm', '-f', '1', '-singlefile', '-r', '288', '-png',
                        str(pdf), str(prefix)], check=True, capture_output=True)
        with Image.open(prefix.with_suffix('.png')) as image:
            image = image.convert('RGB')
            results = []
            for x, y, rgb, expected in declarations(case_id):
                px, py = round(x * 4), round(y * 4)
                pixels = [image.getpixel((px + dx, py + dy)) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
                colored = sum(max(abs(a - b) for a, b in zip(p, rgb)) <= 16 for p in pixels)
                empty = sum(min(p) >= 245 for p in pixels)
                passed = colored >= 7 if expected else empty >= 7
                results.append(dict(pointPt=[x, y], rgb=rgb, expectedFill=expected,
                                    coloredPixels=colored, whitePixels=empty, passed=passed))
            return results
