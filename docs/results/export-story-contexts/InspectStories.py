"""Independent PDF coordinates for authored tab partitions and raised inline boxes."""
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from bench.pdf import inspect_pdf

record = {'schema': 1, 'status': 'unscored-story-geometry-diagnostic', 'captures': [],
          'toolSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'note': 'Raw PDF word coordinates are measured in points. A 0.75pt tolerance allows one CSS pixel of print rounding. These are source-coordinate and paired-input checks, not a Word or raster fidelity score.'}
for folder in map(Path, sys.argv[1:]):
    capture = json.loads((folder / 'capture.json').read_text())
    by_id = {case['id']: case for case in capture['cases']}
    item = {'source': capture['candidate'], 'tabGroups': [], 'raisedPair': []}

    def words(identifier):
        case = by_id[identifier]
        if case['status'] != 'delivered':
            return None
        pdf = folder / identifier / 'candidate.pdf'
        if hashlib.sha256(pdf.read_bytes()).hexdigest() != case['pdfSha256']:
            raise ValueError('Changed PDF: ' + identifier)
        return inspect_pdf(pdf)['words']

    for dialect in ('drawingml', 'vml'):
        group = {'dialect': dialect, 'cases': []}
        for mode in ('isolated-control', 'mixed', 'single'):
            cid = f'export-story-context-mixed-tabs-{dialect}-{mode}'
            found = words(cid)
            observation = {'id': cid, 'status': by_id[cid]['status'], 'rows': []}
            if found is not None:
                for number in range(1, 6):
                    row = [[word for word in found if word['text'] == f'Jasper{column}{number:02d}'] for column in 'ABC']
                    if not all(len(column) == 1 for column in row):
                        observation['rows'].append({'number': number, 'complete': False})
                        continue
                    row = [column[0] for column in row]
                    advances = [row[index]['rect'][0] - row[0]['rect'][0] for index in (1, 2)]
                    observation['rows'].append({'number': number, 'complete': True, 'words': row,
                        'authoredColumnAdvancesPt': [100, 210], 'observedColumnAdvancesPt': advances,
                        'passed': len({word['page'] for word in row}) == 1
                                  and max(word['rect'][1] for word in row) - min(word['rect'][1] for word in row) <= 0.750001
                                  and all(abs(value - expected) <= 0.750001 for value, expected in zip(advances, (100, 210)))})
            observation['passed'] = len(observation['rows']) == 5 and all(row.get('passed', False) for row in observation['rows'])
            group['cases'].append(observation)
        item['tabGroups'].append(group)
    for mode in ('unraised-control', 'raised'):
        cid = 'export-story-context-raised-inline-box-' + mode
        found = words(cid)
        observation = {'id': cid, 'status': by_id[cid]['status']}
        if found is not None:
            for key, token in [('label', 'JasperLiftLabel'), ('receipt', 'JasperLiftReceipt')]:
                matches = [word for word in found if word['text'] == token]
                if len(matches) == 1:
                    observation[key] = matches[0]
        item['raisedPair'].append(observation)
    normal, raised = item['raisedPair']
    if all('label' in result and 'receipt' in result for result in item['raisedPair']):
        label_shift = normal['label']['rect'][1] - raised['label']['rect'][1]
        receipt_shift = normal['receipt']['rect'][1] - raised['receipt']['rect'][1]
        item['raisedCheck'] = {'authoredShiftPt': 18, 'observedShiftPt': label_shift, 'receiptShiftPt': receipt_shift,
                              'passed': abs(label_shift - 18) <= 0.750001 and abs(receipt_shift) <= 0.750001
                                        and all(word['page'] == 1 for result in item['raisedPair'] for word in (result['label'], result['receipt']))}
    record['captures'].append(item)
Path(__file__).with_name('story-geometry.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({item['source']: {'tabsPassed': sum(case['passed'] for group in item['tabGroups'] for case in group['cases']),
                                  'raisedPair': item.get('raisedCheck')}
                  for item in record['captures']}, indent=2))
