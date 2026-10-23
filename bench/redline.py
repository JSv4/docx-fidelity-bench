"""Redline track: run a comparison candidate and score its accept/reject round trips.

A candidate turns each case's inputs into one output package: a redline for `compare` and
`consolidate`, a resolved document for `reject`. The output is then judged by two engines that
share no code with any candidate: the benchmark's own revision engine (`bench/revisions.py`,
compared on the full semantic view) and LibreOffice through headless UNO (compared on the text
view, after both sides take the same LibreOffice load/save path). See docs/REDLINE.md.
"""
from __future__ import annotations

import difflib
import html
import json
import os
import re
import shutil
import signal
import subprocess
from pathlib import Path

from . import revisions
from .redline_build import dotnet as _dotnet, validate_packages, verify_docxodus, verify_validator
from .common import ROOT, contained, digest, execute, identity, read_json, write_json

MANIFEST = ROOT / 'fixtures' / 'redline' / 'manifest.json'
OPERATIONS = {'compare': 2, 'consolidate': None, 'reject': 1, 'table-widths': 1}
ASSERTIONS = {'untracked-text': {1}, 'paragraph-count': {1}, 'para-ids-valid': {1}, 'style-ids-unique': {1}, 'revision-count': {1}, 'comment-threads': {1}, 'table-widths': {1}}
CATEGORIES = {'fields', 'comments', 'bookmarks', 'styles', 'revisions', 'consolidate', 'identity', 'tables'}
SCOPES = {'compare': {'redline', 'accepted', 'rejected'}, 'consolidate': {'redline', 'accepted', 'rejected'}, 'reject': {'output'}, 'table-widths': {'redline', 'accepted', 'rejected'}}
CONTRACT = {'version': 3, 'view': revisions.VIEW_VERSION, 'engines': ['bench-markup', 'libreoffice-text'],
            'caseScore': '100 when every applicable mandatory check passes, otherwise 0',
            'suiteScore': 'mean of category means over every required case',
            'libreofficeEligibility': 'a LibreOffice comparison applies only when the authored redline passes it',
            'validity': 'no OpenXmlValidator finding (id, part, description) occurs more often than in any input',
            'semanticPreflight': 'declared identity cases must report zero changes at raw limits with and without the package supplement',
            'revisionRegistry': 'table width operations must report the declared public registry count and match independent resolved width assertions'}
HARNESS = ['bench/redline.py', 'bench/revisions.py', 'bench/lo_revisions.py', 'bench/redline_build.py']


# ---------------------------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------------------------

def artifact_records(case):
    return case['inputs'] + list(case['expected'].values()) + [case['authored']] + list(case.get('reviewerExpected', {}).values())


