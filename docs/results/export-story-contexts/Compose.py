"""Label unchanged 96-DPI page rasters for review; Pillow is an optional capture tool."""
import hashlib
import json
import subprocess
import sys
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from bench.common import identity
manifest_path, reference_path, baseline_path, candidate_path = map(Path, sys.argv[1:5])
intermediate_path = Path(sys.argv[5]) if len(sys.argv) > 5 else None
manifest = json.loads(manifest_path.read_text())
reference = json.loads((reference_path / 'bundle.json').read_text())
baseline = json.loads((baseline_path / 'inspected.json').read_text())
candidate = json.loads((candidate_path / 'inspected.json').read_text())
output = Path(__file__).resolve().parent
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 15)
heading = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 18)
hash_file = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
by_id = lambda record: {entry['id']: entry for entry in record['cases']}
base_cases, candidate_cases = by_id(baseline), by_id(candidate)
expected = {case['id'] for case in manifest['cases']}
if set(reference['cases']) != expected or set(base_cases) != expected or set(candidate_cases) != expected:
    raise ValueError('Capture coverage differs from the focused manifest')
if reference['suiteDigest'] != identity(manifest):
    raise ValueError('Reference was captured under a different manifest')
for captured in (baseline, candidate):
    if captured['inspectionManifestSha256'] != hash_file(manifest_path):
        raise ValueError('PDF checks were run under a different manifest')
intermediate = None
intermediate_cases = {}
if intermediate_path:
    intermediate = json.loads((intermediate_path / 'inspected.json').read_text())
    captured_manifest = json.loads((intermediate_path / 'manifest.json').read_text())
    if intermediate['inspectionManifestSha256'] != hash_file(intermediate_path / 'manifest.json') or intermediate['manifestSha256'] != hash_file(intermediate_path / 'manifest.json'):
        raise ValueError('Intermediate checks have a different manifest')
    intermediate_cases = by_id(intermediate)
    if set(intermediate_cases) != {case['id'] for case in captured_manifest['cases']}:
        raise ValueError('Intermediate case coverage differs from its manifest')
    if set(intermediate_cases) - expected:
        raise ValueError('Intermediate contains an unknown case')
    current_cases = by_id(manifest)
    def semantic_case(case):
        return {**case, 'generator': {key: value for key, value in case['generator'].items() if key != 'sha256'}}
    for prior in captured_manifest['cases']:
        current = current_cases[prior['id']]
        # Later generator additions refresh its shared digest without changing an existing case.
        if semantic_case(prior) != semantic_case(current):
            raise ValueError('Intermediate source or assertions changed: ' + prior['id'])
record = {
    'schema': 1, 'status': 'unscored-public-api-diagnostics',
    'baseline': {key: baseline[key] for key in ('candidate', 'sourceTree', 'buildIdentitySha256', 'browserVersion', 'executableSha256', 'sandbox', 'fontContract')},
    'candidate': {key: candidate[key] for key in ('candidate', 'sourceTree', 'buildIdentitySha256', 'browserVersion', 'executableSha256', 'sandbox', 'fontContract')},
    'manifestSha256': hash_file(manifest_path),
    'referenceBundleSha256': hash_file(reference_path / 'bundle.json'),
    'referenceEnvironment': reference['environment'],
    'limitations': ['Pinned benchmark runtime is ineligible on this host: unprivileged user namespaces are denied.',
                    'Borrowed system-browser public-API captures carry no rendering fidelity scores.',
                    'These focused cases do not establish full-suite or Word rendering parity.',
                    'Independent PDF checks do not compare candidate page counts or pixels with the reference renderer.',
                    'Any LibreOffice reference failing the declared token contract remains ineligible; placeholder contracts do not establish vector-rendering fidelity.'],
    'cases': [],
}
record['composition'] = {'baseline': baseline.get('composition', []),
                         'candidate': candidate.get('composition', []),
                         'reference': reference.get('composition', [])}

if intermediate:
    record['intermediate'] = {key: intermediate[key] for key in ('candidate', 'sourceTree', 'buildIdentitySha256', 'browserVersion', 'executableSha256', 'sandbox', 'fontContract', 'manifestSha256', 'inspectionManifestSha256')}

def pages(folder):
    return sorted(folder.glob('page-*.png'), key=lambda p: int(p.stem.split('-')[-1]))

