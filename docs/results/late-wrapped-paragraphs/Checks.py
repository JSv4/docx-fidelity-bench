"""Source frames for later Chive pictures; reuse the frozen all-page paint checks."""
import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

shared = Path(__file__).resolve().parent.parent / 'floating-paragraphs' / 'Checks.py'
spec = importlib.util.spec_from_file_location('floating_picture_checks', shared)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
inspect_picture_ink, picture_checks = module.inspect_picture_ink, module.picture_checks
W, WP = module.W, module.WP


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
            alignment = horizontal.find(WP + 'align')
            if alignment is not None:
                assert alignment.text == 'right'
                x = 348
            else:
                x = 36 + int(horizontal.find(WP + 'posOffset').text) / 12700
            y = 36 + (preceding_lines % 29 * 18 if page == preceding_lines // 29 + 1 else 0)
            frames.append(dict(page=page, rect=[x, y, x + 48, y + 48]))
        preceding_lines += line + 1
    return frames