def validate_registry(registry=None):
    registry = registry or read_json(MANIFEST)
    if registry.get('schema') != 1 or not isinstance(registry['suite'].get('version'), int) or registry['suite']['version'] < 1:
        raise ValueError('Unknown redline registry or suite version')
    ids = [c['id'] for c in registry['cases']]
    if len(set(ids)) != len(ids) or ids != registry['suite']['cases']:
        raise ValueError('Duplicate or missing redline suite member')
    for case in registry['cases']:
        if not re.fullmatch('redline-[a-z0-9-]{1,72}', case['id']) or case.get('version') != 1:
            raise ValueError('Invalid redline case id or version: ' + case['id'])
        if case['rights']['license'] != 'MIT' or not case['rights']['author'] or not case['rights']['origin']:
            raise ValueError('Invalid rights record: ' + case['id'])
        operation = case['operation']
        if operation not in OPERATIONS or (OPERATIONS[operation] and len(case['inputs']) != OPERATIONS[operation]) or (operation == 'consolidate' and len(case['inputs']) < 3):
            raise ValueError('Invalid operation or input count: ' + case['id'])
        expected = {'compare': {'accepted', 'rejected'}, 'consolidate': {'accepted', 'rejected'}, 'reject': {'output'}, 'table-widths': {'accepted', 'rejected'}}[operation]
        if set(case['expected']) != expected or case['kind'] not in ('reproducer', 'control', 'identity'):
            raise ValueError('Invalid expectation or kind: ' + case['id'])
        declared = case.get('libreoffice', {})
        if {k for k in declared if k != 'note'} != expected or any(not isinstance(declared[k], bool) for k in expected) or (not all(declared[k] for k in expected) and not declared.get('note')):
            raise ValueError('Invalid LibreOffice eligibility declaration: ' + case['id'])
        if 'reviewerExpected' in case and (operation != 'consolidate' or
                set(case['reviewerExpected']) != {i['author'] for i in case['inputs'] if i['role'] == 'reviewer'}):
            raise ValueError('Reviewer expectations must name every consolidation reviewer: ' + case['id'])
        for record in artifact_records(case):
            if digest(contained(ROOT, record['path'])) != record['sha256']:
                raise ValueError('Stale redline input digest: ' + case['id'] + ' ' + record['path'])
        if digest(contained(ROOT, case['generator']['path'])) != case['generator']['sha256']:
            raise ValueError('Stale redline generator digest: ' + case['id'])
        if case['category'] not in CATEGORIES:
            raise ValueError('Unknown redline category: ' + case['id'])
        if operation == 'table-widths':
            spec = case.get('tableWidths', {})
            registry_count = case.get('revisionRegistry', {})
            if (set(spec) != {'version', 'widths', 'tracked'} or spec['version'] != 1
                    or type(spec['tracked']) is not bool or not isinstance(spec['widths'], list)
                    or not spec['widths'] or any(type(w) is not int or w <= 0 for w in spec['widths'])
                    or registry_count != {'version': 1, 'count': 1 if spec['tracked'] else 0}
                    or type(registry_count.get('count')) is not int):
                raise ValueError('Invalid table widths declaration: ' + case['id'])
        elif 'tableWidths' in case or 'revisionRegistry' in case:
            raise ValueError('Unexpected table width operation data: ' + case['id'])
        if 'semanticPreflight' in case:
            if (operation != 'compare' or case['category'] != 'identity'
                    or case['semanticPreflight'] != {'version': 1, 'limits': 'raw-boundaries', 'changeCount': 0}
                    or case['inputs'][0]['sha256'] != case['inputs'][1]['sha256']):
                raise ValueError('Invalid semantic preflight declaration: ' + case['id'])
        if operation == 'consolidate' and any(i['role'] == 'reviewer' and not i.get('author') for i in case['inputs']):
            raise ValueError('A consolidation reviewer needs an author: ' + case['id'])
        for assertion in case['assertions']:
            if assertion.get('version') not in ASSERTIONS.get(assertion.get('type'), set()) or assertion.get('scope') not in SCOPES[operation]:
                raise ValueError('Unknown assertion type, version or scope: ' + case['id'])
            kind = assertion['type']
            valid = {'untracked-text': lambda a: a.get('story') in ('body', 'headers') and a.get('texts') and all(isinstance(x, str) and x for x in a['texts']),
                     'paragraph-count': lambda a: a.get('story') == 'body' and isinstance(a.get('count'), int) and a['count'] >= 0,
                     'revision-count': lambda a: isinstance(a.get('max'), int) and a['max'] >= 0,
                     'para-ids-valid': lambda a: True, 'style-ids-unique': lambda a: True,
                     'table-widths': lambda a: a['scope'] in {'accepted', 'rejected'} and isinstance(a.get('grid'), list)
                         and a['grid'] and all(type(v) is int and v > 0 for v in a['grid'])
                         and isinstance(a.get('cells'), list) and a['cells'] and all(isinstance(row, list) and row
                             and all(type(v) is int and v > 0 for v in row) for row in a['cells'])
                         and type(a.get('table')) is int and a['table'] > 0,
                     'comment-threads': lambda a: a['scope'] == 'redline' and isinstance(a.get('threads'), list) and all(
                         isinstance(x, list) and len(x) == 2 and all(isinstance(y, str) and y for y in x) for x in a['threads'])}[kind]
            if not valid(assertion):
                raise ValueError('Invalid assertion declaration: ' + case['id'] + ' ' + kind)
        if operation == 'reject' and {'type': 'revision-count', 'version': 1, 'scope': 'output', 'max': 0} not in case['assertions']:
            raise ValueError('A reject case must require an output without revisions: ' + case['id'])
    return registry


