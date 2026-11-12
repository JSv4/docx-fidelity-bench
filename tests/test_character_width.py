import importlib.util
import sys
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from bench.common import ROOT, validate_registry


class CharacterWidthContract(unittest.TestCase):
    def test_percentage_is_the_only_input_difference(self):
        cases = [c for c in validate_registry()['cases'] if c['id'].startswith('character-width-')]
        self.assertEqual(len(cases), 6)
        w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        def normalized(data):
            document = ET.fromstring(data)
            width = document.find(f'{w}body/{w}p/{w}r/{w}rPr/{w}w')
            del width.attrib[f'{w}val']
            return ET.tostring(document)
        for count in (12, 120):
            with ZipFile(ROOT / f'fixtures/character-width-{count}-100.docx') as control:
                expected = normalized(control.read('word/document.xml'))
                for percent in (80, 150):
                    with ZipFile(ROOT / f'fixtures/character-width-{count}-{percent}.docx') as changed:
                        self.assertEqual(set(control.namelist()), set(changed.namelist()))
                        for path in control.namelist():
                            if path == 'word/document.xml':
                                self.assertEqual(normalized(changed.read(path)), expected)
                            else:
                                self.assertEqual(control.read(path), changed.read(path))

    def test_fixed_cell_inputs_wrap_the_unchanged_body_paragraphs(self):
        w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        for count in (12, 120):
            for percent in (80, 100, 150):
                with ZipFile(ROOT / f'fixtures/character-width-{count}-{percent}.docx') as body, ZipFile(ROOT / f'fixtures/cell-character-width-{count}-{percent}.docx') as cell:
                    self.assertEqual(set(body.namelist()), set(cell.namelist()))
                    for path in body.namelist():
                        if path != 'word/document.xml':
                            self.assertEqual(body.read(path), cell.read(path))
                    original = ET.fromstring(body.read('word/document.xml'))
                    wrapped = ET.fromstring(cell.read('word/document.xml'))
                    table = wrapped.find(f'{w}body/{w}tbl')
                    self.assertEqual(table.find(f'{w}tblPr/{w}tblW').attrib, {w + 'w':'9360', w + 'type':'dxa'})
                    self.assertEqual(table.find(f'{w}tblPr/{w}tblLayout').get(w + 'type'), 'fixed')
                    self.assertEqual(table.find(f'{w}tblGrid/{w}gridCol').get(w + 'w'), '9360')
                    self.assertEqual(ET.tostring(original.find(f'{w}body/{w}p')), ET.tostring(table.find(f'{w}tr/{w}tc/{w}p')))

    def test_cell_observations_reject_width_inventory_and_page_mutations(self):
        folder = ROOT / 'docs/results/cell-character-width'
        sys.path.insert(0, str(folder))
        previous = sys.modules.pop('WidthChecks', None)
        try:
            spec = importlib.util.spec_from_file_location('cell_character_width_mutations', folder / 'Mutations.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            records = module.verify()
            self.assertEqual(len(records), 72)
            self.assertTrue(all(r['rejected'] for r in records))
        finally:
            sys.path.remove(str(folder))
            sys.modules.pop('WidthChecks', None)
            if previous is not None:
                sys.modules['WidthChecks'] = previous

    def test_retained_checks_reject_width_height_inventory_and_page_mutations(self):
        folder = ROOT / 'docs/results/character-width'
        sys.path.insert(0, str(folder))
        try:
            spec = importlib.util.spec_from_file_location('character_width_mutations', folder / 'Mutations.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            records = module.verify()
            self.assertEqual(len(records), 72)
            self.assertTrue(all(r['rejected'] for r in records))
            for kind in ('narrow-glyph', 'wide-glyph', 'tall-glyph', 'short-glyph', 'extra-blank-page', 'reordered'):
                self.assertEqual(sum(r['mutation'] == kind for r in records), 6)
        finally:
            sys.path.remove(str(folder))
