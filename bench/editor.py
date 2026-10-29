"""Unweighted, source-bound browser diagnostics for shipped editor interactions.

Build the production runtime with `bench build-docxodus` first. This lane additionally builds
its shipped ribbon bundle, exercises real browser actions, and inspects saved OOXML itself.
It does not share the PDF/redline track's metrics or export-environment eligibility contract.
"""
import argparse
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile
from . import editor_fixtures
from .common import ROOT, contained, digest, execute, read_json, write_json
from .redline_build import _clean, validate_packages, verify_validator

SOURCES = ['bench/editor.py', 'bench/editor_fixtures.py', 'adapters/editor-diagnostic.mjs', 'docs/editor/host.html']
W = '{' + editor_fixtures.W + '}'


def verify_source(source, commit):
    source = Path(source).resolve()
    if not re.fullmatch('[0-9a-f]{40}', commit) or not _clean(source, commit):
        raise ValueError('Editor source must be clean at the exact requested commit')
    record = read_json(source / '.docx-bench-build.json')
    if (record.get('schema') != 1 or record['commit'] != commit
            or record['tree'] != execute(['git', '-C', source, 'rev-parse', 'HEAD^{tree}']).strip()
            or record['node'] != execute(['node', '--version']).strip()
            or record['recipeSha256'] != digest(ROOT / 'bench/build.py')):
        raise ValueError('Stale production build identity')
    for name, value in record['files'].items():
        if digest(contained(source, name)) != value:
            raise ValueError('Production build artifact changed: ' + name)
    assets = read_json(source / 'npm/dist/export-assets.json')
    for asset in assets['assets']:
        if digest(contained(source / 'npm/dist', asset['path'])) != asset['sha256']:
            raise ValueError('Production runtime asset changed: ' + asset['path'])
    return record


def package_facts(path):
    with ZipFile(path) as archive:
        document = ET.fromstring(archive.read('word/document.xml'))
    text = []
    def walk(node):
        if node.tag in {W + 'del', W + 'moveFrom'}:
            return
        if node.tag == W + 't':
            text.append(node.text or '')
        elif node.tag == W + 'tab':
            text.append('\t')
        elif node.tag in {W + 'br', W + 'cr'}:
            text.append('\n')
        else:
            for child in node:
                walk(child)
    walk(document)
    markers = {'moveFromRangeStart', 'moveFromRangeEnd', 'customXmlInsRangeStart', 'customXmlInsRangeEnd'}
    return {'text': ''.join(text), 'tabs': len(document.findall('.//' + W + 'tab')),
            'insertions': len(document.findall('.//' + W + 'ins')),
            'rangeMarkers': sum(node.tag.removeprefix(W) in markers for node in document.iter())}


def checks(case, observation, facts, schema_findings):
    expected = case['expected']
    out = [{'name': key, 'passed': facts[key] == expected[key], 'actual': facts[key], 'expected': expected[key]}
           for key in ('text', 'tabs', 'insertions', 'rangeMarkers')]
    out.append({'name': 'schema', 'passed': not schema_findings, 'findings': schema_findings})
    if case['action'] == 'review-count':
        out.append({'name': 'ribbon-badge', 'passed': observation.get('badge') == expected['badge'],
                    'actual': observation.get('badge'), 'expected': expected['badge']})
    if case['action'].startswith('copy'):
        out.append({'name': 'native-plain-paste', 'passed': observation.get('copiedPlain') == expected['text'],
                    'actual': observation.get('copiedPlain'), 'expected': expected['text']})
        out.append({'name': 'native-rich-text', 'passed': observation.get('richText') == expected['text'],
                    'actual': observation.get('richText'), 'expected': expected['text']})
    if case['action'] == 'copy-classes':
        out.append({'name': 'native-rich-paste', 'passed': observation.get('richFormatted') is True})
    out.append({'name': 'browser-errors', 'passed': observation.get('pageErrors') == []})
    return out


