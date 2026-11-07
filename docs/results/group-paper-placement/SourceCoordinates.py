"""Independently check the literal, unrotated coordinates of the authored Sedge fixtures."""
from fractions import Fraction
from zipfile import ZipFile
import xml.etree.ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
WP = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
WPS = '{http://schemas.microsoft.com/office/word/2010/wordprocessingShape}'
WPG = '{http://schemas.microsoft.com/office/word/2010/wordprocessingGroup}'


def verify(path, case):
    with ZipFile(path) as package:
        root = ET.fromstring(package.read('word/document.xml'))
        styles = ET.fromstring(package.read('word/styles.xml'))
    section, = root.iter(W + 'sectPr')
    assert section.find(W + 'pgSz').attrib == {W + 'w': '12240', W + 'h': '15840'}
    assert section.find(W + 'pgMar').attrib == {W + name: value for name, value in
        [('top', '1200'), ('right', '1200'), ('bottom', '1200'), ('left', '1200'), ('header', '240'), ('footer', '240')]}
    spacing = styles.find(W + 'docDefaults/' + W + 'pPrDefault/' + W + 'pPr/' + W + 'spacing')
    assert spacing.attrib == {W + key: value for key, value in
        [('before', '0'), ('after', '0'), ('line', '320'), ('lineRule', 'exact')]}
    opening, host = list(root.find(W + 'body'))[:2]
    assert not len(opening.find(W + 'pPr')) and not len(host.find(W + 'pPr'))
    parents = {child: parent for parent in root.iter() for child in parent}
    anchor, = root.iter(WP + 'anchor')
    assert anchor.find(WP + 'extent').attrib == {'cx': '3810000', 'cy': '1270000'}
    outer = anchor.find(A + 'graphic/' + A + 'graphicData')[0]
    if outer.tag == WPG + 'wgp':
        assert outer.find(WPG + 'grpSpPr/' + A + 'xfrm/' + A + 'ext').attrib == anchor.find(WP + 'extent').attrib
    assert not any(node.tag.endswith(('sizeRelH', 'sizeRelV', 'linkedTxbx')) for node in anchor.iter())
    positions = [anchor.find(WP + 'position' + axis) for axis in ('H', 'V')]
    relative = [node.attrib for node in positions]
    assert relative in [[{'relativeFrom': 'page'}, {'relativeFrom': 'page'}],
                        [{'relativeFrom': 'column'}, {'relativeFrom': 'paragraph'}]]
    offsets = [Fraction(int(node.find(WP + 'posOffset').text), 12700) for node in positions]
    if relative[0]['relativeFrom'] == 'column':
        # This fixture has exactly one 16pt opening line before its host, with no spacing.
        offsets = [offsets[0] + 60, offsets[1] + 76]
    labels = [node.text for node in root.iter(W + 't')]
    assert labels == ['SedgeOpen', 'SedgeHost', 'SedgeNear', 'SedgeFar', 'SedgeClose']

    def values(node, names):
        assert set(node.attrib) == set(names)
        return [Fraction(int(node.get(name)), 12700) for name in names]

    frames = {}
    for shape in root.iter(WPS + 'wsp'):
        label, = (node.text for node in shape.iter(W + 't'))
        story = shape.find(WPS + 'txbx/' + W + 'txbxContent')
        assert len(story) == 1 and [node.tag for node in story[0]] == [W + 'pPr', W + 'r']
        assert not len(story[0][0]) and not story[0][0].attrib
        assert [node.tag for node in story[0][1]] == [W + 'rPr', W + 't']
        assert not len(story[0][1][0]) and not story[0][1][0].attrib
        body = shape.find(WPS + 'bodyPr')
        assert body.attrib == {name: '0' for name in ('lIns', 'tIns', 'rIns', 'bIns')}
        assert [node.tag for node in body] == [A + 'noAutofit']
        transform = shape.find(WPS + 'spPr/' + A + 'xfrm')
        assert not transform.attrib
        x, y = values(transform.find(A + 'off'), ('x', 'y'))
        width, height = values(transform.find(A + 'ext'), ('cx', 'cy'))
        node = parents[shape]
        while node is not anchor:
            if node.tag in (WPG + 'wgp', WPG + 'grpSp'):
                transform = node.find(WPG + 'grpSpPr/' + A + 'xfrm')
                assert not transform.attrib
                left, top = values(transform.find(A + 'off'), ('x', 'y'))
                extent_x, extent_y = values(transform.find(A + 'ext'), ('cx', 'cy'))
                child_x, child_y = values(transform.find(A + 'chOff'), ('x', 'y'))
                child_width, child_height = values(transform.find(A + 'chExt'), ('cx', 'cy'))
                assert min(extent_x, extent_y, child_width, child_height) > 0
                scale_x, scale_y = extent_x / child_width, extent_y / child_height
                x, y = left + (x - child_x) * scale_x, top + (y - child_y) * scale_y
                width, height = width * scale_x, height * scale_y
            node = parents[node]
        frames[label] = [float(x + offsets[0]), float(y + offsets[1]), float(width), float(height)]
    near, far = frames['SedgeNear'], frames['SedgeFar']
    assert near == [80, 96 if relative[0]['relativeFrom'] == 'column' else 200, 120, 40]
    outside = far[0] >= 612 or far[1] >= 792
    assert outside == ('SedgeFar' in case['pdfCompanion'].get('forbiddenTokens', []))
    assert set(case['tokens']) == {'SedgeOpen', 'SedgeHost', 'SedgeClose', 'SedgeNear'} | (set() if outside else {'SedgeFar'})
    return {'framesPt': frames, 'paperPt': [612, 792], 'outsideFarMember': outside,
            'contract': 'literal authored coordinates; native group normalization is not claimed'}


def output_checks(proof, words, paper=(0, 0, 612, 792)):
    """Visible labels stay inside authored frames, allowing 0.1pt for layout/PDF rounding."""
    checks = []
    for label, (x, y, width, height) in proof['framesPt'].items():
        if label == 'SedgeFar' and proof['outsideFarMember']:
            continue
        left, top = paper[0] + x * paper[2] / 612, paper[1] + y * paper[3] / 792
        right, bottom = left + width * paper[2] / 612, top + height * paper[3] / 792
        matches = [word for word in words if word['text'] == label]
        passed = len(matches) == 1 and matches[0]['page'] == 1
        if passed:
            a, b, c, d = matches[0]['rect']
            passed = left - 0.1 <= a <= c <= right + 0.1 and top - 0.1 <= b <= d <= bottom + 0.1
        checks.append({'name': 'source-frame-' + label, 'passed': passed,
                       'expectedPhysicalPt': [left, top, right, bottom], 'tolerancePt': 0.1, 'observed': matches})
    return checks
