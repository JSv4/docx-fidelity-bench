import copy
import io
import unittest
from zipfile import ZipFile

from bench import audit, common, fixtures, pdf
from bench.collection_fonts import font
from bench.common import ROOT, read_json


def cases():
    return {c['id']: c for c in read_json(ROOT / 'fixtures/manifest.json')['cases']}


def read(case, part):
    with ZipFile(ROOT / case['input']) as package:
        return package.read(part)


class EmbeddedFontInputs(unittest.TestCase):
    def test_the_part_is_the_original_program_obfuscated_with_its_font_key(self):
        stored = bytearray(read(cases()['embedded-font-regular'], 'word/fonts/font1.odttf'))
        key = bytes.fromhex(fixtures.EMBEDDED_FONT_KEY.strip('{}').replace('-', ''))[::-1]
        for index in range(32):
            stored[index] ^= key[index % 16]
        self.assertEqual(bytes(stored), font(fixtures.EMBEDDED_FONT_FAMILY))
        self.assertIn(f'w:fontKey="{fixtures.EMBEDDED_FONT_KEY}"', read(cases()['embedded-font-regular'], 'word/fontTable.xml').decode())

    def test_the_control_differs_only_in_leaving_the_embedded_face_unused(self):
        regular, control = cases()['embedded-font-regular'], cases()['embedded-font-unused-control']
        family = fixtures.EMBEDDED_FONT_FAMILY
        runs = f'<w:rFonts w:ascii="{family}" w:hAnsi="{family}"/>'
        self.assertEqual(read(regular, 'word/document.xml').decode().replace(runs, ''), read(control, 'word/document.xml').decode())
        self.assertIn(runs, read(regular, 'word/document.xml').decode())
        self.assertEqual(read(regular, 'word/fonts/font1.odttf'), read(control, 'word/fonts/font1.odttf'))
        self.assertEqual(regular['tokens'], control['tokens'])
        self.assertEqual([regular['embeddedFonts'], regular['fonts']], [[family], [fixtures.FONT]])

    def test_embedded_families_are_never_provisioned_and_only_they_may_appear_undeclared(self):
        registry = read_json(ROOT / 'fixtures/manifest.json')
        case = next(c for c in registry['cases'] if c['id'] == 'embedded-font-regular')
        for value in ([], 'Liatris Packaged', [fixtures.FONT], ['Liatris Packaged', 'Liatris Packaged']):
            edited = copy.deepcopy(registry)
            next(c for c in edited['cases'] if c['id'] == case['id'])['embeddedFonts'] = value
            with self.assertRaises(ValueError):
                common.validate_registry(edited)
        observed = {'fonts': ['LiatrisPackaged-Regular']}
        self.assertTrue(pdf.font_check(observed, case['fonts'] + case['embeddedFonts']))
        self.assertFalse(pdf.font_check(observed, case['fonts']))

    def test_the_audit_admits_only_the_exact_authored_part(self):
        source = ROOT / cases()['embedded-font-regular']['input']
        with ZipFile(source) as package:
            audit.check_package(package)
            entries = {name: package.read(name) for name in package.namelist()}
        altered = bytearray(entries['word/fonts/font1.odttf'])
        altered[-1] ^= 1
        buffer = io.BytesIO()
        with ZipFile(buffer, 'w') as package:
            for name, payload in entries.items():
                package.writestr(name, bytes(altered) if name == 'word/fonts/font1.odttf' else payload)
        with ZipFile(buffer) as package, self.assertRaises(ValueError):
            audit.check_package(package)


if __name__ == '__main__':
    unittest.main()
