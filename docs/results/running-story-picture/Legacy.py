"""Recheck the six unchanged running-width cases on the repaired renderer."""
import gzip
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from bench.common import digest
from bench.pdf import inspect_companion_pdf, companion_checks, correctness

out = Path(__file__).resolve().parent
previous = out.parent / 'running-character-width'
run = Path(sys.argv[1]).resolve()
source = Path(sys.argv[2]).resolve()
spec = importlib.util.spec_from_file_location('legacy_width_checks', previous / 'WidthChecks.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
manifest = json.loads((run / 'manifest.json').read_text())
capture = json.loads((run / 'capture.json').read_text())
build = json.loads((source / '.docx-bench-build.json').read_text())
assert capture['candidate'] == build['commit'] == subprocess.check_output(['git','rev-parse','HEAD'], cwd=source, text=True).strip()
assert capture['buildIdentitySha256'] == digest(source / '.docx-bench-build.json')
assert capture['manifestSha256'] == digest(run / 'manifest.json')
assert capture['fontPolicy'] == 'strict' and capture['sandbox'] is True
for name, expected in build['files'].items(): assert digest(source / name) == expected
old = json.loads((previous / 'evidence.json').read_text())
result = dict(candidate=build['commit'], buildIdentitySha256=capture['buildIdentitySha256'],
    previousEvidenceSha256=digest(previous / 'evidence.json'), capture=capture, cases=[])
for case in manifest['cases']:
    cid = case['id']; folder = run / cid
    record = next(c for c in capture['cases'] if c['id'] == cid)
    assert record['status'] == 'delivered' and record['inputSha256'] == digest(root / case['input']) == case['sha256']
    pdf = folder / 'candidate.pdf'; assert digest(pdf) == record['pdfSha256']
    info = inspect_companion_pdf(pdf, case['pdfCompanion'])
    with gzip.open(previous / (cid + '-candidate-inspection.json.gz'), 'rt') as stream: before = json.load(stream)
    checks = module.checks(case, info) + companion_checks(case['pdfCompanion'], info) + correctness(case, before, info)
    assert all(c['passed'] for c in checks)
    assert info['geometry'] == before['geometry'] and len(info['words']) == len(before['words'])
    assert all(a['text'] == b['text'] and a['page'] == b['page'] and max(abs(x-y) for x,y in zip(a['rect'],b['rect'])) <= .02 for a,b in zip(before['words'],info['words']))
    report = json.loads((folder / 'production.json').read_text())
    assert digest(folder / 'production.json') == record['renderReportSha256']
    assert report['source']['rawPackageBytesDigest'] == case['sha256'] and report['bindings']['pdfDigest'] == digest(pdf)
    assert report['status'] == 'complete' and not report['warnings'] and not report['unsupportedContent']
    assert report['fonts'] and all(f['verified'] for f in report['fonts'])
    assert report['options']['policy']['strictFonts'] is True
    assert digest(folder / 'candidate.html') == record['htmlSha256']
    target = out / 'legacy'; target.mkdir(exist_ok=True)
    files = {}
    for suffix, payload in [('inspection', json.dumps(info,indent=2).encode()), ('report',(folder/'production.json').read_bytes())]:
        path = target / (cid + '-' + suffix + '.json.gz'); path.write_bytes(gzip.compress(payload,mtime=0)); files[path.name]=digest(path)
    path = target / (cid + '.pdf'); shutil.copyfile(pdf,path); files[path.name]=digest(path)
    expected = next(p['pageRasterSha256'] for c in old['cases'] if c['id'] == cid for p in c['panels'] if p['renderer']=='candidate')
    rasters=[]
    for page in range(1,5):
        path = folder / f'replay-{page}'
        subprocess.run(['pdftoppm','-r','96','-f',str(page),'-l',str(page),'-singlefile','-png',str(pdf),str(path)],check=True,capture_output=True)
        rasters.append(digest(path.with_suffix('.png')))
    assert rasters == expected, cid
    result['cases'].append(dict(id=cid, checks=checks, unchangedGeometryTolerancePt=.02, unchangedPageRasters=rasters, retainedFiles=files))
assert len(result['cases']) == 6
(out / 'legacy-replay.json').write_text(json.dumps(result,indent=2)+'\n')
print('Six unchanged cases: 24 page rasters identical; all source checks and strict-font reports verified')
