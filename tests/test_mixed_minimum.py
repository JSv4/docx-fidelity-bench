import copy
import importlib.util
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from bench.common import ROOT, validate_registry
from bench.pdf import reference_failures

spec = importlib.util.spec_from_file_location('mixed_minimum_measurements',
    ROOT / 'docs/results/mixed-minimum/Measurements.py')
measurements = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measurements)


class MixedMinimumContract(unittest.TestCase):
    def test_source_sizes_and_baseline_regions_reject_centered_leading(self):
        cases = [c for c in validate_registry()['cases'] if c['id'].startswith('mixed-minimum-')]
        self.assertEqual(len(cases), 6)
        w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        for case in cases:
            with self.subTest(case=case['id']), ZipFile(ROOT / case['input']) as package:
                source = ET.fromstring(package.read('word/document.xml'))
                self.assertFalse(list(source.iter(w + 'br')))
                runs = source.findall('.//' + w + 'r')
                labels = [r.find(w + 't').text.strip() for r in runs]
                self.assertEqual(labels, [a['marker'] for a in case['assertions']])
                self.assertTrue(all(a['tolerancePt'] == .76 for a in case['assertions']))
                sizes = [int(r.find(w + 'rPr/' + w + 'sz').get(w + 'val')) / 2 for r in runs]
                self.assertEqual(sizes.count(20), 0 if case['id'].endswith('control') else 1)
                self.assertEqual(source.find('.//' + w + 'ind').get(w + 'right'), '7300')
                ideal = dict(geometry=[dict(media=[0, 0, 612, 792], crop=[0, 0, 612, 792], rotation=0)]
                    * max(a['page'] for a in case['assertions']), fonts=['LiberationSerif'], tokens=case['tokens'],
                    words=[dict(text=a['marker'], page=a['page'], rect=a['rect']) for a in case['assertions']])
                self.assertFalse(reference_failures(case, ideal))
                self.assertFalse(measurements.failures(case, ideal))
                shrunk = copy.deepcopy(ideal)
                for word in shrunk['words']:
                    rect = word['rect']
                    rect[2] = rect[0] + (rect[2] - rect[0]) / 2
                    rect[3] = rect[1] + (rect[3] - rect[1]) / 2
                self.assertFalse(reference_failures(case, shrunk))
                self.assertTrue(measurements.failures(case, shrunk))
                extra_page = copy.deepcopy(ideal)
                extra_page['geometry'].append(copy.deepcopy(ideal['geometry'][0]))
                self.assertIn('total-pages', measurements.failures(case, extra_page))
                if not case['id'].endswith('natural-control'):
                    raised = copy.deepcopy(ideal)
                    for word, size in zip(raised['words'], sizes):
                        if size == 10:
                            word['rect'][1] -= 2
                            word['rect'][3] -= 2
                    self.assertIn('assertion-marker-region', reference_failures(case, raised))
                dropped = copy.deepcopy(ideal)
                dropped['words'].pop()
                self.assertIn('assertion-marker-region', reference_failures(case, dropped))
