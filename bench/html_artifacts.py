"""Read delivered HTML attributes independently of renderer diagnostics.

These feature checks accompany PDF evidence; they do not change the PDF raster score.
"""
from html.parser import HTMLParser
import re
from .common import digest

VERSION = 1


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


def inspect(folder, response, declarations):
    record = response.get('htmlArtifact')
    if not isinstance(record, dict) or record.get('status') != 'ok':
        return {'status': 'unmeasured', 'error': record.get('error', 'Renderer did not deliver requested HTML')
                if isinstance(record, dict) else 'Renderer did not deliver requested HTML'}
    path = folder / 'candidate.html'
    if not path.is_file() or digest(path) != record.get('sha256'):
        return {'status': 'unmeasured', 'error': 'Delivered HTML is missing or its digest differs'}
    try:
        checks = check(path.read_text(encoding='utf-8'), declarations)
    except (UnicodeError, ValueError) as error:
        checks = [{'name': f'html-attribute-{i + 1}', 'marker': d['marker'], 'attribute': d['attribute'],
                   'expected': d['equals'], 'actual': None, 'passed': False, 'error': str(error)}
                  for i, d in enumerate(declarations)]
    return {'status': 'measured', 'sha256': record['sha256'], 'checks': checks}


def aggregate(cases, declarations):
    by_id = {case['id']: case for case in cases}
    measured = passed = 0
    for cid, required in declarations.items():
        value = by_id.get(cid, {}).get('html', {})
        if value.get('status') == 'measured':
            checks = value.get('checks', [])
            if not isinstance(checks, list) or len(checks) != len(required) or any(
                    not isinstance(c, dict) or c.get('name') != f'html-attribute-{i + 1}' or
                    not isinstance(c.get('passed'), bool) or c.get('marker') != required[i]['marker'] or
                    c.get('attribute') != required[i]['attribute'] or c.get('expected') != required[i]['equals'] or
                    c['passed'] != (c.get('actual') == required[i]['equals']) for i, c in enumerate(checks)):
                raise ValueError('Invalid delivered HTML check coverage')
            measured += 1
            passed += all(c['passed'] for c in checks)
    return {'required': len(declarations), 'measured': measured, 'passed': passed,
            'complete': measured == len(declarations)}
