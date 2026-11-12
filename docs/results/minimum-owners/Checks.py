"""Read original Rue source inventories; verify line ownership and unchanged owner geometry."""
import math
from xml.etree import ElementTree as ET
from zipfile import ZipFile

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def control_checks(actual, baseline):
    same = len(actual['geometry']) == len(baseline['geometry']) and len(actual['words']) == len(baseline['words'])
    same = same and all(a['text'] == b['text'] and a['page'] == b['page']
        and all(abs(x - y) <= .02 for x, y in zip(a['rect'], b['rect']))
        for a, b in zip(actual['words'], baseline['words']))
    return [dict(name='unchanged-baseline-natural-control', passed=bool(same), tolerance=.02)]


def source_contract(path):
    with ZipFile(path) as package:
        document = ET.fromstring(package.read('word/document.xml'))
        styles = ET.fromstring(package.read('word/styles.xml'))
    body = document.find(W + 'body')
    paragraph = body.find('.//' + W + 'p')
    labels = ''.join(t.text or '' for t in paragraph.iter(W + 't')).split()
    assert labels == [f'Rue{i:03d}' for i in range(1, len(labels) + 1)] and len(labels) in (18, 64)
    size = int(styles.find(f'{W}docDefaults/{W}rPrDefault/{W}rPr/{W}sz').get(W + 'val')) / 2
    assert size == 20
    spacing = paragraph.find(f'{W}pPr/{W}spacing')
    assert (spacing.get(W + 'lineRule'), spacing.get(W + 'line')) in [('auto', '240'), ('atLeast', '320')]
    step = 2355 / 2048 * size
    return dict(labels=labels, step=step, perPage=math.floor(648 / step),
                numbered=paragraph.find(f'{W}pPr/{W}numPr') is not None)


def checks(contract, info, control):
    labels, per_page, step = contract['labels'], contract['perPage'], contract['step']
    lookup = {label: [w for w in info['words'] if w['text'] == label] for label in labels}
    controls = {w['text']: w for w in control['words']}
    result = []
    def add(name, passed, **values):
        result.append(dict(name=name, passed=bool(passed), **values))
    add('source-page-count', len(info['geometry']) == math.ceil(len(labels) / per_page))
    add('source-label-order', [w['text'] for w in info['words'] if w['text'] in labels] == labels)
    for index, label in enumerate(labels):
        found = lookup[label]
        if len(found) != 1:
            add('source-label-once', False, label=label)
            continue
        word = found[0]
        page = index // per_page + 1
        add('source-label-page', word['page'] == page, label=label, expected=page, observed=word['page'])
        first = lookup[labels[index // per_page * per_page]]
        if len(first) == 1:
            delta = word['rect'][1] - first[0]['rect'][1]
            add('accumulated-line-pitch', abs(delta - step * (index % per_page)) <= .75,
                label=label, expected=step * (index % per_page), observed=delta, tolerance=.75)
        if index % per_page:
            previous = lookup[labels[index - 1]]
            delta = word['rect'][1] - previous[0]['rect'][1] if len(previous) == 1 else None
            add('consecutive-line-pitch', delta is not None and math.isfinite(delta) and abs(delta - step) <= .75,
                label=label, expected=step, observed=delta, tolerance=.75)
        expected = controls.get(label)
        add('natural-control-geometry', expected is not None and word['page'] == expected['page']
            and all(abs(a - b) <= .02 for a, b in zip(word['rect'], expected['rect'])), label=label,
            expected=expected['rect'] if expected else None, observed=word['rect'], tolerance=.02)
    numbers = [w for w in info['words'] if w['text'] == '1.']
    expected = controls.get('1.')
    add('number-once-with-first-line', not numbers if not contract['numbered'] else len(numbers) == 1
        and expected is not None and numbers[0]['page'] == 1
        and all(abs(a - b) <= .02 for a, b in zip(numbers[0]['rect'], expected['rect'])))
    return result
