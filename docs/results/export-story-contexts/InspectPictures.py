"""Record Poppler bitmap entries separately from the unchanged benchmark PDF checks."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

baseline_path, candidate_path = map(Path, sys.argv[1:3])
expected = {
    'picture-square-front': 1, 'picture-square-behind': 1, 'picture-none-behind-control': 1,
}

executable = Path(shutil.which('pdfimages'))
version = subprocess.run([str(executable), '-v'], capture_output=True, text=True, check=True)
record = {'schema': 1, 'status': 'unscored-bitmap-diagnostic',
          'tool': {'sha256': hashlib.sha256(executable.read_bytes()).hexdigest(),
                   'version': (version.stdout + version.stderr).splitlines()[0]},
          'note': 'Counts are Poppler bitmap entries, excluding masks. Integer PPI is retained as reported; no precise physical-size or fidelity score is inferred.',
          'sources': {}, 'cases': []}
for folder, key in [(baseline_path, 'baseline'), (candidate_path, 'candidate')]:
    capture = json.loads((folder / 'capture.json').read_text())
    record['sources'][key] = capture['candidate']
    for case in capture['cases']:
        short = case['id'].removeprefix('export-story-context-')
        if short not in expected:
            continue
        item = {'id': case['id'], 'renderer': key, 'inputSha256': case['inputSha256'],
                'expectedBitmapEntries': expected[short], 'status': case['status']}
        if case['status'] == 'delivered':
            path = folder / case['id'] / 'candidate.pdf'
            item['pdfSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            if item['pdfSha256'] != case['pdfSha256']:
                raise ValueError('Captured PDF changed: ' + case['id'])
            output = subprocess.run([str(executable), '-list', str(path)], capture_output=True, text=True, check=True)
            images = []
            for line in output.stdout.splitlines()[2:]:
                values = line.split()
                if len(values) >= 14 and values[2] == 'image':
                    images.append({'page': int(values[0]), 'index': int(values[1]),
                                   'widthPixels': int(values[3]), 'heightPixels': int(values[4]),
                                   'xPpi': float(values[12]), 'yPpi': float(values[13])})
            item['bitmapEntries'] = images
            item['countMatches'] = len(images) == expected[short]
        record['cases'].append(item)
output = Path(__file__).with_name('bitmap-inventory.json')
record['captureToolSha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
output.write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({'inspected': len(record['cases']),
                  'countMismatches': [item['id'] for item in record['cases'] if item.get('countMatches') is False]}, indent=2))
