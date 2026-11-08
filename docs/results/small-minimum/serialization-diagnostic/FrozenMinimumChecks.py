"""Independent source, glyph, pitch and cumulative-drift checks for Primrose text."""
import math
import subprocess
from collections import Counter
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from bench.common import ROOT


def source_order(path):
    return subprocess.check_output(['pdftotext', '-raw', '-enc', 'UTF-8', str(path), '-'], text=True).split()


def source_contract(case):
    count, rule, line, pitch = {
        'short': (18, 'atLeast', 260, 13), 'continued': (64, 'atLeast', 260, 13),
        'natural-control': (18, 'auto', 240, 2355 / 2048 * 10),
        'sixteen-control': (18, 'atLeast', 320, 16),
    }[case['id'].removeprefix('small-minimum-')]
    labels = [f'Primrose{i // 10}x{i % 10}' for i in range(1, count + 1)]
    w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    with ZipFile(ROOT / case['input']) as package:
        source = ET.fromstring(package.read('word/document.xml'))
        styles = ET.fromstring(package.read('word/styles.xml'))
    body = source.find(w + 'body')
    assert [e.tag for e in body] == [w + 'p', w + 'sectPr']
    paragraph, section = list(body)
    assert [e.tag for e in paragraph] == [w + 'pPr', w + 'r']
    assert [e.tag for e in paragraph.find(w + 'pPr')] == [w + 'spacing', w + 'ind']
    run = paragraph.find(w + 'r')
    assert [e.tag for e in run] == [w + 'rPr', w + 't']
    assert len(run.find(w + 'rPr')) == 0 and not run.find(w + 'rPr').attrib
    assert [e.tag for e in section] == [w + 'pgSz', w + 'pgMar']
    assert len(list(source.iter(w + 'p'))) == len(list(source.iter(w + 'r'))) == 1
    assert not list(source.iter(w + 'br'))
    assert ' '.join(e.text or '' for e in source.iter(w + 't')).split() == labels
    spacing = source.find('.//' + w + 'spacing')
    assert spacing.attrib == {w + 'before': '0', w + 'after': '0', w + 'line': str(line), w + 'lineRule': rule}
    assert source.find('.//' + w + 'ind').attrib == {w + 'right': '8160'}
    assert source.find('.//' + w + 'pgSz').attrib == {w + 'w': '12240', w + 'h': '15840'}
    assert source.find('.//' + w + 'pgMar').attrib == {w + side: '1440' for side in ('top', 'right', 'bottom', 'left')}
    props = styles.find('.//' + w + 'rPrDefault/' + w + 'rPr')
    assert [e.tag for e in styles] == [w + 'docDefaults']
    assert [e.tag for e in styles[0]] == [w + 'rPrDefault', w + 'pPrDefault']
    assert [e.tag for e in props] == [w + 'rFonts', w + 'sz']
    defaults = styles.find('.//' + w + 'pPrDefault/' + w + 'pPr')
    assert [e.tag for e in defaults] == [w + 'widowControl']
    assert defaults[0].get(w + 'val') == '0'
    assert props.find(w + 'sz').get(w + 'val') == '20'
    assert props.find(w + 'rFonts').attrib == {w + 'ascii': 'Liberation Serif', w + 'hAnsi': 'Liberation Serif'}
    assert Counter(labels) == Counter(case['tokens'])
    assert 10467 / 2048 * 10 < 60 < (10467 * 2 + 512) / 2048 * 10
    return labels, pitch


def checks(case, info):
    labels, pitch = source_contract(case)
    per_page = math.floor(648 / pitch)
    words = {label: [w for w in info['words'] if w['text'] == label] for label in labels}
    result = [dict(kind='page-count', expected=math.ceil(len(labels) / per_page),
        observed=len(info['geometry']), passed=len(info['geometry']) == math.ceil(len(labels) / per_page)),
        dict(kind='ordered-inventory', passed=info['rawTokens'] == labels)]
    for i, label in enumerate(labels):
        entries = words[label]
        rect = entries[0]['rect'] if len(entries) == 1 else [math.nan] * 4
        width, height = rect[2] - rect[0], rect[3] - rect[1]
        # hmtx advance and hhea ascent-descent from independently provisioned Serif.
        result.append(dict(kind='glyph-dimensions', marker=label, expectedWidthPt=10467 / 2048 * 10,
            expectedHeightPt=2268 / 2048 * 10, observedWidthPt=width, observedHeightPt=height, tolerancePt=.1,
            passed=math.isfinite(width + height) and abs(width - 10467 / 2048 * 10) <= .1
                and abs(height - 2268 / 2048 * 10) <= .1))
        page = i // per_page + 1
        for kind, start in [('adjacent-pitch', max(i - 1, i // per_page * per_page)),
                            ('cumulative-pitch', i // per_page * per_page)]:
            first = words[labels[start]]
            owned = len(entries) == len(first) == 1 and entries[0]['page'] == first[0]['page'] == page
            observed = rect[1] - first[0]['rect'][1] if owned else math.nan
            expected = (i - start) * pitch
            result.append(dict(kind=kind, marker=label, first=labels[start], page=page,
                expectedPt=expected, observedPt=observed, tolerancePt=.75,
                passed=owned and math.isfinite(observed) and abs(observed - expected) <= .75))
    return result
