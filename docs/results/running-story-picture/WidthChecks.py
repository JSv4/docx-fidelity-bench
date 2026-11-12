"""Source-bound justification isolated from an independent body picture."""
import math
from collections import Counter
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from bench.common import ROOT

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def source(case):
    owner, variant = case['id'].split('-')[-2:]
    percent = 80
    assert owner in ('header', 'footer') and variant in ('control', 'image')
    with ZipFile(ROOT / case['input']) as package:
        document = ET.fromstring(package.read('word/document.xml'))
        story = ET.fromstring(package.read(f'word/{owner}1.xml'))
        styles = ET.fromstring(package.read('word/styles.xml'))
    assert len(story) == 1 and story[0].tag == W + 'p'
    paragraph = story[0]
    assert [c.tag for c in paragraph] == [W + 'pPr', W + 'r']
    assert [c.tag for c in paragraph[0]] == [W + 'spacing', W + 'ind', W + 'jc']
    assert paragraph[0][0].attrib == {W + k:v for k,v in [('before','0'),('after','0'),('line','240'),('lineRule','auto')]}
    assert paragraph[0][1].attrib == {W + 'right':'5760'}
    assert paragraph[0][2].attrib == {W + 'val':'both'}
    run = paragraph[1]
    assert [c.tag for c in run] == [W + 'rPr', W + 't']
    assert len(run[0]) == 1 and run[0][0].tag == W + 'w' and run[0][0].attrib == {W + 'val':str(percent)}
    labels = run[1].text.split()
    assert labels == [f'Sorrel{i:03d}' for i in range(1, 13)]
    props = styles.find(f'{W}docDefaults/{W}rPrDefault/{W}rPr')
    assert [c.tag for c in props] == [W + 'rFonts', W + 'sz']
    assert props[0].attrib == {W + 'ascii':'Liberation Mono', W + 'hAnsi':'Liberation Mono'}
    assert props[1].attrib == {W + 'val':'24'} and not list(styles.iter(W + 'style'))
    sections = list(document.iter(W + 'sectPr'))
    assert len(sections) == 2
    for index, section in enumerate(sections):
        assert [c.tag for c in section] == ([W + owner + 'Reference'] if not index else []) + [W + 'pgSz', W + 'pgMar']
        assert section.find(W + 'pgSz').attrib == {W + 'w':'12240', W + 'h':'15840'}
        assert section.find(W + 'pgMar').attrib == {W + k:v for k,v in [('top','1440'),('right','1440' if not index else '0'),('bottom','1440'),('left','1440'),('header','720'),('footer','720')]}
    body = list(document.find(W + 'body'))
    assert [p.tag for p in body] == [W + 'p'] * (5 if variant == 'image' else 4) + [W + 'sectPr']
    drawings = list(document.iter(W + 'drawing'))
    assert len(drawings) == (1 if variant == 'image' else 0)
    if drawings:
        inline = drawings[0][0]
        assert inline.tag == '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}inline'
        assert inline.attrib == {side:'0' for side in ('distT', 'distB', 'distL', 'distR')}
        assert inline[0].attrib == {'cx':'152400', 'cy':'152400'}
        assert not list(body[4].iter(W + 't'))
    body_labels = [''.join(t.text or '' for t in p.iter(W + 't')) for p in body[:4]]
    assert body_labels == [f'Ledger{i:03d}' for i in range(1, 5)]
    assert [p.find(f'{W}pPr/{W}pageBreakBefore') is not None for p in body[:4]] == [False,True,False,True]
    assert body[1].find(f'{W}pPr/{W}sectPr') is not None
    return dict(owner=owner, labels=labels, body=body_labels, advance=1229 / 2048 * 12 * percent / 100,
                pitch=2320 / 2048 * 12, widths=[180,180,252,252])


def checks(case, info):
    contract = source(case)
    result = []
    def add(kind, passed, **values):
        result.append(dict(kind=kind, passed=bool(passed), **values))
    labels, body, advance, pitch = (contract[k] for k in ('labels','body','advance','pitch'))
    expected_tokens = Counter(labels * 4 + body)
    add('complete-inventory', Counter(w['text'] for w in info['words']) == expected_tokens)
    add('page-geometry', len(info['geometry']) == 4 and all(g['media'] == g['crop'] == [0,0,612,792]
        and g['rotation'] == 0 and g['userUnit'] == 1 for g in info['geometry']))
    add('body-page-order', [(w['page'],w['text']) for w in info['words'] if w['text'] in body] == list(enumerate(body,1)))
    add('repeated-story-order', [(w['page'],w['text']) for w in sorted(info['words'], key=lambda w: (w['page'], round(w['rect'][1],1), w['rect'][0])) if w['text'] in labels]
        == [(page,label) for page in range(1,5) for label in labels])
    add('painted-content', all(w.get('inkPixels',0) > 0 for w in info['words']))
    for page, width in enumerate(contract['widths'],1):
        per_line = math.floor((width + advance) / (10 * advance))
        rows = math.ceil(len(labels) / per_line)
        top = 36 if contract['owner'] == 'header' else 756 - rows * pitch
        body_words = [w for w in info['words'] if w['page'] == page and w['text'] == body[page - 1]]
        body_rect = body_words[0]['rect'] if len(body_words) == 1 else [math.nan] * 4
        body_top = max(72, 36 + rows * pitch) if contract['owner'] == 'header' else 72
        body_width = 9 * 1229 / 2048 * 12
        add('body-band-reservation', all(math.isfinite(v) for v in body_rect)
            and abs(body_rect[0] - 72) <= .5 and abs(body_rect[1] - body_top) <= .5
            and abs(body_rect[2] - body_rect[0] - body_width) <= .1 and abs(body_rect[3] - body_rect[1] - pitch) <= .1,
            page=page, expected=[72,body_top,body_width,pitch], observed=body_rect)
        for index,label in enumerate(labels):
            observed = [w for w in info['words'] if w['page'] == page and w['text'] == label]
            rect = observed[0]['rect'] if len(observed) == 1 else [math.nan] * 4
            row = index // per_line
            step = (width - 9 * advance) / (per_line - 1) if row < rows - 1 else 10 * advance
            left = 72 + index % per_line * step
            y = top + index // per_line * pitch
            add('line-slot', all(math.isfinite(v) for v in rect) and abs(rect[0]-left) <= .5 and abs(rect[1]-y) <= .5,
                page=page, label=label, expected=[left,y], observed=rect[:2], tolerancePt=.5)
            add('glyph-width-height', abs(rect[2]-rect[0]-9*advance) <= .1 and abs(rect[3]-rect[1]-pitch) <= .1,
                page=page, label=label, expected=[9*advance,pitch], observed=[rect[2]-rect[0],rect[3]-rect[1]], tolerancePt=.1)
    return result
