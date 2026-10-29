"""Original packages and exact action expectations for the unweighted editor diagnostic."""
from pathlib import Path
import tempfile
from .common import ROOT, digest, read_json, write_json
from .fixtures import W, FONT, package, para, run

STAMP = 'w:author="Cedar" w:date="2026-01-01T00:00:00Z"'
EMPTY = (f'<w:moveFromRangeStart w:id="8" w:name="CedarLeftover" {STAMP}/><w:moveFromRangeEnd w:id="8"/>'
         f'<w:customXmlInsRangeStart w:id="9" {STAMP}/><w:customXmlInsRangeEnd w:id="9"/>')
INSERT = f'<w:ins w:id="11" {STAMP}>' + run('New ') + '</w:ins>'
STYLES = (f'<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr>'
          f'<w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}"/><w:sz w:val="22"/>'
          '</w:rPr></w:rPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
          '<w:name w:val="Normal"/></w:style></w:styles>')


def generate(root=ROOT):
    root = Path(root)
    folder = root / 'fixtures/editor'
    folder.mkdir(parents=True, exist_ok=True)
    cases = []
    for action in ('review-count', 'revision-target', 'caret', 'copy', 'copy-classes'):
        for control in (False, True):
            cid = action + ('-control' if control else '')
            expected = {'text': 'Cedar clause', 'tabs': 0, 'insertions': 0, 'rangeMarkers': 0}
            if action == 'review-count':
                content = (INSERT if control else EMPTY) + run('Cedar clause')
                expected.update(text=('New ' if control else '') + 'Cedar clause',
                                insertions=int(control), rangeMarkers=0 if control else 4,
                                badge='1 change' if control else 'No tracked changes')
            elif action == 'revision-target':
                content = ('' if control else EMPTY) + INSERT + run('Cedar clause')
                expected.update(text='New Cedar clause', rangeMarkers=0 if control else 4)
            else:
                native = ' ' if control else '\t'
                content = '<w:r><w:rPr>' + ('<w:b/><w:i/>' if action == 'copy-classes' else '') + '</w:rPr>'
                content += '<w:t>1.2</w:t>' + ('<w:t xml:space="preserve"> </w:t>' if control else '<w:tab/>')
                content += '<w:t>Cedar</w:t></w:r>'
                expected.update(text='1.2' + native + ('XCedar' if action == 'caret' else 'Cedar'), tabs=int(not control))
            path = folder / (cid + '.docx')
            package(path, para(runs=content), styles_xml=STYLES)
            cases.append({'id': cid, 'input': str(path.relative_to(root)), 'sha256': digest(path),
                          'action': action, 'control': control, 'expected': expected,
                          'rights': {'author': 'John Scrudato IV', 'license': 'MIT',
                                     'origin': 'Original literal OOXML and Cedar text authored for this diagnostic',
                                     'assets': 'No imported document, font program, image, or external resource'}})
    registry = {'schema': 1, 'suite': 'editor-ui-v1', 'version': 1,
                'scope': 'Exact browser observations; no weighted PDF/redline fidelity score',
                'generatorSha256': digest(Path(__file__)), 'cases': cases}
    write_json(folder / 'manifest.json', registry)
    return registry


def validate(root=ROOT):
    root = Path(root)
    registry = read_json(root / 'fixtures/editor/manifest.json')
    if registry.get('schema') != 1 or registry.get('suite') != 'editor-ui-v1' or registry.get('version') != 1:
        raise ValueError('Unknown editor diagnostic contract')
    if registry.get('generatorSha256') != digest(Path(__file__)):
        raise ValueError('Editor generator changed without regeneration')
    cases = registry.get('cases')
    ids = [c['id'] for c in cases]
    if len(ids) != 10 or len(set(ids)) != len(ids):
        raise ValueError('Editor diagnostic requires all five reproducer/control pairs')
    for case in cases:
        if case['input'] != f"fixtures/editor/{case['id']}.docx" or digest(root / case['input']) != case['sha256']:
            raise ValueError('Editor input missing or changed: ' + case['id'])
        if case['rights']['author'] != 'John Scrudato IV' or case['rights']['license'] != 'MIT':
            raise ValueError('Missing original editor input rights')
    with tempfile.TemporaryDirectory() as temp:
        if generate(Path(temp)) != registry:
            raise ValueError('Editor declarations differ from their versioned original generator')
    return registry


if __name__ == '__main__':
    generate()
