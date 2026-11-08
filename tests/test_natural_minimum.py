import importlib.util
import sys
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from bench.common import ROOT, validate_registry


class NaturalMinimumContract(unittest.TestCase):
    def test_each_minimum_changes_only_spacing_against_its_natural_control(self):
        cases = [c for c in validate_registry()['cases'] if c['id'].startswith('natural-minimum-')]
        self.assertEqual(len(cases), 8)
        w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        def normalized(data):
            document = ET.fromstring(data)
            spacing = document.find(f'{w}body/{w}p/{w}pPr/{w}spacing')
            del spacing.attrib[f'{w}line']
            del spacing.attrib[f'{w}lineRule']
            return ET.tostring(document)
        for count in (18, 64):
            with ZipFile(ROOT / f'fixtures/natural-minimum-{count}-natural-control.docx') as control:
                expected = normalized(control.read('word/document.xml'))
                for kind in ('ten-control', 'sixteen', 'twenty'):
                    with ZipFile(ROOT / f'fixtures/natural-minimum-{count}-{kind}.docx') as changed:
                        self.assertEqual(set(control.namelist()), set(changed.namelist()))
                        for path in control.namelist():
                            if path == 'word/document.xml':
                                self.assertEqual(normalized(changed.read(path)), expected)
                            else:
                                self.assertEqual(control.read(path), changed.read(path))

    def test_retained_checks_reject_line_ownership_inventory_and_paint_mutations(self):
        folder = ROOT / 'docs/results/natural-minimum'
        sys.path.insert(0, str(folder))
        try:
            spec = importlib.util.spec_from_file_location('natural_minimum_mutations', folder / 'Mutations.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            records = module.verify()
            self.assertEqual(len(records), 76)
            self.assertTrue(all(r['rejected'] for r in records))
            self.assertEqual(sum(r['mutation'] == 'missing-last-page' for r in records), 4)
            self.assertEqual(sum(r['mutation'] == 'extra-blank-page' for r in records), 8)
            self.assertEqual(sum(r['mutation'] == 'within-slot-up' for r in records), 8)
        finally:
            sys.path.remove(str(folder))