def run(source, commit, output, validator):
    registry = editor_fixtures.validate()
    source, output = Path(source).resolve(), Path(output).resolve()
    production = verify_source(source, commit)
    validation = verify_validator(validator)
    if output.exists():
        raise ValueError('Editor output directory already exists')
    output.mkdir(parents=True)
    command = ['npm', '--prefix', str(source / 'npm'), 'run', 'build:editor-bundle']
    subprocess.run(command, check=True, timeout=180)
    files = {'npm/dist/editor.bundle.js': digest(source / 'npm/dist/editor.bundle.js')}
    files.update({str(path.relative_to(source)): digest(path)
                  for path in sorted((source / 'npm/dist/wasm/_framework').rglob('*')) if path.is_file()})
    build = {'schema': 1, 'commit': commit, 'tree': production['tree'],
             'productionBuildSha256': digest(source / '.docx-bench-build.json'),
             'commands': [command], 'node': execute(['node', '--version']).strip(), 'files': files,
             'harnessSources': {name: digest(ROOT / name) for name in SOURCES},
             'manifestSha256': digest(ROOT / 'fixtures/editor/manifest.json'), 'validator': validation}
    write_json(output / 'build.json', build)
    inputs = [ROOT / c['input'] for c in registry['cases']]
    input_schema = validate_packages(validator, inputs)
    if any(input_schema.values()):
        raise ValueError('Editor inputs must have zero actual SDK findings')
    write_json(output / 'input-validation.json', input_schema)
    build['inputValidationSha256'] = digest(output / 'input-validation.json')
    write_json(output / 'build.json', build)
    subprocess.run(['node', str(ROOT / 'adapters/editor-diagnostic.mjs'), str(source),
                    str(ROOT / 'fixtures/editor/manifest.json'), str(output)], check=True, timeout=900)
    observations = read_json(output / 'observations.json')
    if (observations.get('schema') != 1 or observations.get('commit') != commit
            or observations.get('suite') != registry['suite']
            or [c['id'] for c in observations.get('cases', [])] != [c['id'] for c in registry['cases']]):
        raise ValueError('Incomplete or mismatched editor observation envelope')
    results = []
    for case, observed in zip(registry['cases'], observations['cases']):
        item = {'id': case['id'], 'control': case['control'], 'status': 'unmeasured', 'checks': []}
        if observed['inputSha256'] != case['sha256'] or digest(output / (case['id'] + '.png')) != observed['pngSha256']:
            raise ValueError('Observation input/screenshot binding changed')
        if observed['status'] == 'observed':
            saved = output / (case['id'] + '.docx')
            if digest(saved) != observed['outputSha256']:
                raise ValueError('Saved editor document binding changed')
            findings = validate_packages(validator, [saved])[str(saved)]
            item.update(status='observed', checks=checks(case, observed, package_facts(saved), findings))
            item['passed'] = all(check['passed'] for check in item['checks'])
        results.append(item)
    verify_source(source, commit)
    if editor_fixtures.validate() != registry or any(digest(source / name) != value for name, value in files.items()):
        raise ValueError('Runtime or fixtures changed during browser observation')
    if build['harnessSources'] != {name: digest(ROOT / name) for name in SOURCES}:
        raise ValueError('Editor observation code changed during the run')
    summary = {'required': len(results), 'observed': sum(c['status'] == 'observed' for c in results),
               'passed': sum(c.get('passed', False) for c in results),
               'controlsPassed': all(c.get('passed', False) for c in results if c['control'])}
    summary['complete'] = summary['observed'] == summary['required'] and summary['controlsPassed']
    result = {'schema': 1, 'suite': registry['suite'], 'commit': commit, 'scope': registry['scope'],
              'buildSha256': digest(output / 'build.json'), 'observationsSha256': digest(output / 'observations.json'),
              'summary': summary, 'cases': results}
    write_json(output / 'result.json', result)
    print(json.dumps(summary))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'commit', 'output', 'validator'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    run(args.source, args.commit, args.output, args.validator)
