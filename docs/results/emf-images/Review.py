"""Freeze the eight original Iris captures, with reference provenance and labeled crops."""
import gzip
import json
import shutil
import sys
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from bench.common import digest
from bench.pdf import inspect_case_pdf, correctness

run, refs, baseline = map(lambda p: Path(p).resolve(), sys.argv[1:4])
out = Path(__file__).resolve().parent
manifest = json.loads((run / 'manifest.json').read_text())
result = json.loads((run / 'candidate/result.json').read_text())
assert len(manifest['cases']) == 8 and result['summary']['mandatoryPassRate'] == 1
bundle = json.loads((refs / 'bundle.json').read_text())
direct = json.loads((refs / 'direct/bundle.json').read_text())
assert bundle['track'] == 'libreoffice-equivalent-controls'
evidence = dict(scope='Eight authored EMF/PNG inputs; seven EMF native main placeholders, '
    'eight production candidate PDFs. Geometry controls are not Word adjudication.',
    candidate=result['candidate'], baseline=json.loads((baseline / 'evidence.json').read_text()),
    summary=result['summary'], cases=[])
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 16)
(out / 'pdf').mkdir(exist_ok=True)
for name, data in [('manifest', manifest), ('reference-bundle', bundle), ('direct-bundle', direct), ('result', result)]:
    (out / (name + '.json.gz')).write_bytes(gzip.compress((json.dumps(data, indent=2)+'\n').encode(), mtime=0))
for case in manifest['cases']:
    cid = case['id']; assert digest(ROOT / case['input']) == case['sha256']
    folder = run / 'candidate' / cid
    native = json.loads((folder / 'evidence.json').read_text())
    production = json.loads((folder / 'production.json').read_text())
    assert production['source']['rawPackageBytesDigest'] == case['sha256']
    assert production['status'] == 'complete' and not production['unsupportedContent']
    assert all(c['passed'] for c in native['checks'])
    candidate = inspect_case_pdf(folder / 'candidate.pdf', case)
    reference = bundle['cases'][cid]['inspection']
    assert all(c['passed'] for c in correctness(case, reference, candidate))
    # Growing a page-anchored, nonwrapping frame must not move the text receipt.
    assert reference['words'] == direct['cases'][cid]['inspection']['words']
    facts = dict(candidate=candidate, reference=reference, direct=direct['cases'][cid]['inspection'],
                 nativeMain=next(c for c in evidence['baseline']['cases'] if c['id'] == cid),
                 production=production, measured=native)
    (out / (cid + '.json.gz')).write_bytes(gzip.compress((json.dumps(facts,indent=2)+'\n').encode(),mtime=0))
    (out / (cid + '-main.html.gz')).write_bytes(gzip.compress((baseline / (cid+'.html')).read_bytes(),mtime=0))
    entry = dict(id=cid, inputSha256=case['sha256'], score=native['score'], panels=[])
    roles = [('LibreOffice direct', refs / 'direct' / direct['cases'][cid]['pdf']),
             ('Reference: ' + bundle['cases'][cid]['referenceSource']['kind'], refs / bundle['cases'][cid]['pdf']),
             ('Docxodus ' + result['candidate'][:8], folder / 'candidate.pdf')]
    sheet = Image.new('RGB', (1050, 435), '#dddddd')
    ImageDraw.Draw(sheet).text((10,8),cid,fill='black',font=font)
    for index, (label, path) in enumerate(roles):
        role = ('direct','reference','candidate')[index]
        target = out / 'pdf' / f'{cid}-{role}.pdf';shutil.copyfile(path,target)
        doc = fitz.open(path);assert len(doc)==1
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(1.4,1.4),clip=fitz.Rect(55,70,295,335),alpha=False)
        panel = Image.new('RGB',(350,400),'white')
        ImageDraw.Draw(panel).text((8,8),label,fill='black',font=font)
        panel.paste(Image.frombytes('RGB',(pix.width,pix.height),pix.samples),(7,32))
        sheet.paste(panel,(index*350,35))
        entry['panels'].append(dict(role=role,pdf=str(target.relative_to(out)),sha256=digest(target)))
    sheet.save(out / (cid+'.png'));entry['screenshot']=cid+'.png'
    evidence['cases'].append(entry)
(out/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
print('Retained eight three-panel review sheets and source-bound production evidence')
