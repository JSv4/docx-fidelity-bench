"""Redline track: run a comparison candidate and score its accept/reject round trips.

A candidate turns each case's inputs into one output package: a redline for `compare` and
`consolidate`, a resolved document for `reject`. The output is then judged by two engines that
share no code with any candidate: the benchmark's own revision engine (`bench/revisions.py`,
compared on the full semantic view) and LibreOffice through headless UNO (compared on the text
view, after both sides take the same LibreOffice load/save path). See docs/REDLINE.md.
"""
from __future__ import annotations

import difflib
import hashlib
import html
import json
import os
import re
import shutil
import signal
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from . import revisions, revision_ownership
from .redline_build import dotnet as _dotnet, validate_packages, verify_docxodus, verify_validator
from .common import ROOT, contained, digest, execute, identity, read_json, write_json

MANIFEST = ROOT / 'fixtures' / 'redline' / 'manifest.json'
OPERATIONS = {'compare': 2, 'consolidate': None, 'reject': 1, 'table-widths': 1, 'column-edit': 1, 'block-insert': 1, 'replace-span': 1, 'replace-text': 1, 'revision-ownership': 1}
ASSERTIONS = {'untracked-text': {1}, 'paragraph-count': {1}, 'para-ids-valid': {1}, 'style-ids-unique': {1}, 'revision-count': {1}, 'comment-threads': {1}, 'table-widths': {1}, 'table-state': {1}, 'people-identity': {1}, 'pending-insertion-deletion': {1}, 'hyperlink-targets': {1}, 'run-atoms': {1}, 'content-controls': {1}, 'revision-text': {1}, 'inline-trees': {1}}
RUN_ATOMS = {'tab', 'ptab', 'br', 'cr', 'noBreakHyphen', 'softHyphen', 'sym'}
CATEGORIES = {'fields', 'comments', 'bookmarks', 'styles', 'revisions', 'consolidate', 'identity', 'tables', 'packages'}
SCOPES = {'compare': {'redline', 'accepted', 'rejected'}, 'consolidate': {'redline', 'accepted', 'rejected'}, 'reject': {'output'}, 'table-widths': {'redline', 'accepted', 'rejected'}, 'column-edit': {'output'}, 'block-insert': {'output'}, 'replace-span': {'redline', 'accepted', 'rejected'}, 'replace-text': {'redline', 'accepted', 'rejected'}, 'revision-ownership': {'redline', 'accepted', 'rejected'}}
CONTRACT = {'version': 14, 'view': revisions.VIEW_VERSION, 'engines': ['bench-markup', 'libreoffice-text'],
            'caseScore': '100 when every applicable mandatory check passes, otherwise 0',
            'suiteScore': 'mean of category means over every required case',
            'libreofficeEligibility': 'a LibreOffice comparison applies only when the authored redline passes it',
            'validity': 'no OpenXmlValidator finding (id, part, description) occurs more often than in any input, and the output opens: a Package_Open finding in the output always fails, whatever the inputs did',
            'semanticPreflight': 'declared identity cases must report zero changes at raw limits with and without the package supplement',
            'revisionRegistry': 'declared table operations must report the public registry count and match independent resolved table assertions',
            'blockInsertion': 'declared insertion outcomes require typed success, error, version change and undo availability',
            'spanEditing': 'public span editing must preserve text and inline-marker order through both independent revision resolvers',
            'paragraphRewrite': 'public untracked whole-paragraph rewrites must preserve exact declared native content-control subtrees as well as independent semantic views',
            'columnReview': 'v2 column edits require the declared typed registry count/status before resolution, successful public resolution and an empty final registry',
            'revisionOwnership': 'account-configured edits require declared before/after public name status, exact raw reviewer identities and retained insertion/deletion markup, in addition to independent round trips',
            'inlineTrees': 'declared math and drawing subtrees retain structure, properties, textbox content and image bytes in both independently resolved views',
            'revisionText': 'declared move sources and ordinary deletions must retain their appropriate text carrier',
            'hyperlinkTargets': 'declared hyperlink-target assertions require every main-document hyperlink to resolve to one external relationship, and the set of their targets to equal the declared strings as written'}
