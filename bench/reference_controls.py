"""Prove the narrow source equivalences declared by the original fixture PRs."""
from copy import deepcopy
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile
from .common import contained, digest

TRACK = 'libreoffice-equivalent-controls'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
XML = '{http://www.w3.org/XML/1998/namespace}'
RULES = {
    'paragraphs-page-number-ordinary-legacy': {
        'control': 'paragraphs-page-number-ordinary-field',
        'rule': 'legacy-decimal-page-field-v1',
    },
    'paragraphs-page-number-restarted-legacy': {
        'control': 'paragraphs-page-number-restarted-field',
        'rule': 'legacy-decimal-page-field-v1',
    },
    'tables-row-height-exact-pt': {
        'control': 'tables-row-height-exact-twips',
        'rule': 'exact-row-height-points-to-twips-v1',
    },
    'tables-vmerge-boundary-merged': {
        'control': 'tables-vmerge-boundary-merged-kept',
        'rule': 'vertical-merge-keep-with-next-v1',
    },
}


def policy():
    return {'version': 1, 'rules': deepcopy(RULES), 'implementationSha256': digest(Path(__file__))}


def legacy_as_field(data):
    root = ET.fromstring(data)
    blocks = list(root.iter(W + 'pgNum'))
    if len(blocks) != 1 or blocks[0].attrib or list(blocks[0]):
        raise ValueError('Expected one empty legacy page-number block')
    paragraphs = root.findall(W + 'p')
    if len(paragraphs) != 1:
        raise ValueError('Expected one running-story paragraph')
    paragraph = paragraphs[0]
    runs = paragraph.findall(W + 'r')
    if len(runs) != 1 or runs[0].find(W + 'pgNum') is not blocks[0]:
        raise ValueError('Legacy page-number run has additional content')
    result = deepcopy(runs[0])
    if [child.tag for child in result] != [W + 'rPr', W + 'pgNum']:
        raise ValueError('Legacy page-number run has additional content')
    result.remove(result.find(W + 'pgNum'))
    ET.SubElement(result, W + 't').text = '1'

    def field_run(tag, attributes=None, text=None):
        run = ET.Element(W + 'r')
        ET.SubElement(run, W + tag, attributes or {}).text = text
        return run

    replacements = [
        field_run('fldChar', {W + 'fldCharType': 'begin'}),
        field_run('instrText', {XML + 'space': 'preserve'}, ' PAGE \\* Arabic '),
        field_run('fldChar', {W + 'fldCharType': 'separate'}),
        result,
        field_run('fldChar', {W + 'fldCharType': 'end'}),
    ]
    position = list(paragraph).index(runs[0])
    paragraph.remove(runs[0])
    for offset, run in enumerate(replacements):
        paragraph.insert(position + offset, run)
    return root


def exact_height_as_twips(data):
    root = ET.fromstring(data)
    heights = list(root.iter(W + 'trHeight'))
    if len(heights) != 3 or any(height.get(W + 'val') != '36pt' or
                               height.get(W + 'hRule') != 'exact' for height in heights):
        raise ValueError('Expected three exact 36pt row heights')
    for height in heights:
        height.set(W + 'val', str(36 * 20))
    return root


def merge_kept_with_next(data):
    """Hold each row of the single vertical merge with the next, ending at its last row."""
    root = ET.fromstring(data)
    tables = list(root.iter(W + 'tbl'))
    if len(tables) != 1:
        raise ValueError('Expected one ledger table')
    rows = tables[0].findall(W + 'tr')
    merged = [index for index, row in enumerate(rows)
              if any(cell.find(W + 'tcPr/' + W + 'vMerge') is not None for cell in row.findall(W + 'tc'))]
    if not merged or merged != list(range(merged[0], merged[-1] + 1)) or len(merged) < 2:
        raise ValueError('Expected one contiguous vertical merge')
    starts = [cell for index in merged for cell in rows[index].findall(W + 'tc')
              if cell.find(W + 'tcPr/' + W + 'vMerge') is not None and
              cell.find(W + 'tcPr/' + W + 'vMerge').get(W + 'val') == 'restart']
    if len(starts) != 1 or starts[0] not in rows[merged[0]].findall(W + 'tc'):
        raise ValueError('Expected one vertical merge starting on its first row')
    if any(element.tag == W + 'keepNext' for element in root.iter()):
        raise ValueError('Original already keeps paragraphs with the next')
    for row in rows[merged[0]:merged[-1]]:
        for paragraph in row.iter(W + 'p'):
            properties = paragraph.find(W + 'pPr')
            if properties is None or list(properties):
                raise ValueError('Merged-row paragraph properties have additional content')
            ET.SubElement(properties, W + 'keepNext')
    return root


def source(case, registry, root):
    rule = RULES.get(case['id'])
    if rule is None:
        return {'kind': 'direct', 'caseId': case['id'], 'input': case['input'],
                'inputSha256': case['sha256']}
    control = next((c for c in registry['cases'] if c['id'] == rule['control']), None)
    if control is None:
        raise ValueError('Missing declared equivalent control: ' + rule['control'])
    for key in ('category', 'fonts', 'profile', 'tokens', 'assertions'):
        if case[key] != control[key]:
            raise ValueError('Equivalent control changes ' + key + ': ' + case['id'])
    paths = [contained(root, c['input']) for c in (case, control)]
    if any(digest(path) != record['sha256'] for path, record in zip(paths, (case, control))):
        raise ValueError('Equivalent control input digest changed: ' + case['id'])
    if rule['rule'] == 'legacy-decimal-page-field-v1':
        changed_part, normalize = 'word/header1.xml', legacy_as_field
        changed_error = 'Equivalent control changes the decimal PAGE representation'
    elif rule['rule'] == 'exact-row-height-points-to-twips-v1':
        changed_part, normalize = 'word/document.xml', exact_height_as_twips
        changed_error = 'Equivalent control changes row layout beyond the exact-height lexical value'
    elif rule['rule'] == 'vertical-merge-keep-with-next-v1':
        changed_part, normalize = 'word/document.xml', merge_kept_with_next
        changed_error = 'Equivalent control changes the ledger beyond keeping its merged rows together'
    else:
        raise ValueError('Unknown equivalent-control rule')
    with ZipFile(paths[0]) as original, ZipFile(paths[1]) as comparison:
        names = original.namelist()
        other = comparison.namelist()
        if len(names) != len(set(names)) or len(other) != len(set(other)) or set(names) != set(other):
            raise ValueError('Equivalent control changes package members: ' + case['id'])
        for name in names:
            if name == changed_part:
                expected = normalize(original.read(name))
                actual = ET.fromstring(comparison.read(name))
                if ET.tostring(expected) != ET.tostring(actual):
                    raise ValueError(changed_error)
            elif original.read(name) != comparison.read(name):
                raise ValueError('Equivalent control changes package part: ' + name)
        if changed_part not in names:
            raise ValueError('Equivalent control is missing its declared package part')
    return {'kind': 'equivalent-control', 'caseId': control['id'], 'input': control['input'],
            'inputSha256': control['sha256'], 'rule': rule['rule']}
