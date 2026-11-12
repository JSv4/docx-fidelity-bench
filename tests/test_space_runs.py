import importlib.util
import sys
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from bench.common import ROOT, validate_registry


class SpaceRunContract(unittest.TestCase):
    def test_only_the_selected_spaces_size_differs_from_the_control(self):
        cases = [c for c in validate_registry()['cases'] if c['id'].startswith('space-run-')]
        self.assertEqual(len(cases), 8)
        w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        for multiple in (1, 2):
            with ZipFile(ROOT / f'fixtures/space-run-{multiple}-control.docx') as control:
                expected = ET.tostring(ET.fromstring(control.read('word/document.xml')))
                for position in ('leading', 'middle', 'trailing'):
                    with ZipFile(ROOT / f'fixtures/space-run-{multiple}-{position}.docx') as changed:
                        self.assertEqual(set(control.namelist()), set(changed.namelist()))
                        for path in control.namelist():
                            if path != 'word/document.xml':
                                self.assertEqual(control.read(path), changed.read(path))
                        document = ET.fromstring(changed.read('word/document.xml'))
                        spaces = [r for r in document.findall(f'{w}body/{w}p/{w}r')
                                  if r.find(f'{w}t') is not None and r.find(f'{w}t').text == ' ']
                        larger = [r for r in spaces if r.find(f'{w}rPr/{w}sz').get(f'{w}val') == '24']
                        self.assertEqual(len(spaces), 64)
                        self.assertEqual(len(larger), 1)
                        self.assertIs(larger[0], spaces[{'leading': 0, 'middle': 31, 'trailing': 63}[position]])
                        larger[0].find(f'{w}rPr/{w}sz').set(f'{w}val', '20')
                        self.assertEqual(ET.tostring(document), expected)

    def test_retained_metrics_reject_pitch_baseline_width_and_inventory_mutations(self):
        folder = ROOT / 'docs/results/space-runs'
        sys.path.insert(0, str(folder))
        # Other retained families have their own Checks module.
        previous = sys.modules.pop('Checks', None)
        try:
            spec = importlib.util.spec_from_file_location('space_run_mutations', folder / 'Mutations.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            records = module.verify()
            self.assertEqual(len(records), 80)
            self.assertTrue(all(r['rejected'] for r in records))
        finally:
            sys.path.remove(str(folder))
            sys.modules.pop('Checks', None)
            if previous is not None:
                sys.modules['Checks'] = previous
