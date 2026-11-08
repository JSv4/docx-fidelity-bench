"""Source-derived Clover line slots, baselines and preserved space advances."""
import math
from xml.etree import ElementTree as ET
from zipfile import ZipFile

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def source_contract(path):
    with ZipFile(path) as package:
        document = ET.fromstring(package.read('word/document.xml'))
        styles = ET.fromstring(package.read('word/styles.xml'))
    spacing = styles.find(f'{W}docDefaults/{W}pPrDefault/{W}pPr/{W}spacing')
    multiple = int(spacing.get(W + 'line')) / 240
    assert spacing.get(W + 'lineRule') == 'auto' and multiple in (1, 2)
    paragraph = document.find(f'{W}body/{W}p')
    lines, current = [], []
    for run in paragraph.findall(W + 'r'):
        if run.find(W + 'br') is not None:
            lines.append(current); current = []
        else:
            current.append((run.find(W + 't').text, int(run.find(f'{W}rPr/{W}sz').get(W + 'val')) / 2))
    lines.append(current)
    assert len(lines) == 64
    assert all(len(line) == 3 and line[0] == (f'Clover{i + 1:02d}', 10)
               and line[1][0] == ' ' and line[2] == ('settled.', 10) for i, line in enumerate(lines))
    step = 2355 / 2048 * 10 * multiple
    return dict(labels=[line[0][0] for line in lines], gaps=[line[1][1] / 4 for line in lines],
                step=step, nativeStep=11.55 * multiple, perPage=math.floor(648 / step))


def checks(contract, info, control, native=False):
    labels, per_page = contract['labels'], contract['perPage']
    step = contract['nativeStep'] if native else contract['step']
    tolerance = .02 if native else .75
    lookup = {label: [w for w in info['words'] if w['text'] == label] for label in labels}
    controls = {w['text']: w for w in control['words'] if w['text'] in labels}
    result = []

    def add(name, passed, **values):
        result.append(dict(name=name, passed=bool(passed), **values))

    add('source-page-count', len(info['geometry']) == math.ceil(len(labels) / per_page))
    for index, label in enumerate(labels):
        found = lookup[label]
        page = index // per_page + 1
        if len(found) != 1:
            add('source-label-once', False, label=label)
            continue
        word = found[0]
        add('source-label-page', word['page'] == page, label=label, expected=page, observed=word['page'])
        paired = [w for w in info['words'] if w['text'] == 'settled.' and w['page'] == word['page']
                  and abs(w['rect'][1] - word['rect'][1]) < .02 and w['rect'][0] > word['rect'][2]]
        gap = paired[0]['rect'][0] - word['rect'][2] if len(paired) == 1 else None
        add('space-advance', gap is not None and abs(gap - contract['gaps'][index]) <= .125,
            label=label, expected=contract['gaps'][index], observed=gap, tolerance=.125)
        first = lookup[labels[index // per_page * per_page]]
        if len(first) == 1:
            delta = word['rect'][1] - first[0]['rect'][1]
            add('accumulated-line-pitch', abs(delta - step * (index % per_page)) <= tolerance,
                label=label, expected=step * (index % per_page), observed=delta, tolerance=tolerance)
        if index % per_page:
            previous = lookup[labels[index - 1]]
            delta = word['rect'][1] - previous[0]['rect'][1] if len(previous) == 1 else None
            add('consecutive-line-pitch', delta is not None and abs(delta - step) <= tolerance,
                label=label, expected=step, observed=delta, tolerance=tolerance)
        else:
            expected = controls.get(label)
            add('unchanged-first-baseline', expected is not None and word['page'] == expected['page']
                and abs(word['rect'][1] - expected['rect'][1]) <= .02, label=label,
                expected=expected['rect'][1] if expected else None, observed=word['rect'][1], tolerance=.02)
    return result
