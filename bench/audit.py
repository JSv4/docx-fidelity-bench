"""Verify the declared repository inventory and regenerate authored packages."""
from pathlib import Path, PurePosixPath
import re
import tempfile
import xml.etree.ElementTree as ET
from unittest.mock import patch
from zipfile import ZipFile
from . import fixtures, redline, redline_fixtures
from .common import PLACEHOLDER_FONT_BYTES, ROOT, digest, execute, read_json, validate_registry, write_json

RELATIONSHIPS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
FONT_TABLE_PARTS = {'word/fonttable.xml', 'word/_rels/fonttable.xml.rels'}
PNG_START, PNG_END = b'\x89PNG\r\n\x1a\n', b'IEND\xaeB`\x82'
FONT_TYPES = ('application/vnd.openxmlformats-officedocument.obfuscatedfont', 'application/vnd.ms-opentype',
              'application/vnd.ms-fontobject')


ADDRESS = r'[a-z0-9._-]+@example\.com'
MAILTO = re.compile(rf'mailto:{ADDRESS}(?:\s*[;,]\s*{ADDRESS}|\s+{ADDRESS})*')


def reserved_link_target(target):
    """A navigation target on the reserved example.com domain: never loaded, names no real party.

    A `mailto:` lists one or more lower-case example.com addresses separated by one `;` or `,` (with
    optional spaces) or by spaces; an `https://example.com` target is a plain path. Anything else,
    including empty addresses, query strings, ports, upper case and percent-encoding, is refused."""
    if target.startswith('mailto:'):
        return MAILTO.fullmatch(target) is not None
    return re.fullmatch(r'https://example\.com(/[A-Za-z0-9._~/-]*)?', target) is not None


def font_program_type(content_type):
    """A content type for a font program (not the font table that lists fonts), parameters ignored."""
    value = (content_type or '').split(';', 1)[0].strip().lower()
    return value.startswith(('font/', 'application/x-font', 'application/font')) or value in FONT_TYPES


def permitted_bytes(payload):
    """Text (XML or otherwise, UTF-8 with no NUL), a complete PNG, or the font placeholder.

    Every font program, obfuscated or compressed, has NUL bytes in its table directory, so this
    refuses one whatever its name, content type or relationship."""
    if payload == PLACEHOLDER_FONT_BYTES or (payload.startswith(PNG_START) and payload.endswith(PNG_END)):
        return True
    if b'\0' in payload:
        return False
    try:
        payload.decode('utf-8')
    except UnicodeDecodeError:
        return False
    return True


def check_package(archive):
    """Refuse embedded assets and external resources in an authored package.

    Two shapes are permitted because cases about the package itself need them: an external
    hyperlink from the main document to a reserved example.com target, and the font table with an
    embedded-font relationship whose target holds exactly the placeholder bytes. Every font
    relationship, wherever its target and whatever the target's name, must come from the font table
    and reach the placeholder; so must every part a font content type types. Part names,
    relationship types and content types are compared case-insensitively, and every entry's bytes
    must be text, a complete PNG or the placeholder.
    """
    names = archive.namelist()
    by_lower = {}
    for name in names:
        by_lower.setdefault(name.lower(), []).append(name)
    def placeholder(part):
        entries = by_lower.get(part.lower(), [])
        return bool(entries) and all(archive.read(n) == PLACEHOLDER_FONT_BYTES for n in entries)
    font_targets = set()
    for name in sorted(names):
        if not name.lower().endswith('.rels'):
            continue
        source = name.lower()
        folder = PurePosixPath(name).parent.parent
        for relationship in ET.fromstring(archive.read(name)):
            kind = (relationship.get('Type') or '').strip().lower()
            target = relationship.get('Target', '')
            if (relationship.get('TargetMode') or '').strip().lower() == 'external':
                if source != 'word/_rels/document.xml.rels' or kind != RELATIONSHIPS.lower() + 'hyperlink' or not reserved_link_target(target):
                    raise ValueError('External document resource is not permitted')
            elif kind.rsplit('/', 1)[-1] == 'font':
                part = str(folder / target)
                if source != 'word/_rels/fonttable.xml.rels' or not placeholder(part):
                    raise ValueError('Unexpected embedded asset: font relationship to ' + part)
                font_targets.add(part.lower())
    for name in [n for n in names if n.lower() == '[content_types].xml']:
        for item in ET.fromstring(archive.read(name)):
            if not font_program_type(item.get('ContentType')):
                continue
            if item.tag.rsplit('}', 1)[-1] == 'Default':
                typed = [n for n in names if n.lower().endswith('.' + (item.get('Extension') or '').lower())]
            else:
                typed = by_lower.get((item.get('PartName') or '').lstrip('/').lower(), [])
            for part in typed:
                if not placeholder(part):
                    raise ValueError('Unexpected embedded asset: font-typed part ' + part)
    for name in names:
        lower = name.lower()
        if lower.startswith('customxml/'):
            raise ValueError('Unexpected embedded asset: ' + name)
        if 'font' in lower and lower not in FONT_TABLE_PARTS and lower not in font_targets:
            raise ValueError('Unexpected embedded asset: ' + name)
        if not permitted_bytes(archive.read(name)):
            raise ValueError('Unexpected embedded asset: binary entry ' + name)


