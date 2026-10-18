"""Read delivered HTML attributes independently of renderer diagnostics.

These feature checks accompany PDF evidence; they do not change the PDF raster score.
"""
from html.parser import HTMLParser
import re
import json
import math
from pathlib import Path
from .common import digest

VERSION = 1

BROWSER_VERSION = 1
BROWSER_SOURCE = Path(__file__).with_name('html_browser.mjs')
BROWSER_POLICY = {'viewport': {'width': 1280, 'height': 1024}, 'javaScriptEnabled': False,
                  'offline': True, 'media': 'screen'}


def needs_browser(declarations):
    return any(d['type'] == 'marker-readable' for d in declarations)


def validate_declaration(declaration):
    if (not isinstance(declaration, dict) or type(declaration.get('version')) is not int or
            declaration['version'] != 1 or not isinstance(declaration.get('marker'), str) or not declaration['marker']):
        raise ValueError('Unknown or invalid delivered HTML assertion')
    if declaration.get('type') == 'marker-attribute':
        if set(declaration) != {'type', 'version', 'marker', 'attribute', 'equals'} or any(
                not isinstance(declaration[k], str) or not declaration[k] for k in ('attribute', 'equals')):
            raise ValueError('Unknown or invalid delivered HTML assertion')
    elif declaration.get('type') == 'marker-readable':
        tokens = declaration.get('tokens')
        if (set(declaration) != {'type', 'version', 'marker', 'tokens'} or not isinstance(tokens, list) or not tokens or
                any(not isinstance(t, str) or not t or re.search(r'\s', t) for t in tokens) or tokens[-1] != declaration['marker']):
            raise ValueError('Unknown or invalid readable HTML assertion')
    else:
        raise ValueError('Unknown or invalid delivered HTML assertion')


def valid_rectangle(value):
    return isinstance(value, list) and len(value) == 4 and all(
        type(n) in (int, float) and math.isfinite(n) for n in value) and value[2] >= value[0] and value[3] >= value[1]


def within(rectangle, clip, axis):
    return rectangle[axis] >= clip[axis] - 1 and rectangle[axis + 2] <= clip[axis + 2] + 1


def readable_pass(declaration, observation, index):
    if (not isinstance(observation, dict) or type(observation.get('index')) is not int or observation.get('index') != index or
            observation.get('marker') != declaration['marker'] or type(observation.get('matches')) is not int or
            observation['matches'] < 0 or not isinstance(observation.get('text'), str) or not isinstance(observation.get('ports'), list)):
        raise ValueError('Malformed browser HTML observation')
    actual_matches = len(list(re.finditer(r'(?<!\w)' + re.escape(declaration['marker']) + r'(?!\w)', observation['text'])))
    if actual_matches != observation['matches']:
        raise ValueError('Inconsistent HTML marker inventory')
    if observation['matches'] != 1:
        return False
    if not isinstance(observation.get('blockText'), str):
        raise ValueError('Missing readable paragraph text')
    if not all(valid_rectangle(observation.get(k)) for k in ('before', 'after', 'viewport')):
        raise ValueError('Malformed readable marker geometry')
    after = observation['after']
    passed = (observation['blockText'] == ' '.join(declaration['tokens']) and
              after[2] > after[0] and after[3] > after[1] and
              observation['viewport'][2] > observation['viewport'][0] and observation['viewport'][3] > observation['viewport'][1] and
              all(within(after, observation['viewport'], axis) for axis in (0, 1)))
    for port in observation['ports']:
        if (not isinstance(port, dict) or not all(valid_rectangle(port.get(k)) for k in ('before', 'clipBefore', 'clipAfter')) or
                any(port.get(k) not in {'auto', 'scroll', 'hidden', 'clip', 'visible'} for k in ('overflowX', 'overflowY')) or
                any(type(port.get(k)) not in (int, float) or not math.isfinite(port[k]) or port[k] < 0 for k in ('scrollHeight', 'clientHeight'))):
            raise ValueError('Malformed readable scrollport geometry')
        for axis, name in [(0, 'overflowX'), (1, 'overflowY')]:
            if port[name] in {'hidden', 'clip'} and not within(port['before'], port['clipBefore'], axis):
                passed = False
            if port[name] != 'visible' and (port['clipAfter'][axis + 2] <= port['clipAfter'][axis] or not within(after, port['clipAfter'], axis)):
                passed = False
    return passed


def browser_metadata_valid(value, html_sha, inspector_sha, runtime):
    return (isinstance(value, dict) and isinstance(runtime, dict) and
            isinstance(html_sha, str) and re.fullmatch('[a-f0-9]{64}', html_sha) is not None and
            isinstance(inspector_sha, str) and re.fullmatch('[a-f0-9]{64}', inspector_sha) is not None and type(value.get('schema')) is int and value['schema'] == BROWSER_VERSION and
            value.get('htmlSha256') == html_sha and value.get('inspectorSha256') == inspector_sha and
            value.get('policy') == BROWSER_POLICY and isinstance(value.get('executableSha256'), str) and
            re.fullmatch('[a-f0-9]{64}', value['executableSha256']) is not None and
            value['executableSha256'] == runtime.get('executableSha256'))


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.chunks = []
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        attributes = {}
        for name, value in attrs:
            attributes.setdefault(name, value)
        node = {'tag': tag, 'attrs': attributes}
        if tag == 'br':
            self.handle_data('\n')
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack and self.stack[-1]['tag'] == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        if tag in {'p', 'div', 'section', 'li', 'tr', 'td', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}:
            self.handle_data('\n')
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]['tag'] == tag:
                del self.stack[i:]
                break

    def handle_data(self, value):
        if not any(n['tag'] in {'head', 'script', 'style', 'template'} or 'hidden' in n['attrs'] for n in self.stack):
            self.chunks.append((value, tuple(self.stack)))


