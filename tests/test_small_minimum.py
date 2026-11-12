import copy
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from bench.common import ROOT, validate_registry
from bench.pdf import reference_failures


class SmallMinimumContract(unittest.TestCase):
    def test_source_properties_cannot_override_the_metric_premise(self):
        spec = importlib.util.spec_from_file_location('small_minimum_source',
            ROOT / 'docs/results/small-minimum/MinimumChecks.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        case = next(c for c in validate_registry()['cases'] if c['id'] == 'small-minimum-short')
        with ZipFile(ROOT / case['input']) as package:
            parts = {name: package.read(name) for name in package.namelist()}
        w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        for part, parent, child in [('document', 'rPr', 'sz'), ('document', 'pPr', 'jc'), ('styles', 'rPr', 'i')]:
            altered = dict(parts); name = f'word/{part}.xml'; xml = ET.fromstring(parts[name])
            ET.SubElement(xml.find('.//' + w + parent), w + child, {w + 'val': '40' if child == 'sz' else '1'})
            altered[name] = ET.tostring(xml)
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'override.docx'
                with ZipFile(path, 'w') as package:
                    for key, value in altered.items(): package.writestr(key, value)
                with self.assertRaises(AssertionError): module.source_contract(dict(case, input=str(path)))

    def test_source_and_independent_metric_checks(self):
        spec = importlib.util.spec_from_file_location('small_minimum_checks',
            ROOT / 'docs/results/small-minimum/MinimumChecks.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        cases = [c for c in validate_registry()['cases'] if c['id'].startswith('small-minimum-')]
        self.assertEqual(len(cases), 4)
        for case in cases:
            labels, pitch = module.source_contract(case)
            ideal = dict(geometry=[dict(media=[0, 0, 612, 792], crop=[0, 0, 612, 792], rotation=0)]
                * max(a['page'] for a in case['assertions']), fonts=['LiberationSerif'], tokens=case['tokens'],
                rawTokens=labels, words=[dict(text=a['marker'], page=a['page'],
                    rect=[72, a['rect'][1], 72 + 10467 / 2048 * 10, a['rect'][1] + 2268 / 2048 * 10])
                    for a in case['assertions']])
            self.assertFalse(reference_failures(case, ideal))
            self.assertTrue(all(c['passed'] for c in module.checks(case, ideal)))
            if case['id'].endswith('continued'):
                self.assertEqual([sum(w['page'] == page for w in ideal['words']) for page in (1, 2)], [49, 15])
            shrunk = copy.deepcopy(ideal)
            for word in shrunk['words']:
                for axis in (2, 3):
                    word['rect'][axis] = word['rect'][axis - 2] + (word['rect'][axis] - word['rect'][axis - 2]) * .95
            self.assertFalse(reference_failures(case, shrunk))
            self.assertTrue(any(not c['passed'] for c in module.checks(case, shrunk) if c['kind'] == 'glyph-dimensions'))
            drifted = copy.deepcopy(ideal)
            for i, word in enumerate(drifted['words']):
                word['rect'][1] += i * .1; word['rect'][3] += i * .1
            checks = module.checks(case, drifted)
            self.assertTrue(all(c['passed'] for c in checks if c['kind'] == 'adjacent-pitch'))
            self.assertTrue(any(not c['passed'] for c in checks if c['kind'] == 'cumulative-pitch'))

    def test_retained_captures_reject_corruption(self):
        folder = ROOT / 'docs/results/small-minimum'
        sys.path.insert(0, str(folder)); previous = sys.modules.pop('MinimumChecks', None)
        try:
            spec = importlib.util.spec_from_file_location('small_minimum_mutations', folder / 'Mutations.py')
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            records = module.verify()
            self.assertEqual(len(records), 47)
            self.assertTrue(all(r['rejected'] and r['failures'] for r in records))
            self.assertEqual(sum(r['mutation'] == 'gradual-drift' for r in records), 4)
        finally:
            sys.path.remove(str(folder)); sys.modules.pop('MinimumChecks', None)
            if previous is not None: sys.modules['MinimumChecks'] = previous
