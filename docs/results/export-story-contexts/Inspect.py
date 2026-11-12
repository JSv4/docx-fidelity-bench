"""Independent PDF content checks and 96-DPI rasters; no numeric fidelity score."""
import json
import hashlib
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from bench.pdf import inspect_case_pdf, reference_failures

manifest_path, capture_path = map(Path, sys.argv[1:3])
manifest = json.loads(manifest_path.read_text())
capture = json.loads(capture_path.read_text())
cases = {case['id']: case for case in manifest['cases']}
capture['inspectionManifestSha256'] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
for result in capture['cases']:
    if result['status'] != 'delivered':
        continue
    if result['inputSha256'] != cases[result['id']]['sha256']:
        raise ValueError('Input changed since capture: ' + result['id'])
    folder = capture_path.parent / result['id']
    pdf = folder / 'candidate.pdf'
    info = inspect_case_pdf(pdf, cases[result['id']])
    result['mandatoryPdfFailures'] = reference_failures(cases[result['id']], info, 'libreoffice')
    (folder / 'inspection.json').write_text(json.dumps(info, indent=2) + '\n')
    subprocess.run(['pdftoppm', '-r', '96', '-png', str(pdf), str(folder / 'page')], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
(capture_path.parent / 'inspected.json').write_text(json.dumps(capture, indent=2) + '\n')
print(json.dumps({'delivered': sum(x['status'] == 'delivered' for x in capture['cases']),
                  'checked': sum(x.get('mandatoryPdfFailures') == [] for x in capture['cases']),
                  'failures': {x['id']: x.get('mandatoryPdfFailures', x.get('message')) for x in capture['cases']
                               if x.get('mandatoryPdfFailures') != []}}, indent=2))
