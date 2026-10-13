from __future__ import annotations
import shutil
import tempfile
import subprocess
from pathlib import Path
from . import adapters, metrics, pdf, report, reference_controls
from .common import ROOT, contained, digest, identity, read_json, validate_registry, write_json
from .environment import environment


def reference_bundle(output):
    registry = validate_registry()
    env = environment([f for c in registry['cases'] for f in c['fonts']])
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    bundle = {'schema': 1, 'track': 'libreoffice', 'suiteDigest': identity(registry), 'environment': env['contract'], 'cases': {}}
    for case in registry['cases']:
        folder = output / case['id']
        folder.mkdir()
        path = folder / 'reference.pdf'
        response = adapters.libreoffice(contained(ROOT, case['input']), path)
        info = pdf.inspect_pdf(path)
        eligible = pdf.inventory_check(info, case) and pdf.font_check(info, case['fonts'])
        bundle['cases'][case['id']] = {'inputSha256': case['sha256'], 'pdf': str(path.relative_to(output)), 'pdfSha256': digest(path), 'renderer': response['renderer'], 'eligible': eligible, 'inspection': info}
        write_json(output / 'bundle.json', bundle)
        print(case['id'] + (': reference registered' if eligible else ': reference ineligible (see token/font evidence)'), flush=True)
    return bundle


def validate_bundle(bundle, root, registry, env):
    if bundle['schema'] != 1 or bundle['track'] not in {'libreoffice', reference_controls.TRACK, 'word-online', 'word-onedrive', 'word-desktop'}:
        raise ValueError('Unknown reference track or bundle version')
    if bundle['suiteDigest'] != identity(registry) or bundle['environment'] != env['contract']:
        raise ValueError('Reference suite or measurement/font environment changed')
    source_bundle = None
    if bundle['track'] == reference_controls.TRACK:
        if bundle.get('sourceBundle') != 'direct/bundle.json' or bundle.get('controlPolicy') != reference_controls.policy():
            raise ValueError('Equivalent-control reference policy is missing or changed')
        source_path = contained(root, bundle['sourceBundle'])
        source_bundle = read_json(source_path)
        if source_bundle['track'] != 'libreoffice' or identity(source_bundle) != bundle.get('sourceBundleDigest'):
            raise ValueError('Equivalent-control source bundle is stale or is not direct LibreOffice')
        validate_bundle(source_bundle, source_path.parent, registry, env)
        if set(bundle['cases']) != set(source_bundle['cases']):
            raise ValueError('Equivalent-control bundle changed reference coverage')
    elif any(key in bundle for key in ('sourceBundle', 'sourceBundleDigest', 'controlPolicy')) or any('referenceSource' in entry for entry in bundle['cases'].values()):
        raise ValueError('Equivalent-control evidence cannot be labeled as a direct reference track')
    for cid, entry in bundle['cases'].items():
        case = next((c for c in registry['cases'] if c['id'] == cid), None)
        if not case or case['sha256'] != entry['inputSha256'] or digest(contained(root, entry['pdf'])) != entry['pdfSha256']:
            raise ValueError('Stale or unknown reference: ' + cid)
        if source_bundle is not None:
            source = reference_controls.source(case, registry, ROOT)
            capture = source_bundle['cases'].get(source['caseId'])
            if entry.get('referenceSource') != source or capture is None:
                raise ValueError('Equivalent-control source declaration changed: ' + cid)
            for key in ('eligible', 'pdfSha256', 'inspection', 'renderer'):
                if entry.get(key) != capture.get(key):
                    raise ValueError('Equivalent-control capture evidence changed: ' + cid)


def equivalent_reference_bundle(output, reference):
    registry = validate_registry()
    env = environment([f for c in registry['cases'] for f in c['fonts']])
    source_root = Path(reference).resolve().parent
    original = read_json(reference)
    if original['track'] != 'libreoffice':
        raise ValueError('Equivalent controls require an immutable direct LibreOffice bundle')
    validate_bundle(original, source_root, registry, env)
    records = {c['id']: c for c in registry['cases']}
    if set(original['cases']) != set(records):
        raise ValueError('Capture every original input before deriving equivalent-control references')
    sources = {cid: reference_controls.source(case, registry, ROOT) for cid, case in records.items()}
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    direct = output / 'direct'
    direct.mkdir()
    for capture in original['cases'].values():
        target = contained(direct, capture['pdf'])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(contained(source_root, capture['pdf']), target)
    write_json(direct / 'bundle.json', original)
    bundle = {'schema': 1, 'track': reference_controls.TRACK, 'suiteDigest': original['suiteDigest'],
              'environment': original['environment'], 'sourceBundle': 'direct/bundle.json',
              'sourceBundleDigest': identity(original), 'controlPolicy': reference_controls.policy(), 'cases': {}}
    for cid, case in records.items():
        source = sources[cid]
        capture = original['cases'][source['caseId']]
        path = output / cid / 'reference.pdf'
        path.parent.mkdir()
        shutil.copyfile(contained(source_root, capture['pdf']), path)
        entry = dict(capture, inputSha256=case['sha256'], pdf=str(path.relative_to(output)), referenceSource=source)
        bundle['cases'][cid] = entry
        print(cid + ': ' + source['kind'] + ' reference from ' + source['caseId'] +
              (' registered' if entry['eligible'] else ' ineligible'), flush=True)
    write_json(output / 'bundle.json', bundle)
    validate_bundle(bundle, output, registry, env)
    return bundle


