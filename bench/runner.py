from __future__ import annotations
import shutil
import tempfile
import subprocess
import re
from pathlib import Path
from . import adapters, metrics, pdf, report, reference_controls, html_artifacts
from .common import WORD_TRACKS, ROOT, contained, digest, identity, read_json, validate_registry, write_json
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
        info = pdf.inspect_case_pdf(path, case)
        failures = pdf.reference_failures(case, info, 'libreoffice')
        eligible = not failures
        bundle['cases'][case['id']] = {'inputSha256': case['sha256'], 'pdf': str(path.relative_to(output)), 'pdfSha256': digest(path), 'renderer': response['renderer'], 'eligible': eligible, 'ineligibleChecks': failures, 'inspection': info}
        write_json(output / 'bundle.json', bundle)
        print(case['id'] + (': reference registered' if eligible else ': reference ineligible (' + ', '.join(failures) + ')'), flush=True)
    return bundle


def validate_bundle(bundle, root, registry, env):
    if bundle['schema'] != 1 or bundle['track'] not in {'libreoffice', reference_controls.TRACK} | WORD_TRACKS:
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
        if case.get('pdfTextNormalization') and entry.get('inspection', {}).get('pdfTextNormalization') != case['pdfTextNormalization']:
            raise ValueError('Reference PDF text normalization evidence is missing or changed')
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
    pdf_policies = {c['id']: c['pdfTextNormalization'] for c in registry['cases'] if c.get('pdfTextNormalization')}
    if pdf_policies:
        contract.update(pdfTextNormalizations=pdf_policies, pdfTextInspectorVersion=pdf.PDF_TEXT_POLICY_VERSION,
                        pdfTextInspectorSha256=digest(Path(pdf.__file__)))
    html_declarations = {c['id']: c['htmlAssertions'] for c in registry['cases'] if c.get('htmlAssertions')}
    # A reference-engine calibration measures PDFs; it cannot attest another artifact's metadata.
    if adapter in ('libreoffice', 'libreoffice-reference'):
        html_declarations = {}
    if html_declarations:
        contract.update(htmlAssertions=html_declarations, htmlInspectorVersion=html_artifacts.VERSION,
                        htmlInspectorSha256=digest(Path(html_artifacts.__file__)))
        html_profiles = {c['id']: c['htmlProfile'] for c in registry['cases'] if c['id'] in html_declarations and c.get('htmlProfile')}
        if html_profiles: contract['htmlProfiles'] = html_profiles
        if any(html_artifacts.needs_browser(d) for d in html_declarations.values()):
            contract.update(htmlBrowserInspectorVersion=html_artifacts.BROWSER_VERSION,
                            htmlBrowserInspectorSha256=digest(html_artifacts.BROWSER_SOURCE))
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
                if entry['referenceSource']['kind'] != 'direct':
                    direct_capture = direct_bundle['cases'][case['id']]
                    direct_root = contained(ref_root, bundle['sourceBundle']).parent
                    shutil.copyfile(contained(direct_root, direct_capture['pdf']), folder / 'direct-reference.pdf')
            reference_info = pdf.inspect_case_pdf(reference_path, case)
            failures = pdf.reference_failures(case, reference_info, bundle['track'])
            if failures:
                raise ValueError('Reference fails its own mandatory checks: ' + ', '.join(failures))
            render_case = case
            if adapter == 'libreoffice-reference' and direct_bundle is not None:
                render_case = next(c for c in registry['cases'] if c['id'] == entry['referenceSource']['caseId'])
            request = {'protocol': 1, 'input': str(contained(ROOT, render_case['input'])), 'inputSha256': render_case['sha256'], 'output': str(folder / 'candidate.pdf'), 'report': str(folder / 'production.json'), 'profile': case['profile'], 'fontDirectories': env['fontDirectories'], 'candidate': candidate, 'timeoutMs': 120000}
            if case['id'] in html_declarations:
                request.update(htmlOutput=str(folder / 'candidate.html'), htmlReport=str(folder / 'html-production.json'))
                if case.get('htmlProfile'): request['htmlProfile'] = case['htmlProfile']
                if html_artifacts.needs_browser(case['htmlAssertions']):
                    request.update(htmlAssertions=case['htmlAssertions'], htmlObservations=str(folder / 'html-browser.json'))
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
                    candidate_info = pdf.inspect_case_pdf(candidate_path, case)
                except (RuntimeError, ValueError) as error:
                    outcome.update(status='measured', score=0.0, close=False, checks=[{'name': 'valid-pdf', 'passed': False, 'error': str(error)}])
                else:
                    # LibreOffice measured against a LibreOffice track is a calibration of the reference engine.
                    calibration = adapter in ('libreoffice', 'libreoffice-reference')
                    outcome['checks'] = pdf.correctness(pdf.binding_case(case, bundle['track'], calibration), reference_info, candidate_info)
                    with tempfile.TemporaryDirectory(dir=folder) as tmp:
                        rpages = pdf.rasterize(reference_path, Path(tmp) / 'r')
                        cpages = pdf.rasterize(candidate_path, Path(tmp) / 'c')
                        for i in range(max(len(rpages), len(cpages))):
                            if i >= len(rpages) or i >= len(cpages):
                                outcome['pages'].append({'score': 0.0, 'unmatched': 'reference' if i >= len(cpages) else 'candidate'})
                                continue
                            rw, rh, rp = metrics.read_ppm(rpages[i])
                            cw, ch, cp = metrics.read_ppm(cpages[i])
                            if not metrics.canvas_compatible((rw, rh), (cw, ch)):
                                outcome['pages'].append({'score': 0.0, 'dimensionsMismatch': True})
                                outcome['checks'].append({'name': f'raster-dimensions-page-{i+1}', 'passed': False, 'reference': [rw, rh], 'candidate': [cw, ch]})
                                continue
                            width, height = max(rw, cw), max(rh, ch)
                            rp = metrics.union_canvas(rp, rw, rh, width, height)
                            cp = metrics.union_canvas(cp, cw, ch, width, height)
                            measurements = metrics.page_metrics(rp, cp, width, height)
                            measurements['raster'] = {'width': width, 'height': height, 'reference': [rw, rh], 'candidate': [cw, ch], 'referenceSha256': digest(rpages[i]), 'candidateSha256': digest(cpages[i])}
                            outcome['pages'].append(measurements)
                            metrics.write_images(folder, i + 1, rp, cp, width, height)
                    outcome.update(status='measured', score=metrics.case_score(outcome['pages'], outcome['checks']), close=all(c['passed'] for c in outcome['checks']) and all(p.get('close', False) for p in outcome['pages']))
            if case['id'] in html_declarations:
                outcome['html'] = html_artifacts.inspect(folder, response, html_declarations[case['id']], case.get('htmlProfile'))
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
        if html_declarations:
            result['htmlSummary'] = html_artifacts.aggregate(result['cases'], html_declarations, contract.get('htmlBrowserInspectorSha256'), contract.get('htmlProfiles'))
        report.save(output, result)
        html_note = ''
        if case['id'] in html_declarations:
            observation = outcome.get('html', {})
            state = ('passed' if all(c['passed'] for c in observation.get('checks', [])) else 'failed') if observation.get('status') == 'measured' else 'unmeasured'
            html_note = '; delivered HTML ' + state
        print(case['id'] + ': ' + outcome['status'] + (' score ' + str(round(outcome['score'], 2)) if 'score' in outcome else ' ' + outcome.get('error', '')) + html_note, flush=True)
    return result


