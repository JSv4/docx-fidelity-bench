"""Literal source/font contracts for notes and independent footer rounding."""
import math
from collections import Counter
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from bench.common import ROOT

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def source(case):
    note = case['id'].startswith('footnote-character-width-')
    count, percent = map(int, case['id'].split('-')[-2:]) if note else (12, 80)
    body_count = 0 if note else int(case['id'].split('-')[-1])
    assert (count, percent) in {(n, p) for n in (12, 400) for p in (80, 100, 150)}
    assert body_count in (0, 40)
    with ZipFile(ROOT / case['input']) as package:
        document = ET.fromstring(package.read('word/document.xml'))
        story = ET.fromstring(package.read('word/footnotes.xml' if note else 'word/footer1.xml'))
        styles = ET.fromstring(package.read('word/styles.xml'))
    defaults = styles.find(W + 'docDefaults')
    assert len(styles) == 1 and [e.tag for e in defaults] == [W + 'rPrDefault', W + 'pPrDefault']
    props = defaults.find(f'{W}rPrDefault/{W}rPr')
    assert [p.tag for p in props] == [W + 'rFonts', W + 'sz']
    assert props[0].attrib == {W + 'ascii':'Liberation Mono', W + 'hAnsi':'Liberation Mono'}
    assert props[1].attrib == {W + 'val':'24'}
    pprops = defaults.find(f'{W}pPrDefault/{W}pPr')
    assert [p.tag for p in pprops] == [W + 'widowControl', W + 'spacing']
    assert pprops[0].attrib == {W + 'val':'0'}
    assert pprops[1].attrib == {W + k:v for k,v in [('before','0'),('after','0'),('line','240'),('lineRule','auto')]}
    if note:
        assert len(story) == 3
        assert [e.attrib for e in story] == [{W + 'type':'separator',W + 'id':'-1'},
            {W + 'type':'continuationSeparator',W + 'id':'0'},{W + 'id':'1'}]
        assert len(story[2]) == 2 and story[2][0].find(f'{W}r/{W}footnoteRef') is not None
        paragraph = story[2][1]
    else:
        assert len(story) == 1
        paragraph = story[0]
    assert paragraph.tag == W + 'p' and [e.tag for e in paragraph] == [W + 'pPr', W + 'r']
    assert not list(paragraph[0]) and not paragraph[0].attrib
    run = paragraph[1]
    assert [e.tag for e in run] == [W + 'rPr', W + 't']
    assert len(run[0]) == 1 and run[0][0].tag == W + 'w' and run[0][0].attrib == {W + 'val':str(percent)}
    labels = run[1].text.split()
    assert labels == [f'Sorrel{i:03d}' for i in range(1, count + 1)]
    body = document.find(W + 'body')
    assert [e.tag for e in body] == [W + 'p'] * (1 if note else body_count + 1) + [W + 'sectPr']
    section = body[-1]
    assert [e.tag for e in section] == ([] if note else [W + 'footerReference']) + [W + 'pgSz', W + 'pgMar']
    assert section.find(W + 'pgSz').attrib == {W + 'w':'12240',W + 'h':'15840'}
    assert section.find(W + 'pgMar').attrib == {W + k:v for k,v in [('top','1440'),('right','1440'),('bottom','1440'),('left','1440'),('header','720'),('footer','720')]}
    body_labels = [''.join(t.text or '' for t in p.iter(W + 't')) for p in body[:-1]]
    assert body_labels == (['HarborCitation'] if note else [f'Harbor{i:03d}' for i in range(body_count + 1)])
    if not note:
        for p in body[:-1]:
            assert [e.tag for e in p] == [W + 'pPr',W + 'r'] and not list(p[0]) and not p[0].attrib
            assert [e.tag for e in p[1]] == [W + 'rPr',W + 't']
            assert [e.tag for e in p[1][0]] == [W + 'rFonts']
            assert p[1][0][0].attrib == {W + 'ascii':'Liberation Serif',W + 'hAnsi':'Liberation Serif'}
    refs = list(document.iter(W + 'footnoteReference'))
    assert [r.attrib for r in refs] == ([{W + 'id':'1'}] if note else [])
    return dict(note=note, labels=labels, body=body_labels, percent=percent,
        advance=1229 / 2048 * 12 * percent / 100, pitch=2320 / 2048 * 12,
        body_pitch=(2320 if note else 2355) / 2048 * 12,
        body_leading=(0 if note else 87) / 2048 * 12,
        pages=1 if count == 12 else {80:2,100:2,150:3}[percent])