HARNESS = ['bench/redline.py', 'bench/revisions.py', 'bench/lo_revisions.py', 'bench/redline_build.py', 'bench/revision_ownership.py']


# ---------------------------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------------------------

def control_tree(element):
    # The candidate adds addressing attributes; they are not native Word control metadata.
    attributes = {k: v for k, v in element.attrib.items()
                  if not k.startswith('{http://powertools.codeplex.com/2011}')}
    text = element.text if element.text and (element.text.strip() or not len(element)) else None
    return [element.tag, attributes, text, [control_tree(e) for e in element]]


def valid_control_trees(values):
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        return False
    try:
        return all(ET.fromstring(value).tag == revisions.w('sdt') for value in values)
    except ET.ParseError:
        return False


INLINE_TREES = {'oMath': revisions.m('oMath'), 'drawing': revisions.w('drawing'), 'pict': revisions.w('pict')}


def inline_tree(element, images):
    # Compare native structure and content. Only remappable drawing ids and engine addressing are ignored.
    attributes = {k: v for k, v in element.attrib.items()
                  if not k.startswith('{http://powertools.codeplex.com/2011}')
                  and not (element.tag == '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}docPr' and k == 'id')}
    embed = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed'
    if embed in attributes:
        attributes[embed] = images.get(attributes[embed], 'unresolved:' + attributes[embed])
    text = element.text if element.text and (element.text.strip() or not len(element)) else None
    children = [inline_tree(e, images) for e in element]
    children = [child for child in children if not (child[0] in {revisions.w('rPr'), revisions.m('rPr')}
                and not child[1] and child[2] is None and not child[3])]
    def text_run(node):
        if node[0] not in {revisions.w('r'), revisions.m('r')}:
            return None
        texts = [child for child in node[3] if child[0] in {revisions.w('t'), revisions.m('t')}]
        props = [child for child in node[3] if child[0] in {revisions.w('rPr'), revisions.m('rPr')}]
        if len(texts) != 1 or len(props) + 1 != len(node[3]):
            return None
        return (node[0], node[1], props, texts[0][0], texts[0][1]), texts[0]
    merged = []
    for child in children:
        previous = text_run(merged[-1]) if merged else None
        current = text_run(child)
        if previous is not None and current is not None and previous[0] == current[0]:
            previous[1][2] = (previous[1][2] or '') + (current[1][2] or '')
        else:
            merged.append(child)
    tag = {revisions.w('delText'): revisions.w('t'), revisions.w('delInstrText'): revisions.w('instrText')}.get(element.tag, element.tag)
    return [tag, attributes, text, merged]


