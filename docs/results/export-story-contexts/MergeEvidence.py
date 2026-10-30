"""Compose immutable capture segments after a four-case authored fixture correction.

Only generator hashes may differ for reused cases. Every other case field, source,
runtime, font identity and actual artifact hash is verified before making a view.
The output is explicitly diagnostic composition, never a registered benchmark run.
"""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from bench.common import identity


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def semantic(case):
    result = copy.deepcopy(case)
    result['generator'].pop('sha256', None)
    return result


def index(manifest):
    cases = {case['id']: case for case in manifest['cases']}
    if len(cases) != len(manifest['cases']) or set(cases) != set(manifest['suite']['cases']):
        raise ValueError('Duplicate or missing manifest case')
    return cases


def manifest_segment(folder):
    path = folder / 'manifest.json'
    manifest = read(path)
    return manifest, index(manifest), digest(path)


def choose(target, primary, correction):
    if set(target) != set(primary) or set(correction) - set(target):
        raise ValueError('Unexpected correction coverage')
    choices = {}
    for cid, case in target.items():
        source = correction if cid in correction else primary
        if semantic(case) != semantic(source[cid]):
            raise ValueError('Changed case fields outside correction: ' + cid)
        choices[cid] = 1 if cid in correction else 0
    return choices


manifest_path, primary_base, correction_base, primary_candidate, correction_candidate, primary_reference, correction_reference, output = map(Path, sys.argv[1:9])
target_manifest = read(manifest_path)
target = index(target_manifest)
output.mkdir(parents=True, exist_ok=False)
binding = {'schema': 1, 'status': 'unscored-evidence-composition', 'manifestSha256': digest(manifest_path),
           'toolSha256': digest(Path(__file__)), 'captures': {}, 'reference': {}}
headers = ('candidate', 'sourceTree', 'buildIdentitySha256', 'browserVersion', 'executableSha256', 'sandbox', 'fontContract')
manifests = []
for label, folders in [('baseline', (primary_base, correction_base)), ('candidate', (primary_candidate, correction_candidate))]:
    definitions = [manifest_segment(folder) for folder in folders]
    choices = choose(target, definitions[0][1], definitions[1][1])
    records = [read(folder / 'capture.json') for folder in folders]
    for record, definition in zip(records, definitions):
        if record['manifestSha256'] != definition[2] or set(case['id'] for case in record['cases']) != set(definition[1]):
            raise ValueError('Capture/manifest coverage or hash differs')
    if any(records[0][key] != records[1][key] for key in headers):
        raise ValueError('Correction used different source/runtime/fonts')
    if label == 'baseline':
        manifests = definitions
    elif any(a[2] != b[2] for a, b in zip(manifests, definitions)):
        raise ValueError('Baseline/candidate segments have different manifests')
    by_id = [{case['id']: case for case in record['cases']} for record in records]
    if any(len(items) != len(record['cases']) for items, record in zip(by_id, records)):
        raise ValueError('Duplicate capture record')
    destination = output / label
    destination.mkdir()
    composed = {key: copy.deepcopy(records[0][key]) for key in headers}
    composed.update({'schema': 1, 'status': 'unscored-composed-public-api-diagnostic',
                     'manifestSha256': digest(manifest_path), 'cases': [], 'composition': []})
    for folder, definition in zip(folders, definitions):
        composed['composition'].append({'manifestSha256': definition[2], 'captureSha256': digest(folder / 'capture.json'),
                                        'caseIds': [cid for cid in target if choices[cid] == (1 if folder == folders[1] else 0)]})
    for cid, selected in choices.items():
        case = by_id[selected][cid]
        if case['inputSha256'] != target[cid]['sha256']:
            raise ValueError('Changed captured input: ' + cid)
        case_dir = destination / cid
        case_dir.mkdir()
        if case['status'] == 'delivered':
            for filename, field in [('candidate.pdf', 'pdfSha256'), ('production.json', 'renderReportSha256')]:
                source = folders[selected] / cid / filename
                if digest(source) != case[field]:
                    raise ValueError('Changed captured artifact: ' + cid)
                shutil.copyfile(source, case_dir / filename)
        composed['cases'].append(copy.deepcopy(case))
    write(destination / 'manifest.json', target_manifest)
    write(destination / 'capture.json', composed)
    binding['captures'][label] = {'source': composed['candidate'], 'segments': composed['composition'],
                                  'composedCaptureSha256': digest(destination / 'capture.json')}

references = [read(folder / 'bundle.json') for folder in (primary_reference, correction_reference)]
for bundle, definition in zip(references, manifests):
    if bundle['suiteDigest'] != identity(definition[0]) or set(bundle['cases']) != set(definition[1]):
        raise ValueError('Reference segment has a different manifest')
if references[0]['environment'] != references[1]['environment'] or references[0]['track'] != references[1]['track']:
    raise ValueError('Reference environment changed')