def compare(previous, current, tolerance):
    validate_result(previous)
    validate_result(current)
    if not math_valid_tolerance(tolerance):
        raise ValueError('Regression tolerance must be finite and nonnegative')
    if not previous['summary']['complete'] or not current['summary']['complete']:
        raise ValueError('Cannot gate or refresh an incomplete run')
    if any(not r.get('htmlSummary', {'complete': True})['complete'] for r in (previous, current)):
        raise ValueError('Cannot gate unmeasured delivered HTML checks')
    if previous['contractDigest'] != current['contractDigest'] or identity(previous['contract']) != previous['contractDigest'] or identity(current['contract']) != current['contractDigest']:
        raise ValueError('Measurement contract changed or is corrupt')
    findings = []
    before = {c['id']: c for c in previous['cases']}
    for case in current['cases']:
        old = before[case['id']]
        if any(not c['passed'] for c in case.get('html', {}).get('checks', [])):
            findings.append(case['id'] + ': delivered HTML check failure')
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
    pdf_policies = result['contract'].get('pdfTextNormalizations', {})
    if 'pdfTextNormalizations' in result['contract'] and (not isinstance(pdf_policies, dict) or
            any(not isinstance(policy, str) or policy not in pdf.PDF_TEXT_POLICIES for policy in pdf_policies.values()) or
            not set(pdf_policies).issubset(result['suite']['cases']) or
            type(result['contract'].get('pdfTextInspectorVersion')) is not int or
            result['contract'].get('pdfTextInspectorVersion') != pdf.PDF_TEXT_POLICY_VERSION or
            not isinstance(result['contract'].get('pdfTextInspectorSha256'), str) or
            not re.fullmatch('[a-f0-9]{64}', result['contract']['pdfTextInspectorSha256'])):
        raise ValueError('Invalid declared PDF text normalization contract')
    html_declarations = result['contract'].get('htmlAssertions', {})
    if (not isinstance(html_declarations, dict) or not set(html_declarations).issubset(result['suite']['cases']) or
            any(not isinstance(d, list) or not d for d in html_declarations.values())):
        raise ValueError('Invalid delivered HTML assertion contract')
    if html_declarations:
        for declarations in html_declarations.values():
            for declaration in declarations: html_artifacts.validate_declaration(declaration)
        profiles = result['contract'].get('htmlProfiles', {})
        if not isinstance(profiles, dict) or not set(profiles).issubset(html_declarations):
            raise ValueError('Invalid delivered HTML profile contract')
        from .common import validate_render_profile
        for profile in profiles.values(): validate_render_profile(profile)
        if any(html_artifacts.needs_browser(d) for d in html_declarations.values()):
            if (type(result['contract'].get('htmlBrowserInspectorVersion')) is not int or
                    result['contract']['htmlBrowserInspectorVersion'] != html_artifacts.BROWSER_VERSION or
                    not isinstance(result['contract'].get('htmlBrowserInspectorSha256'), str) or
                    not re.fullmatch('[a-f0-9]{64}', result['contract']['htmlBrowserInspectorSha256'])):
                raise ValueError('Invalid HTML browser inspector contract')
        if (type(result['contract'].get('htmlInspectorVersion')) is not int or
                result['contract'].get('htmlInspectorVersion') != html_artifacts.VERSION or
                not isinstance(result['contract'].get('htmlInspectorSha256'), str) or
                not re.fullmatch('[0-9a-f]{64}', result['contract']['htmlInspectorSha256']) or result.get('htmlSummary') != html_artifacts.aggregate(result['cases'], html_declarations, result['contract'].get('htmlBrowserInspectorSha256'), profiles)):
            raise ValueError('Invalid delivered HTML measurement contract or summary')
    expected = metrics.aggregate(result['cases'], result['suite']['cases'])
    if expected != result['summary']:
        raise ValueError('Invalid coverage or aggregation summary')
    for case in result['cases']:
        if case['id'] in pdf_policies and case['status'] == 'measured':
            failed_conversion = any(c['name'] in ('conversion', 'valid-pdf') and c['passed'] is False
                                    for c in case['checks'])
            observations = [c for c in case['checks'] if c['name'] == 'declared-pdf-text-normalization']
            if not failed_conversion and (len(observations) != 1 or type(observations[0].get('passed')) is not bool):
                raise ValueError('Missing or invalid PDF text normalization observation')
        if case['status'] == 'measured' and case['score'] != metrics.case_score(case['pages'], case['checks']):
            raise ValueError('Invalid case score')
