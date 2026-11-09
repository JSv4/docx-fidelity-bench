"""Check glyph dimensions and total pages independently of region containment."""
import math
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from bench.common import ROOT


def failures(case, info):
    w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    with ZipFile(ROOT / case['input']) as package:
        source = ET.fromstring(package.read('word/document.xml'))
    result = []
    if len(info['geometry']) != max(a['page'] for a in case['assertions']):
        result.append('total-pages')
    for run in source.findall('.//' + w + 'r'):
        label = run.find(w + 't').text.strip()
        size = int(run.find(w + 'rPr/' + w + 'sz').get(w + 'val')) / 2
        words = [word for word in info['words'] if word['text'] == label]
        if len(words) != 1:
            result.append('glyph-inventory:' + label)
            continue
        x0, y0, x1, y1 = words[0]['rect']
        width, height = x1 - x0, y1 - y0
        if not (math.isfinite(width + height) and abs(width - 10467 / 2048 * size) <= .1
                and abs(height - 2268 / 2048 * size) <= .1):
            result.append('glyph-dimensions:' + label)
    return result