def run(output, reference, adapter, candidate):
    registry = validate_registry()
    env = environment([f for c in registry['cases'] for f in c['fonts']])
    ref_root = Path(reference).resolve().parent
    bundle = read_json(reference)
    validate_bundle(bundle, ref_root, registry, env)
    direct_bundle = read_json(contained(ref_root, bundle['sourceBundle'])) if bundle['track'] == reference_controls.TRACK else None
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    contract = {'metric': metrics.CONTRACT, 'suiteDigest': identity(registry), 'referenceDigest': identity(bundle), 'environment': env['contract'], 'adapter': adapter if isinstance(adapter, str) else {'argv': adapter, 'sourceSha256': digest(ROOT / 'adapters/docxodus.mjs')}}
    result = {'schema': 1, 'suite': registry['suite'], 'candidate': candidate, 'track': bundle['track'], 'contract': contract, 'contractDigest': identity(contract), 'cases': []}
    for case in registry['cases']:
        folder = output / case['id']
        folder.mkdir()
        outcome = {'id': case['id'], 'category': case['category'], 'status': 'unmeasured', 'checks': [], 'pages': []}
        entry = bundle['cases'].get(case['id'])
        try:
            if not entry or not entry['eligible']:
                raise ValueError('Required reference is missing or ineligible')
            reference_path = contained(ref_root, entry['pdf'])
            shutil.copyfile(reference_path, folder / 'reference.pdf')
            if direct_bundle is not None:
                outcome['referenceSource'] = entry['referenceSource']
                if entry['referenceSource']['kind'] == 'equivalent-control':
                    direct_capture = direct_bundle['cases'][case['id']]
                    direct_root = contained(ref_root, bundle['sourceBundle']).parent
                    shutil.copyfile(contained(direct_root, direct_capture['pdf']), folder / 'direct-reference.pdf')
            reference_info = pdf.inspect_pdf(reference_path)
            if not pdf.inventory_check(reference_info, case) or not pdf.font_check(reference_info, case['fonts']):
                raise ValueError('Reference content or fonts are ineligible')
            render_case = case
            if adapter == 'libreoffice-reference' and direct_bundle is not None:
                render_case = next(c for c in registry['cases'] if c['id'] == entry['referenceSource']['caseId'])
            request = {'protocol': 1, 'input': str(contained(ROOT, render_case['input'])), 'inputSha256': render_case['sha256'], 'output': str(folder / 'candidate.pdf'), 'report': str(folder / 'production.json'), 'profile': case['profile'], 'fontDirectories': env['fontDirectories'], 'candidate': candidate, 'timeoutMs': 120000}
            try:
                response = adapters.render(adapter, request)
            except (RuntimeError, subprocess.TimeoutExpired) as error:
                response = {'status': 'failed', 'error': str(error)}
            outcome['adapter'] = response
            if response['status'] == 'unmeasured':
                raise ValueError('Candidate environment is ineligible: ' + str(response['error']))
            if response['status'] == 'failed':
                outcome.update(status='measured', score=0.0, close=False, checks=[{'name': 'conversion', 'passed': False, 'error': response['error']}])
            else:
                candidate_path = folder / 'candidate.pdf'
                try:
                    candidate_info = pdf.inspect_pdf(candidate_path)
                except (RuntimeError, ValueError) as error:
                    outcome.update(status='measured', score=0.0, close=False, checks=[{'name': 'valid-pdf', 'passed': False, 'error': str(error)}])
                else:
                    outcome['checks'] = pdf.correctness(case, reference_info, candidate_info)
                    with tempfile.TemporaryDirectory(dir=folder) as tmp:
                        rpages = pdf.rasterize(reference_path, Path(tmp) / 'r')
                        cpages = pdf.rasterize(candidate_path, Path(tmp) / 'c')
                        for i in range(max(len(rpages), len(cpages))):
                            if i >= len(rpages) or i >= len(cpages):
                                outcome['pages'].append({'score': 0.0, 'unmatched': 'reference' if i >= len(cpages) else 'candidate'})
                                continue
                            rw, rh, rp = metrics.read_ppm(rpages[i])
                            cw, ch, cp = metrics.read_ppm(cpages[i])
                            if (rw, rh) != (cw, ch):
                                outcome['pages'].append({'score': 0.0, 'dimensionsMismatch': True})
                                outcome['checks'].append({'name': f'raster-dimensions-page-{i+1}', 'passed': False})
                                continue
                            measurements = metrics.page_metrics(rp, cp, rw, rh)
                            measurements['raster'] = {'width': rw, 'height': rh, 'referenceSha256': digest(rpages[i]), 'candidateSha256': digest(cpages[i])}
                            outcome['pages'].append(measurements)
                            metrics.write_images(folder, i + 1, rp, cp, rw, rh)
                    outcome.update(status='measured', score=metrics.case_score(outcome['pages'], outcome['checks']), close=all(c['passed'] for c in outcome['checks']) and all(p.get('close', False) for p in outcome['pages']))
            if digest(contained(ROOT, case['input'])) != case['sha256']:
                raise ValueError('Renderer modified source bytes')
            if digest(request['input']) != request['inputSha256']:
                raise ValueError('Renderer modified reference source bytes')
        except Exception as error:
            outcome.update(status='unmeasured', error=f'{type(error).__name__}: {error}')
            outcome.pop('score', None)
            outcome.pop('close', None)
        write_json(folder / 'evidence.json', outcome)
        result['cases'].append(outcome)
        runtimes = [c['adapter']['renderer'].get('runtime') for c in result['cases'] if c.get('adapter', {}).get('status') == 'ok' and c['adapter']['renderer'].get('name') == 'docxodus']
        nodes = [c['adapter']['renderer'].get('node') for c in result['cases'] if c.get('adapter', {}).get('status') == 'ok' and c['adapter']['renderer'].get('name') == 'docxodus']
        contract['candidateRuntime'] = {'runtime': runtimes[0] if runtimes else None, 'node': nodes[0] if nodes else None}
        result['contractDigest'] = identity(contract)
        result['summary'] = metrics.aggregate(result['cases'], registry['suite']['cases'])
        report.save(output, result)
        print(case['id'] + ': ' + outcome['status'] + (' score ' + str(round(outcome['score'], 2)) if 'score' in outcome else ' ' + outcome.get('error', '')), flush=True)
    return result