def valid_inline_trees(assertion):
    if not isinstance(assertion.get('name'), str) or assertion['name'] not in INLINE_TREES:
        return False
    trees, images = assertion.get('trees'), assertion.get('images')
    if not isinstance(trees, list) or not all(isinstance(xml, str) for xml in trees):
        return False
    if not isinstance(images, dict) or not all(isinstance(k, str) and k and isinstance(v, str)
            and re.fullmatch('[0-9a-f]{64}', v) for k, v in images.items()):
        return False
    try:
        return all(ET.fromstring(xml).tag == INLINE_TREES[assertion['name']] for xml in trees)
    except ET.ParseError:
        return False


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
        expected = {'compare': {'accepted', 'rejected'}, 'consolidate': {'accepted', 'rejected'}, 'reject': {'output'}, 'table-widths': {'accepted', 'rejected'}, 'column-edit': {'output'}, 'block-insert': {'output'}, 'replace-span': {'accepted', 'rejected'}, 'replace-text': {'accepted', 'rejected'}, 'revision-ownership': {'accepted', 'rejected'}}[operation]
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
        elif operation == 'column-edit':
            spec = case.get('columnEdit', {})
            version = spec.get('version')
            keys = {'version', 'action', 'position', 'cellIndex', 'resolution'} | ({'tracked'} if version == 2 else set())
            if (set(spec) != keys or version not in {1, 2}
                    or spec['action'] not in ({'insert'} if version == 2 else {'insert', 'delete'}) or spec['position'] not in {'before', 'after'}
                    or type(spec['cellIndex']) is not int or spec['cellIndex'] < 0
                    or spec['resolution'] not in {'reject-all', 'reject-each', 'accept-all'}
                    or case.get('revisionRegistry') != {'version': 1, 'count': 0}
                    or type(case['revisionRegistry']['count']) is not int):
                raise ValueError('Invalid column edit declaration: ' + case['id'])
            if version == 2:
                review = case.get('columnReview', {})
                if (type(spec['tracked']) is not bool
                        or review != {'version': 1, 'beforeCount': 1 if spec['tracked'] else 0,
                                      'supported': True, 'resolutionSuccess': True}
                        or type(review.get('beforeCount')) is not int
                        or type(review.get('supported')) is not bool or type(review.get('resolutionSuccess')) is not bool):
                    raise ValueError('Invalid column review declaration: ' + case['id'])
            elif 'columnReview' in case:
                raise ValueError('Unexpected column review declaration: ' + case['id'])
        elif operation == 'block-insert':
            spec = case.get('blockInsert', {})
            observed = case.get('editOutcome', {})
            success = observed.get('success')
            if (set(spec) != {'version', 'operation', 'anchorKind', 'position', 'markdown'} or spec['version'] != 1
                    or spec['operation'] not in {'paragraph', 'rule', 'table'} or spec['anchorKind'] not in {'p', 'tc'}
                    or spec['position'] not in {'before', 'after'} or not isinstance(spec['markdown'], str)
                    or type(success) is not bool
                    or observed != {'success': success, 'errorCode': None if success else 'AnchorWrongKind',
                                    'versionDelta': 1 if success else 0, 'undoAvailable': success}
                    or type(observed.get('versionDelta')) is not int or type(observed.get('undoAvailable')) is not bool):
                raise ValueError('Invalid block insertion declaration: ' + case['id'])
        elif operation == 'replace-text':
            spec = case.get('paragraphRewrite', {})
            if (not isinstance(spec, dict) or set(spec) != {'version', 'paragraphIndex', 'markdown'} or type(spec['version']) is not int or spec['version'] != 1
                    or type(spec['paragraphIndex']) is not int or spec['paragraphIndex'] < 0
                    or not isinstance(spec['markdown'], str)):
                raise ValueError('Invalid paragraph rewrite declaration: ' + case['id'])
        elif operation == 'replace-span':
            spec = case.get('spanEdit', {})
            if (set(spec) != {'version', 'tracked', 'paragraphIndex', 'start', 'length', 'replacement'}
                    or spec['version'] != 1 or type(spec['tracked']) is not bool
                    or any(type(spec[key]) is not int or spec[key] < 0 for key in ('paragraphIndex', 'start'))
                    or type(spec['length']) is not int or spec['length'] <= 0
                    or not isinstance(spec['replacement'], str)):
                raise ValueError('Invalid span edit declaration: ' + case['id'])
        elif operation == 'revision-ownership':
            if not revision_ownership.valid_spec(case.get('revisionOwnership'), case.get('authorNameStatus')):
                raise ValueError('Invalid revision ownership declaration: ' + case['id'])
        elif 'tableWidths' in case or 'revisionRegistry' in case or 'columnEdit' in case:

            raise ValueError('Unexpected table width operation data: ' + case['id'])
        if operation != 'column-edit' and 'columnReview' in case:
            raise ValueError('Unexpected column review data: ' + case['id'])
        if operation != 'replace-text' and 'paragraphRewrite' in case:
            raise ValueError('Unexpected paragraph rewrite data: ' + case['id'])
        if operation != 'replace-span' and 'spanEdit' in case:
            raise ValueError('Unexpected span edit data: ' + case['id'])
        if operation != 'block-insert' and ('blockInsert' in case or 'editOutcome' in case):
            raise ValueError('Unexpected block insertion data: ' + case['id'])
        if operation != 'revision-ownership' and ('revisionOwnership' in case or 'authorNameStatus' in case):
            raise ValueError('Unexpected revision ownership data: ' + case['id'])
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
                     'revision-text': lambda a: a['scope'] == 'redline' and isinstance(a.get('kind'), str) and a['kind'] in {'moveFrom', 'del'}
                         and isinstance(a.get('text'), str) and bool(a['text']),
                     'table-widths': lambda a: a['scope'] in {'accepted', 'rejected'} and isinstance(a.get('grid'), list)
                         and a['grid'] and all(type(v) is int and v > 0 for v in a['grid'])
                         and isinstance(a.get('cells'), list) and a['cells'] and all(isinstance(row, list) and row
                             and all(type(v) is int and v > 0 for v in row) for row in a['cells'])
                         and type(a.get('table')) is int and a['table'] > 0,
                     'table-state': lambda a: a['scope'] == 'output' and valid_table_state(a.get('state')),
                     'people-identity': lambda a: a['scope'] == 'redline' and isinstance(a.get('author'), str) and bool(a['author'])
                         and revision_ownership.valid_identities(a.get('identities')),
                     'inline-trees': lambda a: a['scope'] in {'accepted', 'rejected'} and valid_inline_trees(a),
                     'content-controls': lambda a: a['scope'] in {'accepted', 'rejected'} and valid_control_trees(a.get('controls')),
                     'run-atoms': lambda a: a['scope'] in {'accepted', 'rejected'} and isinstance(a.get('atoms'), list)
                         and all(isinstance(x, dict) and set(x) == {'name', 'attributes'}
                             and isinstance(x['name'], str) and x['name'] in RUN_ATOMS
                             and isinstance(x['attributes'], dict) and all(isinstance(k, str) and isinstance(v, str)
                                 for k, v in x['attributes'].items()) for x in a['atoms']),
                     'hyperlink-targets': lambda a: a['scope'] == 'redline' and isinstance(a.get('targets'), list) and all(isinstance(x, str) and x for x in a['targets']),
                     'pending-insertion-deletion': lambda a: a['scope'] == 'redline' and all(isinstance(a.get(k), str) and bool(a[k]) for k in ('author', 'deletedBy', 'text')),
                     'comment-threads': lambda a: a['scope'] == 'redline' and isinstance(a.get('threads'), list) and all(
                         isinstance(x, list) and len(x) == 2 and all(isinstance(y, str) and y for y in x) for x in a['threads'])}[kind]
            if not valid(assertion):
                raise ValueError('Invalid assertion declaration: ' + case['id'] + ' ' + kind)
        if operation == 'replace-text' and {'type': 'revision-count', 'version': 1, 'scope': 'redline', 'max': 0} not in case['assertions']:
            raise ValueError('An untracked rewrite must require a redline without revisions: ' + case['id'])
        if operation in {'reject', 'column-edit', 'block-insert'} and {'type': 'revision-count', 'version': 1, 'scope': 'output', 'max': 0} not in case['assertions']:
            raise ValueError('A reject case must require an output without revisions: ' + case['id'])
    return registry


