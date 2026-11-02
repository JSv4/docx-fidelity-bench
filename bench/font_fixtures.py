"""Original Birch documents for unweighted font-observation diagnostics."""
from pathlib import Path
import tempfile
from .common import ROOT, digest, read_json, write_json
from .fixtures import W, package, para, run

MISSING = 'Absent Birch Sans'
SANS = 'Liberation Sans'
SERIF = 'Liberation Serif'


def generate(root=ROOT):
    root = Path(root)
    folder = root / 'fixtures/fonts'
    folder.mkdir(parents=True, exist_ok=True)
    cases = []
    definitions = [
        ('used-missing', False, [(MISSING, 'Birch shelves hold seven tools.')], None),
        ('configured-control', True, [(SANS, 'Birch shelves hold seven tools.')], None),
        ('unused-style-control', True, [(SANS, 'Birch shelves hold seven tools.')], 'style'),
        ('unused-table-control', True, [(SANS, 'Birch shelves hold seven tools.')], 'table'),
        ('mixed-glyphs', False, [(SANS, 'Birch A漢😀')], None),
        ('separate-requests', False, [(SANS, 'Birch first shelf.'), (SERIF, 'Cedar second shelf.')], None),
        ('missing-separate', False, [(MISSING, 'Birch first shelf.'), (SERIF, 'Cedar second shelf.')], None),
    ]
    for cid, control, pages, unused in definitions:
        font = pages[0][0]
        descriptor = lambda family: f'<w:rFonts w:ascii="{family}" w:hAnsi="{family}" w:eastAsia="{family}" w:cs="{family}"/>'
        styles = f'<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr>{descriptor(font)}<w:color w:val="000000"/><w:sz w:val="24"/></w:rPr></w:rPrDefault></w:docDefaults>'
        if unused == 'style':
            styles += f'<w:style w:type="paragraph" w:styleId="Unused"><w:name w:val="Unused"/><w:rPr>{descriptor(MISSING)}</w:rPr></w:style>'
        styles += '</w:styles>'
        body = ''.join(para(props=('<w:pageBreakBefore/>' if i else '')
                            + '<w:spacing w:before="0" w:after="0" w:line="360" w:lineRule="exact"/>'
                            + f'<w:rPr>{descriptor(family)}</w:rPr>', runs=run(text, descriptor(family)))
                       for i, (family, text) in enumerate(pages))
        extra = {}
        if unused == 'table':
            extra = {'extra_parts': {'word/fontTable.xml': f'<w:fonts xmlns:w="{W}"><w:font w:name="{MISSING}"/></w:fonts>'},
                     'relations_extra': [('rFonts', 'fontTable', 'fontTable.xml')],
                     'content_types_extra': '<Override PartName="/word/fontTable.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml"/>'}
        path = folder / (cid + '.docx')
        package(path, body, styles_xml=styles, **extra)
        cases.append({'id': cid, 'input': str(path.relative_to(root)), 'sha256': digest(path), 'control': control,
                      'pages': [{'family': family, 'text': text, 'missing': family == MISSING,
                                 'partial': cid == 'mixed-glyphs'} for family, text in pages],
                      'rights': {'author': 'John Scrudato IV', 'license': 'MIT',
                                 'origin': 'Original literal OOXML and Birch text authored for this diagnostic',
                                 'assets': 'No imported document, font program, image or external resource'}})
    registry = {'schema': 1, 'suite': 'font-observation-v1', 'version': 1,
                'scope': 'Unweighted diagnostic; no PDF/redline fidelity score or verified font-file claim',
                'generatorSha256': digest(Path(__file__)), 'cases': cases}
    write_json(folder / 'manifest.json', registry)
    return registry


def validate(root=ROOT):
    root = Path(root)
    registry = read_json(root / 'fixtures/fonts/manifest.json')
    with tempfile.TemporaryDirectory() as temp:
        if generate(temp) != registry:
            raise ValueError('Font diagnostic declarations differ from their original generator')
    for case in registry['cases']:
        if digest(root / case['input']) != case['sha256']:
            raise ValueError('Font input missing or changed: ' + case['id'])
    return registry


if __name__ == '__main__':
    generate()