choices = choose(target, manifests[0][1], manifests[1][1])
destination = output / 'reference'
destination.mkdir()
reference = {'schema': 1, 'status': 'unscored-composed-reference-evidence', 'suiteDigest': identity(target_manifest),
             'track': references[0]['track'], 'environment': references[0]['environment'], 'cases': {}, 'composition': []}
for selected, (folder, definition) in enumerate(zip((primary_reference, correction_reference), manifests)):
    reference['composition'].append({'manifestSha256': definition[2], 'bundleSha256': digest(folder / 'bundle.json'),
                                     'caseIds': [cid for cid in target if choices[cid] == selected]})
for cid, selected in choices.items():
    case = copy.deepcopy(references[selected]['cases'][cid])
    folder = (primary_reference, correction_reference)[selected]
    source = folder / case['pdf']
    if case['inputSha256'] != target[cid]['sha256'] or digest(source) != case['pdfSha256']:
        raise ValueError('Changed reference input/PDF: ' + cid)
    path = Path(cid) / 'reference.pdf'
    (destination / cid).mkdir()
    shutil.copyfile(source, destination / path)
    case['pdf'] = str(path)
    reference['cases'][cid] = case
write(destination / 'bundle.json', reference)
binding['reference'] = {'segments': reference['composition'], 'composedBundleSha256': digest(destination / 'bundle.json')}
write(output / 'composition.json', binding)
if len(sys.argv) > 9:
    contract_path, original_policy, corrected_policy = map(Path, sys.argv[9:])
    contract = read(contract_path)
    policies = [read(original_policy), read(corrected_policy)]
    for policy, definition in zip(policies, manifests):
        if policy['manifestSha256'] != definition[2]:
            raise ValueError('Policy segment has a different manifest')
    policy_headers = ('candidate', 'sourceTree', 'buildIdentitySha256', 'browserVersion', 'executableSha256', 'sandbox', 'fontContract', 'verifiedFontFiles')
    if any(policies[0][key] != policies[1][key] for key in policy_headers):
        raise ValueError('Policy source/runtime/font binding changed')
    for key in headers:
        if policies[0][key] != composed[key]:
            raise ValueError('Policy and default capture identities differ')
    policy_result = {key: policies[0][key] for key in policy_headers}
    policy_result.update({'schema': 1, 'status': 'unscored-composed-warning-and-strict-policy-diagnostics',
                         'manifestSha256': digest(manifest_path), 'rulesSha256': digest(contract_path), 'cases': [],
                         'composition': [{'policySha256': digest(path), 'manifestSha256': policy['manifestSha256'],
                                          'rulesSha256': policy['rulesSha256']}
                                         for path, policy in zip((original_policy, corrected_policy), policies)]})
    for rule in contract['cases']:
        cid = rule['id']
        selected = choices[cid]
        matches = [case for case in policies[selected]['cases'] if case['id'] == cid]
        if len(matches) != 1:
            raise ValueError('Missing or duplicate policy case: ' + cid)
        case = copy.deepcopy(matches[0])
        if (case['inputSha256'] != target[cid]['sha256'] or case['expectedWarning'] != rule['warning']
                or case['expectedWarningCount'] != rule['warningCount'] or case['expectedStrict'] != rule['strict']):
            raise ValueError('Policy rule/input changed: ' + cid)
        default = next(result for result in composed['cases'] if result['id'] == cid)
        if case['defaultRenderReportSha256'] != default['renderReportSha256']:
            raise ValueError('Policy/default report binding changed: ' + cid)
        report = read(output / 'candidate' / cid / 'production.json')
        codes = [warning['code'] for warning in report['warnings']]
        if codes != case['warningCodes']:
            raise ValueError('Policy/default warning list changed: ' + cid)
        case['warningCheckPassed'] = codes == [rule['warning']] * rule['warningCount']
        strict = case['strictResult']
        if strict['status'] == 'delivered':
            source = (primary_candidate, correction_candidate)[selected] / cid / 'strict.pdf'
            if not source.is_file() or digest(source) != strict['pdfSha256']:
                raise ValueError('Changed or missing strict PDF: ' + cid)
            shutil.copyfile(source, output / 'candidate' / cid / 'strict.pdf')
            case['strictCheckPassed'] = rule['strict'] == 'delivered'
        elif strict['status'] == 'rejected':
            case['strictCheckPassed'] = (rule['strict'] == 'rejected' and strict.get('code') == 'resource_policy_failure'
                                         and strict.get('phase') == 'output_verification')
        else:
            raise ValueError('Unknown strict outcome: ' + cid)
        case['passed'] = case['warningCheckPassed'] and case['strictCheckPassed']
        policy_result['cases'].append(case)
    write(output / 'policy-results.json', policy_result)
print('Composed', len(target), 'cases from', len(target) - len(manifests[1][1]), 'unchanged and', len(manifests[1][1]), 'corrected inputs')