def valid_table_state(state):
    if not isinstance(state, dict) or set(state) != {'grid', 'rows'}:
        return False
    if not isinstance(state['grid'], list) or not state['grid'] or any(type(w) is not int or w < 0 for w in state['grid']):
        return False
    if not isinstance(state['rows'], list) or not state['rows']:
        return False
    for row in state['rows']:
        if not isinstance(row, dict) or set(row) != {'before', 'after', 'height', 'cells'}:
            return False
        if any(type(row[key]) is not int or row[key] < 0 for key in ('before', 'after')):
            return False
        if row['height'] is not None and (type(row['height']) is not int or row['height'] < 0):
            return False
        if not isinstance(row['cells'], list) or not row['cells']:
            return False
        for cell in row['cells']:
            if (not isinstance(cell, dict) or set(cell) != {'span', 'width', 'type', 'fill'}
                    or type(cell['span']) is not int or cell['span'] <= 0
                    or type(cell['width']) is not int or cell['width'] < 0 or cell['type'] != 'dxa'
                    or (cell['fill'] is not None and not isinstance(cell['fill'], str))):
                return False
        if row['before'] + row['after'] + sum(c['span'] for c in row['cells']) != len(state['grid']):
            return False
    return True


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
    if 'columnEdit' in case:
        request['settings']['columnEdit'] = case['columnEdit']
    if 'blockInsert' in case:
        request['settings']['blockInsert'] = case['blockInsert']
    if 'paragraphRewrite' in case:
        request['settings']['paragraphRewrite'] = case['paragraphRewrite']
    if 'spanEdit' in case:
        request['settings']['spanEdit'] = case['spanEdit']
    if 'revisionOwnership' in case:
        request['settings']['revisionOwnership'] = case['revisionOwnership']
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
    if kind == 'people-identity':
        observed = revision_ownership.people_identities(package, assertion['author'])
        check.update(passed=observed == assertion['identities'], observed=observed)
    elif kind == 'pending-insertion-deletion':
        check.update(passed=revision_ownership.retained_deletion(package, assertion['author'], assertion['deletedBy'], assertion['text']))
    elif kind == 'table-state':
        roots = parts if parts is not None else package.story_parts()
        tables = list(roots[package.main].iter(revisions.w('tbl')))
        def number(element, attribute, default=None):
            value = None if element is None else element.get(revisions.w(attribute))
            return int(value) if value is not None and value.isdecimal() else default if value is None else value
        observed = None
        if len(tables) == 1:
            table = tables[0]
            grid = table.find(revisions.w('tblGrid'))
            rows = []
            for row in table.findall(revisions.w('tr')):
                row_pr = row.find(revisions.w('trPr'))
                row_property = lambda name: None if row_pr is None else row_pr.find(revisions.w(name))
                cells = []
                for cell in row.findall(revisions.w('tc')):
                    pr = cell.find(revisions.w('tcPr'))
                    property_of = lambda name: None if pr is None else pr.find(revisions.w(name))
                    width = property_of('tcW')
                    fill = property_of('shd')
                    cells.append({'span': number(property_of('gridSpan'), 'val', 1), 'width': number(width, 'w'),
                                  'type': None if width is None else width.get(revisions.w('type')),
                                  'fill': None if fill is None else fill.get(revisions.w('fill'))})
                rows.append({'before': number(row_property('gridBefore'), 'val', 0),
                             'after': number(row_property('gridAfter'), 'val', 0),
                             'height': number(row_property('trHeight'), 'val'), 'cells': cells})
            observed = {'grid': [] if grid is None else [number(c, 'w') for c in grid.findall(revisions.w('gridCol'))], 'rows': rows}
        check.update(passed=observed == assertion['state'], observed=observed)
    elif kind == 'table-widths':
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
    elif kind == 'revision-text':
        root = package.xml(package.main).find(revisions.w('body'))
        wrappers = list(root.iter(revisions.w(assertion['kind'])))
        is_move = assertion['kind'] == 'moveFrom'
        def text_of(wrapper):
            return ''.join(t.text or '' for t in wrapper.iter(revisions.w('t' if is_move else 'delText')))
        texts = []
        if is_move:
            active = {}
            for element in root.iter():
                if element.tag == revisions.w('moveFromRangeStart'):
                    active[element.get(revisions.w('id'))] = []
                elif element.tag == revisions.w('moveFrom'):
                    for group in active.values(): group.append(text_of(element))
                elif element.tag == revisions.w('moveFromRangeEnd'):
                    group = active.pop(element.get(revisions.w('id')), None)
                    if group is not None: texts.append(''.join(group))
        else:
            for parent in root.iter():
                group = []
                for child in parent:
                    if child.tag == revisions.w('del'):
                        group.append(text_of(child))
                    elif child.tag in {revisions.w('proofErr'), revisions.w('bookmarkStart'), revisions.w('bookmarkEnd'),
                                       revisions.w('commentRangeStart'), revisions.w('commentRangeEnd'),
                                       revisions.w('permStart'), revisions.w('permEnd'), revisions.w('lastRenderedPageBreak')}:
                        continue
                    elif group:
                        texts.append(''.join(group)); group = []
                if group: texts.append(''.join(group))
        invalid = sum(1 for wrapper in wrappers for e in wrapper.iter()
                      if e.tag in {revisions.w('delText' if is_move else 't'),
                                   revisions.w('delInstrText' if is_move else 'instrText')})
        check.update(passed=any(assertion['text'] in text for text in texts) and invalid == 0, observed=texts, invalid=invalid)
    elif kind == 'paragraph-count':
        count = revisions.body_paragraph_count(package, parts)
        check.update(passed=count == assertion['count'], observed=count)
    elif kind == 'para-ids-valid':
        findings = revisions.para_id_findings(package)
        check.update(passed=not findings, findings=findings)
    elif kind == 'style-ids-unique':
        findings = revisions.style_id_findings(package)
        check.update(passed=not findings, findings=findings)
    elif kind == 'inline-trees':
        root = parts[package.main] if parts is not None else package.xml(package.main)
        images = {identifier: hashlib.sha256(package.members[target]).hexdigest()
                  for identifier, (relationship_type, target) in package.main_rels.items()
                  if relationship_type == 'image' and target in package.members}
        observed = [inline_tree(e, images) for e in root.find(revisions.w('body')).iter(INLINE_TREES[assertion['name']])]
        expected = [inline_tree(ET.fromstring(xml), assertion['images']) for xml in assertion['trees']]
        check.update(passed=observed == expected, observed=observed)
    elif kind == 'content-controls':
        root = parts[package.main] if parts is not None else package.xml(package.main)
        observed = [control_tree(e) for e in root.find(revisions.w('body')).iter(revisions.w('sdt'))]
        expected = [control_tree(ET.fromstring(xml)) for xml in assertion['controls']]
        check.update(passed=observed == expected, observed=observed)
    elif kind == 'run-atoms':
        root = parts[package.main] if parts is not None else package.xml(package.main)
        observed = [dict(name=e.tag.split('}', 1)[-1],
                         attributes={k.split('}', 1)[-1]: v for k, v in e.attrib.items() if k.startswith(revisions.w(''))})
                    for run in root.find(revisions.w('body')).iter(revisions.w('r')) for e in run
                    if e.tag in {revisions.w(name) for name in RUN_ATOMS}]
        check.update(passed=observed == assertion['atoms'], observed=observed)
    elif kind == 'hyperlink-targets':
        findings = revisions.hyperlink_target_findings(package, assertion['targets'])
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
    # An input the SDK cannot open reports no schema findings at all, so its Package_Open finding
    # can never license the output's: an output that fails to open would go unvalidated.
    for key in [k for k in allowed if k[0] == 'Package_Open']:
        allowed[key] = 0
    new = [{'id': k[0], 'part': k[1], 'description': k[2], 'count': v, 'allowed': allowed.get(k, 0)}
           for k, v in sorted(counts(documents[str(output)]).items(), key=lambda item: str(item[0])) if v > allowed.get(k, 0)]
    return {'name': 'no-new-validation-errors', 'passed': not new, 'new': new}


