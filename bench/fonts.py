"""Unweighted, source-bound diagnostics of actual exported font usage.

Poppler reads fonts from each PDF page independently of Chromium's reported observations.
Each authored page uses one requested family, making the request-to-face comparison independent.
This lane does not relax or contribute to the scored adapter's strict verified-font contract.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from . import font_fixtures, pdf
from .common import ROOT, digest, execute, read_json, write_json
from .editor import verify_source
from .redline_build import validate_packages, verify_validator

SOURCES = ['bench/fonts.py', 'bench/font_fixtures.py', 'adapters/font-diagnostic.mjs', 'bench/pdf.py',
           'bench/common.py', 'bench/editor.py', 'bench/redline_build.py', 'bench/metrics.py', 'bench/fixtures.py']


def pdf_font_names(text):
    """Only PDF's six-uppercase-letter subset prefix is ignored; names otherwise stay exact."""
    return sorted(set(re.sub(r'^[A-Z]{6}\+', '', line.split()[0])
                      for line in text.splitlines()[2:] if line.strip()))


def compact(text):
    return re.sub(r'\s+', '', text)


def checks(case, report, screen_report, page_map, html_pages, info, page_fonts, html_nodes, screen_map):
    result = []
    def check(name, passed):
        result.append({'name': name, 'passed': bool(passed)})
    pages = case['pages']
    check('source-digest', report.get('source', {}).get('rawPackageBytesDigest') == case['sha256']
          == screen_report.get('source', {}).get('rawPackageBytesDigest'))
    check('page-coverage', len(info['geometry']) == len(pages) == len(html_pages) == len(page_map['pages']))
    check('missing-warning', any(w['code'] == 'font_unavailable' for w in report['warnings'])
          == any(p['missing'] for p in pages))
    requested = {p['family'] for p in pages}
    check('only-used-requests', {f['requestedFamily'] for f in report['fonts']} == requested)
    check('screen-resolver-consistency', report['fonts'] == screen_report['fonts'])
    identity = lambda use: tuple(use.get(k) for k in ['pageNumber', 'anchorId', 'fragmentId', 'textDigest', 'textCodePointCount'])
    for medium, observed_report in [('print', report), ('screen', screen_report)]:
        uses = observed_report.get('fontObservation', {}).get('uses', [])
        medium_map = page_map if medium == 'print' else screen_map
        map_digest = hashlib.sha256(json.dumps(medium_map, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        check(f'{medium}-page-map-binding', observed_report['bindings']['pageMapDigest'] == map_digest
              and medium_map.get('rendererFingerprint') == observed_report['environment']['rendererFingerprint'])
        check(f'{medium}-missing-warning', any(w['code'] == 'font_unavailable' for w in observed_report['warnings'])
              == any(p['missing'] for p in pages))
        check(f'{medium}-node-metadata', all(type(u.get('pageNumber')) is int
              and type(u.get('textCodePointCount')) is int and 0 < u['textCodePointCount'] <= 9007199254740991
              and isinstance(u.get('textDigest'), str) and re.fullmatch('[0-9a-f]{64}', u['textDigest']) for u in uses))
        check(f'{medium}-complete-text-node-inventory', bool(html_nodes)
              and Counter(map(identity, uses)) == Counter(map(identity, html_nodes)))
    for number, expected in enumerate(pages, 1):
        text = ''.join(w['text'] for w in info['words'] if w['page'] == number)
        # Fallback faces can be emitted in separate PDF text objects with a different extraction
        # order. This diagnostic checks the complete per-page character inventory, not reading order.
        check(f'page-{number}-pdf-text', Counter(compact(text)) == Counter(compact(expected['text'])))
        check(f'page-{number}-html-text', len(html_pages) >= number and html_pages[number - 1]['number'] == number
              and compact(html_pages[number - 1]['text']) == compact(expected['text']))
        fonts = [f for f in report['fonts'] if f['requestedFamily'] == expected['family']]
        check(f'page-{number}-resolver', len(fonts) == 1
              and fonts[0]['status'] == ('missing' if expected['missing'] else 'resolved')
              and fonts[0]['verified'] == (not expected['missing'] and not expected['partial']))
        for medium, observed_report in [('print', report), ('screen', screen_report)]:
            observation = observed_report.get('fontObservation', {})
            check(f'{medium}-observation', observation.get('status') == 'observed'
                  and observation.get('method') == 'chromium-cdp' and observation.get('media') == medium
                  and observation.get('fileIdentity') == 'unavailable')
            uses = [u for u in observation.get('uses', []) if u.get('pageNumber') == number]
            request = fonts[0]['requestId'] if len(fonts) == 1 else None
            check(f'page-{number}-{medium}-request', bool(uses) and all(u.get('requestId') == request for u in uses))
            # The fixture has no generated labels: every observed glyph must belong to this page's one request.
            faces = [f for u in uses for f in u.get('faces', [])]
            actual = sorted(set(f.get('postscriptName', '') for f in faces))
            check(f'page-{number}-{medium}-pdf-faces', bool(actual) and actual == page_fonts[number - 1])
            check(f'page-{number}-{medium}-face-evidence', bool(faces) and all(
                type(f.get('glyphCount')) is int and 0 < f['glyphCount'] <= 9007199254740991
                and type(f.get('isCustomFont')) is bool and isinstance(f.get('family'), str)
                and re.fullmatch(r'[^\x00-\x1f\x7f]{1,2048}', f['family'])
                and set(f) == {'family', 'postscriptName', 'isCustomFont', 'glyphCount'} for f in faces))
            if expected['partial']:
                check(f'page-{number}-{medium}-mixed-fallback', len(actual) >= 2
                      and any(f.get('isCustomFont') is True for f in faces)
                      and any(f.get('isCustomFont') is False for f in faces))
            medium_map = page_map if medium == 'print' else screen_map
            fragments = {(f['pageNumber'], f['anchorId'], f['fragmentId']) for f in medium_map['fragments']}
            check(f'page-{number}-{medium}-source-location', bool(uses) and all(
                (u.get('pageNumber'), u.get('anchorId'), u.get('fragmentId')) in fragments for u in uses))
            material = json.dumps(observation, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
            bound = hashlib.sha256(('docxodus:font-observation:v1\0' + material).encode()).hexdigest()
            check(f'{medium}-observation-digest', observed_report.get('fontObservationDigest') == bound)
    declaration = {'requiredTokens': dict(Counter(w['text'] for w in info['words'])),
                   'exactInventory': True, 'pageSizePt': [612, 792]}
    result += pdf.companion_checks(declaration, info)
    return result


def run(source, commit, output, validator):
    registry = font_fixtures.validate()
    source, output = Path(source).resolve(), Path(output).resolve()
    production = verify_source(source, commit)
    validation = verify_validator(validator)
    if output.exists():
        raise ValueError('Font diagnostic output already exists')
    output.mkdir(parents=True)
    shutil.copyfile(source / '.docx-bench-build.json', output / 'production-build.json')
    shutil.copyfile(source / 'npm/dist/export-assets.json', output / 'export-assets.json')
    font_directory = Path(os.environ.get('BENCH_FONT_DIRECTORY', '/usr/share/fonts/truetype/liberation2')).resolve()
    font_files = {str(p): digest(p) for p in sorted(font_directory.glob('*.ttf'))}
    if not font_files:
        raise ValueError('Separately provisioned Liberation font files are required')
    tools = {}
    for name in ['pdffonts', 'pdftotext', 'pdftoppm', 'qpdf']:
        version = subprocess.run([name, '--version' if name == 'qpdf' else '-v'], capture_output=True,
                                 text=True, check=True, timeout=10)
        tools[name] = {'sha256': digest(Path(shutil.which(name))),
                       'version': (version.stdout + version.stderr).splitlines()[0]}
    build = {'schema': 1, 'commit': commit, 'tree': production['tree'],
             'productionBuildSha256': digest(source / '.docx-bench-build.json'), 'validator': validation,
             'exportAssetsSha256': digest(output / 'export-assets.json'),
             'sources': {n: digest(ROOT / n) for n in SOURCES}, 'fontFiles': font_files, 'tools': tools,
             'systemFontCatalogSha256': hashlib.sha256('\n'.join(sorted(execute(['fc-list']).splitlines())).encode()).hexdigest(),
             'manifestSha256': digest(ROOT / 'fixtures/fonts/manifest.json')}
    write_json(output / 'build.json', build)
    findings = validate_packages(validator, [ROOT / c['input'] for c in registry['cases']])
    if any(findings.values()):
        raise ValueError('Font input has Open XML schema findings')
    write_json(output / 'input-validation.json', findings)
    build['inputValidationSha256'] = digest(output / 'input-validation.json')
    write_json(output / 'build.json', build)
    subprocess.run(['node', str(ROOT / 'adapters/font-diagnostic.mjs'), str(source),
                    str(ROOT / 'fixtures/fonts/manifest.json'), str(output)], check=True, timeout=1800)
    observed = read_json(output / 'observations.json')
    if observed['suite'] != registry['suite'] or [c['id'] for c in observed['cases']] != [c['id'] for c in registry['cases']]:
        raise ValueError('Incomplete font observation envelope')
    results = []
    for case, record in zip(registry['cases'], observed['cases']):
        folder = output / case['id']
        if record['inputSha256'] != case['sha256']:
            raise ValueError('Observation source changed')
        item = {'id': case['id'], 'control': case['control'], 'status': record['status'], 'checks': [], 'passed': False}
        if record['status'] == 'observed':
            for name, value in record['artifacts'].items():
                if digest(folder / name) != value:
                    raise ValueError('Observed artifact changed: ' + name)
            report = read_json(folder / 'report.json')
            screen = read_json(folder / 'screen-report.json')
            info = pdf.inspect_pdf(folder / 'candidate.pdf')
            declaration = {'requiredTokens': dict(Counter(w['text'] for w in info['words']))}
            info = pdf.inspect_companion_pdf(folder / 'candidate.pdf', declaration)
            faces = [pdf_font_names(execute(['pdffonts', '-f', str(n), '-l', str(n), folder / 'candidate.pdf']))
                     for n in range(1, len(case['pages']) + 1)]
            write_json(folder / 'pdf-facts.json', {'pages': info, 'fontNamesByPage': faces})
            subprocess.run(['pdftoppm', '-png', '-scale-to', '1100', str(folder / 'candidate.pdf'), str(folder / 'page')],
                           check=True, capture_output=True, timeout=60)
            item['checks'] = checks(case, report, screen, read_json(folder / 'page-map.json'), record['htmlPages'], info, faces,
                                    record['htmlTextNodes'], read_json(folder / 'screen-page-map.json'))
            item['checks'].append({'name': 'artifact-bindings', 'passed': report['bindings']['pdfDigest'] == digest(folder / 'candidate.pdf')
                                   and report['bindings']['htmlDigest'] == digest(folder / 'candidate.html')
                                   and screen['bindings']['htmlDigest'] == digest(folder / 'screen.html')
                                   and report['bindings']['pageMapDigest'] == digest(folder / 'page-map.json')
                                   and screen['bindings']['pageMapDigest'] == digest(folder / 'screen-page-map.json')})
            item['passed'] = all(c['passed'] for c in item['checks'])
        results.append(item)
    verify_source(source, commit)
    if (digest(source / '.docx-bench-build.json') != build['productionBuildSha256']
            or digest(output / 'production-build.json') != build['productionBuildSha256']
            or digest(source / 'npm/dist/export-assets.json') != build['exportAssetsSha256']
            or digest(output / 'export-assets.json') != build['exportAssetsSha256']):
        raise ValueError('Production runtime build record changed during observation')
    if font_fixtures.validate() != registry or build['sources'] != {n: digest(ROOT / n) for n in SOURCES}:
        raise ValueError('Diagnostic sources changed during observation')
    if any(digest(Path(p)) != value for p, value in font_files.items()):
        raise ValueError('Configured font files changed during observation')
    summary = {'required': len(results), 'observed': sum(c['status'] == 'observed' for c in results),
               'passed': sum(c['passed'] for c in results)}
    result = {'schema': 1, 'suite': registry['suite'], 'scope': registry['scope'], 'commit': commit,
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
