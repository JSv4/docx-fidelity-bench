"""Original exact-text projection diagnostics, independent of PDF and redline scores."""
from pathlib import Path
import tempfile
from .common import ROOT, digest, read_json, write_json
from .fixtures import W, package, para, run

NS = (' xmlns:v="urn:schemas-microsoft-com:vml"'
      ' xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"'
      ' xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup"'
      ' xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:unknown="urn:unknown"')


def control(content):
    return '<w:sdt><w:sdtPr/><w:sdtContent>' + content + '</w:sdtContent></w:sdt>'


def shape(content):
    return ('<wps:wsp><wps:cNvSpPr txBox="1"/><wps:spPr/><wps:txbx><w:txbxContent>' + content +
            '</w:txbxContent></wps:txbx><wps:bodyPr/></wps:wsp>')


def drawing(content, group=False):
    kind = 'Group' if group else 'Shape'
    payload = shape(content)
    if group:
        payload = '<wpg:wgp><wpg:cNvGrpSpPr/><wpg:grpSpPr/>' + payload + '</wpg:wgp>'
    return ('<w:drawing><wp:inline><wp:extent cx="2540000" cy="1270000"/><wp:docPr id="1" name="AshPanel"/>'
            '<a:graphic><a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessing' + kind + '">' +
            payload + '</a:graphicData></a:graphic></wp:inline></w:drawing>')


def vml(content):
    return ('<w:pict><v:shape id="AshPanel" style="width:200pt;height:100pt"><v:textbox><w:txbxContent>' +
            content + '</w:txbxContent></v:textbox></v:shape></w:pict>')


def table(row_sdt=False, cell_sdt=False):
    cells = ['<w:tc><w:tcPr/>' + para(text) + '</w:tc>' for text in ('AshLeft', 'AshRight')]
    if cell_sdt:
        cells[1] = control(cells[1])
    row = '<w:tr>' + ''.join(cells) + '</w:tr>'
    return ('<w:tbl><w:tblPr/><w:tblGrid><w:gridCol w:w="2400"/><w:gridCol w:w="2400"/></w:tblGrid>' +
            (control(row) if row_sdt else row) + '</w:tbl>')


