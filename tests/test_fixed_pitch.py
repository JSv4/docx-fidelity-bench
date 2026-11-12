import copy
import importlib.util
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from bench.common import ROOT, validate_registry

spec = importlib.util.spec_from_file_location('fixed_pitch_measurements',
    ROOT / 'docs/results/fixed-pitch/Measurements.py')
measurements = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measurements)


class FixedPitchContract(unittest.TestCase):
    def test_original_sources_and_independent_geometry_reject_corruption(self):
        cases = [c for c in validate_registry()['cases'] if c['id'].startswith('fixed-pitch-')]
        self.assertEqual(len(cases), 4)
        w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        for case in cases:
            with self.subTest(case=case['id']), ZipFile(ROOT / case['input']) as package:
                source = ET.fromstring(package.read('word/document.xml'))
                self.assertFalse(list(source.iter(w + 'br')))
                labels = source.find('.//' + w + 't').text.split()
                self.assertEqual(labels, [a['marker'] for a in case['assertions']])
                first = ' '.join(labels[:8])
                self.assertEqual(len(first), 60 if 'indented' in case['id'] else 65)
                self.assertEqual(source.find('.//' + w + 'ind').get(w + 'right'),
                    '1' if 'narrow' in case['id'] else '0')
                ideal = dict(geometry=[dict(media=[0, 0, 612, 792], crop=[0, 0, 612, 792], rotation=0)],
                    fonts=['LiberationMono'], tokens=case['tokens'],
                    words=[dict(text=a['marker'], page=a['page'], rect=a['rect'], inkPixels=20) for a in case['assertions']])
                self.assertFalse(measurements.failures(case, ideal))
                for mutation in ['last-word-line', 'missing', 'shrink', 'extra-page', 'wrong-paper', 'unpainted']:
                    damaged = copy.deepcopy(ideal)
                    if mutation == 'last-word-line':
                        damaged['words'][7]['rect'][1] += 13.59375
                        damaged['words'][7]['rect'][3] += 13.59375
                    elif mutation == 'missing':
                        damaged['words'].pop()
                    elif mutation == 'wrong-paper':
                        damaged['geometry'][0]['media'][2] = 700
                    elif mutation == 'unpainted':
                        damaged['words'][0]['inkPixels'] = 0
                    elif mutation == 'extra-page':
                        damaged['geometry'].append(copy.deepcopy(damaged['geometry'][0]))
                    else:
                        rect = damaged['words'][0]['rect']
                        rect[2] = rect[0] + (rect[2] - rect[0]) / 2
                    self.assertTrue(measurements.failures(case, damaged), mutation)