def wrapped(draw, text, xy, width=55, fill='#243244', bold=False):
    y = xy[1]
    for line in textwrap.wrap(text, width=width, break_long_words=True):
        draw.text((xy[0], y), line, font=heading if bold else font, fill=fill)
        y += 23 if bold else 20
    return y

for case in manifest['cases']:
    cid = case['id']
    ref = reference['cases'][cid]
    if ref['inputSha256'] != case['sha256']:
        raise ValueError('Reference input changed: ' + cid)
    ref_folder = reference_path / cid
    subprocess.run(['pdftoppm', '-r', '96', '-png', str(reference_path / ref['pdf']), str(ref_folder / 'page')],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    base, cand = base_cases[cid], candidate_cases[cid]
    for result in (base, cand):
        if result['inputSha256'] != case['sha256']:
            raise ValueError('Candidate input changed: ' + cid)
    panels = [
        ('Baseline ' + baseline['candidate'][:8], base, pages(baseline_path / cid)),
        ('LibreOffice reference', {'status': 'delivered', 'mandatoryPdfFailures': ref['ineligibleChecks']}, pages(ref_folder)),
        ('Candidate ' + candidate['candidate'][:8], cand, pages(candidate_path / cid)),
    ]
    if cid in intermediate_cases:
        prior = intermediate_cases[cid]
        if prior['inputSha256'] != case['sha256']:
            raise ValueError('Intermediate input changed: ' + cid)
        panels.insert(1, ('Intermediate ' + intermediate['candidate'][:8], prior, pages(intermediate_path / cid)))
    all_pages = [p for _, _, images in panels for p in images]
    widths = [Image.open(p).width for p in all_pages]
    panel_width = max(widths + [507]) + 24
    panel_heights = [sum(Image.open(p).height + 28 for p in images) for _, _, images in panels]
    sheet = Image.new('RGB', (panel_width * len(panels) + 32, max(panel_heights + [220]) + 210), '#e9eef3')
    draw = ImageDraw.Draw(sheet)
    draw.text((16, 12), cid, font=heading, fill='#16283b')
    draw.text((16, 40), 'Unscored diagnostics. Pages shown at original 96-DPI scale; no raster content altered.', font=font, fill='#33475b')
    for i, (title, result, images) in enumerate(panels):
        x = 16 + i * panel_width
        draw.text((x, 76), title, font=heading, fill='#16283b')
        if result['status'] != 'delivered':
            label = 'No PDF delivered: ' + result.get('code', 'conversion failed')
            y = wrapped(draw, label, (x, 108), width=53, fill='#9b2534')
            wrapped(draw, result.get('message', ''), (x, y + 8), width=57, fill='#6b3941')
            continue
        failures = result.get('mandatoryPdfFailures', [])
        label = 'Independent PDF checks: ' + ('pass' if not failures else ', '.join(failures))
        wrapped(draw, label, (x, 108), width=57, fill='#21623c' if not failures else '#8b4a15')
        y = 166
        for number, path in enumerate(images, 1):
            page = Image.open(path).convert('RGB')
            draw.text((x, y), f'Page {number}', font=font, fill='#33475b')
            y += 24
            sheet.paste(page, (x, y))
            y += page.height + 4
    destination = output / (cid + '.png')
    sheet.save(destination, optimize=True)
    record['cases'].append({
        'id': cid, 'inputSha256': case['sha256'], 'screenshot': destination.name, 'screenshotSha256': hash_file(destination),
        'reference': {'eligible': ref['eligible'], 'pdfSha256': ref['pdfSha256'], 'failures': ref['ineligibleChecks'], 'renderer': ref['renderer']},
        'pageRasterSha256': {title: [hash_file(path) for path in images] for title, _, images in panels},
        'baseline': base, 'candidate': cand,
    })
    if cid in intermediate_cases:
        record['cases'][-1]['intermediate'] = intermediate_cases[cid]
record['captureTools'] = {name: hash_file(output / name) for name in ('Capture.mjs', 'Inspect.py', 'Compose.py', 'Policy.mjs', 'InspectPictures.py', 'InspectFonts.py', 'InspectStories.py', 'ProbeClipBoundary.py', 'MergeEvidence.py')}
(output / 'capture.json').write_text(json.dumps(record, indent=2) + '\n')
print(f'Wrote {len(record["cases"])} labeled case sheets')
