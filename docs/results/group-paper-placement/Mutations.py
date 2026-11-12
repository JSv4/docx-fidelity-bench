"""Reject corrupted retained PDF observations without reusing renderer geometry logic."""
import copy
import gzip
import json
import sys
from pathlib import Path

folder = Path(__file__).resolve().parent
sys.path.insert(0, str(folder.parents[2]))
from bench.common import digest
from bench.pdf import correctness
from SourceCoordinates import output_checks

evidence = json.loads((folder / 'evidence.json').read_text())
manifest = json.loads(gzip.decompress((folder / evidence['manifest']['file']).read_bytes()))
results = []
for entry in evidence['cases']:
    case = next(c for c in manifest['cases'] if c['id'] == entry['id'])
    panel = next(p for p in entry['panels'] if p['renderer'] == 'candidate')
    inspection = folder / panel['inspection']['file']
    assert digest(inspection) == panel['inspection']['sha256']
    info = json.loads(gzip.decompress(inspection.read_bytes()))
    geometry = json.loads(gzip.decompress((folder / panel['groupGeometry']['file']).read_bytes()))
    paper = geometry['sourcePaperOnPhysicalPt']
    proof = entry['sourceCoordinates']
    assert all(c['passed'] for c in output_checks(proof, info['words'], paper))
    primary = case['pdfCompanion']['profile'].get('commentColumnPlacement') != 'balloons'
    if primary:
        assert all(c['passed'] for c in correctness(case, info, info))
    for label in proof['framesPt']:
        if label == 'SedgeFar' and proof['outsideFarMember']:
            continue
        for mutation in ('right', 'left', 'missing', 'duplicate', 'page'):
            changed = copy.deepcopy(info)
            word = next(w for w in changed['words'] if w['text'] == label)
            if mutation in ('right', 'left'):
                for axis in (0, 2):
                    word['rect'][axis] += 100 if mutation == 'right' else -100
            elif mutation == 'missing':
                changed['words'].remove(word)
            elif mutation == 'duplicate':
                changed['words'].append(copy.deepcopy(word))
            else:
                word['page'] = 2
            assert not all(c['passed'] for c in output_checks(proof, changed['words'], paper))
            if primary:
                assert not all(c['passed'] for c in correctness(case, info, changed))
            results.append({'case': case['id'], 'label': label, 'mutation': mutation,
                            'sourceFrameRejected': True, 'primaryRejected': primary})
result = {'scope': 'Mutated retained PDF observations; no modified PDF was rendered.',
          'scriptSha256': digest(Path(__file__)), 'evidenceSha256': digest(folder / 'evidence.json'),
          'mutations': results}
(folder / 'mutations.json').write_text(json.dumps(result, indent=2) + '\n')
print(f'Rejected {len(results)} corrupted observations; {sum(r["primaryRejected"] for r in results)} also reject primary assertions')
