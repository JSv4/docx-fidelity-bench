"""Bind actual configured font bytes to each delivered public render report."""
import hashlib
import json
from pathlib import Path
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


environment = json.loads(Path(sys.argv[1]).read_text())
record = {'schema': 1, 'status': 'unscored-font-binding-diagnostic', 'files': [], 'captures': [],
          'toolSha256': digest(Path(__file__))}
for name, expected in environment['contract']['fonts'].items():
    paths = [Path(folder) / name for folder in environment['fontDirectories'] if (Path(folder) / name).is_file()]
    if len(paths) != 1 or digest(paths[0]) != expected['sha256']:
        raise ValueError('Changed or ambiguous configured font: ' + name)
    record['files'].append({'name': name, **expected})
for folder in map(Path, sys.argv[2:]):
    capture = json.loads((folder / 'capture.json').read_text())
    if capture['fontContract'] != environment['contract']['fonts']:
        raise ValueError('Different declared font contract')
    item = {'source': capture['candidate'], 'captureSha256': digest(folder / 'capture.json'), 'cases': []}
    for case in capture['cases']:
        if case['status'] != 'delivered':
            continue
        path = folder / case['id'] / 'production.json'
        if digest(path) != case['renderReportSha256']:
            raise ValueError('Changed report: ' + case['id'])
        report = json.loads(path.read_text())
        faces = report['fonts']
        passed = bool(faces) and all(
            any(font['fileSha256'] == expected['sha256'] and font['resolvedFamily'] == expected['family']
                for expected in record['files'])
            and font['verified'] and font['faceMatch'] == 'exact' and font['source'] == 'configured'
            and font['glyphCoverage'] == 'complete' for font in faces)
        item['cases'].append({'id': case['id'], 'reportSha256': digest(path), 'passed': passed,
                              'faces': [{key: font.get(key) for key in
                                         ('resolvedFamily', 'resolvedFace', 'fileSha256', 'verified', 'faceMatch', 'source', 'glyphCoverage')}
                                        for font in faces]})
    record['captures'].append(item)
Path(__file__).with_name('font-bindings.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({item['source']: {'delivered': len(item['cases']), 'verified': sum(case['passed'] for case in item['cases'])}
                  for item in record['captures']}, indent=2))
