"""Prove the narrow source equivalences declared by the original fixture PRs."""
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
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
    **{'tables-row-height-' + unit: {
        'control': 'tables-row-height-twips',
        'rule': 'minimum-row-height-units-to-twips-v1',
    } for unit in ('pt', 'in', 'cm', 'mm', 'pc', 'pi')},
    'tables-row-height-multipage-pt': {
        'control': 'tables-row-height-multipage-twips',
        'rule': 'minimum-row-height-units-to-twips-v1',
    },
    'tables-row-height-fractional-pt': {
        'control': 'tables-row-height-fractional-twips',
        'rule': 'minimum-row-height-nearest-twip-v1',
    },
    **{'paragraphs-indentation-' + form: {
        'control': 'paragraphs-indentation-' + ('small-' if form.startswith('small') else '') + 'twips-logical-only',
        'rule': 'logical-indentation-without-conflicting-aliases-v1',
    } for form in ('pt', 'in', 'cm', 'mm', 'pc', 'pi', 'twips', 'small-pt', 'small-twips')},
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


TWIPS_PER_UNIT = {'pt': Decimal(20), 'pc': Decimal(240), 'pi': Decimal(240), 'in': Decimal(1440),
                  'cm': Decimal(1440) / Decimal('2.54'), 'mm': Decimal(144) / Decimal('2.54')}


def unit_twips(value):
    """Exact twips for an ST_PositiveUniversalMeasure, or None for any other lexical form."""
    number, unit = value[:-2], value[-2:]
    if unit not in TWIPS_PER_UNIT or not number or not number.replace('.', '', 1).isdigit():
        return None
    return Decimal(number) * TWIPS_PER_UNIT[unit]


def minimum_heights(data, nearest):
    """Rewrite one uniform unit-valued minimum row height as whole twips.

    LibreOffice 25.8.7.3 reads unit-valued heights as tiny twip values and collapses the table, so
    unit forms are captured through their whole-twip control. The exact rule admits only a value
    that is an exact whole number of twips. The nearest rule admits a value with no whole-twip
    form (25.075pt is 501.5 twips) and rounds it half up; LibreOffice lays rows out in whole twips,
    so it cannot capture the original more precisely. `nearest_twip_bound` limits that rule.
    """
    root = ET.fromstring(data)
    heights = list(root.iter(W + 'trHeight'))
    values = {(height.get(W + 'val'), height.get(W + 'hRule')) for height in heights}
    if not heights or len(values) != 1 or next(iter(values))[1] != 'atLeast' or any(set(h.attrib) != {W + 'val', W + 'hRule'} for h in heights):
        raise ValueError('Expected one uniform unit-valued minimum row height')
    twips = unit_twips(next(iter(values))[0])
    if twips is None:
        raise ValueError('Expected one uniform unit-valued minimum row height')
    whole = twips.to_integral_value(rounding=ROUND_HALF_UP)
    if (whole == twips) == nearest:
        raise ValueError('Row height is ' + ('already' if nearest else 'not') + ' a whole number of twips')
    for height in heights:
        height.set(W + 'val', str(int(whole)))
    return root


def nearest_twip_bound(case, data):
    """Bound the nearest-twip control's displacement of every declared reference position."""
    heights = list(ET.fromstring(data).iter(W + 'trHeight'))
    twips = unit_twips(heights[0].get(W + 'val'))
    per_row = abs(twips.to_integral_value(rounding=ROUND_HALF_UP) - twips) / 20
    bound = per_row * (len(heights) - 1)
    tolerances = [a['tolerancePt'] for a in case['assertions'] if a['type'] == 'marker-reference-position']
    if not tolerances or bound * 10 > Decimal(str(min(tolerances))):
        raise ValueError('Nearest-twip control displacement is not bounded by a tenth of the position tolerance')
    return {'perRowPt': str(per_row), 'maxDisplacementPt': str(bound)}


def logical_indentation(data):
    """Write exact unit indents as twips and drop legacy aliases that contradict logical edges.

    ECMA-376 Part 4 §14.3.1.2 treats w:left/w:right as the transitional names of w:start/w:end.
    The original Elm inventories give one RTL paragraph both pairs with different values, so the
    paragraph's width is ambiguous; LibreOffice uses the legacy pair. The control states only the
    logical pair the fixture is named for.
    """
    root = ET.fromstring(data)
    indents = list(root.iter(W + 'ind'))
    for indent in indents:
        for name, value in list(indent.attrib.items()):
            if name not in {W + edge for edge in ('left', 'right', 'start', 'end', 'firstLine', 'hanging')}:
                raise ValueError('Unexpected indentation attribute')
            if not value.isdigit():
                twips = unit_twips(value)
                if twips is None or twips != twips.to_integral_value():
                    raise ValueError('Indentation is not a whole number of twips: ' + value)
                indent.set(name, str(int(twips)))
    logical = [indent for indent in indents if W + 'start' in indent.attrib or W + 'end' in indent.attrib]
    if len(logical) != 1:
        raise ValueError('Expected one logical indentation')
    indent = logical[0]
    edges = [(W + 'start', W + 'left'), (W + 'end', W + 'right')]
    if any(alias not in indent.attrib or edge not in indent.attrib or indent.get(alias) == indent.get(edge)
           for edge, alias in edges):
        raise ValueError('Expected conflicting legacy aliases on both logical edges')
    for _, alias in edges:
        del indent.attrib[alias]
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
    if case.get('pdfTextNormalization') != control.get('pdfTextNormalization'):
        raise ValueError('Equivalent control changes PDF text normalization: ' + case['id'])
    if case.get('htmlAssertions', []) != control.get('htmlAssertions', []):
        raise ValueError('Equivalent control changes delivered HTML assertions: ' + case['id'])
    paths = [contained(root, c['input']) for c in (case, control)]
    if any(digest(path) != record['sha256'] for path, record in zip(paths, (case, control))):
        raise ValueError('Equivalent control input digest changed: ' + case['id'])
    if rule['rule'] == 'legacy-decimal-page-field-v1':
        changed_part, normalize = 'word/header1.xml', legacy_as_field
        changed_error = 'Equivalent control changes the decimal PAGE representation'
    elif rule['rule'] == 'exact-row-height-points-to-twips-v1':
        changed_part, normalize = 'word/document.xml', exact_height_as_twips
        changed_error = 'Equivalent control changes row layout beyond the exact-height lexical value'
    elif rule['rule'] in ('minimum-row-height-units-to-twips-v1', 'minimum-row-height-nearest-twip-v1'):
        nearest = rule['rule'] == 'minimum-row-height-nearest-twip-v1'
        changed_part, normalize = 'word/document.xml', lambda data: minimum_heights(data, nearest)
        changed_error = 'Equivalent control changes row layout beyond the minimum-height lexical value'
    elif rule['rule'] == 'logical-indentation-without-conflicting-aliases-v1':
        changed_part, normalize = 'word/document.xml', logical_indentation
        changed_error = 'Equivalent control changes indentation beyond the logical edges'
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
    result = {'kind': 'equivalent-control', 'caseId': control['id'], 'input': control['input'],
              'inputSha256': control['sha256'], 'rule': rule['rule']}
    if rule['rule'] == 'minimum-row-height-nearest-twip-v1':
        with ZipFile(paths[0]) as original:
            result.update(kind='nearest-twip-control', bound=nearest_twip_bound(case, original.read(changed_part)))
    return result