# ---------------------------------------------------------------------------------------------
# Environment: LibreOffice, its Python, and the optional validator
# ---------------------------------------------------------------------------------------------

# LibreOffice's bundled Python is a wrapper that sets PYTHONHOME, so the driver cannot run in isolated
# mode (-I). -s and -P still keep user site packages and the script and working directories off sys.path.
def libreoffice_paths():
    executable = os.environ.get('BENCH_LIBREOFFICE') or shutil.which('libreoffice') or shutil.which('soffice')
    if not executable:
        raise RuntimeError('LibreOffice is required for the redline track')
    real = Path(executable).resolve()
    program = real.parent
    soffice = program / 'soffice' if (program / 'soffice').is_file() else real
    python = os.environ.get('BENCH_LIBREOFFICE_PYTHON')
    if not python:
        bundled = program / 'python'
        python = str(bundled) if bundled.is_file() else '/usr/bin/python3'
    return executable, soffice, Path(python)


def environment(validator=None):
    executable, soffice, python = libreoffice_paths()
    version = execute([executable, '--version']).strip()
    probe = execute([python, '-s', '-P', '-c', 'import sys, uno; print(sys.version.split()[0])']).strip()
    contract = {'libreoffice': {'version': version, 'sha256': digest(soffice)},
                'libreofficePython': {'version': probe, 'sha256': digest(python.resolve())},
                'harness': {name: digest(ROOT / name) for name in HARNESS},
                'validator': None}
    if validator is not None:
        contract['validator'] = verify_validator(validator)
    return {'contract': contract, 'soffice': str(soffice), 'python': str(python)}


