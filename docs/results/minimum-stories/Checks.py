"""Source-bound Poppy line metrics, complete ordered content and natural-control geometry."""
from xml.etree import ElementTree as ET
from zipfile import ZipFile

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def source_contract(path):
    with ZipFile(path) as package:
        owner = next(owner for owner in ('header', 'footer', 'footnote', 'endnote')
                     if f'word/{owner}{"1" if owner in ("header", "footer") else "s"}.xml' in package.namelist())
        story = ET.fromstring(package.read(f'word/{owner}{"1" if owner in ("header", "footer") else "s"}.xml'))
        document = ET.fromstring(package.read('word/document.xml'))
        styles = ET.fromstring(package.read('word/styles.xml'))
    paragraphs = [p for p in story.iter(W + 'p') if any('Poppy' in (t.text or '') for t in p.iter(W + 't'))]
    assert len(paragraphs) == 1
    paragraph = paragraphs[0]
    assert [child.tag for child in paragraph] == [W + 'pPr', W + 'r']
    assert [child.tag for child in paragraph.find(W + 'r')] == [W + 'rPr', W + 't']
    assert [child.tag for child in paragraph.find(W + 'pPr')] == [W + 'widowControl', W + 'spacing', W + 'ind']
    assert paragraph.find(f'{W}pPr/{W}widowControl').attrib == {W + 'val': '0'}
    labels = ''.join(t.text or '' for t in paragraph.iter(W + 't')).split()
    assert labels == [f'Poppy{i:03d}' for i in range(1, len(labels) + 1)] and len(labels) in (8, 18, 64)
    defaults = styles.find(f'{W}docDefaults/{W}rPrDefault/{W}rPr')
    assert [child.tag for child in defaults] == [W + 'rFonts', W + 'sz']
    assert defaults.find(W + 'rFonts').attrib == {W + 'ascii': 'Liberation Serif', W + 'hAnsi': 'Liberation Serif'}
    assert all(not list(props) and not props.attrib for props in story.iter(W + 'rPr'))
    assert not list(styles.iter(W + 'style'))
    size = int(defaults.find(W + 'sz').get(W + 'val')) / 2
    assert size == 20
    spacing = paragraph.find(f'{W}pPr/{W}spacing')
    assert (spacing.get(W + 'lineRule'), spacing.get(W + 'line')) in [('auto', '240'), ('atLeast', '320')]
    assert spacing.get(W + 'before') == spacing.get(W + 'after') == '0' and len(spacing.attrib) == 4
    assert paragraph.find(f'{W}pPr/{W}ind').attrib == {W + 'right': '7440'}
    section = document.find(f'{W}body/{W}sectPr')
    assert section.find(W + 'pgSz').attrib == {W + 'w': '12240', W + 'h': '15840'}
    assert section.find(W + 'pgMar').attrib == {W + name: value for name, value in
        [('top', '1440'), ('right', '1440'), ('bottom', '1440'), ('left', '1440'), ('header', '720'), ('footer', '720')]}
    body = [t.text.strip() for t in document.iter(W + 't')]
    running = owner in ('header', 'footer')
    repeats = len(body) if running else 1
    assert repeats in (1, 3) and body == [f'Garden{i:03d}' for i in range(1, len(body) + 1)]
    return dict(owner=owner, labels=labels, body=body, repeats=repeats, step=2355 / 2048 * size,
                tolerance=.5 if running else .02)


def control_checks(actual, baseline):
    same = actual['geometry'] == baseline['geometry'] and len(actual['words']) == len(baseline['words'])
    same = same and all(a['text'] == b['text'] and a['page'] == b['page']
        and all(abs(x - y) <= .02 for x, y in zip(a['rect'], b['rect']))
        for a, b in zip(actual['words'], baseline['words']))
    return [dict(name='unchanged-baseline-natural-control', passed=bool(same), tolerance=.02)]


def checks(contract, info, control):
    result = []
    def add(name, passed, **values):
        result.append(dict(name=name, passed=bool(passed), **values))
    add('natural-control-page-count', len(info['geometry']) == len(control['geometry']))
    expected_order = [(w['page'], w['text']) for w in control['words']]
    add('complete-ordered-content', [(w['page'], w['text']) for w in info['words']] == expected_order)
    add('natural-control-complete-geometry', len(info['words']) == len(control['words']) and
        all(a['page'] == b['page'] and a['text'] == b['text'] and
            all(abs(x - y) <= contract['tolerance'] for x, y in zip(a['rect'], b['rect']))
            for a, b in zip(info['words'], control['words'])), tolerance=contract['tolerance'])
    labels = [w for w in info['words'] if w['text'] in contract['labels']]
    add('source-label-inventory-order', [w['text'] for w in labels] == contract['labels'] * contract['repeats'])
    add('source-body-page-ownership', [(w['page'], w['text']) for w in info['words'] if w['text'] in contract['body']]
        == list(enumerate(contract['body'], 1)))
    if contract['owner'] in ('header', 'footer'):
        add('source-running-page-count', len(info['geometry']) == contract['repeats'])
        for page in range(1, contract['repeats'] + 1):
            add('source-running-page-inventory', [w['text'] for w in labels if w['page'] == page] == contract['labels'], page=page)
    elif len(contract['labels']) == 64:
        add('source-note-continuation', len(info['geometry']) > 1)
    for page in range(1, len(info['geometry']) + 1):
        rows = [w for w in labels if w['page'] == page]
        for index, word in enumerate(rows):
            delta = word['rect'][1] - rows[0]['rect'][1]
            add('accumulated-natural-pitch', abs(delta - index * contract['step']) <= .75,
                page=page, label=word['text'], expected=index * contract['step'], observed=delta, tolerance=.75)
            if index:
                delta = word['rect'][1] - rows[index - 1]['rect'][1]
                add('consecutive-natural-pitch', abs(delta - contract['step']) <= .75,
                    page=page, label=word['text'], expected=contract['step'], observed=delta, tolerance=.75)
    return result