def compare(previous, current, tolerance):
    validate_result(previous)
    validate_result(current)
    if not math_valid_tolerance(tolerance):
        raise ValueError('Regression tolerance must be finite and nonnegative')
    if not previous['summary']['complete'] or not current['summary']['complete']:
        raise ValueError('Cannot gate or refresh an incomplete run')
    if previous['contractDigest'] != current['contractDigest'] or identity(previous['contract']) != previous['contractDigest'] or identity(current['contract']) != current['contractDigest']:
        raise ValueError('Measurement contract changed or is corrupt')
    findings = []
    before = {c['id']: c for c in previous['cases']}
    for case in current['cases']:
        old = before[case['id']]
        if any(not c['passed'] for c in case['checks']):
            findings.append(case['id'] + ': mandatory check failure')
        if len(old['pages']) != len(case['pages']):
            findings.append(case['id'] + ': measured page coverage changed')
        for number, (a, b) in enumerate(zip(old['pages'], case['pages']), 1):
            for key in ('score', 'ssim', 'inkF1', 'precision', 'recall'):
                if key in a and key in b and b[key] + tolerance < a[key]:
                    findings.append(f'{case["id"]} page {number}: {key} regressed')
    return findings


def math_valid_tolerance(value):
    import math
    return math.isfinite(value) and value >= 0


def validate_result(result):
    if result['schema'] != 1 or result['contract']['metric'] != metrics.CONTRACT or identity(result['contract']) != result['contractDigest']:
        raise ValueError('Invalid result measurement contract')
    expected = metrics.aggregate(result['cases'], result['suite']['cases'])
    if expected != result['summary']:
        raise ValueError('Invalid coverage or aggregation summary')
    for case in result['cases']:
        if case['status'] == 'measured' and case['score'] != metrics.case_score(case['pages'], case['checks']):
            raise ValueError('Invalid case score')