def audit():
    registry = validate_registry()
    with tempfile.TemporaryDirectory() as temp, patch.object(fixtures, 'ROOT', Path(temp)):
        regenerated = fixtures.generate()
        if registry != regenerated:
            raise ValueError('Manifest is not generated from the declared original corpus source')
        for case in registry['cases']:
            paths = [case['input']] + [s['path'] for s in case.get('preparation', {}).get('inputs', [])]
            for path in paths:
                actual = ROOT / path
                if actual.read_bytes() != (Path(temp) / path).read_bytes():
                    raise ValueError('Fixture differs from its generator: ' + path)
                with ZipFile(actual) as archive:
                    check_package(archive)
    redline_registry = redline.validate_registry()
    with tempfile.TemporaryDirectory() as temp, patch.object(redline_fixtures, 'ROOT', Path(temp)):
        if redline_fixtures.generate() != redline_registry:
            raise ValueError('Redline manifest is not generated from the declared original corpus source')
        for case in redline_registry['cases']:
            for record in redline.artifact_records(case):
                actual = ROOT / record['path']
                if actual.read_bytes() != (Path(temp) / record['path']).read_bytes():
                    raise ValueError('Redline fixture differs from its generator: ' + record['path'])
                with ZipFile(actual) as archive:
                    check_package(archive)
    inventory = read_json(ROOT / 'PROVENANCE.json')
    actual = set()
    for path in ROOT.rglob('*'):
        relative = path.relative_to(ROOT)
        if any(part in {'.git', '__pycache__', '.venv', 'runs', 'references', 'renderer', 'node_modules'} for part in relative.parts) or not path.is_file():
            continue
        if str(relative) == 'PROVENANCE.json':
            continue
        actual.add(str(relative))
    if actual != set(inventory['files']):
        raise ValueError('Repository inventory differs from provenance record: ' + str(sorted(actual ^ set(inventory['files']))))
    if (ROOT / '.git').exists():
        tracked = set(execute(['git', '-C', ROOT, 'ls-files', '-z']).rstrip('\0').split('\0')) - {''}
        if tracked and tracked != actual | {'PROVENANCE.json'}:
            raise ValueError('Tracked inventory includes undeclared or excluded files')
    for name in actual:
        record = inventory['files'][name]
        if record['license'] != 'MIT' or record['author'] != 'John Scrudato IV' or record['sha256'] != digest(ROOT / name):
            raise ValueError('File provenance mismatch: ' + name)
    print(f'Audited {len(actual)} source/artifact files, {len(registry["cases"])} regenerated DOCX inputs and {len(redline_registry["cases"])} regenerated redline cases')


def record():
    files = {}
    for path in sorted(ROOT.rglob('*')):
        relative = path.relative_to(ROOT)
        if any(part in {'.git', '__pycache__', '.venv', 'runs', 'references', 'renderer', 'node_modules'} for part in relative.parts) or not path.is_file() or str(relative) == 'PROVENANCE.json':
            continue
        origin = 'Authored for this repository'
        if relative.parts[0] == 'fixtures':
            origin = 'Generated by bench/redline_fixtures.py' if relative.parts[1] == 'redline' else 'Generated by bench/fixtures.py'
        files[str(relative)] = {'author': 'John Scrudato IV', 'license': 'MIT', 'origin': origin, 'sha256': digest(path)}
    write_json(ROOT / 'PROVENANCE.json', {'schema': 1, 'scope': 'Repository files excluding this self-referential inventory and untracked run/runtime outputs', 'files': files})


if __name__ == '__main__':
    audit()
