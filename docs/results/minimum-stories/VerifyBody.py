"""Replay the eight unchanged body-minimum contracts after shared paint normalization."""
import gzip
import json
import shutil
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / 'docs/results/natural-minimum'))
from bench.common import digest
from bench.pdf import inspect_companion_pdf, correctness, companion_checks
from MinimumPitch import checks as pitch_checks

run = Path(sys.argv[1]).resolve()
out = Path(__file__).resolve().parent / 'body-regression'
out.mkdir(exist_ok=True)
manifest = json.loads((run / 'manifest.json').read_text())
capture = json.loads((run / 'candidate/capture.json').read_text())
story_capture = json.loads((run.parent / 'candidate/capture.json').read_text())
for key in ('candidate', 'sourceTree', 'buildIdentitySha256', 'browserVersion',
            'executableSha256', 'sandbox', 'fontPolicy', 'fontContract'):
    assert capture[key] == story_capture[key], key
assert capture['manifestSha256'] == digest(run / 'manifest.json')
assert capture['sandbox'] is True and capture['fontPolicy'] == 'strict'
assert len(manifest['cases']) == len(capture['cases']) == 8
records = []
for case in manifest['cases']:
    cid = case['id']
    assert digest(root / case['input']) == case['sha256']
    folder = run / 'candidate' / cid
    record = next(c for c in capture['cases'] if c['id'] == cid)
    assert record['inputSha256'] == case['sha256'] and record['status'] == 'delivered'
    pdf = folder / 'candidate.pdf'
    assert digest(pdf) == record['pdfSha256']
    report = json.loads((folder / 'production.json').read_text())
    assert digest(folder / 'production.json') == record['renderReportSha256']
    assert digest(folder / 'candidate.html') == record['htmlSha256']
    assert report['source']['rawPackageBytesDigest'] == case['sha256'] and report['bindings']['pdfDigest'] == digest(pdf)
    assert report['status'] == 'complete' and not report['warnings'] and not report['unsupportedContent']
    assert report['options']['policy']['strictFonts'] is True and all(f['verified'] for f in report['fonts'])
    assert report['options']['reviewProfile'] == 'final' and report['options']['commentProfile'] == 'hidden'
    assert report['environment']['verification'] == 'browserObserved'
    assert report['environment']['observed']['browserBuild'] == capture['browserVersion']
    info = inspect_companion_pdf(pdf, case['pdfCompanion'])
    with gzip.open(root / f'docs/results/natural-minimum/{cid}-reference-inspection.json.gz', 'rt') as stream:
        reference = json.load(stream)
    checks = correctness(case, reference, info) + companion_checks(case['pdfCompanion'], info) + pitch_checks(case, info)
    assert all(c['passed'] for c in checks), (cid, [c for c in checks if not c['passed']])
    target = out / (cid + '.pdf'); shutil.copyfile(pdf, target)
    for suffix, value in [('inspection', info), ('report', report)]:
        (out / f'{cid}-{suffix}.json.gz').write_bytes(gzip.compress((json.dumps(value, indent=2) + '\n').encode(), mtime=0))
    records.append(dict(id=cid, inputSha256=case['sha256'], pdf=target.name, pdfSha256=digest(target), pages=len(info['geometry']), checks=checks))
(out / 'evidence.json').write_text(json.dumps(dict(capture=capture, manifestSha256=digest(run / 'manifest.json'), cases=records), indent=2) + '\n')
print('All eight unchanged body contracts pass:', sum(c['pages'] for c in records), 'pages')