def check(source, declarations):
    document = Document(source)
    text = ''.join(value for value, _ in document.chunks)
    results = []
    for index, declaration in enumerate(declarations):
        if declaration['type'] != 'marker-attribute': continue
        marker = declaration['marker']
        matches = list(re.finditer(r'(?<!\w)' + re.escape(marker) + r'(?!\w)', text))
        actual = None
        if len(matches) == 1:
            start, end = matches[0].span()
            values, offset = [], 0
            for value, ancestors in document.chunks:
                if offset < end and offset + len(value) > start:
                    nearest = next((n['attrs'][declaration['attribute']] for n in reversed(ancestors)
                                    if declaration['attribute'] in n['attrs']), None)
                    values.append(nearest)
                offset += len(value)
            if values and all(value == values[0] for value in values):
                actual = values[0]
        results.append({'name': f'html-attribute-{index + 1}', 'marker': marker,
                        'attribute': declaration['attribute'], 'expected': declaration['equals'],
                        'actual': actual, 'passed': actual == declaration['equals']})
    return results


def inspect(folder, response, declarations, profile=None):
    record = response.get('htmlArtifact') if isinstance(response, dict) else None
    if not isinstance(record, dict) or record.get('status') != 'ok':
        return {'status': 'unmeasured', 'error': record.get('error', 'Renderer did not deliver requested HTML')
                if isinstance(record, dict) else 'Renderer did not deliver requested HTML'}
    path = folder / 'candidate.html'
    if not path.is_file() or digest(path) != record.get('sha256'):
        return {'status': 'unmeasured', 'error': 'Delivered HTML is missing or its digest differs'}
    if profile is not None and record.get('profile') != profile:
        return {'status': 'unmeasured', 'error': 'Delivered HTML profile differs from its declaration'}
    result = {'status': 'measured', 'sha256': record['sha256']}
    if profile is not None: result['profile'] = profile
    try:
        for declaration in declarations: validate_declaration(declaration)
        checks = check(path.read_text(encoding='utf-8'), declarations)
        if needs_browser(declarations):
            browser_path = folder / 'html-browser.json'
            if not browser_path.is_file() or digest(browser_path) != record.get('browserFactsSha256'):
                raise ValueError('Delivered HTML browser observations are missing or their digest differs')
            browser = json.loads(browser_path.read_text(encoding='utf-8'))
            renderer = response.get('renderer')
            runtime = renderer.get('runtime', {}) if isinstance(renderer, dict) else {}
            if not browser_metadata_valid(browser, record['sha256'], digest(BROWSER_SOURCE), runtime):
                raise ValueError('HTML browser observation identity differs')
            observations = browser.get('observations')
            indexes = [i for i, d in enumerate(declarations) if d['type'] == 'marker-readable']
            if (not isinstance(observations, list) or len(observations) != len(indexes) or
                    [o.get('index') if isinstance(o, dict) else None for o in observations] != indexes):
                raise ValueError('HTML browser observations do not cover the declarations')
            result['browser'] = {k: v for k, v in browser.items() if k != 'observations'}
            for index, observation in zip(indexes, observations):
                declaration = declarations[index]
                checks.append({'name': f'html-readable-{index + 1}', 'marker': declaration['marker'],
                               'tokens': declaration['tokens'], 'observation': observation,
                               'passed': readable_pass(declaration, observation, index)})
        result['checks'] = sorted(checks, key=lambda c: int(c['name'].rsplit('-', 1)[1]))
    except (UnicodeError, ValueError, TypeError) as error:
        return {'status': 'unmeasured', 'error': str(error)}
    return result


def aggregate(cases, declarations, browser_sha=None, profiles=None):
    by_id = {case['id']: case for case in cases}
    profiles = profiles or {}
    measured = passed = 0
    for cid, required in declarations.items():
        for declaration in required: validate_declaration(declaration)
        case = by_id.get(cid, {})
        value = case.get('html', {})
        if not isinstance(value, dict):
            raise ValueError('Invalid delivered HTML measurement')
        if value.get('status') == 'measured':
            if cid in profiles and value.get('profile') != profiles[cid]:
                raise ValueError('Invalid delivered HTML profile coverage')
            if needs_browser(required):
                adapter = case.get('adapter')
                renderer = adapter.get('renderer') if isinstance(adapter, dict) else {}
                runtime = renderer.get('runtime', {}) if isinstance(renderer, dict) else {}
                if not browser_metadata_valid(value.get('browser'), value.get('sha256'), browser_sha, runtime):
                    raise ValueError('Invalid HTML browser measurement identity')
            checks = value.get('checks', [])
            if not isinstance(checks, list) or len(checks) != len(required):
                raise ValueError('Invalid delivered HTML check coverage')
            for index, (declaration, item) in enumerate(zip(required, checks)):
                if not isinstance(item, dict) or type(item.get('passed')) is not bool or item.get('marker') != declaration['marker']:
                    raise ValueError('Invalid delivered HTML check coverage')
                if declaration['type'] == 'marker-attribute':
                    valid = (item.get('name') == f'html-attribute-{index + 1}' and item.get('attribute') == declaration['attribute'] and
                             item.get('expected') == declaration['equals'] and item['passed'] == (item.get('actual') == declaration['equals']))
                else:
                    valid = (item.get('name') == f'html-readable-{index + 1}' and item.get('tokens') == declaration['tokens'] and
                             item['passed'] == readable_pass(declaration, item.get('observation'), index))
                if not valid: raise ValueError('Invalid delivered HTML check coverage')
            measured += 1
            passed += all(c['passed'] for c in checks)
    return {'required': len(declarations), 'measured': measured, 'passed': passed,
            'complete': measured == len(declarations)}
