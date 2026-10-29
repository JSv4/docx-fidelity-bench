"""Compose labeled sheets from the immutable CI reports' actual first-page rasters.

Usage: python3 Capture.py BEFORE_ARTIFACT AFTER_ARTIFACT HTML_DIR
Then run Capture.mjs with pinned Playwright, HTML_DIR, and this directory.
"""
import base64
import hashlib
import html
import json
import sys
from pathlib import Path

before_root, after_root, output = map(Path, sys.argv[1:])
output.mkdir(parents=True, exist_ok=True)
here = Path(__file__).resolve().parent
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text())
before_path = before_root / 'runs/candidate/result.json'
after_path = after_root / 'runs/candidate/result.json'
before, after = read(before_path), read(after_path)
assert before['summary']['complete'] and after['summary']['complete']
assert after['summary']['mandatoryPassRate'] == 1
assert before['suite'] == after['suite'] and before['contractDigest'] == after['contractDigest']
assert [c['id'] for c in before['cases']] == [c['id'] for c in after['cases']]
records = []

def image_panel(title, image):
    data = base64.b64encode(image.read_bytes()).decode()
    return f'<section><h2>{html.escape(title)}</h2><img src="data:image/png;base64,{data}"></section>'

for old, new in zip(before['cases'], after['cases']):
    cid = new['id']
    assert cid.startswith('nested-inline-') and '/' not in cid
    old_dir = before_root / 'runs/candidate' / cid
    new_dir = after_root / 'runs/candidate' / cid
    panels = image_panel('LibreOffice registered reference', new_dir / '1-reference.png')
    evidence = {'referenceRaster': sha(new_dir / '1-reference.png'),
                'beforeEvidence': sha(old_dir / 'evidence.json'),
                'afterEvidence': sha(new_dir / 'evidence.json')}
    if (old_dir / 'candidate.pdf').exists():
        panels += image_panel(f"Baseline {before['candidate'][:8]} — score {old['score']:.5f}", old_dir / '1-candidate.png')
        evidence.update(beforePdf=sha(old_dir / 'candidate.pdf'), beforeRaster=sha(old_dir / '1-candidate.png'))
    else:
        error = old['adapter']['error']
        panels += '<section><h2>Baseline ' + before['candidate'][:8] + ' — no PDF delivered</h2><pre>' + html.escape(json.dumps(error, indent=2)) + '</pre><p>The recorded export readiness failure is shown here. No baseline page exists.</p></section>'
        evidence['beforeError'] = error
    panels += image_panel(f"Candidate {after['candidate'][:8]} — score {new['score']:.5f}", new_dir / '1-candidate.png')
    evidence.update(afterPdf=sha(new_dir / 'candidate.pdf'), afterRaster=sha(new_dir / '1-candidate.png'))
    document = '<!doctype html><meta charset="utf-8"><style>body{font:16px Arial;margin:20px;color:#172536}h1{font-size:24px}h2{font-size:17px;margin:12px}main{display:flex;gap:12px}section{border:1px solid #aab8c8;flex:1;min-width:0;background:#f4f7fb}img{display:block;width:100%}pre,p{white-space:pre-wrap;overflow-wrap:anywhere;margin:18px}header p{margin:8px 0}</style><header><h1>' + cid + '</h1><p>Exact CI PDFs; first page. Same authored input and registered reference in both runs.</p><p>Diagnostic subset only — availability at depth 64, not a scaling or full-suite claim.</p></header><main>' + panels + '</main>'
    page = output / (cid + '.html')
    page.write_text(document)
    records.append({'id': cid, 'inputSha256': new['referenceSource']['inputSha256'],
                    'before': {'status': old['status'], 'score': old['score']},
                    'after': {'status': new['status'], 'score': new['score']},
                    'htmlSha256': sha(page), **evidence})

binding = {'schema': 1, 'beforeCommit': before['candidate'], 'afterCommit': after['candidate'],
           'beforeRun': 40925979882, 'afterRun': 40928532433,
           'beforeResultSha256': sha(before_path), 'afterResultSha256': sha(after_path),
           'selectedManifestSha256': sha(after_root / 'runs/selected-manifest.json'),
           'scripts': {n: sha(here / n) for n in ('Capture.py', 'Capture.mjs')}, 'cases': records}
(output / 'capture.json').write_text(json.dumps(binding, indent=2) + '\n')
