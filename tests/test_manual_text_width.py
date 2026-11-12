import importlib.util
import sys
import unittest
from collections import Counter
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from bench.common import ROOT, validate_registry


class ManualTextWidthContract(unittest.TestCase):
    def test_authored_ids_widths_and_complete_source_inventory(self):
        w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        cases = [c for c in validate_registry()['cases'] if c['id'].startswith('manual-text-width-')]
        self.assertEqual(len(cases), 6)
        expected = {'control': [], 'single-20': [('400', '11')], 'single-100': [('2000', '11')],
                    'mixed-100': [('2000', '11'), ('2000', '11')],
                    'separate-100': [('2000', '11'), ('2000', '12')], 'continued-100': [('2000', '11')]}
        for case in cases:
            with ZipFile(ROOT / case['input']) as package:
                source = ET.fromstring(package.read('word/document.xml'))
            variant = case['id'].removeprefix('manual-text-width-')
            self.assertEqual([(e.get(w + 'val'), e.get(w + 'id')) for e in source.iter(w + 'fitText')], expected[variant])
            self.assertEqual(Counter(''.join(e.text or '' for e in source.iter(w + 't')).split()), Counter(case['tokens']))
            self.assertTrue(case['pdfCompanion']['exactInventory'])
            self.assertEqual(case['pdfCompanion']['requiredTokens'], case['tokens'])
            self.assertEqual(len(case['assertions']), sum(case['tokens'].values()))
            self.assertEqual(len(list(source.iter(w + 'b'))), int(variant == 'mixed-100'))

    def test_retained_checks_reject_damage_and_incorrect_group_allocation(self):
        folder = ROOT / 'docs/results/manual-text-width'
        sys.path.insert(0, str(folder)); previous = sys.modules.pop('WidthChecks', None)
        try:
            spec = importlib.util.spec_from_file_location('manual_width_mutations', folder / 'Mutations.py')
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            records = module.verify()
            self.assertEqual(len(records), 73)
            self.assertTrue(all(r['rejected'] and r['failures'] for r in records))
            self.assertEqual(sum(r['mutation'] == 'merged-ids' for r in records), 1)
            self.assertEqual(sum(r['mutation'] == 'lost-bold' for r in records), 1)
        finally:
            sys.path.remove(str(folder)); sys.modules.pop('WidthChecks', None)
            if previous is not None: sys.modules['WidthChecks'] = previous
