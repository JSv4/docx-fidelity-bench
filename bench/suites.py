"""Versioned CI selection; the complete corpus remains the default."""
from copy import deepcopy
from pathlib import Path
from .common import identity, read_json, validate_registry


def select_cases(registry, case_ids):
    """Explicit diagnostics have their own identity; they never stand in for the full suite."""
    if (not isinstance(case_ids, list) or not case_ids
            or any(not isinstance(cid, str) for cid in case_ids) or len(set(case_ids)) != len(case_ids)):
        raise ValueError('Diagnostic cases must be a nonempty array of unique case ids')
    registry = validate_registry(registry)
    wanted = set(case_ids)
    if wanted - set(registry['suite']['cases']):
        raise ValueError('Unknown diagnostic case')
    cases = [deepcopy(case) for case in registry['cases'] if case['id'] in wanted]
    ids = [case['id'] for case in cases]
    return validate_registry({'schema': registry['schema'],
                              'suite': {'id': 'diagnostic-' + identity(ids)[:12], 'version': 1, 'cases': ids},
                              'cases': cases})


def select_suite(registry, suite=None):
    if suite is None:
        return registry
    contract = read_json(Path(__file__).with_name('ci-suite.json'))
    if suite != contract['id']:
        raise ValueError('Unknown registered suite: ' + str(suite))
    by_id = {case['id']: case for case in registry['cases']}
    cases = []
    for cid in contract['cases']:
        if cid not in by_id or by_id[cid]['sha256'] != contract['inputSha256'][cid]:
            raise ValueError('CI input is missing or changed: ' + cid)
        cases.append(deepcopy(by_id[cid]))
    selected = {'schema': registry['schema'], 'suite': {
        'id': contract['id'], 'version': contract['version'], 'cases': list(contract['cases'])},
        'cases': cases}
    return validate_registry(selected)