def libreoffice_batch(env, folder, items, attempts=2):
    """Run one private LibreOffice session over `items`; return one result per item.

    An item LibreOffice cannot process carries an `error`. A session that fails, or that fails on a
    benchmark fixture rather than the candidate's output, is repeated from a fresh profile; the
    caller treats a remaining fixture failure as unmeasured.
    """
    job = {'soffice': env['soffice'], 'profile': str(Path(folder) / 'lo-profile'), 'items': items}
    results, failure = None, 'no attempt'
    for attempt in range(attempts):
        for item in items:
            Path(item['output']).unlink(missing_ok=True)
        process = subprocess.Popen([env['python'], '-s', '-P', str(ROOT / 'bench/lo_revisions.py')], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            stdout, stderr = process.communicate(json.dumps(job), timeout=600)
        except subprocess.TimeoutExpired:
            # The driver's soffice child shares its process group; end only that group.
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            stdout, stderr = '', 'LibreOffice session timed out'
        shutil.rmtree(Path(folder) / 'lo-profile', ignore_errors=True)
        if process.returncode:
            failure = stderr[-2000:]
            continue
        results = json.loads(stdout)['results']
        if not any('error' in r for r, i in zip(results, items) if not i['key'].startswith('candidate-')):
            return results
        failure = '; '.join(r['error'] for r in results if 'error' in r)
    if results is not None:
        return results
    raise RuntimeError('LibreOffice revision engine failed: ' + failure)


# ---------------------------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------------------------

def run_candidate(adapter, build, case, output, candidate, timeout=300):
    if adapter == 'authored':
        shutil.copyfile(contained(ROOT, case['authored']['path']), output)
        return {'status': 'ok', 'outputSha256': digest(output), 'engine': {'name': 'authored-redline'}}
    if adapter != 'docxodus':
        raise ValueError('Unknown redline adapter: ' + adapter)
    verify_docxodus(build, candidate)
    inputs = [{'path': str(contained(ROOT, i['path'])), 'sha256': i['sha256'], 'author': i.get('author')} for i in case['inputs']]
    request = {'protocol': 1, 'operation': case['operation'], 'inputs': inputs, 'output': str(output),
               'settings': {'author': 'Bench', 'date': '2026-01-01T00:00:00Z'}}
    if 'semanticPreflight' in case:
        request['settings']['semanticPreflight'] = case['semanticPreflight']
    if 'tableWidths' in case:
        request['settings']['tableWidths'] = case['tableWidths']
    response = json.loads(execute([_dotnet(), str(Path(build).resolve() / 'bin' / 'DocxBenchRedline.dll')], input=json.dumps(request), timeout=timeout))
    if response.get('protocol') != 1 or response.get('status') not in ('ok', 'failed', 'unmeasured'):
        raise ValueError('Invalid redline adapter response')
    if response['status'] == 'ok' and digest(output) != response.get('outputSha256'):
        raise ValueError('Adapter output digest does not match')
    return response


# ---------------------------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------------------------

def _diff(expected, actual):
    a, b = revisions.flatten_view(expected), revisions.flatten_view(actual)
    return {'similarity': difflib.SequenceMatcher(None, a, b, autojunk=False).ratio(),
            'diff': list(difflib.unified_diff(a, b, 'expected', 'actual', lineterm='', n=1))[:80]}


def _comparison(name, expected, actual):
    check = {'name': name, 'passed': expected == actual}
    if not check['passed']:
        check.update(_diff(expected, actual))
    return check


def _assertion(assertion, package, resolved):
    kind, scope = assertion['type'], assertion['scope']
    parts = resolved.get(scope)
    check = {'name': 'assertion-' + kind, 'declaration': assertion}
    if kind == 'table-widths':
        roots = parts if parts is not None else package.story_parts()
        tables = list(roots[package.main].iter(revisions.w('tbl')))
        def width(element):
            value = None if element is None else element.get(revisions.w('w'))
            return int(value) if value is not None and value.isdecimal() else value
        observed = None
        if len(tables) == 1:
            table = tables[0]
            columns = table.find(revisions.w('tblGrid'))
            cells = [[cell.find(revisions.w('tcPr') + '/' + revisions.w('tcW')) for cell in row.findall(revisions.w('tc'))]
                     for row in table.findall(revisions.w('tr'))]
            table_width = table.find(revisions.w('tblPr') + '/' + revisions.w('tblW'))
            observed = {'grid': [] if columns is None else [width(col) for col in columns.findall(revisions.w('gridCol'))],
                        'cells': [[width(cell) for cell in row] for row in cells], 'table': width(table_width)}
            types_ok = all(cell is not None and cell.get(revisions.w('type')) == 'dxa' for row in cells for cell in row)
            types_ok = types_ok and table_width is not None and table_width.get(revisions.w('type')) == 'dxa'
        else:
            types_ok = False
        check.update(passed=types_ok and observed == {k: assertion[k] for k in ('grid', 'cells', 'table')}, observed=observed)
    elif kind == 'untracked-text':
        texts = revisions.untracked_text(package, assertion['story'])
        missing = [x for x in assertion['texts'] if not any(x in text for text in texts)]
        check.update(passed=not missing, missing=missing)
    elif kind == 'paragraph-count':
        count = revisions.body_paragraph_count(package, parts)
        check.update(passed=count == assertion['count'], observed=count)
    elif kind == 'para-ids-valid':
        findings = revisions.para_id_findings(package)
        check.update(passed=not findings, findings=findings)
    elif kind == 'style-ids-unique':
        findings = revisions.style_id_findings(package)
        check.update(passed=not findings, findings=findings)
    elif kind == 'comment-threads':
        findings = revisions.comment_thread_findings(package, assertion['threads'])
        check.update(passed=not findings, findings=findings)
    elif kind == 'revision-count':
        count = revisions.revision_count(parts if parts is not None else package.story_parts())
        check.update(passed=count <= assertion['max'], observed=count)
    return check


def _validity(documents, inputs, output):
    def counts(findings):
        result = {}
        for finding in findings:
            key = (finding['id'], finding['part'], finding['description'])
            result[key] = result.get(key, 0) + 1
        return result
    allowed = {}
    for path in inputs:
        for key, value in counts(documents[str(path)]).items():
            allowed[key] = max(allowed.get(key, 0), value)
    new = [{'id': k[0], 'part': k[1], 'description': k[2], 'count': v, 'allowed': allowed.get(k, 0)}
           for k, v in sorted(counts(documents[str(output)]).items(), key=lambda item: str(item[0])) if v > allowed.get(k, 0)]
    return {'name': 'no-new-validation-errors', 'passed': not new, 'new': new}


def score_case(case, folder, adapter, build, candidate, env, validator):
    outcome = {'id': case['id'], 'category': case['category'], 'kind': case['kind'], 'issue': case['issue'],
               'operation': case['operation'], 'status': 'unmeasured', 'checks': []}
    inputs = [contained(ROOT, i['path']) for i in case['inputs']]
    output = folder / ('candidate-redline.docx' if case['operation'] != 'reject' else 'candidate-output.docx')
    try:
        try:
            response = run_candidate(adapter, build, case, output, candidate)
        except (RuntimeError, subprocess.TimeoutExpired) as error:
            response = {'status': 'failed', 'error': str(error)}
        outcome['adapter'] = response
        if response['status'] == 'unmeasured':
            raise ValueError('Candidate environment is ineligible: ' + json.dumps(response.get('error')))
        if any(digest(path) != record['sha256'] for path, record in zip(inputs, case['inputs'])):
            raise ValueError('Candidate modified its inputs')
        if response['status'] == 'failed':
            outcome['checks'].append({'name': 'conversion', 'passed': False, 'error': response.get('error')})
            return _finish(outcome, 'measured')
        outcome['checks'].append({'name': 'conversion', 'passed': True})
        try:
            package = revisions.Package(str(output))
            parts = package.story_parts()
        except Exception as error:
            outcome['checks'].append({'name': 'readable-package', 'passed': False, 'error': f'{type(error).__name__}: {error}'})
            return _finish(outcome, 'measured')
        outcome['checks'].append({'name': 'readable-package', 'passed': True})
        expected = {key: contained(ROOT, record['path']) for key, record in case['expected'].items()}
        authored = contained(ROOT, case['authored']['path'])
        for path, record in list(zip(expected.values(), case['expected'].values())) + [(authored, case['authored'])]:
            if digest(path) != record['sha256']:
                raise ValueError('Benchmark fixture changed during the run: ' + record['path'])
        resolved = {'redline': None, 'output': None}
        if case['operation'] == 'reject':
            outcome['checks'].append(_comparison('markup-output', revisions.view(revisions.Package(str(expected['output']))), revisions.view(package)))
        else:
            for mode, key in (('accept', 'accepted'), ('reject', 'rejected')):
                resolved[key] = revisions.resolve(parts, mode)
                outcome['checks'].append(_comparison('markup-' + key, revisions.view(revisions.Package(str(expected[key]))),
                                                     revisions.view(package, resolved[key])))
        if case['operation'] == 'consolidate':
            # Conflict policies can intentionally suppress a competing edit. Those cases declare
            # independently authored projections; ordinary merges still reproduce each input.
            for path, record in zip(inputs, case['inputs']):
                if record['role'] == 'reviewer':
                    projection = case.get('reviewerExpected', {}).get(record['author'], record)
                    path = contained(ROOT, projection['path'])
                    if digest(path) != projection['sha256']:
                        raise ValueError('Reviewer expectation changed during the run: ' + projection['path'])
                    outcome['checks'].append(_comparison('markup-reviewer-' + record['author'], revisions.view(revisions.Package(str(path))),
                                                         revisions.view(package, revisions.resolve(parts, 'accept', record['author']))))
        outcome['checks'].extend(_libreoffice_checks(case, folder, env, output, authored, expected))
        if validator is not None:
            documents = validate_packages(validator, inputs + [output])
            outcome['checks'].append(_validity(documents, inputs, output))
        else:
            outcome['checks'].append({'name': 'no-new-validation-errors', 'passed': None, 'reason': 'validator not provisioned'})
        for assertion in case['assertions']:
            outcome['checks'].append(_assertion(assertion, package, resolved))
        if 'semanticPreflight' in case:
            expected_counts = {'withPackageChanges': 0, 'withoutPackageChanges': 0}
            # The authored calibration's identity is established independently by both round trips.
            observed = expected_counts if adapter == 'authored' else response.get('semanticPreflight')
            outcome['checks'].append({'name': 'semantic-preflight',
                                      'passed': observed == expected_counts and all(type(v) is int for v in observed.values()),
                                      'expected': expected_counts, 'observed': observed})
        if 'revisionRegistry' in case:
            expected_count = case['revisionRegistry']['count']
            observed_count = expected_count if adapter == 'authored' else response.get('revisionRegistryCount')
            outcome['checks'].append({'name': 'revision-registry-count',
                                      'passed': type(observed_count) is int and observed_count == expected_count,
                                      'expected': expected_count, 'observed': observed_count})
        if any(c['passed'] is None and not c.get('ineligible') for c in outcome['checks']):
            raise ValueError('A required measurement is unavailable: ' + ', '.join(c['name'] for c in outcome['checks'] if c['passed'] is None and not c.get('ineligible')))
        return _finish(outcome, 'measured')
    except Exception as error:
        outcome.update(status='unmeasured', error=f'{type(error).__name__}: {error}')
        outcome.pop('score', None)
        return outcome


def _finish(outcome, status):
    outcome['status'] = status
    applicable = [c for c in outcome['checks'] if c['passed'] is not None]
    outcome['score'] = 100.0 if applicable and all(c['passed'] for c in applicable) else 0.0
    return outcome


def _libreoffice_checks(case, folder, env, output, authored, expected):
    """Text-view comparisons through LibreOffice; each applies only where the authored redline passes."""
    lo = folder / 'libreoffice'
    lo.mkdir()
    items, names = [], {}
    def item(key, source, operation):
        target = lo / (key + '.docx')
        names[key] = len(items)
        items.append({'key': key, 'input': str(source), 'operation': operation, 'output': str(target)})
        return target
    if case['operation'] == 'reject':
        pairs = [('output', item('expected-output', expected['output'], 'load'), item('authored-output', authored, 'load'), item('candidate-output', output, 'load'), None)]
    else:
        pairs = []
        for mode, key in (('accept', 'accepted'), ('reject', 'rejected')):
            pairs.append((key, item('expected-' + key, expected[key], 'load'), item('authored-' + key, authored, mode),
                          item('candidate-' + key, output, mode), mode))
    results = libreoffice_batch(env, lo, items)
    authored_revisions = revisions.revision_count(revisions.Package(str(authored)).story_parts())
    checks = []
    for key, expected_path, authored_path, candidate_path, mode in pairs:
        expected_run, authored_run, candidate_run = (results[names[prefix + key]] for prefix in ('expected-', 'authored-', 'candidate-'))
        check = {'name': 'libreoffice-' + key, 'engine': {'expected': expected_run, 'authored': authored_run, 'candidate': candidate_run}}
        if 'error' in expected_run or 'error' in authored_run:
            check.update(passed=None, reason='LibreOffice could not process a benchmark fixture')
            checks.append(check)
            continue
        expected_view = revisions.view(revisions.Package(str(expected_path)), text_only=True)
        calibration = revisions.view(revisions.Package(str(authored_path)), text_only=True)
        # The authored redline proves the engine in this session: it must see the authored revisions,
        # resolve all of them and reproduce the expected text view, exactly where the case says it can.
        calibrated = calibration == expected_view and (mode is None or (
            authored_run['redlinesAfter'] == 0 and (authored_revisions == 0 or authored_run['redlinesBefore'] > 0)))
        declared = case['libreoffice'][key]
        if calibrated != declared:
            check.update(passed=None, reason='LibreOffice calibration does not match the declared eligibility', calibration=_diff(expected_view, calibration))
        elif not declared:
            check.update(passed=None, ineligible=True, reason=case['libreoffice']['note'])
        elif 'error' in candidate_run:
            check.update(passed=False, reason='LibreOffice could not process the candidate output: ' + candidate_run['error'])
        elif mode is not None and candidate_run['redlinesAfter'] != 0:
            check.update(passed=False, reason='LibreOffice left revisions of the candidate unresolved')
        else:
            actual = revisions.view(revisions.Package(str(candidate_path)), text_only=True)
            check['passed'] = actual == expected_view
            if not check['passed']:
                check.update(_diff(expected_view, actual))
        checks.append(check)
    return checks


def aggregate(cases, required):
    ids = {c['id'] for c in cases}
    measured = [c for c in cases if c['status'] == 'measured']
    complete = ids == set(required) and len(measured) == len(required) and len(ids) == len(cases)
    categories = {}
    for case in measured:
        categories.setdefault(case['category'], []).append(case['score'])
    means = {k: sum(v) / len(v) for k, v in sorted(categories.items())}
    kinds = {}
    for case in measured:
        entry = kinds.setdefault(case['kind'], {'passed': 0, 'measured': 0})
        entry['measured'] += 1
        entry['passed'] += case['score'] == 100.0
    eligible = sum(1 for c in measured for check in c['checks'] if check['name'].startswith('libreoffice-') and check['passed'] is not None)
    total = sum(1 for c in measured for check in c['checks'] if check['name'].startswith('libreoffice-'))
    return {'complete': complete, 'measured': len(measured), 'required': len(required),
            'score': sum(means.values()) / len(means) if complete and means else None, 'categoryMeans': means,
            'passRate': sum(c['score'] == 100.0 for c in measured) / len(required) if required else 0,
            'byKind': kinds, 'libreofficeComparisons': {'applicable': eligible, 'total': total}}


def run(output, adapter, candidate, build=None, validator=None, only=None):
    registry = validate_registry()
    env = environment(validator)
    if adapter == 'docxodus':
        if build is None:
            raise ValueError('The docxodus adapter needs --build')
        adapter_identity = {'name': 'docxodus', 'build': verify_docxodus(build, candidate)}
    else:
        adapter_identity = {'name': adapter}
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    contract = {'metric': CONTRACT, 'suiteDigest': identity(registry), 'environment': env['contract'], 'adapter': adapter_identity}
    required = registry['suite']['cases']
    if only is not None and set(only) - set(required):
        raise ValueError('Unknown redline case: ' + ', '.join(sorted(set(only) - set(required))))
    selected = required if only is None else [c for c in required if c in only]
    result = {'schema': 1, 'track': 'redline', 'suite': registry['suite'], 'candidate': candidate,
              'contract': contract, 'contractDigest': identity(contract), 'cases': []}
    for case in registry['cases']:
        if case['id'] not in selected:
            continue
        folder = output / case['id']
        folder.mkdir()
        outcome = score_case(case, folder, adapter, build, candidate, env, validator)
        write_json(folder / 'evidence.json', outcome)
        result['cases'].append(outcome)
        result['summary'] = aggregate(result['cases'], required)
        save(output, result)
        print(case['id'] + ': ' + outcome['status'] + (' score ' + str(outcome['score']) if 'score' in outcome else ' ' + outcome.get('error', '')), flush=True)
    return result


def compare(previous, current):
    for result in (previous, current):
        if result.get('track') != 'redline' or identity(result['contract']) != result['contractDigest']:
            raise ValueError('Invalid redline result')
        if aggregate(result['cases'], result['suite']['cases']) != result['summary']:
            raise ValueError('Invalid redline summary')
    if not previous['summary']['complete'] or not current['summary']['complete']:
        raise ValueError('Cannot compare an incomplete redline run')
    if previous['suite'] != current['suite']:
        raise ValueError('Redline suites differ')
    strip = lambda contract: {k: v for k, v in contract.items() if k != 'adapter'} | {'adapter': contract['adapter']['name']}
    if strip(previous['contract']) != strip(current['contract']):
        raise ValueError('Redline measurement contract changed')
    before = {c['id']: c for c in previous['cases']}
    return [c['id'] + ': regressed from 100 to 0' for c in current['cases'] if before[c['id']]['score'] == 100.0 and c['score'] != 100.0]


def save(output, result):
    write_json(output / 'result.json', result)
    summary = result['summary']
    headline = f'{summary["score"]:.2f}' if summary['complete'] else 'Incomplete — no suite score'
    rows, sections = [], []
    for case in result['cases']:
        cid = html.escape(case['id'])
        shown = f'{case["score"]:.0f}' if case['status'] == 'measured' else 'Unmeasured'
        rows.append(f'<tr><td><a href="#{cid}">{cid}</a></td><td>{html.escape(case["category"])}</td><td>{case["kind"]}</td><td>{html.escape(case["issue"] or "")}</td><td>{shown}</td></tr>')
        details = []
        for check in case.get('checks', []):
            state = 'n/a' if check['passed'] is None else 'pass' if check['passed'] else 'FAIL'
            extra = check.get('reason') or ''
            if check.get('diff'):
                extra += '<pre>' + html.escape('\n'.join(check['diff'])) + '</pre>'
            for key in ('missing', 'observed', 'findings', 'new', 'error'):
                if check.get(key) not in (None, [], {}):
                    extra += ' ' + key + ': <code>' + html.escape(json.dumps(check[key])) + '</code>'
            details.append(f'<li>{html.escape(check["name"])}: <strong>{state}</strong> {extra}</li>')
        sections.append(f'<details id="{cid}"><summary>{cid} — {shown}</summary><p>{html.escape(case.get("error", ""))}</p><ul>{"".join(details)}</ul>'
                        f'<p><a href="{cid}/evidence.json">Case evidence</a></p></details>')
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Redline round trips</title>
    <style>body{{font:16px/1.5 system-ui;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#1c2430}}table{{border-collapse:collapse}}th,td{{text-align:left;padding:.4rem .8rem;border-bottom:1px solid #ccd}}details{{margin:.8rem 0;border:1px solid #ccd;padding:.8rem}}pre{{overflow:auto;background:#f4f5f7;padding:.5rem}}</style>
    <h1>Redline round trips</h1><p>Candidate <code>{html.escape(str(result["candidate"]))}</code>. Suite result: <strong>{headline}</strong>. Coverage {summary["measured"]}/{summary["required"]}; pass rate {summary["passRate"]:.1%}.</p>
    <p>A case scores 100 only when accept-all and reject-all of the candidate's redline reproduce the declared documents in the benchmark's own revision engine and, where eligible, in LibreOffice, the package introduces no new validation errors, and every declared assertion holds. See docs/REDLINE.md.</p>
    <table><thead><tr><th>Case</th><th>Category</th><th>Kind</th><th>Issue</th><th>Score</th></tr></thead><tbody>{"".join(rows)}</tbody></table>{"".join(sections)}</html>'''
    (output / 'index.html').write_text(page)
