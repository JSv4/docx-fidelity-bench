"""Versioned CI selection; the complete corpus remains the default."""
from copy import deepcopy
from pathlib import Path
from .common import read_json, validate_registry


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
