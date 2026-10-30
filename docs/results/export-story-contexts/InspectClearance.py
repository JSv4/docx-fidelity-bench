"""Check the four authored rectangle bounds in unchanged 96-DPI candidate rasters."""
import hashlib
import json
from pathlib import Path
import sys
from PIL import Image

folder = Path(sys.argv[1])
capture = json.loads((folder / 'inspected.json').read_text())
cases = {case['id']: case for case in capture['cases']}
record = {'schema': 1, 'status': 'unscored-authored-rectangle-geometry', 'source': capture['candidate'],
          'rasterDpi': 96, 'tolerancePixels': 2,
          'toolSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'method': 'Bounding box of exact authored fill RGB(220,233,210) in the unchanged page raster. Compares 135pt width, 64/430pt height, column 2pt plus 50pt margin, 40pt top. Outline and pixel rounding allow 2 pixels. No image alignment or scoring change.',
          'cases': []}
for behind in ('front', 'behind'):
    for tall in (False, True):
        cid = 'export-story-context-shape-clearance-' + behind + ('-oversized' if tall else '-fitting-control')
        pdf, raster = folder / cid / 'candidate.pdf', folder / cid / 'page-1.png'
        if hashlib.sha256(pdf.read_bytes()).hexdigest() != cases[cid]['pdfSha256']:
            raise ValueError('Changed captured PDF: ' + cid)
        with Image.open(raster).convert('RGB') as image:
            points = [(x, y) for y in range(image.height) for x in range(image.width)
                      if image.getpixel((x, y)) == (220, 233, 210)]
        if not points:
            raise ValueError('Authored fill is absent: ' + cid)
        xs, ys = zip(*points)
        bounds = [min(xs), min(ys), max(xs) + 1, max(ys) + 1]
        observed = [bounds[0], bounds[1], bounds[2] - bounds[0], bounds[3] - bounds[1]]
        expected = [52 * 96 / 72, 40 * 96 / 72, 135 * 96 / 72, (430 if tall else 64) * 96 / 72]
        record['cases'].append({'id': cid, 'rasterSha256': hashlib.sha256(raster.read_bytes()).hexdigest(),
                                'fillBoundsPixels': bounds, 'observedOriginSizePixels': observed,
                                'authoredOriginSizePixels': expected,
                                'passed': all(abs(actual - wanted) <= 2 for actual, wanted in zip(observed, expected))})
Path(__file__).with_name('clearance-geometry.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record['cases'], indent=2))
