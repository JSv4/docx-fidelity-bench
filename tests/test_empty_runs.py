import importlib.util
import sys
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from bench.common import ROOT, validate_registry


class EmptyRunContract(unittest.TestCase):
    def test_each_reproducer_differs_from_its_control_only_by_one_empty_run(self):
        cases = [c for c in validate_registry()['cases'] if c['id'].startswith('empty-run-')]
        self.assertEqual(len(cases), 8)
        w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        for multiple in (1, 2):
            with ZipFile(ROOT / f'fixtures/empty-run-{multiple}-control.docx') as control:
                expected = ET.tostring(ET.fromstring(control.read('word/document.xml')))
                for position in ('leading', 'middle', 'trailing'):
                    with ZipFile(ROOT / f'fixtures/empty-run-{multiple}-{position}.docx') as changed:
                        self.assertEqual(set(control.namelist()), set(changed.namelist()))
                        for path in control.namelist():
                            if path != 'word/document.xml':
                                self.assertEqual(control.read(path), changed.read(path))
                        document = ET.fromstring(changed.read('word/document.xml'))
                        paragraph = document.find(f'{w}body/{w}p')
                        empty = [r for r in paragraph.findall(f'{w}r')
                                 if r.find(f'{w}t') is not None and not r.find(f'{w}t').text]
                        self.assertEqual(len(empty), 1)
                        self.assertEqual(empty[0].find(f'{w}rPr/{w}sz').get(f'{w}val'), '28')
                        paragraph.remove(empty[0])
                        self.assertEqual(ET.tostring(document), expected)

    def test_retained_checks_reject_every_line_and_inventory_mutation(self):
        folder = ROOT / 'docs/results/empty-runs'
        sys.path.insert(0, str(folder))
        try:
            spec = importlib.util.spec_from_file_location('empty_run_mutations', folder / 'Mutations.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            records = module.verify()
            self.assertEqual(len(records), 52)
            self.assertTrue(all(r['rejected'] for r in records))
            self.assertEqual(sum(r['mutation'] == 'within-slot' for r in records), 4)
        finally:
            sys.path.remove(str(folder))
