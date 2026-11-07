"""Source-positioned probes supplement area/bounds checks without changing benchmark metrics.

Coordinates below are in the independently authored 600 x 400 path space. Samples
stay away from curve edges. Same-winding holes document LibreOffice's even/odd
policy; they do not establish Word equivalence.
"""
import subprocess
import tempfile
from pathlib import Path
from PIL import Image

BLUE, COPPER = [48, 102, 144], [186, 96, 58]
TRIANGLE = [(210, 90, True), (470, 90, False), (90, 300, True), (510, 300, False), (300, 320, True)]
QUADRATIC = [(150, 180, True), (450, 145, False), (300, 130, True), (300, 70, False), (300, 330, True)]
CUBIC = [(300, 230, True), (300, 80, False), (120, 280, True), (500, 150, False), (300, 350, False)]
HOLE = [(80, 200, True), (300, 80, True), (300, 200, False), (500, 200, True), (300, 330, True)]


def declarations(case_id):
    kind = case_id.removeprefix('custom-path-')
    frame = lambda samples, rgb=BLUE, left=106, top=168, width=113, height=67: [
        (left + x * width / 600, top + y * height / 400, rgb, filled) for x, y, filled in samples]
    if kind == 'rectangle-control':
        return frame([(x, y, True) for x, y, _ in TRIANGLE])
    if kind == 'invisible-control':
        return frame([(x, y, False) for x, y, _ in TRIANGLE])
    if kind in ('hole', 'same-winding-hole'):
        return frame(HOLE)
    if kind == 'flipped':
        return frame([(600 - x, 400 - y, filled) for x, y, filled in TRIANGLE])
    if kind == 'group':
        return frame(TRIANGLE) + frame(CUBIC, COPPER, 231, 198, 100, 60)
    if kind == 'multiple':
        return frame(TRIANGLE) + frame([(300, 200, True)], COPPER)
    if kind == 'open-stroke':
        return frame([(100, 104, True), (300, 200, True), (500, 296, True), (300, 240, False)], COPPER)
    return frame({'polygon': TRIANGLE, 'quadratic': QUADRATIC, 'cubic': CUBIC}[kind])


def inspect(pdf, case_id):
    with tempfile.TemporaryDirectory() as scratch:
        prefix = Path(scratch) / 'page'
        subprocess.run(['pdftoppm', '-f', '1', '-singlefile', '-r', '288', '-png', str(pdf), str(prefix)],
                       check=True, capture_output=True)
        with Image.open(prefix.with_suffix('.png')) as image:
            image = image.convert('RGB')
            results = []
            for x, y, rgb, expected in declarations(case_id):
                px, py = round(x * 4), round(y * 4)
                pixels = [image.getpixel((px + dx, py + dy)) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
                colored = sum(max(abs(a - b) for a, b in zip(p, rgb)) <= 16 for p in pixels)
                empty = sum(min(p) >= 245 for p in pixels)
                results.append(dict(pointPt=[x, y], rgb=rgb, expectedFill=expected, coloredPixels=colored,
                                    whitePixels=empty, passed=colored >= 7 if expected else empty >= 7))
            if case_id == 'custom-path-invisible-control':
                region = image.crop((106 * 4, 168 * 4, 219 * 4, 235 * 4))
                unexpected = sum(min(pixel) < 245 for pixel in region.getdata())
                results.append(dict(regionPt=[106, 168, 219, 235], expectedFill=False,
                                    unexpectedPixels=unexpected, passed=unexpected == 0))
            return results