def score_case(case, folder, adapter, build, candidate, env, validator):
    outcome = {'id': case['id'], 'category': case['category'], 'kind': case['kind'], 'issue': case['issue'],
               'operation': case['operation'], 'status': 'unmeasured', 'checks': []}
    inputs = [contained(ROOT, i['path']) for i in case['inputs']]
    output = folder / ('candidate-output.docx' if case['operation'] in {'reject', 'column-edit', 'block-insert'} else 'candidate-redline.docx')
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
        if case['operation'] in {'reject', 'column-edit', 'block-insert'}:
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
        if 'authorNameStatus' in case:
            observed = (revision_ownership.name_status_check(case, None)['expected'] if adapter == 'authored'
                        else response.get('revisionAuthorNameStatus'))
            outcome['checks'].append(revision_ownership.name_status_check(case, observed))
        if 'editOutcome' in case:
            expected_outcome = case['editOutcome']
            observed = expected_outcome if adapter == 'authored' else response.get('blockInsertion')
            typed = (isinstance(observed, dict) and type(observed.get('success')) is bool
                     and type(observed.get('versionDelta')) is int and type(observed.get('undoAvailable')) is bool)
            outcome['checks'].append({'name': 'block-insertion-outcome', 'passed': typed and observed == expected_outcome,
                                      'expected': expected_outcome, 'observed': observed})
        if 'columnReview' in case:
            expected_review = {key: value for key, value in case['columnReview'].items() if key != 'version'}
            observed = expected_review if adapter == 'authored' else response.get('columnReview')
            typed = (isinstance(observed, dict) and type(observed.get('beforeCount')) is int
                     and type(observed.get('supported')) is bool and type(observed.get('resolutionSuccess')) is bool)
            outcome['checks'].append({'name': 'column-revision-resolution', 'passed': typed and observed == expected_review,
                                      'expected': expected_review, 'observed': observed})
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
    if case['operation'] in {'reject', 'column-edit', 'block-insert'}:
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