def checks(case, info):
    contract = source(case)
    result = []
    def add(kind, passed, **values):
        result.append(dict(kind=kind, passed=bool(passed), **values))
    labels, body, advance, pitch = (contract[k] for k in ('labels','body','advance','pitch'))
    expected = Counter(labels + body + (['1','1'] if contract['note'] else []))
    add('complete-inventory', Counter(w['text'] for w in info['words']) == expected)
    add('page-geometry', len(info['geometry']) == contract['pages'] and all(g['media'] == g['crop'] == [0,0,612,792]
        and g['rotation'] == 0 and g['userUnit'] == 1 for g in info['geometry']))
    add('painted-content', all(w.get('inkPixels',0) > 0 for w in info['words']))
    words = sorted((w for w in info['words'] if w['text'] in labels), key=lambda w:(w['page'],round(w['rect'][1],1),w['rect'][0]))
    add('story-order', [w['text'] for w in words] == labels)
    per_line = math.floor((468 + advance) / (10 * advance))
    lines = []
    for word in words:
        if not lines or word['page'] != lines[-1][0]['page'] or abs(word['rect'][1] - lines[-1][0]['rect'][1]) > .1:
            lines.append([])
        lines[-1].append(word)
    add('source-line-breaks', [[w['text'] for w in line] for line in lines] == [labels[i:i + per_line] for i in range(0,len(labels),per_line)])
    for index,line in enumerate(lines):
        for slot,word in enumerate(line):
            x,y,right,bottom = word['rect']
            if contract['note']:
                add('note-band-bounds', y >= 72 - .5 and bottom <= 720 + .5,
                    label=word['text'], page=word['page'], observed=[y,bottom], expected=[72,720], tolerancePt=.5)
            add('glyph-width-height', abs(right-x-9*advance) <= .1 and abs(bottom-y-pitch) <= .1,
                label=word['text'], expected=[9*advance,pitch], observed=[right-x,bottom-y], tolerancePt=.1)
            add('word-slot', abs(x-(72+slot*10*advance)) <= .5,
                label=word['text'], expected=72+slot*10*advance, observed=x, tolerancePt=.5)
        if index and line[0]['page'] == lines[index-1][0]['page']:
            observed = line[0]['rect'][1]-lines[index-1][0]['rect'][1]
            add('line-pitch', abs(observed-pitch) <= .1, page=line[0]['page'],
                previous=lines[index-1][0]['text'], current=line[0]['text'],
                expected=pitch, observed=observed, tolerancePt=.1)
        if index == len(lines)-1 or line[0]['page'] != lines[index+1][0]['page']:
            # Footer precision distinguishes the prior accumulated body rounding;
            # note-band placement keeps the existing half-point raster allowance.
            edge, tolerance = (720,.5) if contract['note'] else (756,.1)
            add('story-bottom', abs(line[-1]['rect'][3]-edge) <= tolerance,
                page=line[-1]['page'], expected=edge, observed=line[-1]['rect'][3], tolerancePt=tolerance)
    for index,label in enumerate(body):
        observed = [w for w in info['words'] if w['text'] == label]
        rect = observed[0]['rect'] if len(observed) == 1 else [math.nan]*4
        top = 72 + contract['body_leading'] + index * contract['body_pitch']
        add('body-slot', len(observed) == 1 and observed[0]['page'] == 1 and abs(rect[0]-72) <= .5
            and abs(rect[1]-top) <= .5, label=label, expected=[72,top], observed=rect, tolerancePt=.5)
        height = contract['body_pitch'] - contract['body_leading']
        add('body-glyph-height', abs(rect[3]-rect[1]-height) <= .1,
            label=label, expected=height, observed=rect[3]-rect[1], tolerancePt=.1)
    return result
