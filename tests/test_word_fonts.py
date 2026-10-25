import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from bench import pdf, word_fonts


class WordFontIdentityBindings(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / 'source.docx'
        self.local = b'original source font'
        self.program = b'captured native subset program'
        self.alias = '___WordFontAlias'
        self.family = 'Liberation Serif'
        self.write_source()
        self.info = {'fonts': [self.alias]}
        self.contract = {'source.ttf': {'family': self.family, 'sha256': self.hash(self.local)}}
        self.binding = {'pdfFontName': self.alias, 'family': self.family,
                        'sourceFontPart': 'word/fonts/source.ttf', 'sourceFontSha256': self.hash(self.local),
                        'embeddedProgramSha256': self.hash(self.program), 'glyphAuditSha256': 'a' * 64,
                        'reviewedGlyphIdentity': True}
        self.objects = {'obj:5 0 R': {'value': {'/Type': '/Font', '/Subtype': '/TrueType',
                        '/BaseFont': '/ABCDEF+' + self.alias, '/FontDescriptor': '6 0 R'}},
                        'obj:6 0 R': {'value': {'/FontFile2': '7 0 R'}},
                        'obj:7 0 R': {'stream': {'dict': {'/Length': len(self.program)}}}}

    @staticmethod
    def hash(value):
        return hashlib.sha256(value).hexdigest()

    def write_source(self, external=False, local=None):
        w = word_fonts.W[1:-1]
        r = word_fonts.R[1:-1]
        mode = ' TargetMode="External"' if external else ''
        with ZipFile(self.source, 'w') as package:
            package.writestr('word/fontTable.xml', f'<w:fonts xmlns:w="{w}" xmlns:r="{r}"><w:font w:name="{self.family}"><w:embedRegular r:id="rFont"/></w:font></w:fonts>')
            package.writestr('word/_rels/fontTable.xml.rels', f'<Relationships><Relationship Id="rFont" Type="{r}/font" Target="fonts/source.ttf"{mode}/></Relationships>')
            package.writestr('word/fonts/source.ttf', self.local if local is None else local)

    def qualify(self, bindings=None, program=None, contract=None, objects=None):
        payload = json.dumps({'qpdf': [{'jsonversion': 2}, self.objects if objects is None else objects]}).encode()
        responses = [SimpleNamespace(stdout=payload), SimpleNamespace(stdout=self.program if program is None else program)]
        with patch.object(word_fonts.subprocess, 'run', side_effect=responses) as process:
            result = word_fonts.qualify('native.pdf', self.source, self.info,
                                        [self.binding] if bindings is None else bindings,
                                        self.contract if contract is None else contract, [self.family])
        self.assertEqual(process.call_args_list[-1].args[0], ['qpdf', '--show-object=7,0', '--filtered-stream-data', 'native.pdf'])
        return result

    def test_raw_alias_is_ineligible_until_its_exact_program_binding_is_verified(self):
        self.assertFalse(pdf.font_check(self.info, [self.family]))
        actual = self.qualify()
        self.assertTrue(pdf.font_check(actual, [self.family]))
        self.assertEqual(actual['fonts'], [self.alias])
        self.assertNotIn('verifiedWordFontBindings', self.info)
        self.assertEqual(actual['verifiedWordFontBindings'][self.alias]['embeddedProgramSha256'], self.hash(self.program))

    def test_changed_native_program_fails_even_when_alias_name_matches(self):
        with self.assertRaisesRegex(ValueError, 'actual PDF font program'):
            self.qualify(program=b'different font program')

    def test_changed_source_font_fails(self):
        self.write_source(local=b'different embedded font')
        with self.assertRaisesRegex(ValueError, 'source embedding'):
            self.qualify()

    def test_changed_local_font_contract_fails(self):
        contract = copy.deepcopy(self.contract)
        contract['source.ttf']['sha256'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'local font contract'):
            self.qualify(contract=contract)

    def test_unreviewed_glyph_identity_does_not_authorize_an_alias(self):
        self.binding['reviewedGlyphIdentity'] = False
        with self.assertRaisesRegex(ValueError, 'unreviewed'):
            self.qualify()

    def test_family_binding_cannot_change_the_declared_family(self):
        self.binding['family'] = 'Arial'
        with self.assertRaisesRegex(ValueError, 'Invalid'):
            self.qualify()

    def test_a_duplicate_alias_cannot_supply_two_identities(self):
        with self.assertRaisesRegex(ValueError, 'Invalid'):
            self.qualify(bindings=[self.binding, dict(self.binding)])

    def test_an_alias_absent_from_the_actual_pdf_is_rejected(self):
        self.binding['pdfFontName'] = 'UnknownAlias'
        with self.assertRaisesRegex(ValueError, 'Invalid'):
            self.qualify()

    def test_missing_pdf_font_program_fails(self):
        objects = copy.deepcopy(self.objects)
        objects['obj:6 0 R']['value'].clear()
        with self.assertRaisesRegex(ValueError, 'embedded TrueType'):
            self.qualify(objects=objects)

    def test_a_font_program_must_be_an_actual_pdf_stream(self):
        objects = copy.deepcopy(self.objects)
        objects['obj:7 0 R'] = {'value': {}}
        with self.assertRaisesRegex(ValueError, 'not a PDF stream'):
            self.qualify(objects=objects)

    def test_external_font_embedding_target_is_rejected(self):
        self.write_source(external=True)
        with self.assertRaisesRegex(ValueError, 'External'):
            self.qualify()

    def test_missing_audit_digest_is_rejected(self):
        self.binding['glyphAuditSha256'] = ''
        with self.assertRaisesRegex(ValueError, 'Invalid'):
            self.qualify()