def generate(root=ROOT):
    root = Path(root)
    folder = root / 'fixtures/projection'
    folder.mkdir(parents=True, exist_ok=True)
    cases = []
    for kind in ('vml', 'choice', 'fallback', 'group-sdt', 'row-sdt', 'cell-sdt', 'table-in-box'):
        for is_control in (False, True):
            cid = kind + ('-control' if is_control else '')
            table_case = kind in ('row-sdt', 'cell-sdt', 'table-in-box')
            content = table() + para('AshTail') if table_case else para('AshInside')
            expected_middle = '| AshLeft | AshRight | | --- | --- | AshTail' if table_case else 'AshInside'
            anchored = ['AshTail'] if table_case else ['AshInside']
            if is_control:
                body = para('AshHost') + content
            elif kind in ('row-sdt', 'cell-sdt'):
                body = para('AshHost') + table(kind == 'row-sdt', kind == 'cell-sdt') + para('AshTail')
            else:
                if kind in ('vml', 'table-in-box'):
                    carrier = vml(content)
                elif kind == 'group-sdt':
                    carrier = drawing(control(content), group=True)
                else:
                    requires = 'unknown' if kind == 'fallback' else 'wps'
                    choice_content = para('InactiveChoice') if kind == 'fallback' else content
                    carrier = ('<mc:AlternateContent><mc:Choice Requires="' + requires + '">' + drawing(choice_content) +
                               '</mc:Choice><mc:Fallback>' + vml(para('InactiveFallback') if kind == 'choice' else content) + '</mc:Fallback></mc:AlternateContent>')
                body = para(runs=run('AshHost') + '<w:r>' + carrier + '</w:r>')
            body += para('AshFollowing')
            path = folder / (cid + '.docx')
            package(path, body, namespaces_extra=NS, styles_xml=f'<w:styles xmlns:w="{W}"/>')
            cases.append({'id': cid, 'input': str(path.relative_to(root)), 'sha256': digest(path),
                          'control': is_control, 'expected': '# Document AshHost ' + expected_middle + ' AshFollowing',
                          'anchored': anchored, 'rights': {'author': 'John Scrudato IV', 'license': 'MIT',
                          'origin': 'Original literal OOXML and Ash labels; no imported assets'}})
    for operation in ('raw-replace', 'raw-insert'):
        for tracked in (True, False):
            cid = operation + ('-tracked' if tracked else '-control')
            path = folder / (cid + '.docx')
            package(path, para('LarchOriginal') + para('LarchTail'),
                    styles_xml=f'<w:styles xmlns:w="{W}"/>')
            middle = 'LarchOriginal' if tracked else ('LarchOriginal LarchReplacement'
                if operation == 'raw-insert' else 'LarchReplacement')
            cases.append({'id': cid, 'input': str(path.relative_to(root)), 'sha256': digest(path),
                          'control': not tracked, 'operation': operation, 'tracked': tracked,
                          'expected': '# Document ' + middle + ' LarchTail', 'anchored': ['LarchTail'],
                          'rights': {'author': 'John Scrudato IV', 'license': 'MIT',
                          'origin': 'Original literal OOXML and Larch labels; no imported assets'}})
    for placement in ('before-table', 'end-of-body'):
        for tracked in (True, False):
            cid = 'table-insert-' + placement + ('-tracked' if tracked else '-control')
            path = folder / (cid + '.docx')
            existing = ('<w:tbl><w:tblPr/><w:tblGrid><w:gridCol w:w="2400"/></w:tblGrid><w:tr><w:tc><w:tcPr/>'
                        + para('LarchCell') + '</w:tc></w:tr></w:tbl>')
            package(path, para('LarchAlpha') + para('LarchBravo') + existing + para('LarchCharlie'),
                    styles_xml=f'<w:styles xmlns:w="{W}"/>')
            original = '# Document LarchAlpha LarchBravo | LarchCell | | --- | LarchCharlie'
            added = '| LarchNew | | --- |'
            inserted = (original.replace('LarchBravo', 'LarchBravo ' + added) if placement == 'before-table'
                        else original + ' ' + added)
            cases.append({'id': cid, 'input': str(path.relative_to(root)), 'sha256': digest(path),
                          'control': not tracked, 'operation': 'table-insert', 'tracked': tracked,
                          'anchor': 'LarchBravo' if placement == 'before-table' else 'LarchCharlie',
                          'expected': inserted, 'anchored': ['LarchAlpha'],
                          'tableInsert': {'revisions': 1 if tracked else 0, 'accepted': inserted,
                                          'rejected': original if tracked else inserted},
                          'rights': {'author': 'John Scrudato IV', 'license': 'MIT',
                          'origin': 'Original literal OOXML and Larch labels; no imported assets'}})
    for kind in ('middle', 'first', 'only', 'wrapped', 'merged', 'textbox', 'opaque'):
        for is_control in (False, True):
            cid = 'deleted-row-' + kind + ('-control' if is_control else '')
            mark = 'w:id="1" w:author="Larch Reviewer"'
            deleted = '' if is_control else '<w:trPr><w:del ' + mark + '/></w:trPr>'
            text = run('LarchRemoved') if is_control else '<w:del w:id="2" w:author="Larch Reviewer"><w:r><w:delText>LarchRemoved</w:delText></w:r></w:del>'
            cell_props = '<w:tcPr><w:gridSpan w:val="2"/></w:tcPr>' if kind == 'merged' else ''
            box = '<w:r>' + vml(para('LarchBox')) + '</w:r>' if kind == 'textbox' else ''
            removed = '<w:tr>' + deleted + '<w:tc>' + cell_props + para(runs=text + box) + '</w:tc></w:tr>'
            if kind == 'wrapped':
                removed = control(removed)
            columns = 2 if kind == 'merged' else 1
            def kept(label):
                return '<w:tr>' + ''.join('<w:tc>' + para(label + (str(i) if columns > 1 else '')) + '</w:tc>' for i in range(columns)) + '</w:tr>'
            rows = removed if kind == 'only' else (removed + kept('LarchHeader') if kind == 'first'
                    else kept('LarchHeader') + removed) + kept('LarchTail')
            body = '<w:tbl><w:tblPr/><w:tblGrid>' + '<w:gridCol w:w="2400"/>' * columns + '</w:tblGrid>' + rows + '</w:tbl>' + para('LarchAfter')
            path = folder / (cid + '.docx')
            package(path, body, namespaces_extra=NS, styles_xml=f'<w:styles xmlns:w="{W}"/>')
            opaque = kind == 'opaque' or (kind == 'merged' and is_control)
            if opaque:
                middle = '```table rows: ' + ('3' if is_control else '2') + ' cols: ' + str(columns) + ' ```'
            elif kind == 'only':
                middle = '| LarchRemoved | | --- |' if is_control else ''
            else:
                labels = ['LarchHeader', 'LarchTail']
                if is_control:
                    labels.insert(0 if kind == 'first' else 1, 'LarchRemoved')
                lines = ['| ' + ' | '.join(label + (str(i) if columns > 1 else '') for i in range(columns)) + ' |' for label in labels]
                lines.insert(1, '|' + ' --- |' * columns)
                middle = ' '.join(lines)
            if kind == 'textbox' and is_control:
                middle += ' LarchBox'
            cases.append({'id': cid, 'input': str(path.relative_to(root)), 'sha256': digest(path),
                          'control': is_control, 'tableMode': 'AlwaysOpaque' if kind == 'opaque' else 'GfmWithOpaqueFallback',
                          'expected': ' '.join(('# Document ' + middle + ' LarchAfter').split()), 'anchored': ['LarchAfter'],
                          'rights': {'author': 'John Scrudato IV', 'license': 'MIT',
                          'origin': 'Original literal OOXML and Larch row labels; no imported assets'}})
    manifest = {'schema': 1, 'suite': 'projection-v4', 'version': 4,
                'generatorSha256': digest(Path(__file__)), 'cases': cases}
    write_json(folder / 'manifest.json', manifest)
    return manifest


def validate(root=ROOT):
    root = Path(root)
    manifest = read_json(root / 'fixtures/projection/manifest.json')
    with tempfile.TemporaryDirectory() as temp:
        regenerated = generate(Path(temp))
        if manifest != regenerated:
            raise ValueError('Projection manifest differs from its original generator')
        for case in manifest['cases']:
            if (root / case['input']).read_bytes() != (Path(temp) / case['input']).read_bytes():
                raise ValueError('Projection input changed: ' + case['id'])
    return manifest


if __name__ == '__main__':
    generate()
