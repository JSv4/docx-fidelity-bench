"""Bind operator-reviewed Word font aliases to the exact audited font programs.

This verifies the cryptographic binding, source embedding declaration and local
font contract. The capture operator's glyph audit is an attestation, not a new
font-outline comparison performed by this module. Raw PDF names remain intact.
"""
from __future__ import annotations
import hashlib
import json
import re
import subprocess
from pathlib import PurePosixPath
from zipfile import ZipFile
import xml.etree.ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
DIGEST = re.compile('[a-f0-9]{64}')
FIELDS = {'pdfFontName', 'family', 'sourceFontPart', 'sourceFontSha256',
          'embeddedProgramSha256', 'glyphAuditSha256', 'reviewedGlyphIdentity'}
VERSION = 1


def name(value):
    return value.removeprefix('/').split('+', 1)[-1]


def source_embeddings(source):
    with ZipFile(source) as package:
        fonts = ET.fromstring(package.read('word/fontTable.xml'))
        relationships = ET.fromstring(package.read('word/_rels/fontTable.xml.rels'))
        targets = {}
        for rel in relationships:
            if rel.get('Type') != R[1:-1] + '/font':
                continue
            target = PurePosixPath('word') / rel.get('Target', '')
            if (rel.get('TargetMode') or target.is_absolute() or '..' in target.parts or
                    '%' in str(target) or '#' in str(target)):
                raise ValueError('External or ambiguous embedded font target')
            targets[rel.get('Id')] = str(target)
        result = {}
        for font in fonts:
            family = font.get(W + 'name')
            for embedded in font:
                rid = embedded.get(R + 'id')
                if rid:
                    part = targets.get(rid)
                    if not part:
                        raise ValueError('Missing embedded font relationship')
                    result.setdefault(part, set()).add(family)
        return {part: {'families': families, 'sha256': hashlib.sha256(package.read(part)).hexdigest()}
                for part, families in result.items()}


def font_programs(pdf, requested):
    response = subprocess.run(['qpdf', '--json', '--json-key=qpdf', str(pdf)],
                              capture_output=True, check=True, timeout=30)
    document = json.loads(response.stdout)
    objects = document['qpdf'][1]

    def value(ref):
        if not isinstance(ref, str) or not re.fullmatch(r'\d+ \d+ R', ref):
            raise ValueError('Invalid indirect font object')
        return objects['obj:' + ref]['value']

    found = {}
    for wrapper in objects.values():
        font = wrapper.get('value')
        if not isinstance(font, dict) or font.get('/Type') != '/Font':
            continue
        alias = name(font.get('/BaseFont', ''))
        if alias not in requested:
            continue
        if font.get('/Subtype') == '/Type0':
            descendants = font.get('/DescendantFonts', [])
            if len(descendants) != 1:
                raise ValueError('Ambiguous descendant font')
            font = value(descendants[0])
        descriptor = value(font.get('/FontDescriptor'))
        ref = descriptor.get('/FontFile2')
        if not isinstance(ref, str) or not re.fullmatch(r'\d+ \d+ R', ref):
            raise ValueError('Word font binding requires an embedded TrueType program')
        if 'stream' not in objects['obj:' + ref]:
            raise ValueError('Embedded font program is not a PDF stream')
        obj = ref.removesuffix(' R').replace(' ', ',')
        raw = subprocess.run(['qpdf', '--show-object=' + obj, '--filtered-stream-data', str(pdf)],
                             capture_output=True, check=True, timeout=30).stdout
        found.setdefault(alias, set()).add(hashlib.sha256(raw).hexdigest())
    return found


def qualify(pdf, source, info, records, font_contract, families):
    if not isinstance(records, list) or not records:
        raise ValueError('Explicit nonempty Word font bindings are required')
    if not isinstance(font_contract, dict) or not font_contract:
        raise ValueError('Verified local font contract is required')
    aliases = set()
    embeddings = source_embeddings(source)
    for record in records:
        if (not isinstance(record, dict) or set(record) != FIELDS or
                not isinstance(record['pdfFontName'], str) or not record['pdfFontName'] or
                record['pdfFontName'] != name(record['pdfFontName']) or
                record['pdfFontName'] not in info['fonts'] or record['pdfFontName'] in aliases or
                record['family'] not in families or record['reviewedGlyphIdentity'] is not True or
                any(not isinstance(record[k], str) or not DIGEST.fullmatch(record[k])
                    for k in ('sourceFontSha256', 'embeddedProgramSha256', 'glyphAuditSha256'))):
            raise ValueError('Invalid or unreviewed Word font binding')
        aliases.add(record['pdfFontName'])
        embedded = embeddings.get(record['sourceFontPart'])
        if (not embedded or record['family'] not in embedded['families'] or
                record['sourceFontSha256'] != embedded['sha256'] or
                not any(f.get('family') == record['family'] and f.get('sha256') == record['sourceFontSha256']
                        for f in font_contract.values())):
            raise ValueError('Word font binding does not match the source embedding and local font contract')
    programs = font_programs(pdf, aliases)
    verified = {}
    for record in records:
        if programs.get(record['pdfFontName']) != {record['embeddedProgramSha256']}:
            raise ValueError('Word font binding does not match the actual PDF font program')
        verified[record['pdfFontName']] = dict(record, method='operator-reviewed-glyph-audit-v1')
    return dict(info, verifiedWordFontBindings=verified)
