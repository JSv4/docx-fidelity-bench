"""Record textbox line advances independently; do not alter benchmark scores or PDF content."""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from bench.pdf import inspect_pdf

folders = dict(zip(('baseline', 'candidate'), map(Path, sys.argv[1:3])))
if len(folders) != 2:
    raise SystemExit('Usage: InspectLines.py BASELINE_DIR CANDIDATE_DIR')
record = {'schema': 1, 'status': 'unscored-textbox-line-diagnostic', 'sources': {}, 'pairs': [],
          'note': 'Line advances use raw PDF word yMin coordinates. A 0.75pt tolerance allows one CSS pixel of print rounding; no raster or Word-parity score is inferred.'}
for renderer, folder in folders.items():
    capture = json.loads((folder / 'capture.json').read_text())
    record['sources'][renderer] = capture['candidate']
    cases = {case['id']: case for case in capture['cases']}
    for dialect in ('drawingml', 'vml'):
        for inner in ('natural', 'exact'):
            pair = {'renderer': renderer, 'dialect': dialect, 'innerSpacing': inner, 'observations': []}
            for host in (1, 3):
                cid = f'export-inline-context-textbox-{dialect}-{inner}-host{host}'
                case = cases[cid]
                item = {'id': cid, 'inputSha256': case['inputSha256'], 'hostMultiple': host, 'status': case['status']}
                if case['status'] == 'delivered':
                    pdf = folder / cid / 'candidate.pdf'
                    item['pdfSha256'] = hashlib.sha256(pdf.read_bytes()).hexdigest()
                    if item['pdfSha256'] != case['pdfSha256']:
                        raise ValueError('Captured PDF changed: ' + cid)
                    info = inspect_pdf(pdf)
                    lines = [[word for word in info['words'] if word['text'] == f'FlintBoxLine{index}'] for index in range(1, 5)]
                    item['completeUniqueLines'] = all(len(line) == 1 for line in lines)
                    item['lines'] = [line[0] for line in lines if len(line) == 1]
                    if item['completeUniqueLines'] and len({line[0]['page'] for line in lines}) == 1:
                        item['advancesPt'] = [lines[index + 1][0]['rect'][1] - lines[index][0]['rect'][1] for index in range(3)]
                        if inner == 'exact':
                            item['authoredAdvancePt'] = 14
                            item['withinAuthoredAdvanceTolerance'] = all(abs(step - 14) <= 0.750001 for step in item['advancesPt'])
                pair['observations'].append(item)
            observations = pair['observations']
            if all('advancesPt' in item for item in observations):
                difference = max(abs(a - b) for a, b in zip(observations[0]['advancesPt'], observations[1]['advancesPt']))
                pair['maxHostAdvanceDifferencePt'] = difference
                pair['hostAdvancesAgreeWithinTolerance'] = difference <= 0.750001
            record['pairs'].append(pair)
record['captureToolSha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
Path(__file__).with_name('textbox-line-inventory.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({'pairs': len(record['pairs']), 'comparable': sum('maxHostAdvanceDifferencePt' in pair for pair in record['pairs']),
                  'hostAdvanceMismatches': [pair for pair in record['pairs'] if pair.get('hostAdvancesAgreeWithinTolerance') is False]}, indent=2))
