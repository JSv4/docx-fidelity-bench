from __future__ import annotations
import hashlib
import json
import os
import subprocess
import re
import math
import xml.etree.ElementTree as ET
from zipfile import ZipFile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Word reference tracks. `word` is the provider-neutral track; a capture that names no specific route uses it.
WORD_TRACKS = frozenset({'word', 'word-online', 'word-onedrive', 'word-desktop'})
# The only bytes an authored package may hold at an embedded-font relationship's target: a
# placeholder that is visibly not a font program, for cases about the package shape itself.
PLACEHOLDER_FONT_BYTES = b'Placeholder bytes for an embedded-font package part; this is not a font program.\n'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def read_json(path):
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError('Duplicate JSON key: ' + key)
            obj[key] = value
        return obj
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs, parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON value: ' + value)))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def execute(args, timeout=120, input=None):
    result = subprocess.run([str(a) for a in args], input=input, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(f'{Path(str(args[0])).name} exited {result.returncode}: {result.stderr[-4000:]}')
    return result.stdout


def contained(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError('Path escapes registry root: ' + str(relative))
    return path


def validate_pdf_companion(declaration):
    if (not isinstance(declaration, dict) or set(declaration) - {'profile', 'requiredTokens', 'pageSizePt', 'exactInventory'} or
            not {'profile', 'requiredTokens', 'pageSizePt'}.issubset(declaration) or
            ('exactInventory' in declaration and declaration['exactInventory'] is not True) or
            not isinstance(declaration['pageSizePt'], list) or len(declaration['pageSizePt']) != 2 or
            any(type(n) not in (int, float) or not math.isfinite(n) or n <= 0 for n in declaration['pageSizePt']) or
            not isinstance(declaration['requiredTokens'], dict) or not declaration['requiredTokens'] or
            any(not isinstance(word, str) or len(word.split()) != 1 or word.strip() != word or
                type(count) is not int or count < 1 for word, count in declaration['requiredTokens'].items())):
        raise ValueError('Invalid companion PDF declaration')
    validate_render_profile(declaration['profile'])


def validate_pdf_text_policy(case, root=None):
    root = ROOT if root is None else root
    if 'pdfTextNormalization' not in case:
        return
    if case['pdfTextNormalization'] != 'isolated-dot-leaders-v1':
        raise ValueError('Unknown PDF text normalization policy')
    w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    has_dot_tab = False
    has_tab_character = False
    with ZipFile(contained(root, case['input'])) as archive:
        for name in archive.namelist():
            if not name.startswith('word/') or not name.endswith('.xml'):
                continue
            xml = ET.fromstring(archive.read(name))
            if any('...' in (node.text or '') for node in xml.iter()):
                raise ValueError('Decorative dot policy cannot suppress authored ellipses')
            has_dot_tab |= any(node.get(w + 'leader') == 'dot' for node in xml.iter(w + 'tab'))
            has_tab_character |= any(run.find(w + 'tab') is not None or any(
                node.tag in {w + 't', w + 'delText'} and '\t' in (node.text or '') for node in run)
                for run in xml.iter(w + 'r'))
    if not has_dot_tab or not has_tab_character:
        raise ValueError('Decorative dot policy requires an authored dot-leader tab')


def validate_render_profile(profile, *, allow_additional_css=False):
    allowed = {'review', 'comments', 'markupPresentation'}
    if allow_additional_css: allowed.add('additionalCss')
    if (not isinstance(profile, dict) or not {'review', 'comments'}.issubset(profile) or
            set(profile) - allowed or
            not isinstance(profile.get('review'), str) or profile['review'] not in {'final', 'original', 'markup'} or
            not isinstance(profile.get('comments'), str) or profile['comments'] not in {'hidden', 'inline', 'margin', 'endnotes'} or
            ('markupPresentation' in profile and (not isinstance(profile['markupPresentation'], str) or profile['markupPresentation'] not in {'html', 'word'}))):
        raise ValueError('Invalid declared artifact profile')
    if 'additionalCss' in profile:
        css = profile['additionalCss']
        if not isinstance(css, str) or not css:
            raise ValueError('HTML stylesheet must be nonempty text')
        try: css.encode('utf-8', errors='strict')
        except UnicodeError as error: raise ValueError('Malformed Unicode HTML stylesheet') from error
    return profile


def validate_registry(registry=None):
    registry = read_json(ROOT / 'fixtures/manifest.json') if registry is None else registry
    if registry.get('schema') != 1 or not isinstance(registry['suite'].get('version'), int) or registry['suite']['version'] < 1:
        raise ValueError('Unknown registry or suite version')
    ids = [c['id'] for c in registry['cases']]
    if len(set(ids)) != len(ids) or len(set(registry['suite']['cases'])) != len(registry['suite']['cases']) or set(ids) != set(registry['suite']['cases']):
        raise ValueError('Duplicate or missing suite member')
    for case in registry['cases']:
        if not re.fullmatch('[a-z][a-z0-9-]{0,79}', case['id']) or not isinstance(case['version'], int) or case['version'] < 1 or case['rights']['license'] != 'MIT' or not case['rights']['author'] or not case['rights']['origin']:
            raise ValueError('Invalid case version or rights record')
        if digest(contained(ROOT, case['input'])) != case['sha256']:
            raise ValueError('Stale input digest: ' + case['id'])
        if digest(contained(ROOT, case['generator']['path'])) != case['generator']['sha256']:
            raise ValueError('Stale generator digest: ' + case['id'])
        if 'preparation' in case:
            preparation = case['preparation']
            if (not isinstance(preparation, dict) or set(preparation) != {'operation', 'inputs'} or preparation['operation'] not in {'build', 'compare', 'consolidate'} or
                    not isinstance(preparation['inputs'], list) or len(preparation['inputs']) < 2 or
                    (preparation['operation'] == 'compare' and len(preparation['inputs']) != 2)):
                raise ValueError('Invalid document preparation')
            for source in preparation['inputs']:
                if not isinstance(source, dict) or set(source) != {'path', 'sha256'} or digest(contained(ROOT, source['path'])) != source['sha256']:
                    raise ValueError('Stale preparation source digest')
        if not case['tokens'] or any(not isinstance(n, int) or n < 1 for n in case['tokens'].values()):
            raise ValueError('Invalid token inventory')
        if 'clippedTokens' in case:
            optional = case['clippedTokens']
            if (not isinstance(optional, dict) or not optional or set(optional) & set(case['tokens']) or
                    any(not isinstance(word, str) or len(word.split()) != 1 or type(count) is not int or count < 1
                        for word, count in optional.items())):
                raise ValueError('Invalid clipped token inventory')
            from collections import Counter
            w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
            all_words, row_words = Counter(), Counter()
            with ZipFile(contained(ROOT, case['input'])) as archive:
                from .source_clipping import textbox_clipped_words
                row_words.update(textbox_clipped_words(archive))
                for name in archive.namelist():
                    if not name.startswith('word/') or not name.endswith('.xml'): continue
                    xml = ET.fromstring(archive.read(name))
                    all_words.update(' '.join(t.text or '' for t in xml.iter(w + 't')).split())
                    for row in xml.iter(w + 'tr'):
                        height = row.find(w + 'trPr/' + w + 'trHeight')
                        if height is not None and height.get(w + 'hRule') == 'exact':
                            for cell in row.findall(w + 'tc'):
                                offset = 0
                                for paragraph in cell.findall(w + 'p'):
                                    spacing = paragraph.find(w + 'pPr/' + w + 'spacing')
                                    if (spacing is None or spacing.get(w + 'lineRule') != 'exact' or
                                            not spacing.get(w + 'line', '').isdigit() or
                                            spacing.get(w + 'before') != '0' or spacing.get(w + 'after') != '0'):
                                        break
                                    if offset >= int(height.get(w + 'val', '0')):
                                        row_words.update(' '.join(t.text or '' for t in paragraph.iter(w + 't')).split())
                                    offset += int(spacing.get(w + 'line'))
            if any(all_words[word] != count or row_words[word] != count for word, count in optional.items()):
                raise ValueError('Clipped tokens must occur only outside a proven exact row or fixed textbox clip, with authored exact line spacing and counts')
        validate_render_profile(case['profile'])
        if 'pdfCompanion' in case:
            validate_pdf_companion(case['pdfCompanion'])
            with ZipFile(contained(ROOT, case['input'])) as archive:
                w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
                sizes = [p.find(w + 'pgSz') for p in ET.fromstring(archive.read('word/document.xml')).iter(w + 'sectPr')]
                if not sizes or any(p is None or [int(p.get(w + key, '0')) / 20 for key in ('w', 'h')] !=
                                    case['pdfCompanion']['pageSizePt'] for p in sizes):
                    raise ValueError('Companion paper dimensions must match every authored section')
        validate_pdf_text_policy(case)
        if not isinstance(case.get('htmlAssertions', []), list):
            raise ValueError('Delivered HTML assertions must be a list')
        from .html_artifacts import validate_declaration
        for assertion in case.get('htmlAssertions', []):
            validate_declaration(assertion)
        if 'htmlProfile' in case:
            validate_render_profile(case['htmlProfile'], allow_additional_css=True)
            if not case.get('htmlAssertions'):
                raise ValueError('An HTML profile override requires declared HTML checks')
        for assertion in case['assertions']:
            versions = {'marker-region': {1, 2}, 'same-page': {1}, 'marker-reference-position': {1}, 'color-reference-geometry': {1}, 'color-geometry': {1}}
            if assertion.get('version') not in versions.get(assertion.get('type'), set()):
                raise ValueError('Unknown assertion type or version')
            if assertion['type'] in ('color-reference-geometry', 'color-geometry'):
                absolute = assertion['type'] == 'color-geometry'
                keys = {'type', 'version', 'page', 'rgb', 'tolerancePt', 'coverageTolerance'}
                if absolute: keys |= {'boundsPt', 'coverage', 'adjudicated'}
                if (set(assertion) != keys or
                        type(assertion['page']) is not int or assertion['page'] < 1 or
                        not isinstance(assertion['rgb'], list) or len(assertion['rgb']) != 3 or
                        any(type(c) is not int or not 0 <= c < 255 for c in assertion['rgb']) or
                        len(set(assertion['rgb'])) < 2 or
                        any(type(assertion[k]) not in (int, float) or not math.isfinite(assertion[k]) for k in ('tolerancePt', 'coverageTolerance')) or
                        not 0 <= assertion['tolerancePt'] <= 2 or not 0 <= assertion['coverageTolerance'] <= 0.1):
                    raise ValueError('Invalid color geometry declaration')
                if absolute:
                    bounds, coverage = assertion['boundsPt'], assertion['coverage']
                    if (not isinstance(bounds, list) or len(bounds) != 4 or
                            any(type(v) not in (int, float) or not math.isfinite(v) for v in bounds) or
                            bounds[0] < 0 or bounds[1] < 0 or bounds[2] <= bounds[0] or bounds[3] <= bounds[1] or
                            type(coverage) not in (int, float) or not math.isfinite(coverage) or coverage <= 0):
                        raise ValueError('Invalid absolute color geometry')
            if assertion.get('adjudicated', 'word') != 'word':
                raise ValueError('Unknown assertion adjudication')
            if 'adjudicated' in assertion and (assertion['type'] == 'marker-reference-position' or assertion.get('page') == 'reference'):
                raise ValueError('A Word-adjudicated assertion cannot be relative to the reference')
            if assertion['type'] == 'marker-reference-position' or (assertion['type'] == 'marker-region' and assertion['version'] == 2):
                tolerance = assertion.get('tolerancePt')
                if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or not math.isfinite(tolerance) or tolerance < 0 or not isinstance(assertion.get('marker'), str):
                    raise ValueError('Invalid marker tolerance declaration')
    return registry
